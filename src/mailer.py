"""
Modulo di generazione template email HTML responsive e spedizione tramite Gmail SMTP.
Permette la notifica automatica quotidiana sia in locale che tramite GitHub Actions.
"""

import os
import ssl
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Optional
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
import config
from src.scorer import select_top_articles_for_ticker

console = Console()


def generate_html_email(aggregated_data: Dict) -> str:
    """
    Genera un digest email HTML ultra-snello, pulito e mirato:
    - Esclude categoricamente SEC Filings e comunicati Borsa Italiana;
    - Assegna a Seeking Alpha il Tier 0 (+40 punti esclusivo);
    - Assegna alle grandi testate (Reuters, Bloomberg, WSJ, Barron's, MarketWatch, CNBC, FT) il Tier 1 (+25 punti);
    - Assegna a portali e analisi (IBD, GuruFocus, Forbes, Fortune, Quartz) il Tier 2 (+15 punti);
    - Seleziona esattamente al massimo i 2 migliori articoli per ticker;
    - Evita duplicati o ripetizioni sullo stesso evento.
    """
    today_str = datetime.now().strftime("%d %B %Y")
    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M UTC")

    summary = aggregated_data.get("summary", {})
    by_ticker = aggregated_data.get("by_ticker", {})

    total_tickers = summary.get("total_tickers", len(by_ticker))

    # Selezione qualitativa Top 2 per ticker
    active_tickers = []
    quiet_tickers = []
    total_selected_articles = 0

    for ticker, info in by_ticker.items():
        name = info.get("name") or ticker
        raw_news = info.get("news", [])

        top_articles = select_top_articles_for_ticker(
            raw_news,
            ticker=ticker,
            company_name=name,
            max_items=2
        )

        if top_articles:
            # Ordina gli articoli internamente per punteggio decrescente
            top_articles.sort(key=lambda x: x.get("quality_score", 0.0), reverse=True)
            max_score = max(it.get("quality_score", 0.0) for it in top_articles)
            active_tickers.append((ticker, info, top_articles, len(raw_news), max_score))
            total_selected_articles += len(top_articles)
        else:
            quiet_tickers.append(ticker)

    # Ordina i ticker nell'email dal punteggio più alto al più basso
    active_tickers.sort(key=lambda x: x[4], reverse=True)

    # 1. Header & Stili CSS Inlined
    html = f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Finance Digest - {today_str}</title>
