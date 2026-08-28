"""
Modulo di reporting: generazione del report giornaliero in formato Markdown e JSON,
con visualizzazione a terminale tramite Rich e sezione dedicata agli Avvisi (Warnings).
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

import config

console = Console()


def generate_reports(aggregated_data: Dict, output_dir: Path = config.REPORTS_DIR) -> Dict[str, Path]:
    """
    Genera i file di report Markdown e JSON per la data corrente.
    Include la sezione dedicata agli avvisi per aziende meno popolari o titoli esteri.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    today_str = datetime.now().strftime("%Y-%m-%d")
    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    md_path = output_dir / f"report_{today_str}.md"
    json_path = output_dir / f"report_{today_str}.json"

    # 1. Salvataggio JSON
    def sanitize_item(obj):
        if isinstance(obj, dict):
            return {k: sanitize_item(v) for k, v in obj.items() if k != "published_dt"}
        elif isinstance(obj, list):
            return [sanitize_item(i) for i in obj]
        return obj

    serializable_data = sanitize_item(aggregated_data)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(serializable_data, f, indent=2, ensure_ascii=False)

    # 2. Generazione Markdown
    summary = aggregated_data.get("summary", {})
    by_ticker = aggregated_data.get("by_ticker", {})
    warnings = aggregated_data.get("warnings", [])

    lines = []
    lines.append(f"# 📊 Report Giornaliero Investimenti & Notizie - {today_str}")
    lines.append(f"*Generato automaticamente il: {timestamp_str}*\n")

    # Sommario esecutivo
    lines.append("## 📌 Sommario Esecutivo")
    lines.append(f"- **Ticker monitorati:** {summary.get('total_tickers', 0)}")
    lines.append(f"- **Ticker con aggiornamenti:** {summary.get('tickers_with_updates', 0)}")
    lines.append(f"- **Nuove idee VIC trovate:** {summary.get('total_vic_ideas', 0)}")
    lines.append(f"- **Nuovi messaggi VIC trovati:** {summary.get('total_vic_messages', 0)}")
    lines.append(f"- **Notizie & Comunicati Web (SEC / Yahoo / Google):** {summary.get('total_web_news', 0)}")
    lines.append(f"- **Avvisi di compatibilità / diagnostica:** {summary.get('total_warnings', len(warnings))}")
    lines.append("")

    # Sezione Avvisi & Diagnostica se presenti
    if warnings:
        lines.append("## ⚠️ Avvisi & Note di Riconoscimento Ticker")
        lines.append("Note sulle aziende meno diffuse, disambiguazioni o titoli esteri rilevati durante la scansione:\n")
        for w in warnings:
            t_str = f"**{w['ticker']}**" if w.get("ticker") else "**Avviso Generale**"
            lines.append(f"- ⚠️ {t_str}: {w.get('message')}")
        lines.append("\n---\n")

    # Tabella riepilogativa rapida
    lines.append("### Panoramica per Ticker")
    lines.append("| Ticker | Nome Azienda | Mercato | Idee VIC | Messaggi VIC | SEC Filings | Notizie Web |")
    lines.append("| :--- | :--- | :--- | :---: | :---: | :---: | :---: |")

    tickers_with_content = []
    tickers_quiet = []

    for ticker, info in by_ticker.items():
        name = info.get("name") or "-"
        market = info.get("market") or "-"
        n_ideas = len(info.get("vic_ideas", []))
        n_msgs = len(info.get("vic_messages", []))
        n_filings = len(info.get("sec_filings", []))
        n_news = len(info.get("news", []))

        sec_str = str(n_filings) if info.get("is_sec_eligible", True) else "N/A (Estero)"

        lines.append(f"| **{ticker}** | {name} | {market} | {n_ideas} | {n_msgs} | {sec_str} | {n_news} |")

        if info.get("has_updates"):
            tickers_with_content.append((ticker, info))
        else:
            tickers_quiet.append(ticker)

    lines.append("\n---\n")

    # Sezione Dettagliata per Ticker con Novità
    lines.append("## 🔍 Dettaglio Aggiornamenti per Ticker")

    if not tickers_with_content:
        lines.append("*Nessun nuovo aggiornamento rilevato nelle ultime 24 ore per i ticker in watchlist.*")
    else:
        for ticker, info in tickers_with_content:
            name_str = f" - {info['name']}" if info.get("name") else ""
            lines.append(f"### 📈 {ticker}{name_str}")

            # 1. Sezione VIC Ideas
            if info.get("vic_ideas"):
                lines.append("#### 💡 Value Investors Club - Nuove Idee")
                for idea in info["vic_ideas"]:
                    title = idea.get("title", "Idea")
                    url = idea.get("url", "#")
                    author = f" | Autore: `{idea['author']}`" if idea.get("author") else ""
                    date_info = f" | Data: {idea['date']}" if idea.get("date") else ""
                    lines.append(f"- **[{title}]({url})**{author}{date_info}")
                    if idea.get("snippet"):
                        lines.append(f"  > {idea['snippet']}")
                lines.append("")

            # 2. Sezione VIC Messages
            if info.get("vic_messages"):
                lines.append("#### 💬 Value Investors Club - Nuovi Messaggi / Discussioni")
                for msg in info["vic_messages"]:
                    title = msg.get("title", "Messaggio")
                    url = msg.get("url", "#")
                    lines.append(f"- **[{title}]({url})**")
                    if msg.get("snippet"):
                        lines.append(f"  > {msg['snippet']}")
                lines.append("")

            # 3. Sezione SEC Filings
            if info.get("sec_filings"):
                lines.append("#### 📑 SEC EDGAR Filings Ufficiali")
                for filing in info["sec_filings"]:
                    title = filing.get("title", "Filing")
                    url = filing.get("url", "#")
                    pub = filing.get("published_at", "")
                    lines.append(f"- **[{title}]({url})** ({pub})")
                    if filing.get("summary"):
                        lines.append(f"  > {filing['summary']}")
                lines.append("")

            # 4. Sezione Notizie Web & Agenzie
            if info.get("news"):
                lines.append("#### 📰 Notizie Web & Rassegna Finanziaria")
                for item in info["news"]:
                    source = item.get("source", "Web")
                    title = item.get("title", "Notizia")
                    url = item.get("url", "#")
                    pub = item.get("published_at", "")
                    author = item.get("author", "").strip()
                    date_str = f" - *{pub}*" if pub else ""
                    author_str = f" (Autore: {author})" if author else ""
                    lines.append(f"- **[{source}]** [{title}]({url}){date_str}{author_str}")
                    if item.get("summary"):
                        lines.append(f"  > {item['summary']}")
                lines.append("")

            lines.append("---\n")

    if tickers_quiet:
        lines.append(f"\n*Nessuna novità recente per:* {', '.join(tickers_quiet)}\n")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return {"markdown": md_path, "json": json_path}


