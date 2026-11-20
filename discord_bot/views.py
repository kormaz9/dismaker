"""
DisMaker - Discord UI Bileşenleri ve İnteraktif Görünümler (Views & Embeds)
Kalıcı Rol Menüleri (Açılır Menü / Buton), Bilet Sistemi ve Doğrulama Kapısı
"""

import re
import asyncio
import discord
from discord.ui import View, Button, Select
from typing import Optional, List, Tuple

from core.schema import ServerArchitecture
from discord_bot.builder import ServerBuilder
from config import COLOR_SUCCESS, COLOR_NEUTRAL, COLOR_DANGER, COLOR_INFO
from core.database import db


def create_progress_bar(percentage: int, total_blocks: int = 12) -> str:
    """Matematiksel olarak düzgün bir metin ilerleme çubuğu üretir"""
    pct = max(0, min(100, percentage))
    filled_len = int(round(total_blocks * pct / 100))
    bar = "█" * filled_len + "░" * (total_blocks - filled_len)
    return f"`[{bar}]` **{pct}%**"


def create_architecture_embed(arch: ServerArchitecture, model_used: str) -> discord.Embed:
    """
    Swiss Grid / Linear standartlarında minimalist ve sofistike önizleme embed'i.
    """
    embed = discord.Embed(
        title=f"◈ {arch.server_name}",
        description=f"**Tema:** {arch.server_theme}\n*Yapay Zeka Mimarı ({model_used}) tarafından hazırlandı.*",
        color=COLOR_NEUTRAL
    )

    # Roller Özeti
    roles_preview = []
    for r in arch.roles[:6]:
        roles_preview.append(f"`{r.color}` **{r.name}**")
    if len(arch.roles) > 6:
        roles_preview.append(f"*...ve {len(arch.roles) - 6} rol daha*")
    embed.add_field(
        name=f"Hiyerarşik Roller ({len(arch.roles)})",
        value="\n".join(roles_preview) if roles_preview else "Tanımlı rol yok",
        inline=False
    )

    # Kategoriler ve Kanallar Özeti
    cats_preview = []
    for cat in arch.categories[:5]:
        ch_count = len(cat.channels)
        sample_channels = ", ".join(f"`{ch.name}`" for ch in cat.channels[:3])
        if ch_count > 3:
            sample_channels += f" +{ch_count - 3}"
        cats_preview.append(f"**{cat.name}** ({ch_count} kanal)\n↳ {sample_channels}")
    if len(arch.categories) > 5:
        cats_preview.append(f"*...ve {len(arch.categories) - 5} kategori daha*")

    embed.add_field(
        name=f"Kategoriler & Kanallar ({len(arch.categories)} Kategori / {arch.total_channels_count()} Kanal)",
        value="\n\n".join(cats_preview) if cats_preview else "Kategori tanımlı değil",
        inline=False
    )

    # Güvenlik ve Moderasyon Politikası
    mod = arch.moderation_policy
    if mod.enabled:
        mod_info = (
            f"✓ **Durum:** Aktif (7/24)\n"
            f"✓ **Küfür Filtresi:** {'Açık' if mod.filter_profanity else 'Kapalı'}\n"
            f"✓ **Davet Engeli:** {'Açık' if mod.filter_invites else 'Kapalı'}\n"
            f"⏱ **Timeout:** {mod.mute_duration_seconds} saniye\n"
            f"📋 **Log Kanalı:** `{mod.log_channel_name}`"
        )
    else:
        mod_info = "Standart (Dinamik ceza politikası kapalı)"

    embed.add_field(
        name="🛡 Moderasyon ve Güvenlik Motoru",
        value=mod_info,
        inline=True
    )

    # Autorole Bilgisi
    embed.add_field(
        name="👤 Giriş Rolü (Autorole)",
        value=f"**{arch.autorole}**\n*(Yeni üyelere otomatik atanır)*",
        inline=True
    )

    embed.set_footer(text="Aşağıdaki butonları kullanarak sunucu inşasını onaylayabilir veya iptal edebilirsiniz.")
    return embed


