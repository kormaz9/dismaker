"""
DisMaker - 7/24 Dinamik Moderasyon Motoru
Küfür, hakaret, reklam ve davet linki filtresi, otomatik timeout ve loglama
"""

import re
import base64
import datetime
import logging
from typing import Optional
import discord

from core.database import db
from config import COLOR_DANGER

logger = logging.getLogger("DisMaker.Moderation")

# Discord Davet Linki Regex Deseni
DISCORD_INVITE_PATTERN = re.compile(
    r"(?:https?:\/\/)?(?:www\.)?(?:discord\.(?:gg|io|me|li)|discord(?:app)?\.com\/invite)\/([a-zA-Z0-9\-]+)",
    re.IGNORECASE
)

# Yayıncı ve Canlı Yayın Standartları:
# Uygunsuz kelime kökleri, kod incelemelerinde veya canlı yayınlarda izleyicilerin
# rahatsız olmaması ve yayın platform kuralları gereği güvenli base64 formatında saklanır.
_ENCODED_PROFANITY_ROOTS = [
    "b8On", "b3Jvc3B1", "cGlj", "cGnDpw==", "c2lr", "c2lraWs=", "c2lrZXJpbQ==",
    "eWFycmFr", "YW1r", "YXE=", "YW1x", "Z290", "Z8O2dA==", "Z2F2YXQ=",
    "aWJuZQ==", "a2FocGU=", "cGV6ZXZlbms=", "c8O8cnTDvGs=", "eWFycmFt",
    "ZnVjaw==", "Yml0Y2g=", "YXNzaG9sZQ==", "ZGljaw==", "cHVzc3k=",
    "YmFzdGFyZA==", "Y3VudA==", "bW90aGVyZnVja2Vy"
]
PROFANITY_ROOTS = [base64.b64decode(item).decode("utf-8") for item in _ENCODED_PROFANITY_ROOTS]

def normalize_text(text: str) -> str:
    """
    Kelimeleri leetspeak, araya boşluk/nokta koyma ve harf uzatmalarına karşı normalleştirir.
    """
    s = text.lower()
    
    # Türkçe karakter değişimi
    tr_map = str.maketrans("ıiüğşöç", "iiugsoc")
    s = s.translate(tr_map)
    
    # Leetspeak dönüşümleri (@ -> a, 1 -> i, 0 -> o, 3 -> e, 5 -> s, $ -> s, 7 -> t, ! -> i, + -> t)
    leet_map = str.maketrans("@1035$7!+", "aioesstit")
    s = s.translate(leet_map)

    # Ardışık tekrarlanan harfleri teke indir (ör: siiiik -> sik)
    s = re.sub(r"(.)\1+", r"\1", s)
    return s


def contains_profanity(text: str) -> bool:
    """Metinde küfür veya hakaret olup olmadığını tespit eder"""
    normalized = normalize_text(text)
    words = re.findall(r"\b\w+\b", normalized)

    # Doğrudan kelime kontrolü
    for word in words:
        if word in PROFANITY_ROOTS:
            return True

    # Boşluksuz harf birleştirmelerine karşı alt dize kontrolü (kısa kelimeler hariç)
    compact = re.sub(r"[^a-z0-9]", "", normalized)
    for root in PROFANITY_ROOTS:
        if len(root) >= 3 and root in compact:
            return True

    return False


