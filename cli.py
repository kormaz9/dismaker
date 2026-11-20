"""
DisMaker - Komut Satırı (CLI) Mimari Üretim Aracı
Discord botunu çalıştırmadan doğrudan terminal üzerinden mimari tasarlayın ve JSON çıktısı alın.
"""

import sys
import json
import asyncio
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax

from config import is_configured, GEMINI_MODELS
from core.gemini_client import GeminiArchitectClient, GeminiAPIError

console = Console()


def display_architecture(arch, model_used: str):
    """Üretilen mimariyi terminalde şık tablolarla gösterir"""
    console.print(f"\n[bold green]✓ Mimari Başarıyla Üretildi![/bold green] (Model: [cyan]{model_used}[/cyan])\n")

    # Genel Bilgiler Paneli
    info_table = Table(show_header=False, box=None)
    info_table.add_row("[bold]Sunucu Adı:[/bold]", f"[bold white]{arch.server_name}[/bold white]")
    info_table.add_row("[bold]Tema:[/bold]", f"[white]{arch.server_theme}[/white]")
    info_table.add_row("[bold]Giriş Rolü (Autorole):[/bold]", f"[yellow]{arch.autorole}[/yellow]")
    info_table.add_row(
        "[bold]7/24 Moderasyon:[/bold]",
        "[green]Aktif[/green]" if arch.moderation_policy.enabled else "[dim]Devre Dışı[/dim]"
    )
    if arch.moderation_policy.enabled:
        info_table.add_row("  ↳ [dim]Küfür Filtresi:[/dim]", "Açık" if arch.moderation_policy.filter_profanity else "Kapalı")
        info_table.add_row("  ↳ [dim]Davet Filtresi:[/dim]", "Açık" if arch.moderation_policy.filter_invites else "Kapalı")
        info_table.add_row("  ↳ [dim]Timeout Süresi:[/dim]", f"{arch.moderation_policy.mute_duration_seconds} saniye")
        info_table.add_row("  ↳ [dim]Log Kanalı:[/dim]", f"`{arch.moderation_policy.log_channel_name}`")

    console.print(Panel(info_table, title="[bold cyan]◈ GENEL YAPILANDIRMA[/bold cyan]", border_style="cyan"))

    # Roller Tablosu
    role_table = Table(title="◈ HİYERARŞİK ROLLER", border_style="dim")
    role_table.add_column("Rol Adı", style="bold")
    role_table.add_column("HEX Renk", justify="center")
    role_table.add_column("Ayrı Göster (Hoist)", justify="center")
    role_table.add_column("Bahsedilebilir", justify="center")
    role_table.add_column("İzinler")

    for r in arch.roles:
        role_table.add_row(
            r.name,
            f"[{r.color}]{r.color}[/{r.color}]",
            "✓" if r.hoist else "✕",
            "✓" if r.mentionable else "✕",
            ", ".join(r.permissions[:4]) + (f" (+{len(r.permissions)-4})" if len(r.permissions) > 4 else "")
        )
    console.print(role_table)

    # Kategoriler ve Kanallar
    cat_table = Table(title="◈ KATEGORİLER VE KANALLAR", border_style="dim")
    cat_table.add_column("Kategori / Kanal Adı", style="bold")
    cat_table.add_column("Tür", justify="center")
    cat_table.add_column("Yavaş Mod", justify="center")
    cat_table.add_column("Konu / İzinler")

    for cat in arch.categories:
        cat_table.add_row(f"[bold yellow]{cat.name}[/bold yellow]", "KATEGORİ", "-", f"{len(cat.channels)} kanal")
        for ch in cat.channels:
            ch_type = "🔊 Ses" if ch.type == "voice" else "💬 Metin"
            slow = f"{ch.slowmode}s" if ch.slowmode else "-"
            cat_table.add_row(f"  {ch.name}", ch_type, slow, ch.topic or "-")

    console.print(cat_table)

    # Kurallar Embed Özeti
    if arch.rules_embed:
        rules_box = f"[bold]{arch.rules_embed.title}[/bold]\n"
        if arch.rules_embed.description:
            rules_box += f"{arch.rules_embed.description}\n\n"
        for f in arch.rules_embed.fields:
            rules_box += f"• [bold]{f.name}:[/bold] {f.value}\n"
        if arch.rules_embed.footer:
            rules_box += f"\n[dim]{arch.rules_embed.footer}[/dim]"
        console.print(Panel(rules_box, title="[bold magenta]◈ KURALLAR EMBED PANELI[/bold magenta]", border_style="magenta"))


async def run_cli(prompt_text: str, save_path: str = None):
    """CLI yürütme fonksiyonu"""
    configured, missing = is_configured()
    if not configured and "GEMINI_API_KEY" in missing:
        console.print(
            "[bold red]HATA:[/bold red] .env dosyasında [yellow]GEMINI_API_KEY[/yellow] eksik veya doldurulmamış!\n"
            "Lütfen .env dosyasını açıp geçerli bir Gemini API anahtarı ekleyin."
        )
        return

    console.print(Panel(
        f"[bold white]İstek:[/bold white] [italic]{prompt_text}[/italic]\n"
        f"[bold cyan]Model Sıralaması:[/bold cyan] {' ➔ '.join(GEMINI_MODELS[:4])}",
        title="[bold]DisMaker Sistem Mimarı Başlatılıyor[/bold]",
        border_style="blue"
    ))

    with console.status("[cyan]Gemini yapay zeka modelleri analiz ediyor... (3.5 / 2.5)[/cyan]"):
        client = GeminiArchitectClient()
        try:
            arch, model_used = await client.generate_architecture(prompt_text)
        except GeminiAPIError as e:
            console.print(f"[bold red]Gemini Hatası:[/bold red] {e}")
            return
        except Exception as e:
            console.print(f"[bold red]Hata:[/bold red] {e}")
            return

    display_architecture(arch, model_used)

    # JSON Çıktısı Kaydetme
    if save_path:
        out_file = Path(save_path)
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(arch.model_dump(), f, indent=2, ensure_ascii=False)
        console.print(f"\n[green]✓ JSON mimarisi kaydedildi:[/green] [bold]{out_file.resolve()}[/bold]")
    else:
        # Ekrana JSON formatında bas
        json_str = json.dumps(arch.model_dump(), indent=2, ensure_ascii=False)
        syntax = Syntax(json_str, "json", theme="monokai", line_numbers=True)
        console.print(Panel(syntax, title="[bold]HAM JSON VERİ MODELİ (STRICT SCHEMA)[/bold]", border_style="dim"))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        user_prompt = " ".join(sys.argv[1:])
        save_file = "server_architecture.json"
    else:
        console.print("[bold cyan]DisMaker Evrensel Discord Mimarı - Terminal Arayüzü[/bold cyan]")
        console.print("İstediğiniz sunucu temasını, kurallarını ve rollerini yazın:")
        user_prompt = input("\n> ").strip()
        save_file = "server_architecture.json" if user_prompt else None

    if user_prompt:
        asyncio.run(run_cli(user_prompt, save_file))
    else:
        console.print("[yellow]İstek girilmedi, çıkılıyor.[/yellow]")
