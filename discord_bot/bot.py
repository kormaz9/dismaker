"""
DisMaker - Discord Bot Sınıfı ve Komut Yöneticisi
Slash ve Metin Komutları, Olay Dinleyicileri ve Etkileşimler
"""

import sys
import logging
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

from config import (
    BOT_PREFIX,
    GEMINI_MODELS,
    COLOR_SUCCESS,
    COLOR_INFO,
    COLOR_WARNING,
    COLOR_DANGER,
    COLOR_NEUTRAL
)
from core.gemini_client import GeminiArchitectClient, GeminiAPIError
from core.database import db
from discord_bot.views import create_architecture_embed, ServerBuildConfirmView
from discord_bot.moderation import handle_message_moderation
from discord_bot.autorole import handle_member_join

logger = logging.getLogger("DisMaker.Bot")


class DisMakerBot(commands.Bot):
    """DisMaker Bot Ana Sınıfı"""

    def __init__(self):
        intents = discord.Intents.default()
        intents.guilds = True
        intents.members = True
        intents.message_content = True
        intents.voice_states = True

        super().__init__(
            command_prefix=BOT_PREFIX,
            intents=intents,
            help_command=None
        )

        self.gemini_client = GeminiArchitectClient()
        self.temp_voice_channels: set[int] = set()

    async def setup_hook(self):
        """Slash komutlarını ve kalıcı UI bileşenlerini hazırlar"""
        # 7/24 Kalıcı Butonları ve Menüleri (Rol Alma, Kurallar Onaylama, Bilet Açma/Kapatma) Kaydet
        from discord_bot.views import (
            PersistentRulesVerifyView,
            PersistentRoleSelectView,
            PersistentRoleDropdownView,
            PersistentTicketCreateView,
            PersistentTicketCloseView
        )
        self.add_view(PersistentRulesVerifyView())
        self.add_view(PersistentRoleSelectView())
        self.add_view(PersistentRoleDropdownView())
        self.add_view(PersistentTicketCreateView())
        self.add_view(PersistentTicketCloseView())

        # Komut ağacını senkronize et
        try:
            synced = await self.tree.sync()
            logger.info(f"✓ {len(synced)} adet global Slash komutu senkronize edildi.")
        except Exception as e:
            logger.warning(f"Slash komutları senkronize edilirken uyarı: {e}")

    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """
        Dinamik Ses Odası (Join-to-Create):
        1. Üye '➕・Oda Oluştur' kanalına katıldığında ona özel geçici oda açar ve taşır.
        2. Geçici oda boşaldığında odayı otomatik olarak siler.
        """
        if member.bot:
            return

        # 1. Join-to-Create: Yeni oda oluşturma
        if after.channel is not None and after.channel != before.channel:
            ch_name = after.channel.name.lower()
            if "➕" in after.channel.name or "oda oluştur" in ch_name or "oda-olustur" in ch_name or "create room" in ch_name:
                guild = member.guild
                category = after.channel.category

                temp_room_name = f"🔊・{member.display_name} Odası"

                overwrites = dict(category.overwrites) if category else {}
                overwrites[member] = discord.PermissionOverwrite(
                    connect=True,
                    speak=True,
                    manage_channels=True,
                    move_members=True
                )

                try:
                    temp_channel = await guild.create_voice_channel(
                        name=temp_room_name,
                        category=category,
                        overwrites=overwrites,
                        reason=f"DisMaker Dinamik Ses Odası: {member.display_name}"
                    )
                    self.temp_voice_channels.add(temp_channel.id)
                    await member.move_to(temp_channel)
                    logger.info(f"✓ [Dinamik Ses] '{member.display_name}' için geçici ses odası oluşturuldu.")
                except Exception as ex:
                    logger.warning(f"Dinamik ses odası oluşturulamadı: {ex}")

        # 2. Auto-Delete: Boşalan geçici odaları temizleme
        if before.channel is not None and before.channel != after.channel:
            b_channel = before.channel
            is_temp = (
                b_channel.id in self.temp_voice_channels
                or (b_channel.name.startswith("🔊・") and "Odası" in b_channel.name)
            )

            if is_temp and len(b_channel.members) == 0:
                try:
                    await b_channel.delete(reason="DisMaker: Boşalan geçici ses odası silindi.")
                    self.temp_voice_channels.discard(b_channel.id)
                    logger.info(f"✓ [Dinamik Ses] Boşalan ses odası silindi: {b_channel.name}")
                except Exception as ex:
                    logger.warning(f"Geçici ses odası silinemedi: {ex}")

    async def on_interaction(self, interaction: discord.Interaction):
        """Kalıcı buton ve dinamik etkileşimleri yakalar (Fallback)"""
        if interaction.type == discord.InteractionType.component:
            custom_id = interaction.data.get("custom_id", "")
            # Dinamik rol alma butonu (dis_role_{role_id})
            if custom_id.startswith("dis_role_") and custom_id != "dis_role_dropdown_menu":
                try:
                    role_id = int(custom_id.replace("dis_role_", ""))
                    guild = interaction.guild
                    member = interaction.user
                    if guild and isinstance(member, discord.Member):
                        role = guild.get_role(role_id)
                        if role:
                            if role >= guild.me.top_role:
                                if not interaction.response.is_done():
                                    await interaction.response.send_message("⚠ Botun yetki sırası bu rolü yönetmeye yetmiyor.", ephemeral=True)
                                return

                            if role in member.roles:
                                await member.remove_roles(role, reason="DisMaker Rol Menüsü: Rol bırakıldı.")
                                if not interaction.response.is_done():
                                    await interaction.response.send_message(f"✕ **{role.name}** rolü sizden alındı.", ephemeral=True)
                            else:
                                await member.add_roles(role, reason="DisMaker Rol Menüsü: Rol alındı.")
                                if not interaction.response.is_done():
                                    await interaction.response.send_message(f"✓ **{role.name}** rolü üzerinize eklendi!", ephemeral=True)
                            return
                except Exception as ex:
                    logger.debug(f"Role button fallback hatası: {ex}")

    async def on_ready(self):
        """Bot hazır olduğunda tetiklenir"""
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name=f"Sunucu Mimarisi & 7/24 Güvenlik | {BOT_PREFIX}dismaker help"
        )
        await self.change_presence(status=discord.Status.online, activity=activity)

        print("\n" + "=" * 65)
        print("  DISMAKER - EVRENSEL DİSCORD MİMARI & GÜVENLİK BOTU")
        print("=" * 65)
        print(f"  • Bot Kullanıcısı : {self.user} (ID: {self.user.id})")
        print(f"  • Bağlı Sunucular : {len(self.guilds)} adet")
        print(f"  • Model Zinciri   : {' -> '.join(GEMINI_MODELS[:4])}")
        print(f"  • Komut Ön Eki    : {BOT_PREFIX} (veya /dismaker)")
        print(f"  • Sistem Durumu   : Çevrimiçi ve Göreve Hazır")
        print("=" * 65 + "\n")

    async def on_message(self, message: discord.Message):
        """Gelen mesajları dinler: Önce moderasyon filtresi, sonra komutlar"""
        if message.author.bot:
            return

        # 1. 7/24 Moderasyon Denetimi
        violation = await handle_message_moderation(message)
        if violation:
            return

        # 2. Standart Komut İşleme
        await self.process_commands(message)

    async def on_member_join(self, member: discord.Member):
        """Yeni üye katıldığında Autorole motorunu tetikler"""
        await handle_member_join(member)