class ServerBuildConfirmView(View):
    """Kullanıcının mimariyi onaylayıp sunucuya uygulamasını sağlayan buton menüsü"""

    def __init__(
        self,
        author: discord.User | discord.Member,
        architecture: ServerArchitecture,
        model_used: str,
        clean_existing: bool = False,
        timeout: float = 180.0
    ):
        super().__init__(timeout=timeout)
        self.author = author
        self.arch = architecture
        self.model_used = model_used
        self.clean_existing = clean_existing
        self.message: Optional[discord.Message] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Sadece komutu çalıştıran kişinin veya sunucu sahibinin tıklamasına izin verir"""
        if interaction.user.id != self.author.id and interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message(
                "Bu onay penceresi sadece komutu başlatan yetkili içindir.",
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="◈ Sunucuyu İnşa Et", style=discord.ButtonStyle.success)
    async def confirm_build(self, interaction: discord.Interaction, button: Button):
        # Butonları devre dışı bırak
        for child in self.children:
            child.disabled = True

        progress_embed = discord.Embed(
            title="◈ Sunucu İnşası Başlatıldı",
            description=f"{create_progress_bar(5)}\n\n*Hazırlık yapılıyor, mimari uygulanmaya başlandı...*",
            color=COLOR_INFO
        )
        await interaction.response.edit_message(embed=progress_embed, view=self)

        # İnşayı Başlat (Mevcut kanalı süreç bitene kadar koru)
        builder = ServerBuilder(interaction.guild, self.arch, preserve_channel_id=interaction.channel_id)

        async def safe_edit(embed: discord.Embed, view: Optional[discord.ui.View] = None):
            """Etkileşim mesajını güvenli bir şekilde günceller; mesaj silinmişse yeni kanala gönderir"""
            try:
                await interaction.edit_original_response(embed=embed, view=view)
            except discord.NotFound:
                target = builder.rules_channel or builder.log_channel or next(
                    (ch for ch in interaction.guild.text_channels if ch.permissions_for(interaction.guild.me).send_messages),
                    None
                )
                if target:
                    try:
                        await target.send(embed=embed, view=view)
                    except Exception:
                        pass
            except Exception:
                pass

        async def live_progress(stage: str, percentage: int):
            try:
                progress_embed.description = f"{create_progress_bar(percentage)}\n\n**Aşama:** {stage}"
                await safe_edit(progress_embed)
            except Exception:
                pass

        try:
            stats = await builder.execute_build(
                clean_existing=self.clean_existing,
                progress_callback=live_progress
            )

            # Bot Rol Hiyerarşisi Kontrolü
            bot_top = interaction.guild.me.top_role
            hierarchy_warning = ""
            lower_than = [r for r in builder.created_roles.values() if r >= bot_top and r != bot_top]
            if lower_than:
                hierarchy_warning = (
                    "\n\n⚠️ **ÖNEMLİ YETKİ UYARISI:**\n"
                    f"Botun rolü (`{bot_top.name}`), oluşturulan bazı rollerin altında kalıyor. "
                    "Butonların ve rollerin sorunsuz çalışması için Discord sunucu ayarlarından botun rolünü **en üste taşıyınız!**"
                )

            # Başarı Embed'i
            success_embed = discord.Embed(
                title="✓ Sunucu Mimarisi Başarıyla Tamamlandı",
                description=(
                    f"**{self.arch.server_name}** sunucusu başarıyla yapılandırıldı!\n\n"
                    f"• **Ağaç Dalı Hiyerarşisi:** Uygulandı (`├・` ve `╰・`)\n"
                    f"• **Oluşturulan Roller:** {stats['roles_created']}\n"
                    f"• **Kategoriler:** {stats['categories_created']}\n"
                    f"• **Metin Kanalları:** {stats['text_channels_created']}\n"
                    f"• **Ses Kanalları:** {stats['voice_channels_created']}\n"
                    f"• **Doğrulama Kapısı:** {'Aktif (Kuralları Onayla Butonlu)' if stats['rules_posted'] else 'Atlandı'}\n"
                    f"• **Rol Seçim Paneli:** {'Aktif (Açılır Menü / Butonlu)' if stats.get('role_menu_posted') else 'Atlandı'}\n"
                    f"• **Destek Sistemi:** {'Aktif (Bilet Açma Butonlu)' if stats.get('ticket_system_posted') else 'Atlandı'}\n"
                    f"• **Dinamik Ses:** {'Aktif (Join-to-Create)' if stats.get('dynamic_voice_created') else 'Atlandı'}\n"
                    f"• **7/24 Moderasyon:** {'Devrede' if stats['moderation_active'] else 'Kapalı'}\n"
                    f"• **Giriş Rolü (Autorole):** {'Aktif' if stats['autorole_set'] else 'Bulunamadı'}"
                    f"{hierarchy_warning}"
                ),
                color=COLOR_SUCCESS
            )
            success_embed.set_footer(text=f"Mimari Üretici: {self.model_used} | DisMaker Master Engine (2026)")
            await safe_edit(success_embed, view=None)

        except Exception as ex:
            error_embed = discord.Embed(
                title="⚠ İnşa Sırasında Bir Hata Oluştu",
                description=f"Hata detayı: ```\n{str(ex)[:1000]}\n```",
                color=COLOR_DANGER
            )
            await safe_edit(error_embed, view=None)

    @discord.ui.button(label="✕ İptal Et", style=discord.ButtonStyle.secondary)
    async def cancel_build(self, interaction: discord.Interaction, button: Button):
        for child in self.children:
            child.disabled = True

        cancel_embed = discord.Embed(
            title="✕ İşlem İptal Edildi",
            description="Sunucu inşası kullanıcı tarafından iptal edildi. Hiçbir kanala veya role dokunulmadı.",
            color=COLOR_NEUTRAL
        )
        await interaction.response.edit_message(embed=cancel_embed, view=self)

    async def on_timeout(self):
        """Zaman aşımına uğradığında butonları kapat"""
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass


# ==============================================================================
# ETKİLEŞİMLİ 7/24 KALICI BUTONLAR VE MENÜLER (PERSISTENT VIEWS)
# ==============================================================================

class RoleToggleButton(Button):
    """Tek bir role tıklayınca veren/alan buton"""

    def __init__(self, role_id: int, role_name: str, label: str, style: discord.ButtonStyle = discord.ButtonStyle.secondary):
        super().__init__(
            label=label,
            style=style,
            custom_id=f"dis_role_{role_id}"
        )
        self.role_id = role_id
        self.role_name = role_name

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        member = interaction.user
        if not guild or not isinstance(member, discord.Member):
            return

        role = guild.get_role(self.role_id)
        if not role:
            role = discord.utils.get(guild.roles, name=self.role_name)

        if not role:
            await interaction.response.send_message("⚠ Bu rol artık sunucuda bulunamadı.", ephemeral=True)
            return

        if role >= guild.me.top_role:
            await interaction.response.send_message("⚠ Botun yetki sırası bu rolü yönetmek için yetersiz.", ephemeral=True)
            return

        if role in member.roles:
            try:
                await member.remove_roles(role, reason="DisMaker Rol Menüsü: Rol bırakıldı.")
                await interaction.response.send_message(f"✕ **{role.name}** rolü sizden alındı.", ephemeral=True)
            except discord.Forbidden:
                await interaction.response.send_message("⚠ Bu rolü sizden almak için yetkim yetersiz.", ephemeral=True)
        else:
            try:
                await member.add_roles(role, reason="DisMaker Rol Menüsü: Rol alındı.")
                await interaction.response.send_message(f"✓ **{role.name}** rolü başarıyla verildi!", ephemeral=True)
            except discord.Forbidden:
                await interaction.response.send_message("⚠ Bu rolü size vermek için yetkim yetersiz.", ephemeral=True)


class PersistentRoleSelectView(View):
    """Rol alma kanalı için 7/24 kesintisiz çalışan kalıcı buton ve açılır menü menüsü"""

    def __init__(
        self,
        role_buttons: Optional[List[Tuple[int, str, str]]] = None,
        dropdown_options: Optional[List[discord.SelectOption]] = None
    ):
        super().__init__(timeout=None)
        # 1. Satır: Açılır Menü (Varsa)
        if dropdown_options:
            self.add_item(RoleDropdownSelect(options=dropdown_options[:25]))
        # 2-5. Satırlar: Hızlı Tıklama Butonları
        if role_buttons:
            for role_id, role_name, label in role_buttons[:20]:
                self.add_item(RoleToggleButton(role_id=role_id, role_name=role_name, label=label))


class RoleDropdownSelect(Select):
    """Açılır menüden çoklu rol seçimi"""

    def __init__(self, options: Optional[List[discord.SelectOption]] = None, placeholder: str = "🎭 Rollerinizi açılır menüden seçin..."):
        opts = options if options else [discord.SelectOption(label="Rollerinizi seçiniz...", value="0")]
        super().__init__(
            placeholder=placeholder,
            min_values=0,
            max_values=min(len(opts), 25),
            options=opts[:25],
            custom_id="dis_role_dropdown_menu"
        )

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        member = interaction.user
        if not guild or not isinstance(member, discord.Member):
            return

        selected_role_ids = {v for v in self.values if v != "0"}

        # Canlı Discord mesajındaki tüm rol ID seçeneklerini tara
        all_option_role_ids = set()
        if interaction.message and interaction.message.components:
            for row in interaction.message.components:
                for comp in row.children:
                    if getattr(comp, "custom_id", None) == "dis_role_dropdown_menu" and hasattr(comp, "options"):
                        for opt in comp.options:
                            if opt.value != "0":
                                all_option_role_ids.add(opt.value)

        if not all_option_role_ids:
            all_option_role_ids = {opt.value for opt in self.options if opt.value != "0"}

        added = []
        removed = []

        for r_id_str in all_option_role_ids:
            try:
                role = guild.get_role(int(r_id_str))
                if not role or role >= guild.me.top_role:
                    continue

                if r_id_str in selected_role_ids:
                    if role not in member.roles:
                        await member.add_roles(role, reason="DisMaker Rol Menüsü: Açılır menü seçimi.")
                        added.append(role.name)
                else:
                    if role in member.roles:
                        await member.remove_roles(role, reason="DisMaker Rol Menüsü: Seçim kaldırıldı.")
                        removed.append(role.name)
            except Exception:
                pass

        msg_parts = []
        if added:
            msg_parts.append(f"✓ **Eklenen roller:** {', '.join(added)}")
        if removed:
            msg_parts.append(f"✕ **Kaldırılan roller:** {', '.join(removed)}")
        if not msg_parts:
            msg_parts.append("Rollerinizde bir değişiklik yapılmadı.")

        await interaction.response.send_message("\n".join(msg_parts), ephemeral=True)


class PersistentRoleDropdownView(View):
    """Rol alma kanalı için yalnızca açılır menülü kalıcı görünüm"""

    def __init__(self, options: Optional[List[discord.SelectOption]] = None, placeholder: str = "🎭 Rollerinizi açılır menüden seçin..."):
        super().__init__(timeout=None)
        opts = options if options else [discord.SelectOption(label="Rollerinizi seçiniz...", value="0")]
        self.add_item(RoleDropdownSelect(options=opts[:25], placeholder=placeholder))


class PersistentRulesVerifyView(View):
    """Doğrulama Kapısı: Kuralları onaylayan üyelere rol verir ve tüm sunucuyu açar"""

    def __init__(self, autorole_id: Optional[int] = None, autorole_name: Optional[str] = None):
        super().__init__(timeout=None)
        self.autorole_id = autorole_id
        self.autorole_name = autorole_name or "Üye"

    @discord.ui.button(
        label="✅ Kuralları Okudum ve Onaylıyorum",
        style=discord.ButtonStyle.success,
        custom_id="dis_rules_verify_btn"
    )
    async def verify_callback(self, interaction: discord.Interaction, button: Button):
        guild = interaction.guild
        member = interaction.user
        if not guild or not isinstance(member, discord.Member):
            return

        role: Optional[discord.Role] = None

        if self.autorole_id:
            role = guild.get_role(self.autorole_id)
        if not role and self.autorole_name:
            role = discord.utils.get(guild.roles, name=self.autorole_name)

        if not role:
            settings = db.get_guild_settings(guild.id)
            if settings:
                r_id = settings.get("autorole_id")
                r_name = settings.get("autorole_name")
                if r_id:
                    role = guild.get_role(r_id)
                if not role and r_name:
                    role = discord.utils.get(guild.roles, name=r_name)

        if not role:
            await interaction.response.send_message("✓ Kuralları onayladınız! Topluluğumuza hoş geldiniz.", ephemeral=True)
            return

        if role >= guild.me.top_role:
            await interaction.response.send_message("⚠ Botun yetki sırası bu rolü vermeye yetmiyor. Lütfen yetkililere bildirin.", ephemeral=True)
            return

        if role in member.roles:
            await interaction.response.send_message(f"ℹ Zaten onaylı üyesiniz (**{role.name}** rolünüz mevcut).", ephemeral=True)
        else:
            try:
                await member.add_roles(role, reason="DisMaker Doğrulama Kapısı: Kurallar onaylandı.")
                await interaction.response.send_message(
                    f"✓ **Kurallar başarıyla onaylandı!**\n"
                    f"**{role.name}** rolünüz tanımlandı ve tüm sunucu kanallarınızın kilidi açıldı. Hoş geldiniz!",
                    ephemeral=True
                )
            except discord.Forbidden:
                await interaction.response.send_message("⚠ Botun rol verme yetkisi yetersiz.", ephemeral=True)


class PersistentTicketCloseView(View):
    """Açılan destek talebini kapatma butonu"""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Talebi Kapat ve Sil", style=discord.ButtonStyle.danger, custom_id="dis_ticket_close_btn")
    async def close_ticket(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("Talebiniz kapatılıyor, kanal 3 saniye içinde silinecektir...", ephemeral=True)
        await asyncio.sleep(3)
        try:
            await interaction.channel.delete(reason=f"DisMaker Destek: {interaction.user.name} talebi kapattı.")
        except Exception:
            pass


class PersistentTicketCreateView(View):
    """Canlı destek talebi açma butonu"""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📩 Destek Talebi Aç", style=discord.ButtonStyle.primary, custom_id="dis_ticket_create_btn")
    async def create_ticket(self, interaction: discord.Interaction, button: Button):
        guild = interaction.guild
        member = interaction.user
        if not guild or not isinstance(member, discord.Member):
            return

        clean_username = re.sub(r'[^a-zA-Z0-9]', '', member.name.lower())[:12] or str(member.id)[:8]
        ticket_channel_name = f"bilet-{clean_username}"

        existing = discord.utils.find(lambda c: c.name == ticket_channel_name, guild.text_channels)
        if existing:
            await interaction.response.send_message(f"⚠ Zaten açık bir destek talebiniz bulunuyor: {existing.mention}", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        category = interaction.channel.category if isinstance(interaction.channel, discord.TextChannel) else None

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
        }

        for role in guild.roles:
            if role.permissions.administrator or role.permissions.manage_guild or role.permissions.manage_channels:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        try:
            ticket_channel = await guild.create_text_channel(
                name=ticket_channel_name,
                category=category,
                overwrites=overwrites,
                topic=f"{member.mention} kullanıcısının destek talebi.",
                reason="DisMaker Destek Talebi Oluşturma"
            )

            welcome_embed = discord.Embed(
                title=f"📩 Destek Talebi: {member.display_name}",
                description=(
                    f"Merhaba {member.mention}, yetkili ekibimiz en kısa sürede sizinle ilgilenecektir.\n\n"
                    "Lütfen sorununuzu, talebinizi veya ekran görüntüsünü bu kanaldan iletiniz.\n"
                    "Görüşmeniz tamamlandığında aşağıdaki butona basarak bileti kapatabilirsiniz."
                ),
                color=COLOR_INFO,
                timestamp=discord.utils.utcnow()
            )
            welcome_embed.set_footer(text="DisMaker Canlı Destek Sistemi")

            await ticket_channel.send(content=f"{member.mention} | @here", embed=welcome_embed, view=PersistentTicketCloseView())
            await interaction.followup.send(f"✓ Destek talebiniz oluşturuldu: {ticket_channel.mention}", ephemeral=True)

        except Exception as e:
            await interaction.followup.send(f"⚠ Destek talebi oluşturulamadı: {e}", ephemeral=True)
