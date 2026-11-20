"""
DisMaker - Otomatik Rol (Autorole) Motoru
Yeni katılan üyelere belirlenen temel rolü otomatik atar.
"""

import logging
import discord
from core.database import db

logger = logging.getLogger("DisMaker.Autorole")


async def handle_member_join(member: discord.Member) -> None:
    """
    Sunucuya yeni bir üye katıldığında tetiklenir ve autorole tanımlıysa atar.
    """
    if member.bot:
        return

    guild = member.guild
    settings = db.get_guild_settings(guild.id)
    if not settings:
        return

    # Eğer sunucuda Doğrulama Kapısı (Verification Gate) aktifse, kullanıcı kuralları onaylayana kadar bekle
    if settings.get("rules_channel_id"):
        logger.info(
            f"ℹ [Doğrulama Kapısı] '{member.display_name}' ({member.id}) sunucuya katıldı. "
            "Kuralları onaylayana kadar autorole beklemede tutuluyor."
        )
        return

    role_id = settings.get("autorole_id")
    role_name = settings.get("autorole_name")

    target_role: discord.Role | None = None

    if role_id:
        target_role = guild.get_role(role_id)

    if not target_role and role_name:
        target_role = discord.utils.get(guild.roles, name=role_name)

    if target_role:
        try:
            # Botun rol hiyerarşisi kontrolü
            if target_role < guild.me.top_role:
                await member.add_roles(
                    target_role,
                    reason=f"DisMaker Autorole: {target_role.name} rolü atandı."
                )
                logger.info(f"✓ [Autorole] '{member.display_name}' kullanıcısına '{target_role.name}' verildi.")
            else:
                logger.warning(
                    f"⚠ [Autorole] Botun en yüksek rolü '{target_role.name}' rolünden düşük olduğu için rol verilemedi."
                )
        except discord.Forbidden:
            logger.warning(f"⚠ [Autorole] '{member.display_name}' için rol verme izni yetersiz.")
        except Exception as e:
            logger.error(f"⚠ [Autorole] Rol atanırken hata oluştu: {e}")