<style>
  body {{
    margin: 0;
    padding: 0;
    background-color: #f1f5f9;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    color: #1e293b;
    -webkit-font-smoothing: antialiased;
  }}
  .container {{
    max-width: 640px;
    margin: 20px auto;
    background: #ffffff;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
    border: 1px solid #e2e8f0;
  }}
  .header {{
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
    color: #ffffff;
    padding: 22px 26px;
  }}
  .header h1 {{
    margin: 0 0 4px 0;
    font-size: 19px;
    font-weight: 700;
    letter-spacing: -0.4px;
  }}
  .header .date {{
    font-size: 13px;
    color: #94a3b8;
    margin: 0;
  }}
  .stats-bar {{
    display: flex;
    background-color: #f8fafc;
    border-bottom: 1px solid #e2e8f0;
    padding: 10px 26px;
    gap: 16px;
  }}
  .stat-pill {{
    font-size: 12px;
    font-weight: 600;
    color: #475569;
  }}
  .stat-num {{
    color: #0284c7;
  }}
  .content {{
    padding: 20px 26px;
  }}
  .section-title {{
    font-size: 13px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #64748b;
    margin-top: 0;
    margin-bottom: 14px;
  }}
  .ticker-card {{
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    margin-bottom: 16px;
    overflow: hidden;
    background: #ffffff;
  }}
  .ticker-header {{
    background-color: #f8fafc;
    padding: 10px 14px;
    border-bottom: 1px solid #e2e8f0;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}
  .ticker-title {{
    font-size: 15px;
    font-weight: 700;
    color: #0f172a;
    margin: 0;
  }}
  .market-badge {{
    display: inline-block;
    padding: 2px 7px;
    border-radius: 4px;
    font-size: 10.5px;
    font-weight: 600;
    background-color: #e0f2fe;
    color: #0369a1;
  }}
  .ticker-body {{
    padding: 12px 14px;
  }}
  .item-list {{
    list-style: none;
    padding: 0;
    margin: 0;
  }}
  .item {{
    margin-bottom: 10px;
    padding-bottom: 10px;
    border-bottom: 1px solid #f1f5f9;
  }}
  .item:last-child {{
    margin-bottom: 0;
    padding-bottom: 0;
    border-bottom: none;
  }}
  .score-badge {{
    font-size: 9.5px;
    font-weight: 700;
    padding: 2px 5px;
    border-radius: 3px;
    display: inline-block;
    margin-right: 5px;
  }}
  .score-high {{
    background: #ecfdf5;
    color: #047857;
    border: 1px solid #a7f3d0;
  }}
  .score-med {{
    background: #e0f2fe;
    color: #0369a1;
    border: 1px solid #bae6fd;
  }}
  .score-low {{
    background: #f1f5f9;
    color: #475569;
    border: 1px solid #e2e8f0;
  }}
  .source-tag {{
    font-size: 9.5px;
    font-weight: 700;
    text-transform: uppercase;
    padding: 2px 6px;
    border-radius: 3px;
    background: #f1f5f9;
    color: #475569;
    display: inline-block;
    margin-right: 6px;
  }}
  .source-sa {{
    background: #ffedd5;
    color: #9a3412;
    border: 1px solid #fed7aa;
  }}
  .source-tier1 {{
    background: #e0f2fe;
    color: #0369a1;
    border: 1px solid #bae6fd;
  }}
  .item-link {{
    color: #0f172a;
    text-decoration: none;
    font-size: 13px;
    font-weight: 500;
    line-height: 1.4;
  }}
  .item-link:hover {{
    color: #0284c7;
    text-decoration: underline;
  }}
  .item-meta {{
    font-size: 11px;
    color: #94a3b8;
    margin-top: 3px;
  }}
  .quiet-section {{
    margin-top: 20px;
    padding: 12px 14px;
    background-color: #f8fafc;
    border-radius: 6px;
    font-size: 12px;
    color: #64748b;
    border: 1px solid #f1f5f9;
  }}
  .footer {{
    padding: 18px 26px;
    background-color: #f8fafc;
    border-top: 1px solid #e2e8f0;
    text-align: center;
    font-size: 11px;
    color: #94a3b8;
  }}
</style>
</head>
<body>

<div class="container">
  <!-- Header -->
  <div class="header">
    <h1>📊 Finance Watcher Digest</h1>
    <p class="date">{today_str} &bull; Ordinato per Rilevanza Decrescente</p>
  </div>

  <!-- Barra Statistiche -->
  <div class="stats-bar">
    <div class="stat-pill">Watchlist: <span class="stat-num">{total_tickers}</span></div>
    <div class="stat-pill">Ticker in Focus: <span class="stat-num">{len(active_tickers)}</span></div>
    <div class="stat-pill">Articoli Selezionati: <span class="stat-num">{total_selected_articles}</span></div>
  </div>

  <div class="content">
"""

    # 2. Dettaglio Ticker Attivi
    if not active_tickers:
        html += """
    <p style="text-align: center; color: #64748b; font-size: 14px; padding: 24px 0;">
      Nessuna notizia o analisi rilevante selezionata nelle ultime 24 ore per i ticker in watchlist.
    </p>
"""
    else:
        html += """    <div class="section-title">Aggiornamenti & Tesi Principali (Ordinati per Score)</div>\n"""
        for ticker, info, top_articles, raw_count, max_sc in active_tickers:
            name = info.get("name") or ticker
            market = info.get("market") or "Borsa"
            sc_header_class = "score-high" if max_sc >= 40 else ("score-med" if max_sc >= 20 else "score-low")
            sc_header_str = f"+{int(max_sc)}" if max_sc == int(max_sc) else f"+{max_sc:.1f}"

            html += f"""
    <div class="ticker-card">
      <div class="ticker-header">
        <h2 class="ticker-title">{ticker} &mdash; <span style="font-weight: 500; font-size: 13.5px; color: #475569;">{name}</span></h2>
        <div>
          <span class="score-badge {sc_header_class}">Score: {sc_header_str}</span>
          <span class="market-badge">{market}</span>
        </div>
      </div>
      <div class="ticker-body">
        <ul class="item-list">
"""
            for item in top_articles:
                src = item.get("source", "Web")
                title = item.get("title", "Notizia")
                url = item.get("url", "#")
                pub = item.get("published_at", "")
                it_score = item.get("quality_score", 0.0)

                it_sc_str = f"+{int(it_score)}" if it_score == int(it_score) else f"+{it_score:.1f}"
                it_sc_class = "score-high" if it_score >= 40 else ("score-med" if it_score >= 20 else "score-low")
                score_pill = f'<span class="score-badge {it_sc_class}">{it_sc_str} pt</span>'

                src_lower = src.lower()
                is_sa = "seeking alpha" in src_lower
                is_tier1 = any(k in src_lower for k in ["bloomberg", "reuters", "barron", "marketwatch", "wsj", "cnbc", "financial times"])

                if is_sa:
                    badge_html = '<span class="source-tag source-sa">SEEKING ALPHA</span>'
                elif is_tier1:
                    badge_html = f'<span class="source-tag source-tier1">{src}</span>'
                else:
                    badge_html = f'<span class="source-tag">{src}</span>'

                author = item.get("author", "").strip()
                author_html = f" &bull; Autore: <strong style=\"color: #475569;\">{author}</strong>" if author else ""

                html += f"""
          <li class="item">
            {score_pill}
            {badge_html}
            <a href="{url}" class="item-link" target="_blank">{title}</a>
            <div class="item-meta">{pub}{author_html}</div>
          </li>
"""
            if raw_count > len(top_articles):
                remaining = raw_count - len(top_articles)
                html += f"""
          <li class="item" style="border: none; padding-top: 4px;">
            <span style="font-size: 11px; color: #94a3b8; font-style: italic;">...altri {remaining} articoli archiviati nel report completo.</span>
          </li>
"""

            html += """        </ul>
      </div>
    </div>
"""


    # 3. Sezione Ticker Invariati
    if quiet_tickers:
        html += f"""
    <div class="quiet-section">
      <strong>Invariati / Nessuna novit&agrave; rilevante:</strong> {', '.join(quiet_tickers)}
    </div>
"""

    # 4. Footer
    html += f"""
  </div>
  <div class="footer">
    Generato automaticamente il {timestamp_str} via Personal Finance Notifications.<br>
    Configurato con GitHub Actions &bull; Filtro qualitativo Top 2 per ticker &bull; Seeking Alpha Tier 0.
  </div>
</div>

</body>
</html>
"""
    return html


def send_email_report(
    aggregated_data: Dict,
    report_paths: Optional[Dict[str, Path]] = None,
    recipient_override: Optional[str] = None
) -> bool:
    """
    Invia il digest via email a mezzo del server SMTP di Gmail.
    Utilizza le credenziali definite in config.py / variabili d'ambiente.
    """
    gmail_user = config.GMAIL_USER
    gmail_app_password = config.GMAIL_APP_PASSWORD
    recipient = recipient_override or config.NOTIFICATION_EMAIL or gmail_user

    if not gmail_user or not gmail_app_password:
        console.print(
            Panel.fit(
                "[bold yellow]⚠️ Notifica Email Saltata (Credenziali non configurate)[/bold yellow]\n\n"
                "Per ricevere il digest via email:\n"
                "1. Genera una 'Password per le app' sul tuo account Google;\n"
                "2. Aggiungi nel tuo file .env (o nei GitHub Secrets):\n"
                "   [cyan]GMAIL_USER=latuamail@gmail.com[/cyan]\n"
                "   [cyan]GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx[/cyan]\n"
                "   [cyan]NOTIFICATION_EMAIL=latuamail@gmail.com[/cyan]",
                title="Configurazione Email",
                border_style="yellow"
            )
        )
        return False

    summary = aggregated_data.get("summary", {})
    n_updates = summary.get("tickers_with_updates", 0)
    today_str = datetime.now().strftime("%d/%m/%Y")

    subject = f"📊 Finance Digest [{today_str}] - {n_updates} ticker con novita'"

    # Costruzione messaggio MIME Multipart
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Personal Finance Watcher <{gmail_user}>"
    msg["To"] = recipient

    # Versione testuale semplice
    text_content = f"Finance Digest del {today_str}\n\nTicker con novita': {n_updates}\n\nVisualizza il report completo in allegato o nei report locali."
    if report_paths and report_paths.get("markdown") and report_paths["markdown"].exists():
        try:
            with open(report_paths["markdown"], "r", encoding="utf-8") as f:
                text_content = f.read()
        except Exception:
            pass

    # Versione HTML Responsive
    html_content = generate_html_email(aggregated_data)

    msg.attach(MIMEText(text_content, "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    console.print(f"[dim]Connessione al server SMTP di Gmail ({config.SMTP_HOST}:{config.SMTP_PORT})...[/dim]")
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, context=context, timeout=15) as server:
            server.login(gmail_user, gmail_app_password)
            server.send_message(msg)

        console.print(
            Panel.fit(
                f"[bold green]✓ Notifica Email inviata con successo![/bold green]\n"
                f"Destinatario: [cyan]{recipient}[/cyan]\n"
                f"Oggetto:      [dim]{subject}[/dim]",
                title="Email Spedita",
                border_style="green"
            )
        )
        return True
    except Exception as e:
        console.print(f"[bold red]Errore durante l'invio dell'email via Gmail: {e}[/bold red]")
        return False


if __name__ == "__main__":
    # Test standalone
    sample_data = {
        "summary": {
            "total_tickers": 3,
            "tickers_with_updates": 2,
            "total_web_news": 5,
            "total_warnings": 1
        },
        "warnings": [
            {"ticker": "BEC:XMIL", "message": "Titolo quotato su Borsa Italiana (Euronext Milan)."}
        ],
        "by_ticker": {
            "TGYM:XMIL": {
                "name": "Technogym S.p.A.",
                "market": "Borsa Italiana (Euronext Milan)",
                "has_updates": True,
                "sec_filings": [],
                "news": [
                    {
                        "source": "Borsa IT (Il Sole 24 Ore)",
                        "title": "Technogym approva bilancio semestrale record oltre 1 miliardo",
                        "url": "https://www.ilsole24ore.com",
                        "published_at": "2026-08-27 10:30 UTC"
                    }
                ]
            },
            "CRM": {
                "name": "Salesforce Inc.",
                "market": "NYSE",
                "has_updates": True,
                "sec_filings": [
                    {
                        "title": "8-K: Formulario informativo straordinario",
                        "url": "https://www.sec.gov",
                        "published_at": "2026-08-27 12:00 UTC"
                    }
                ],
                "news": [
                    {
                        "source": "Finviz (Bloomberg)",
                        "title": "Salesforce expands cloud AI integrations with key enterprise clients",
                        "url": "https://www.bloomberg.com",
                        "published_at": "2026-08-27 14:15 UTC"
                    }
                ]
            },
            "SLDP": {
                "name": "Solid Power Inc.",
                "market": "NASDAQ",
                "has_updates": False,
                "sec_filings": [],
                "news": []
            }
        }
    }

    html = generate_html_email(sample_data)
    test_html_path = config.REPORTS_DIR / "test_preview_email.html"
    test_html_path.parent.mkdir(parents=True, exist_ok=True)
    with open(test_html_path, "w", encoding="utf-8") as f:
        f.write(html)
    console.print(f"[bold green]Anteprima HTML generata con successo in:[/bold green] [cyan]{test_html_path}[/cyan]")