bot = DisMakerBot()


# ==============================================================================
# SLASH KOMUTLARI (/dismaker)
# ==============================================================================

dismaker_group = app_commands.Group(
    name="dismaker",
    description="DisMaker Evrensel Sunucu Mimarı ve Yönetim Komutları"
)


@dismaker_group.command(name="build", description="Doğal dille belirttiğiniz temada eksiksiz Discord sunucusu inşa eder.")
@app_commands.describe(
    prompt="Sunucunun temasını, rollerini, özel kanallarını veya moderasyon kurallarını yazın.",
    clean_existing="Eski kanalları ve kategorileri temizleyip sıfırdan mı kursun? (Varsayılan: Hayır)"
)
async def slash_build(
    interaction: discord.Interaction,
    prompt: str,
    clean_existing: bool = False
):
    # Yetki Kontrolü: Yalnızca Yönetici veya Sunucu Sahibi
    if not interaction.user.guild_permissions.administrator and interaction.user.id != interaction.guild.owner_id:
        await interaction.response.send_message(
            "⚠ Bu komutu kullanabilmek için `Yönetici` (Administrator) yetkisine sahip olmalısınız.",
            ephemeral=True
        )
        return

    # Yanıtı ertele (Gemini analizi birkaç saniye sürebilir)
    await interaction.response.defer(ephemeral=False)

    loading_embed = discord.Embed(
        title="◈ Evrensel Sistem Mimarı Analiz Ediyor...",
        description=(
            f"**İstek:** *\"{prompt}\"*\n\n"
            "Gemini yapay zeka modelleri (3.5 / 2.5) sunucu mimarisini, UTF-8 hiyerarşisini, "
            "izin matrisini ve moderasyon politikasını tasarlıyor. Lütfen bekleyin..."
        ),
        color=COLOR_INFO
    )
    await interaction.followup.send(embed=loading_embed)

    try:
        # Gemini çağrısı (fallback zinciri ile)
        arch, model_used = await bot.gemini_client.generate_architecture(prompt)

        # Önizleme Embed'i ve Onay Butonları
        preview_embed = create_architecture_embed(arch, model_used)
        view = ServerBuildConfirmView(
            author=interaction.user,
            architecture=arch,
            model_used=model_used,
            clean_existing=clean_existing
        )

        sent_msg = await interaction.edit_original_response(embed=preview_embed, view=view)
        view.message = sent_msg

    except GeminiAPIError as api_err:
        err_embed = discord.Embed(
            title="⚠ Yapay Zeka Hatası",
            description=f"Mimari üretilirken hata oluştu:\n```\n{str(api_err)}\n```",
            color=COLOR_DANGER
        )
        await interaction.edit_original_response(embed=err_embed, view=None)

    except Exception as ex:
        err_embed = discord.Embed(
            title="⚠ Beklenmeyen Bir Hata Oluştu",
            description=f"Detay: ```\n{str(ex)}\n```",
            color=COLOR_DANGER
        )
        await interaction.edit_original_response(embed=err_embed, view=None)


