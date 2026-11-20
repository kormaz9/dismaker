"""
DisMaker - Evrensel Discord Mimarı ve Sistem Mühendisi
Ana Çalıştırma Dosyası
"""

import sys
import logging
from rich.logging import RichHandler
from rich.console import Console

from config import (
    DISCORD_BOT_TOKEN,
    is_configured,
    GEMINI_PRIMARY_MODEL,
    GEMINI_FALLBACK_MODEL
)
from discord_bot.bot import bot

# Log Yapılandırması (Rich Formatı)
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True, show_path=False)]
)

logger = logging.getLogger("DisMaker")
console = Console()


def show_setup_guide(missing: list[str]):
    """Eksik yapılandırma durumunda kullanıcıya görsel rehber sunar"""
    console.print("\n[bold yellow]══════════════════════════════════════════════════════════════════[/bold yellow]")
    console.print("  [bold cyan]DISMAKER - YAPILANDIRMA GEREKLİ[/bold cyan]")
    console.print("[bold yellow]══════════════════════════════════════════════════════════════════[/bold yellow]\n")

    if "DISCORD_BOT_TOKEN" in missing:
        console.print("[bold red]✕ DISCORD_BOT_TOKEN EKSİK[/bold red]")
        console.print("  1. https://discord.com/developers/applications adresine gidin.")
        console.print("  2. Bir uygulama ve Bot oluşturun.")
        console.print("  3. [bold white]Privileged Gateway Intents[/bold white] kısmındaki:")
        console.print("     • [cyan]SERVER MEMBERS INTENT[/cyan] (Açık olmalı)")
        console.print("     • [cyan]MESSAGE CONTENT INTENT[/cyan] (Açık olmalı)")
        console.print("  4. Token'ı kopyalayıp [bold white].env[/bold white] dosyasındaki [cyan]DISCORD_BOT_TOKEN[/cyan] alanına yapıştırın.\n")

    if "GEMINI_API_KEY" in missing:
        console.print("[bold red]✕ GEMINI_API_KEY EKSİK[/bold red]")
        console.print("  1. https://aistudio.google.com/ adresine gidin.")
        console.print("  2. 'Get API key' butonuna basarak ücretsiz bir Gemini API anahtarı alın.")
        console.print("  3. Anahtarı [bold white].env[/bold white] dosyasındaki [cyan]GEMINI_API_KEY[/cyan] alanına yapıştırın.\n")

    console.print(f"[bold dim]Yapay Zeka Modelleri: {GEMINI_PRIMARY_MODEL} (Öncelikli) -> {GEMINI_FALLBACK_MODEL} (Yedek)[/bold dim]\n")
    console.print("[yellow]Anahtarları .env dosyasına ekledikten sonra botu tekrar çalıştırın:[/yellow]")
    console.print("[bold white]python main.py[/bold white]\n")


def start_bot():
    """Botu başlatır"""
    configured, missing = is_configured()

    if not configured:
        show_setup_guide(missing)
        return

    logger.info("DisMaker Discord Botu başlatılıyor...")
    try:
        bot.run(DISCORD_BOT_TOKEN, log_handler=None)
    except KeyboardInterrupt:
        logger.info("Bot kullanıcı tarafından durduruldu.")
    except Exception as e:
        logger.error(f"Bot çalıştırılırken bir hata oluştu: {e}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--cli":
        import cli
        import asyncio
        prompt = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "Yazılım ve Yapay Zeka Geliştiricileri Topluluğu"
        asyncio.run(cli.run_cli(prompt, "server_architecture.json"))
    else:
        start_bot()
