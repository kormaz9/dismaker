"""
DisMaker - Sunucu İnşa Motoru (Discord Server Builder)
JSON mimari modelini canlı Discord sunucusuna dönüştürür.
Ağaç Dalı Hiyerarşisi (Tree-Branch), Doğrulama Kapısı (Verification Gate),
Canlı Destek Sistemi (Ticket), Dinamik Ses (Join-to-Create) ve Rol Menüleri
"""

import re
import asyncio
import logging
from typing import Optional, Callable, Awaitable, Dict, List, Tuple
import discord

from core.schema import ServerArchitecture, ChannelPermissions, ChannelDefinition
from core.database import db

logger = logging.getLogger("DisMaker.Builder")

# Discord İzin Eşleme Tablosu
PERMISSION_MAP = {
    "ADMINISTRATOR": "administrator",
    "MANAGE_GUILD": "manage_guild",
    "MANAGE_ROLES": "manage_roles",
    "MANAGE_CHANNELS": "manage_channels",
    "KICK_MEMBERS": "kick_members",
    "BAN_MEMBERS": "ban_members",
    "MODERATE_MEMBERS": "moderate_members",
    "MANAGE_MESSAGES": "manage_messages",
    "VIEW_CHANNEL": "view_channel",
    "SEND_MESSAGES": "send_messages",
    "SEND_MESSAGES_IN_THREADS": "send_messages_in_threads",
    "CREATE_PUBLIC_THREADS": "create_public_threads",
    "CREATE_PRIVATE_THREADS": "create_private_threads",
    "EMBED_LINKS": "embed_links",
    "ATTACH_FILES": "attach_files",
    "READ_MESSAGE_HISTORY": "read_message_history",
    "MENTION_EVERYONE": "mention_everyone",
    "USE_EXTERNAL_EMOJIS": "use_external_emojis",
    "ADD_REACTIONS": "add_reactions",
    "CONNECT": "connect",
    "SPEAK": "speak",
    "MUTE_MEMBERS": "mute_members",
    "DEAFEN_MEMBERS": "deafen_members",
    "MOVE_MEMBERS": "move_members",
    "VIEW_AUDIT_LOG": "view_audit_log",
}


def build_discord_permissions(perm_list: list[str]) -> discord.Permissions:
    """Metin tabanlı izin listesini discord.Permissions nesnesine çevirir"""
    perms = discord.Permissions.none()
    for raw_p in perm_list:
        clean = raw_p.upper().strip().replace(" ", "_")
        attr = PERMISSION_MAP.get(clean)
        if attr and hasattr(perms, attr):
            setattr(perms, attr, True)
    return perms


def hex_to_discord_color(hex_str: str) -> discord.Color:
    """HEX renk kodunu discord.Color nesnesine çevirir"""
    try:
        clean = hex_str.strip().lstrip("#")
        return discord.Color(int(clean, 16))
    except Exception:
        return discord.Color.default()


def is_staff_entity(name: str) -> bool:
    """Kanalın veya kategorinin yetkililere özel olup olmadığını denetler"""
    clean = name.lower()
    keywords = [
        "yetkili", "yonetim", "yönetim", "staff", "admin", "mod-log",
        "denetim", "toplantı", "toplanti", "logs", "güvenlik", "guvenlik", "kurucu"
    ]
    return any(k in clean for k in keywords)


def is_info_entity(name: str) -> bool:
    """Kanalın veya kategorinin bilgilendirme/salt-okunur olup olmadığını denetler"""
    clean = name.lower()
    keywords = [
        "bilgi", "duyuru", "kural", "info", "rehber", "rol-secim",
        "announcement", "rules", "faq", "destek", "tanıtım", "tanitim", "guncelleme"
    ]
    return any(k in clean for k in keywords)


def is_media_entity(name: str) -> bool:
    """Kanalın fotoğraf/medya kanalı olup olmadığını denetler"""
    clean = name.lower()
    keywords = [
        "foto", "medya", "gorsel", "görsel", "resim", "galeri",
        "cizim", "çizim", "media", "screenshot", "klip", "video", "sanat"
    ]
    return any(k in clean for k in keywords)


def is_voice_afk(name: str) -> bool:
    """Kanalın AFK kanalı olup olmadığını denetler"""
    return "afk" in name.lower()