@dismaker_group.command(name="preview", description="Sunucuya dokunmadan yalnızca mimari tasarımını önizler.")
@app_commands.describe(prompt="Sunucu teması veya açıklaması")
async def slash_preview(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer(ephemeral=True)

    try:
        arch, model_used = await bot.gemini_client.generate_architecture(prompt)
        embed = create_architecture_embed(arch, model_used)
        embed.set_footer(text="Bu yalnızca bir önizlemedir. Sunucuya uygulamak için /dismaker build komutunu kullanın.")
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as ex:
        await interaction.followup.send(f"⚠ Önizleme oluşturulamadı: {ex}", ephemeral=True)


@dismaker_group.command(name="autorole", description="Sunucuya katılan yeni üyelere atanacak rolü belirler.")
@app_commands.describe(role="Otomatik atanacak rol")
async def slash_autorole(interaction: discord.Interaction, role: discord.Role):
    if not interaction.user.guild_permissions.manage_roles:
        await interaction.response.send_message("⚠ Bu işlem için `Rolleri Yönet` yetkisi gereklidir.", ephemeral=True)
        return

    db.save_guild_settings(guild_id=interaction.guild.id, autorole_name=role.name, autorole_id=role.id)
    await interaction.response.send_message(
        f"✓ Yeni katılan üyelere verilecek otomatik rol **{role.name}** olarak ayarlandı.",
        ephemeral=True
    )


@dismaker_group.command(name="moderation", description="Sunucunun 7/24 moderasyon ve güvenlik motoru ayarlarını yönetir.")
@app_commands.describe(
    enabled="Moderasyon motoru açık mı olsun?",
    filter_profanity="Küfür/hakaret filtresi",
    filter_invites="Discord davet linki filtresi",
    mute_seconds="İhlal durumunda verilecek timeout süresi (saniye)"
)
async def slash_moderation(
    interaction: discord.Interaction,
    enabled: Optional[bool] = None,
    filter_profanity: Optional[bool] = None,
    filter_invites: Optional[bool] = None,
    mute_seconds: Optional[int] = None
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("⚠ Bu ayar için `Yönetici` yetkisi gereklidir.", ephemeral=True)
        return

    current = db.get_guild_settings(interaction.guild.id) or {}

    if enabled is not None or filter_profanity is not None or filter_invites is not None or mute_seconds is not None:
        db.save_guild_settings(
            guild_id=interaction.guild.id,
            moderation_enabled=enabled,
            filter_profanity=filter_profanity,
            filter_invites=filter_invites,
            mute_duration_seconds=mute_seconds
        )
        current = db.get_guild_settings(interaction.guild.id) or {}
        msg_prefix = "✓ Moderasyon ayarları güncellendi:\n"
    else:
        msg_prefix = "📋 Mevcut Moderasyon Durumu:\n"

    status_embed = discord.Embed(
        title="🛡 DisMaker Dinamik Moderasyon Yapılandırması",
        description=(
            f"{msg_prefix}"
            f"• **Motor Durumu:** {'🟢 Aktif' if current.get('moderation_enabled') else '🔴 Devre Dışı'}\n"
            f"• **Küfür/Hakaret Filtresi:** {'Açık' if current.get('filter_profanity') else 'Kapalı'}\n"
            f"• **Davet Linki Engeli:** {'Açık' if current.get('filter_invites') else 'Kapalı'}\n"
            f"• **Mute / Timeout Süresi:** {current.get('mute_duration_seconds', 600)} saniye\n"
            f"• **Log Kanalı:** `{current.get('log_channel_name', '› mod-log')}`\n"
        ),
        color=COLOR_INFO
    )
    await interaction.response.send_message(embed=status_embed, ephemeral=True)


@dismaker_group.command(name="help", description="DisMaker kullanım kılavuzu, izin gereksinimleri ve örnek promptlar.")
async def slash_help(interaction: discord.Interaction):
    help_embed = discord.Embed(
        title="◈ DisMaker - Evrensel Discord Mimarı Rehberi",
        description=(
            "DisMaker, gelişmiş Gemini yapay zeka modelleriyle doğal dil komutlarından "
            "en yüksek tipografik ve güvenlik standartlarında Discord sunucuları inşa eden profesyonel bir sistemdir.\n\n"
            "**Temel İlkelerimiz:**\n"
            "• **Anti-Slop:** Rastgele renkli emojiler yok, sadece zarif minimalist UTF-8 glifleri.\n"
            "• **Semantik İzinler:** Bilgi kanalları salt-okunur, medya kanalları yavaş modlu, roller hoist'li.\n"
            "• **7/24 Güvenlik:** İsteğe bağlı dinamik küfür ve davet linki filtresi, anlık timeout ve audit log.\n"
            "• **Dinamik Model:** Öncelikli Gemini 3.5, kesintisiz 2.5 fallback desteği."
        ),
        color=COLOR_NEUTRAL
    )

    help_embed.add_field(
        name="⚡ Komutlar",
        value=(
            "`/dismaker build <prompt> [clean_existing]`\n"
            "↳ Verilen temaya göre sunucuyu tasarlar ve onayınızla inşa eder.\n\n"
            "`/dismaker preview <prompt>`\n"
            "↳ Sunucuyu değiştirmeden yalnızca mimari planını görüntüler.\n\n"
            "`/dismaker moderation`\n"
            "↳ 7/24 moderasyon motorunu ve timeout sürelerini yapılandırır.\n\n"
            "`/dismaker autorole <rol>`\n"
            "↳ Yeni gelen üyelere verilecek rolü ayarlar."
        ),
        inline=False
    )

    help_embed.add_field(
        name="💡 Örnek Prompt İstekleri",
        value=(
            "• *\"Yapay zeka ve Python geliştiricileri için profesyonel bir topluluk sunucusu. Proje paylaşım kanalları, makale tartışma odaları olsun. Reklam ve küfür kesinlikle yasak olsun, 15 dk mute atılsın.\"*\n"
            "• *\"FPS ve RPG oyuncuları için bir klan sunucusu. Takım ses odaları, maç duyuruları ve turnuva alanı olsun.\"*\n"
            "• *\"3D modelleme ve dijital sanatçılar için portfolyo ve geri bildirim sunucusu.\"*"
        ),
        inline=False
    )

    help_embed.set_footer(text=f"Metin komutları için: {BOT_PREFIX}dismaker build <prompt>")
    await interaction.response.send_message(embed=help_embed, ephemeral=True)


# Komut grubunu ağaca kaydet
bot.tree.add_command(dismaker_group)


# ==============================================================================
# KLASİK METİN KOMUTLARI (!dismaker ...)
# ==============================================================================

@bot.group(name="dismaker", invoke_without_command=True)
async def cmd_dismaker(ctx: commands.Context):
    """DisMaker ana komut yardımcısı"""
    await ctx.send(f"Kullanım: `{BOT_PREFIX}dismaker build <istek>` veya `{BOT_PREFIX}dismaker help`")


@cmd_dismaker.command(name="build")
@commands.has_permissions(administrator=True)
async def cmd_build(ctx: commands.Context, *, prompt: str):
    """Metin tabanlı sunucu inşa komutu"""
    msg = await ctx.send("◈ Evrensel Sistem Mimarı analiz ediyor, lütfen bekleyin...")
    try:
        arch, model_used = await bot.gemini_client.generate_architecture(prompt)
        preview_embed = create_architecture_embed(arch, model_used)
        view = ServerBuildConfirmView(
            author=ctx.author,
            architecture=arch,
            model_used=model_used,
            clean_existing=False
        )
        sent = await ctx.send(embed=preview_embed, view=view)
        view.message = sent
        await msg.delete()
    except Exception as ex:
        await msg.edit(content=f"⚠ Hata: {ex}")


@cmd_dismaker.command(name="help")
async def cmd_help(ctx: commands.Context):
    """Metin tabanlı yardım mesajı"""
    await ctx.send(
        f"**DisMaker Evrensel Discord Mimarı**\n"
        f"Kullanım: `{BOT_PREFIX}dismaker build <sunucu açıklaması>`\n"
        f"Örnek: `{BOT_PREFIX}dismaker build Yazılımcılar için topluluk sunucusu, küfür yasak olsun.`\n"
        f"Ayrıca modern `/dismaker build` slash komutunu da kullanabilirsiniz!"
    )
