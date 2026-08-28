"""
Script Principale di Monitoraggio Finanziario (Versione 1):
- Web Financial News (SEC EDGAR, Finviz, Yahoo Finance, Google News, Seeking Alpha, Borsa IT / SDIR)
- Motore di Validazione e Avvisi (Warnings) per Ticker Meno Popolari e Internazionali
- Notifiche Email HTML Responsive via Gmail SMTP (Locale & GitHub Actions)
- Value Investors Club facoltativo su richiesta (--with-vic)
"""

import sys
import argparse
from pathlib import Path
from typing import List, Optional, Dict, Any
from rich.console import Console
from rich.panel import Panel

import config
from src.watchlist import load_watchlist, get_ticker_symbols
from src.validator import validate_watchlist, print_validation_summary
from src.news_engine import fetch_news_for_watchlist
from src.aggregator import aggregate_results
from src.reporter import generate_reports, print_cli_summary
from src.mailer import send_email_report

console = Console()


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Monitoraggio Finanziario Automatico per Watchlist Personale (News, SEC Filings & Email Digest).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Esempi di utilizzo:
  python main.py --run               # Scansione quotidiana completa V1 (SEC + Finviz + Google + Yahoo + Borsa IT)
  python main.py --run --email       # Scansione ed invio immediato del report via email Gmail
  python main.py --validate          # Diagnosi preventiva e controllo riconoscibilità ticker
  python main.py --tickers CRM,TGYM:xmil # Controlla solo i ticker specificati
  python main.py --days 3            # Finestra temporale di 3 giorni
  python main.py --with-vic          # Include anche lo scraping di Value Investors Club (richiede Playwright)
  python main.py --login             # Esegue il login manuale a VIC e salva la sessione
        """
    )

    parser.add_argument(
        "--run",
        action="store_true",
        default=False,
        help="Esegue la scansione quotidiana delle notizie e dei filing SEC per tutti i ticker in watchlist."
    )
    parser.add_argument(
        "--email",
        action="store_true",
        default=False,
        help="Invia il report generato via email (Gmail SMTP) al termine della scansione."
    )
    parser.add_argument(
        "--validate", "--check-tickers",
        action="store_true",
        dest="validate",
        help="Esegue la diagnosi di compatibilità e mapping dei ticker senza effettuare la scansione delle news."
    )
    parser.add_argument(
        "--with-vic",
        action="store_true",
        default=False,
        help="Include lo scraping di Value Investors Club (avvia browser Playwright per idee e messaggi)."
    )
    parser.add_argument(
        "--login",
        action="store_true",
        help="Apre il browser per effettuare il login interattivo su Value Investors Club e salvare la sessione."
    )
    parser.add_argument(
        "--tickers",
        type=str,
        help="Lista di ticker separati da virgola (es. CRM,TGYM:xmil,700) per sovrascrivere temporaneamente la watchlist."
    )
    parser.add_argument(
        "--days",
        type=int,
        default=1,
        help="Finestra temporale in giorni per le notizie (default: 1 giorno / 24 ore)."
    )
    parser.add_argument(
        "--headful",
        action="store_true",
        help="Avvia il browser visibile (non headless) se --with-vic è attivo."
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(config.REPORTS_DIR),
        help="Percorso della cartella dove salvare i report generati."
    )

    return parser.parse_args()


def run_daily_monitoring(
    override_tickers: List[str] = None,
    with_vic: bool = False,
    send_email: bool = False,
    lookback_days: int = 1,
    headless: bool = True,
    output_dir: Path = config.REPORTS_DIR
):
    """Orchestratore principale per la raccolta dati dal Web, SEC, VIC e invio email."""
    lookback_hours = max(1, lookback_days * 24)

    # 1. Caricamento Watchlist
    watchlist = load_watchlist(override_tickers=override_tickers)
    ticker_symbols = get_ticker_symbols(watchlist)

    mode_label = "Completo (News Web + SEC + Finviz + Borsa IT)"
    if with_vic:
        mode_label += " + Value Investors Club"

    console.print(
        Panel.fit(
            f"[bold cyan]Avvio Monitoraggio Finanziario Quotidiano[/bold cyan]\n"
            f"• Ticker in watchlist: [bold yellow]{', '.join(ticker_symbols)}[/bold yellow]\n"
            f"• Finestra temporale: [bold]{lookback_days} {'giorno' if lookback_days == 1 else 'giorni'}[/bold] ({lookback_hours} ore)\n"
            f"• Canali attivi:      [bold]{mode_label}[/bold]\n"
            f"• Notifica Email:     [bold]{'Abilitata' if send_email or config.ENABLE_EMAIL else 'Disabilitata (usa --email)'}[/bold]",
            title="Stato Iniziale",
            border_style="cyan"
        )
    )

    # 2. Diagnosi & Validazione Ticker (silente in modalità run)
    validation_report = validate_watchlist(watchlist, check_vic=with_vic)

    vic_ideas = []
    vic_messages = []
    web_news = {}

    # 3. Sezione Value Investors Club (Opzionale su richiesta)
    if with_vic:
        console.print("\n[bold cyan]1. Connessione e Controllo Value Investors Club...[/bold cyan]")
        try:
            from playwright.sync_api import sync_playwright
            from src.auth import launch_vic_context
            from src.vic_client import VICClient

            with sync_playwright() as p:
                context = launch_vic_context(p, headless=headless)
                vic = VICClient(context)

                # Verifica login
                vic.verify_login_status()

                # Scansione Idee recenti
                console.print(f"[dim]Controllo nuove idee su VIC per la watchlist...[/dim]")
                ideas = vic.scrape_recent_ideas(watchlist)
                vic_ideas.extend(ideas)
                console.print(f"  [green]✓ Trovate {len(ideas)} idee corrispondenti nel feed recente di VIC[/green]")

                # Scansione Messaggi / Discussioni
                console.print(f"[dim]Controllo nuovi messaggi/commenti su VIC...[/dim]")
                messages = vic.scrape_recent_messages(watchlist)
                vic_messages.extend(messages)
                console.print(f"  [green]✓ Trovati {len(messages)} messaggi correlati su VIC[/green]")

                # Ricerca mirata per ciascun ticker
                for item in watchlist:
                    sym = item["ticker"]
                    meta = item.get("metadata", {})
                    vic_syms = meta.get("vic_symbols", [sym])
                    cname = item.get("name", "")
                    if not any(x["ticker"] == sym for x in vic_ideas):
                        specific_ideas = vic.search_ticker_ideas(sym, vic_symbols=vic_syms, company_name=cname)
                        for sp in specific_ideas:
                            if not any(x["url"] == sp["url"] for x in vic_ideas):
                                vic_ideas.append(sp)

                context.close()
        except Exception as e:
            console.print(f"[bold red]Errore durante la scansione di VIC: {e}[/bold red]")
            console.print("[yellow]I controlli proseguono con la raccolta notizie dal Web...[/yellow]")

    # 4. Sezione Notizie Web & SEC Filings (SEC + Finviz + Yahoo + Google + Seeking Alpha + Borsa IT)
    console.print("\n[bold cyan]1. Raccolta Notizie Web, SEC Filings & Comunicati Ufficiali...[/bold cyan]")
    console.print("[dim]Interrogazione SEC EDGAR, Finviz News, Yahoo Finance, Google News, Seeking Alpha e Borsa IT...[/dim]")
    web_news = fetch_news_for_watchlist(watchlist, lookback_hours=lookback_hours)
    total_items = sum(len(items) for items in web_news.values())
    console.print(f"  [green]✓ Raccolti {total_items} articoli e comunicati totali[/green]")

    # 5. Aggregazione & Deduplicazione
    console.print("\n[dim]Aggregazione e deduplicazione dati in corso...[/dim]")
    aggregated = aggregate_results(
        watchlist,
        vic_ideas,
        vic_messages,
        web_news,
        validation_report=validation_report
    )

    # 6. Generazione Report Markdown e JSON
    report_paths = generate_reports(aggregated, output_dir=output_dir)
    print_cli_summary(aggregated, report_paths)

    # 7. Invio Notifica Email (se abilitata)
    if send_email or config.ENABLE_EMAIL:
        console.print("\n[bold cyan]2. Spedizione Digest Email...[/bold cyan]")
        send_email_report(aggregated, report_paths=report_paths)


def main():
    args = parse_arguments()

    if args.login:
        from src.auth import run_interactive_login
        run_interactive_login()
        sys.exit(0)

    override = [t.strip() for t in args.tickers.split(",")] if args.tickers else None

    # Modalità sola validazione / diagnosi
    if args.validate:
        watchlist = load_watchlist(override_tickers=override)
        report = validate_watchlist(watchlist, check_vic=args.with_vic)
        print_validation_summary(report)
        sys.exit(0)

    headless = not args.headful

    # Esecuzione scansione
    run_daily_monitoring(
        override_tickers=override,
        with_vic=args.with_vic,
        send_email=args.email,
        lookback_days=args.days,
        headless=headless,
        output_dir=Path(args.output_dir)
    )


if __name__ == "__main__":
    main()