def format_tree_channel_name(raw_name: str, is_last: bool, is_voice: bool) -> str:
    """
    Kanalları ultra-şık Ağaç Dalı (Tree-Branch: ├・ ve ╰・) formatına dönüştürür.
    Kategori içindeki hiyerarşiyi görsel bir sanat haline getirir.
    """
    branch = "╰・" if is_last else "├・"
    clean = raw_name.strip()

    # Önceden eklenmiş olabilecek sembol ve dal karakterlerini ayıkla
    for p in ["├・", "╰・", "├", "╰", "› ", "›", "• ", "•", "── ", "──", "│ ", "│"]:
        if clean.startswith(p):
            clean = clean[len(p):].strip()

    if is_voice:
        lower = clean.lower()
        if "afk" in lower:
            clean_text = clean.replace("🔊・", "").replace("🔊", "").replace("💤・", "").replace("💤", "").strip()
            return f"{branch}💤・{clean_text or 'AFK'}"
        elif any(k in lower for k in ["oda oluştur", "oda-olustur", "oda olustur", "create room", "➕"]):
            return f"{branch}➕・Oda Oluştur"
        else:
            clean_text = clean.replace("🔊・", "").replace("🔊", "").strip()
            return f"{branch}🔊・{clean_text}"
    else:
        # Metin kanalı
        # Eğer başında özel tematik ikon varsa (örneğin 📸・ veya 🌸・) koru
        if "・" in clean and len(clean.split("・")[0]) <= 4:
            icon_part, text_part = clean.split("・", 1)
            text_slug = text_part.strip().replace(" ", "-").lower()
            text_slug = re.sub(r"-+", "-", text_slug)
            return f"{branch}{icon_part}・{text_slug}"
        else:
            clean_slug = clean.replace(" ", "-").lower()
            clean_slug = re.sub(r"-+", "-", clean_slug)
            return f"{branch}{clean_slug}"