def print_cli_summary(aggregated_data: Dict, report_paths: Dict[str, Path]):
    """Mostra a terminale una sintesi visiva tramite tabelle Rich con indicazione degli avvisi."""
    summary = aggregated_data.get("summary", {})
    by_ticker = aggregated_data.get("by_ticker", {})
    warnings = aggregated_data.get("warnings", [])

    console.print("\n")
    console.print(
        Panel.fit(
            f"[bold green]Scansione Completata con Successo![/bold green]\n"
            f"Report Markdown: [cyan]{report_paths['markdown']}[/cyan]\n"
            f"Report JSON:     [cyan]{report_paths['json']}[/cyan]",
            title="Risultati Monitoraggio",
            border_style="green"
        )
    )

    table = Table(title="Riepilogo Ticker Monitorati", header_style="bold magenta")
    table.add_column("Ticker", style="cyan", no_wrap=True)
    table.add_column("Nome Azienda", style="white")
    table.add_column("Borsa / Mercato", style="dim")
    table.add_column("Idee VIC", justify="center")
    table.add_column("Messaggi VIC", justify="center")
    table.add_column("SEC Filings", justify="center")
    table.add_column("Notizie Web", justify="center")
    table.add_column("Stato", justify="center")

    for ticker, info in by_ticker.items():
        name = info.get("name") or "-"
        market = info.get("market") or "-"
        n_ideas = len(info.get("vic_ideas", []))
        n_msgs = len(info.get("vic_messages", []))
        n_filings = len(info.get("sec_filings", []))
        n_news = len(info.get("news", []))

        status_badge = "[bold green]Novità[/bold green]" if info.get("has_updates") else "[dim]Invariato[/dim]"
        sec_col = f"[bold red]{n_filings}[/bold red]" if info.get("is_sec_eligible", True) else "[dim]N/A (Est)[/dim]"

        table.add_row(
            ticker,
            name[:24],
            market[:18],
            f"[bold yellow]{n_ideas}[/bold yellow]" if n_ideas else "0",
            f"[bold blue]{n_msgs}[/bold blue]" if n_msgs else "0",
            sec_col,
            f"[bold green]{n_news}[/bold green]" if n_news else "0",
            status_badge
        )

    console.print(table)
    console.print("\n")