async def send_moderation_log(
    guild: discord.Guild,
    member: discord.Member,
    action: str,
    reason: str,
    duration_seconds: int,
    channel: discord.abc.GuildChannel,
    message_content: str,
    log_ch_name_or_id: Optional[str | int] = None
) -> None:
    """Moderasyon log kanalına şık bir embed gönderir"""
    target_channel: Optional[discord.TextChannel] = None

    if isinstance(log_ch_name_or_id, int):
        target_channel = guild.get_channel(log_ch_name_or_id)

    if not target_channel and log_ch_name_or_id:
        # İsimle ara
        name_clean = str(log_ch_name_or_id).lstrip("›").strip()
        target_channel = discord.utils.find(
            lambda c: isinstance(c, discord.TextChannel) and name_clean.lower() in c.name.lower(),
            guild.channels
        )

    if not target_channel:
        # 'mod-log' veya 'log' kanalını ara
        target_channel = discord.utils.find(
            lambda c: isinstance(c, discord.TextChannel) and "log" in c.name.lower(),
            guild.channels
        )

    if not target_channel:
        return

    embed = discord.Embed(
        title="🛡 DisMaker Dinamik Moderasyon Bildirimi",
        color=COLOR_DANGER,
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(name="Kullanıcı", value=f"{member.mention} (`{member.id}`)", inline=True)
    embed.add_field(name="Uygulanan Eylem", value=f"**{action}** ({duration_seconds}s Timeout)", inline=True)
    embed.add_field(name="İhlal Nedeni", value=reason, inline=False)
    embed.add_field(name="Kanal", value=f"#{channel.name}", inline=True)
    
    # Mesaj içeriğini sansürlü/kısaltılmış göster
    snippet = message_content[:200] if len(message_content) <= 200 else message_content[:197] + "..."
    embed.add_field(name="Mesaj İçeriği", value=f"```{snippet}```", inline=False)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text="DisMaker 7/24 Güvenlik Motoru")

    try:
        await target_channel.send(embed=embed)
    except Exception as e:
        logger.warning(f"Mod log kanalına bildirim gönderilemedi: {e}")


async def handle_message_moderation(message: discord.Message) -> bool:
    """
    Gelen mesajı sunucunun moderasyon politikasına göre inceler.
    İhlal varsa mesajı siler, kullanıcıyı timeout'a alır ve loglar.
    Dönüş: İhlal olduysa True, temizse False
    """
    # Bot mesajlarını ve DM'leri atla
    if message.author.bot or not message.guild or not isinstance(message.author, discord.Member):
        return False

    # Sunucu yöneticileri ve yetkililer cezalandırılmaz
    perms = message.author.guild_permissions
    if perms.administrator or perms.manage_guild or perms.manage_messages:
        return False

    guild_id = message.guild.id
    settings = db.get_guild_settings(guild_id)
    if not settings or not settings.get("moderation_enabled"):
        return False

    filter_profanity = bool(settings.get("filter_profanity", 1))
    filter_invites = bool(settings.get("filter_invites", 1))
    mute_seconds = int(settings.get("mute_duration_seconds", 600))
    log_ch = settings.get("log_channel_id") or settings.get("log_channel_name")

    content = message.content or ""
    violation_reason = None

    # 1. Davet Linki Kontrolü
    if filter_invites and DISCORD_INVITE_PATTERN.search(content):
        violation_reason = "İzinsiz Discord davet linki paylaşımı"

    # 2. Küfür ve Uygunsuz Kelime Kontrolü
    elif filter_profanity and contains_profanity(content):
        violation_reason = "Uygunsuz dil, küfür veya hakaret kullanımı"

    if violation_reason:
        try:
            # Mesajı sil
            await message.delete()

            # Kullanıcıya timeout ver
            timeout_until = discord.utils.utcnow() + datetime.timedelta(seconds=mute_seconds)
            await message.author.timeout(
                timeout_until,
                reason=f"DisMaker Otomatik Moderasyon: {violation_reason}"
            )

            # Veritabanına kaydet
            db.log_moderation_event(
                guild_id=guild_id,
                user_id=message.author.id,
                user_tag=str(message.author),
                action="TIMEOUT",
                reason=violation_reason,
                duration_seconds=mute_seconds,
                channel_id=message.channel.id
            )

            # Log kanalına gönder
            await send_moderation_log(
                guild=message.guild,
                member=message.author,
                action="Zaman Aşımı (Timeout)",
                reason=violation_reason,
                duration_seconds=mute_seconds,
                channel=message.channel,
                message_content=content,
                log_ch_name_or_id=log_ch
            )

            # Kullanıcıya bilgilendirme (kanal içi geçici uyarı)
            warning_msg = await message.channel.send(
                f"⚠ {message.author.mention}, sunucu kurallarını ihlal ettiğiniz için mesajınız silindi ve **{mute_seconds // 60} dakika** süreyle susturuldunuz."
            )
            # 5 saniye sonra uyarı mesajını sil (chat temizliği)
            await warning_msg.delete(delay=5.0)

            return True

        except discord.Forbidden:
            logger.warning(f"Botun '{message.author}' kullanıcısına ceza vermek için yetkisi yetersiz.")
        except Exception as e:
            logger.error(f"Moderasyon yürütülürken hata: {e}")

    return False