class ServerBuilder:
    """JSON mimarisini canlı Discord sunucusuna inşa eden ana motor"""

    def __init__(
        self,
        guild: discord.Guild,
        architecture: ServerArchitecture,
        preserve_channel_id: Optional[int] = None
    ):
        self.guild = guild
        self.arch = architecture
        self.preserve_channel_id = preserve_channel_id
        self.created_roles: Dict[str, discord.Role] = {}
        self.staff_roles: List[discord.Role] = []
        self.created_channels: Dict[str, discord.abc.GuildChannel] = {}
        self.rules_channel: Optional[discord.TextChannel] = None
        self.log_channel: Optional[discord.TextChannel] = None

    async def execute_build(
        self,
        clean_existing: bool = False,
        progress_callback: Optional[Callable[[str, int], Awaitable[None]]] = None
    ) -> dict:
        """
        Sunucuyu adım adım inşa eder.
        Dönüş: İnşa istatistikleri ve sonuç özeti
        """
        stats = {
            "roles_created": 0,
            "categories_created": 0,
            "text_channels_created": 0,
            "voice_channels_created": 0,
            "rules_posted": False,
            "role_menu_posted": False,
            "ticket_system_posted": False,
            "dynamic_voice_created": False,
            "moderation_active": False,
            "autorole_set": False
        }

        async def update_progress(msg: str, pct: int):
            if progress_callback:
                try:
                    await progress_callback(msg, pct)
                except Exception as ex:
                    logger.debug(f"Progress callback hatası: {ex}")

        # 1. Mevcut kanalları temizleme (Opsiyonel)
        if clean_existing:
            await update_progress("Mevcut kanallar ve kategoriler temizleniyor...", 10)
            for channel in list(self.guild.channels):
                # Komutun çalıştırıldığı etkileşim kanalını süreç bitene kadar koru
                if self.preserve_channel_id and channel.id == self.preserve_channel_id:
                    continue
                try:
                    await channel.delete(reason="DisMaker: Yeniden inşa için temizlik.")
                    await asyncio.sleep(0.2)
                except Exception as e:
                    logger.warning(f"Kanal silinemedi ({channel.name}): {e}")

        # 2. Sunucu adını güncelleme
        await update_progress("Sunucu kimliği ve ismi yapılandırılıyor...", 20)
        try:
            if self.guild.me.guild_permissions.manage_guild:
                await self.guild.edit(name=self.arch.server_name, reason="DisMaker Sunucu Mimarisi")
        except Exception as e:
            logger.warning(f"Sunucu adı güncellenemedi: {e}")

        # 3. Rollerin Oluşturulması ve Hiyerarşi
        await update_progress("Roller ve yetki matrisi oluşturuluyor...", 35)
        for role_def in reversed(self.arch.roles):
            try:
                role_perms = build_discord_permissions(role_def.permissions)
                color = hex_to_discord_color(role_def.color)

                existing = discord.utils.get(self.guild.roles, name=role_def.name)
                if existing and existing < self.guild.me.top_role:
                    await existing.edit(
                        colour=color,
                        hoist=role_def.hoist,
                        mentionable=role_def.mentionable,
                        permissions=role_perms,
                        reason="DisMaker Rol Güncellemesi"
                    )
                    self.created_roles[role_def.name] = existing
                else:
                    new_role = await self.guild.create_role(
                        name=role_def.name,
                        colour=color,
                        hoist=role_def.hoist,
                        mentionable=role_def.mentionable,
                        permissions=role_perms,
                        reason="DisMaker Rol Mimarisi"
                    )
                    self.created_roles[role_def.name] = new_role

                stats["roles_created"] += 1
                await asyncio.sleep(0.3)
            except Exception as e:
                logger.error(f"Rol oluşturulamadı ({role_def.name}): {e}")

        # Yetkili Rollerini Belirle (İzin matrisi için)
        self.staff_roles = [
            r for r in self.created_roles.values()
            if r.permissions.administrator
            or r.permissions.manage_guild
            or r.permissions.manage_channels
            or r.permissions.moderate_members
            or is_staff_entity(r.name)
        ]

        # Başlangıç Doğrulama Rolünü (Autorole) Garantiye Al
        autorole_obj = self.created_roles.get(self.arch.autorole) or discord.utils.get(self.guild.roles, name=self.arch.autorole)
        if not autorole_obj:
            try:
                fallback_name = self.arch.autorole or "✦ ┃ Üye"
                autorole_obj = await self.guild.create_role(
                    name=fallback_name,
                    colour=hex_to_discord_color("#3B82F6"),
                    hoist=True,
                    mentionable=False,
                    reason="DisMaker: Başlangıç Doğrulama Rolü (Autorole)"
                )
                self.created_roles[fallback_name] = autorole_obj
                stats["roles_created"] += 1
            except Exception as e:
                logger.warning(f"Autorole oluşturulamadı: {e}")

        # 4. Kategoriler ve Kanalların Oluşturulması (Ağaç Dalı + Doğrulama Kapısı)
        total_cats = len(self.arch.categories)
        for cat_idx, cat_def in enumerate(self.arch.categories, start=1):
            pct = 40 + int((cat_idx / max(total_cats, 1)) * 35)
            await update_progress(f"Kategori inşa ediliyor: {cat_def.name}", pct)

            try:
                # Kategori Düzeyinde İzinler (Category Overwrites)
                cat_overwrites = {}
                if is_staff_entity(cat_def.name):
                    # 1. Kural: Yetkili kategorisini @everyone için tamamen gizle
                    cat_overwrites[self.guild.default_role] = discord.PermissionOverwrite(
                        view_channel=False,
                        send_messages=False,
                        connect=False
                    )
                    for sr in self.staff_roles:
                        cat_overwrites[sr] = discord.PermissionOverwrite(
                            view_channel=True,
                            send_messages=True,
                            connect=True,
                            read_message_history=True,
                            manage_messages=True
                        )
                elif is_info_entity(cat_def.name):
                    # 2. Kural: Bilgilendirme kategorisi (Doğrulama Kapısı Giriş Noktası)
                    # @everyone görebilir ama mesaj yazamaz
                    cat_overwrites[self.guild.default_role] = discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=False,
                        add_reactions=True,
                        attach_files=False
                    )
                    for sr in self.staff_roles:
                        cat_overwrites[sr] = discord.PermissionOverwrite(
                            view_channel=True,
                            send_messages=True,
                            manage_messages=True
                        )
                else:
                    # 3. Kural: DOĞRULAMA KAPISI (VERIFICATION GATE) KİLİDİ:
                    # Topluluk, Uzmanlık, Medya ve Ses kategorileri @everyone'a KAPALIDIR.
                    # Yalnızca kuralları onaylayıp autorole alan üyeler görebilir!
                    cat_overwrites[self.guild.default_role] = discord.PermissionOverwrite(
                        view_channel=False,
                        send_messages=False,
                        connect=False
                    )
                    if autorole_obj:
                        cat_overwrites[autorole_obj] = discord.PermissionOverwrite(
                            view_channel=True,
                            send_messages=True,
                            connect=True
                        )
                    for sr in self.staff_roles:
                        cat_overwrites[sr] = discord.PermissionOverwrite(
                            view_channel=True,
                            send_messages=True,
                            connect=True,
                            manage_messages=True
                        )

                category = await self.guild.create_category(
                    name=cat_def.name,
                    overwrites=cat_overwrites,
                    reason="DisMaker Kategori Mimarisi"
                )
                stats["categories_created"] += 1
                await asyncio.sleep(0.3)

                # Kanalları Hazırla
                channels_to_create = list(cat_def.channels)

                # 4.A: Bilgilendirme kategorisinde Destek Kanalı Güvencesi:
                if is_info_entity(cat_def.name):
                    has_support = any("destek" in ch.name.lower() or "bilet" in ch.name.lower() or "ticket" in ch.name.lower() for ch in channels_to_create)
                    if not has_support:
                        channels_to_create.append(ChannelDefinition(
                            name="sunucu-destek",
                            type="text",
                            topic="Yetkili ekibimizden 7/24 canlı destek ve bilet almak için tıklayın.",
                            slowmode=0,
                            permissions={"everyone": ChannelPermissions(view=True, send=False, add_reactions=True)}
                        ))

                # 4.B: Fotoğraf Kanalı Güvencesi: Genel Sohbetin hemen altına fotoğraf kanalı ekle
                is_community_cat = any(k in cat_def.name.lower() for k in ["sohbet", "topluluk", "chat", "community", "genel"])
                has_media_channel = any(is_media_entity(ch.name) for ch in channels_to_create)

                if is_community_cat and not has_media_channel:
                    photo_channel_def = ChannelDefinition(
                        name="📸・foto-paylasim",
                        type="text",
                        topic="Üyelerimizin fotoğraf, görsel ve anı paylaşım alanı.",
                        slowmode=5,
                        permissions={
                            "everyone": ChannelPermissions(
                                view=True,
                                send=True,
                                attach_files=True,
                                add_reactions=True
                            )
                        }
                    )
                    insert_idx = 1
                    for idx, ch in enumerate(channels_to_create):
                        if "genel" in ch.name.lower() or "sohbet" in ch.name.lower():
                            insert_idx = idx + 1
                            break
                    channels_to_create.insert(insert_idx, photo_channel_def)

                # 4.C: Ses Kategorisinde Dinamik Ses (➕・Oda Oluştur) Güvencesi:
                is_voice_cat = any(k in cat_def.name.lower() for k in ["ses", "voice", "oda", "konusma", "odalar"])
                if is_voice_cat:
                    has_create_room = any(any(k in ch.name.lower() for k in ["oda oluştur", "oda-olustur", "➕"]) for ch in channels_to_create)
                    if not has_create_room:
                        channels_to_create.append(ChannelDefinition(
                            name="➕・Oda Oluştur",
                            type="voice",
                            topic="Kendi özel geçici ses odanızı oluşturmak için tıklayın.",
                            user_limit=0,
                            permissions={"everyone": ChannelPermissions(connect=True, speak=True)}
                        ))

                # Kanalları Oluştur (Ağaç Dalı Formatlaması ile)
                num_channels = len(channels_to_create)
                for ch_idx, ch_def in enumerate(channels_to_create):
                    is_last = (ch_idx == num_channels - 1)
                    is_voice = (ch_def.type == "voice")
                    formatted_name = format_tree_channel_name(ch_def.name, is_last=is_last, is_voice=is_voice)

                    overwrites = dict(cat_overwrites)

                    # Yetkili kanalı izinleri
                    if is_staff_entity(ch_def.name) or is_staff_entity(cat_def.name):
                        overwrites[self.guild.default_role] = discord.PermissionOverwrite(
                            view_channel=False,
                            send_messages=False,
                            connect=False
                        )
                        for sr in self.staff_roles:
                            overwrites[sr] = discord.PermissionOverwrite(
                                view_channel=True,
                                send_messages=True,
                                connect=True,
                                read_message_history=True,
                                manage_messages=True
                            )

                    # Bilgilendirme / Kurallar / Duyuru kanalları
                    elif is_info_entity(ch_def.name) or is_info_entity(cat_def.name):
                        # Eğer rol seçim kanalıysa, henüz kuralları onaylamamış olanlardan gizle
                        if any(k in ch_def.name.lower() for k in ["rol-secim", "roller", "rol-alma", "rol-seçim"]):
                            overwrites[self.guild.default_role] = discord.PermissionOverwrite(view_channel=False)
                            if autorole_obj:
                                overwrites[autorole_obj] = discord.PermissionOverwrite(
                                    view_channel=True,
                                    send_messages=False,
                                    add_reactions=True
                                )
                        else:
                            overwrites[self.guild.default_role] = discord.PermissionOverwrite(
                                view_channel=True,
                                send_messages=False,
                                add_reactions=True,
                                attach_files=False
                            )
                        for sr in self.staff_roles:
                            overwrites[sr] = discord.PermissionOverwrite(
                                view_channel=True,
                                send_messages=True,
                                manage_messages=True
                            )

                    # Medya / Fotoğraf kanalı
                    elif is_media_entity(ch_def.name):
                        if autorole_obj:
                            overwrites[autorole_obj] = discord.PermissionOverwrite(
                                view_channel=True,
                                send_messages=True,
                                attach_files=True,
                                embed_links=True,
                                add_reactions=True
                            )

                    # Normal Metin Kanalı (Genel sohbet vb. - dosya yükleme kapalı)
                    elif ch_def.type == "text":
                        if autorole_obj:
                            overwrites[autorole_obj] = discord.PermissionOverwrite(
                                view_channel=True,
                                send_messages=True,
                                attach_files=False,
                                add_reactions=True
                            )

                    # AFK Ses Kanalı
                    if ch_def.type == "voice" and is_voice_afk(ch_def.name):
                        target_perm = overwrites.get(autorole_obj) or overwrites.get(self.guild.default_role)
                        if target_perm:
                            target_perm.speak = False
                            target_perm.send_messages = False

                    # Özel tanımlı rol izinleri varsa uygula
                    for role_key, perm_obj in ch_def.permissions.items():
                        if role_key == "everyone":
                            continue
                        target_role = self.created_roles.get(role_key) or discord.utils.get(self.guild.roles, name=role_key)
                        if target_role:
                            overwrites[target_role] = discord.PermissionOverwrite(
                                view_channel=perm_obj.view if perm_obj.view is not None else True,
                                send_messages=perm_obj.send if perm_obj.send is not None else True,
                                attach_files=perm_obj.attach_files if perm_obj.attach_files is not None else True,
                                add_reactions=perm_obj.add_reactions if perm_obj.add_reactions is not None else True,
                                connect=perm_obj.connect if perm_obj.connect is not None else True,
                                speak=perm_obj.speak if perm_obj.speak is not None else True,
                            )

                    # Yavaş mod (Medya kanallarında en az 5s)
                    slowmode_val = ch_def.slowmode
                    if is_media_entity(ch_def.name):
                        slowmode_val = max(slowmode_val, 5)

                    # Kanalı Oluştur
                    if ch_def.type == "voice":
                        v_channel = await self.guild.create_voice_channel(
                            name=formatted_name,
                            category=category,
                            user_limit=ch_def.user_limit,
                            overwrites=overwrites,
                            reason="DisMaker Ses Kanalı Mimarisi"
                        )
                        self.created_channels[ch_def.name] = v_channel
                        stats["voice_channels_created"] += 1

                        if "➕" in formatted_name or "oda oluştur" in formatted_name.lower():
                            stats["dynamic_voice_created"] = True
                    else:
                        t_channel = await self.guild.create_text_channel(
                            name=formatted_name,
                            category=category,
                            topic=ch_def.topic or None,
                            slowmode_delay=slowmode_val,
                            overwrites=overwrites,
                            reason="DisMaker Metin Kanalı Mimarisi"
                        )
                        self.created_channels[ch_def.name] = t_channel
                        stats["text_channels_created"] += 1

                        # Kurallar veya Log kanalı tespiti
                        if any(k in ch_def.name.lower() for k in ["kural", "rule", "info", "bilgi"]):
                            if not self.rules_channel:
                                self.rules_channel = t_channel

                        if ch_def.name == self.arch.moderation_policy.log_channel_name or "mod-log" in ch_def.name:
                            self.log_channel = t_channel

                    await asyncio.sleep(0.25)

            except Exception as e:
                logger.error(f"Kategori veya kanal oluşturulamadı ({cat_def.name}): {e}")

        # 5. Kurallar Embed Paneli Gönderimi (Doğrulama Kapısı Butonlu)
        await update_progress("Kurallar ve doğrulama kapısı sabitleniyor...", 80)
        autorole_id = autorole_obj.id if autorole_obj else None

        if self.arch.rules_embed:
            target_rules_channel = self.rules_channel
            if not target_rules_channel and stats["text_channels_created"] > 0:
                target_rules_channel = next(
                    (ch for ch in self.created_channels.values() if isinstance(ch, discord.TextChannel)),
                    None
                )

            if target_rules_channel:
                try:
                    from discord_bot.views import PersistentRulesVerifyView

                    embed = discord.Embed(
                        title=self.arch.rules_embed.title,
                        description=self.arch.rules_embed.description,
                        color=hex_to_discord_color(self.arch.rules_embed.color)
                    )
                    for f in self.arch.rules_embed.fields:
                        embed.add_field(name=f.name, value=f.value, inline=False)
                    if self.arch.rules_embed.footer:
                        embed.set_footer(text=self.arch.rules_embed.footer)

                    rules_view = PersistentRulesVerifyView(autorole_id=autorole_id, autorole_name=self.arch.autorole)

                    rules_msg = await target_rules_channel.send(
                        content="@everyone 📢 **Sunucu kurallarımız yayımlandı! Lütfen aşağıdaki maddeleri dikkatle okuyunuz ve sunucunun kilidini açmak için aşağıdaki butona tıklayınız.**",
                        embed=embed,
                        view=rules_view
                    )
                    await rules_msg.pin(reason="DisMaker Sunucu Kuralları Sabitleme")
                    stats["rules_posted"] = True
                except Exception as e:
                    logger.warning(f"Kurallar embedi gönderilemedi: {e}")

        # 6. Rol Seçim Paneli (Açılır Menü + Tıklanabilir Butonlar)
        role_channel = next(
            (ch for ch in self.created_channels.values() if isinstance(ch, discord.TextChannel) and any(k in ch.name.lower() for k in ["rol-secim", "roller", "rol-alma", "rol-seçim", "roles"])),
            None
        )
        if role_channel:
            await update_progress("Rol seçim paneli, açılır menü ve butonlar hazırlanıyor...", 87)
            try:
                from discord_bot.views import PersistentRoleSelectView
                role_buttons: List[Tuple[int, str, str]] = []

                if self.arch.role_menu and self.arch.role_menu.items:
                    for item in self.arch.role_menu.items:
                        target_r = self.created_roles.get(item.role_name) or discord.utils.get(self.guild.roles, name=item.role_name)
                        if target_r:
                            role_buttons.append((target_r.id, target_r.name, item.button_label or target_r.name))
                else:
                    for r_name, r_obj in self.created_roles.items():
                        if r_obj in self.staff_roles or r_name == self.arch.autorole or r_obj == self.guild.default_role:
                            continue
                        label = r_name
                        if "┃" in label:
                            label = label.split("┃")[-1].strip()
                        role_buttons.append((r_obj.id, r_obj.name, label))

                if role_buttons:
                    menu_title = self.arch.role_menu.title if self.arch.role_menu else "🎭 İLGİ ALANLARI VE ROL SEÇİM PANELİ"
                    menu_desc = self.arch.role_menu.description if self.arch.role_menu else "Aşağıdaki açılır menüden veya butonlara tıklayarak dilediğiniz rolleri alabilir veya üzerinizden çıkartabilirsiniz."
                    menu_color = hex_to_discord_color(self.arch.role_menu.color if self.arch.role_menu else "#3B82F6")

                    role_embed = discord.Embed(
                        title=menu_title,
                        description=menu_desc,
                        color=menu_color
                    )

                    roles_list_text = []
                    dropdown_options: List[discord.SelectOption] = []

                    for r_id, r_name, btn_lbl in role_buttons[:25]:
                        roles_list_text.append(f"• **{r_name}** ➔ `{btn_lbl}` butonu")
                        dropdown_options.append(
                            discord.SelectOption(
                                label=btn_lbl[:100],
                                value=str(r_id),
                                description=f"{r_name} rolünü seç/kaldır"[:100]
                            )
                        )

                    role_embed.add_field(
                        name="Seçilebilir Roller",
                        value="\n".join(roles_list_text) if roles_list_text else "Roller hazırlandı.",
                        inline=False
                    )
                    role_embed.set_footer(text="Rolleri almak veya bırakmak için açılır menüyü veya butonları kullanabilirsiniz.")

                    role_view = PersistentRoleSelectView(
                        role_buttons=role_buttons,
                        dropdown_options=dropdown_options
                    )
                    role_msg = await role_channel.send(embed=role_embed, view=role_view)
                    await role_msg.pin(reason="DisMaker Rol Seçim Paneli")
                    stats["role_menu_posted"] = True
            except Exception as e:
                logger.warning(f"Rol seçim paneli oluşturulamadı: {e}")

        # 7. Canlı Destek & Bilet Sistemi Paneli (PersistentTicketCreateView)
        support_channel = next(
            (ch for ch in self.created_channels.values() if isinstance(ch, discord.TextChannel) and any(k in ch.name.lower() for k in ["destek", "ticket", "bilet", "yardim"])),
            None
        )
        if support_channel:
            await update_progress("Canlı destek ve bilet paneli hazırlanıyor...", 92)
            try:
                from discord_bot.views import PersistentTicketCreateView

                ticket_embed = discord.Embed(
                    title="📩 CANLI DESTEK & BİLET MERKEZİ",
                    description=(
                        "Sunucumuzla, topluluğumuzla veya teknik konularla ilgili bir sorun, öneri veya yetkili talebiniz mi var?\n\n"
                        "Aşağıdaki **'📩 Destek Talebi Aç'** butonuna tıklayarak yalnızca sizin ve yetkili ekibimizin görebileceği "
                        "özel, güvenli ve şifreli bir destek odası başlatabilirsiniz."
                    ),
                    color=hex_to_discord_color("#3B82F6")
                )
                ticket_embed.add_field(
                    name="⚡ Hızlı İletişim",
                    value="Bilet açıldığında sorununuzu ve varsa ekran görüntünüzü doğrudan iletebilirsiniz.",
                    inline=False
                )
                ticket_embed.add_field(
                    name="🔒 Gizlilik Güvencesi",
                    value="Destek görüşmeleriniz diğer üyelere tamamen gizlidir. İşiniz bittiğinde bileti saniyeler içinde kapatabilirsiniz.",
                    inline=False
                )
                ticket_embed.set_footer(text="DisMaker 7/24 Canlı Destek & Ticket Motoru (2026)")

                ticket_view = PersistentTicketCreateView()
                ticket_msg = await support_channel.send(embed=ticket_embed, view=ticket_view)
                await ticket_msg.pin(reason="DisMaker Canlı Destek Paneli Sabitleme")
                stats["ticket_system_posted"] = True
            except Exception as e:
                logger.warning(f"Destek paneli gönderilemedi: {e}")

        # 8. Autorole & Moderasyon Ayarlarını Veritabanına Kaydetme
        await update_progress("7/24 Moderasyon ve Autorole motoru etkinleştiriliyor...", 96)
        if autorole_obj:
            stats["autorole_set"] = True

        log_ch_id = self.log_channel.id if self.log_channel else None
        rules_ch_id = self.rules_channel.id if self.rules_channel else None

        db.save_guild_settings(
            guild_id=self.guild.id,
            autorole_name=self.arch.autorole,
            autorole_id=autorole_id,
            moderation_enabled=self.arch.moderation_policy.enabled,
            filter_profanity=self.arch.moderation_policy.filter_profanity,
            filter_invites=self.arch.moderation_policy.filter_invites,
            mute_duration_seconds=self.arch.moderation_policy.mute_duration_seconds,
            log_channel_id=log_ch_id,
            log_channel_name=self.arch.moderation_policy.log_channel_name,
            rules_channel_id=rules_ch_id
        )

        if self.arch.moderation_policy.enabled:
            stats["moderation_active"] = True

        await update_progress("Sunucu inşası başarıyla tamamlandı!", 100)
        return stats
