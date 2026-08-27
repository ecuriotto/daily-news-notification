"""
Modulo di validazione preventiva e health check per la Watchlist.
Verifica la riconoscibilità dei ticker e delle aziende su:
1. Value Investors Club (tramite query di ricerca nativa JSON)
2. SEC EDGAR (titoli USA / ADR vs esenzione titoli esteri)
3. Yahoo Finance & Google News (risoluzione simboli e query)
Genera avvisi (warnings) chiari per ticker non censiti, esteri o ambigui.
"""

import requests
from typing import List, Dict, Tuple
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

import config

console = Console()


from concurrent.futures import ThreadPoolExecutor, as_completed

session = requests.Session()
session.headers.update({"User-Agent": config.BROWSER_USER_AGENT})


def check_single_vic_query(query: str) -> List[Dict]:
    """Interroga l'API di ricerca di VIC per una singola query con gestione timeout ed errori."""
    if not query or len(query) < 2:
        return []
    try:
        r = session.post(
            "https://valueinvestorsclub.com/search",
            data={"query": query, "tab": "ideas"},
            timeout=3
        )
        if r.status_code == 200:
            data = r.json()
            return data.get("result", [])
    except Exception:
        # Timeout o connessione rifiutata/chiusa
        pass
    return []


def check_vic_presence(vic_symbols: List[str]) -> Tuple[int, str, List[Dict]]:
    """
    Verifica la presenza su VIC interrogando i simboli candidati.
    Se trova idee con il primo simbolo, evita query ridondanti.
    """
    seen_ids = set()
    found_ideas = []
    latest_date = ""

    for sym in vic_symbols:
        results = check_single_vic_query(sym)
        for item in results:
            idea_id = item.get("idea_id")
            if idea_id and idea_id not in seen_ids:
                seen_ids.add(idea_id)
                found_ideas.append(item)
                if not latest_date and item.get("add_date"):
                    latest_date = item.get("add_date")
        # Se abbiamo già trovato idee pertinenti, non è necessario interrogare ulteriori alias
        if found_ideas:
            break

    return len(found_ideas), latest_date, found_ideas


def validate_single_ticker(item: Dict[str, any], check_vic: bool = True) -> Tuple[str, Dict[str, any], List[Dict[str, any]]]:
    """Valida un singolo ticker e restituisce (ticker, ticker_status, warnings)."""
    ticker = item["ticker"]
    name = item.get("name", "")
    meta = item.get("metadata", {})
    yahoo_sym = meta.get("yahoo_symbol", ticker)
    is_sec = meta.get("is_sec_eligible", True)
    vic_syms = meta.get("vic_symbols", [ticker])
    market = meta.get("market", "Unknown")

    ticker_warnings = []
    global_warnings = []
    ticker_status = {
        "name": name,
        "market": market,
        "yahoo_symbol": yahoo_sym,
        "is_sec_eligible": is_sec,
        "vic_ideas_count": 0,
        "vic_latest_date": "",
        "vic_status": "Non Verificato",
        "sec_status": "Abilitato" if is_sec else "Non Applicabile (Estero)",
        "warnings": []
    }

    # 1. Verifica Value Investors Club
    if check_vic:
        n_ideas, last_date, ideas = check_vic_presence(vic_syms)
        ticker_status["vic_ideas_count"] = n_ideas
        ticker_status["vic_latest_date"] = last_date

        if n_ideas > 0:
            ticker_status["vic_status"] = f"OK ({n_ideas} idee, ult. {last_date})"
        else:
            ticker_status["vic_status"] = "Nessuna idea"
            w = f"Value Investors Club: Nessuna idea trovata per '{ticker}' ({name}). Azienda poco diffusa o mai analizzata su VIC."
            ticker_warnings.append(w)
            global_warnings.append({"ticker": ticker, "type": "VIC_MISSING", "message": w})

    # 2. Verifica Titoli Esteri / SEC EDGAR
    if not is_sec:
        if ticker in ["BEC:XMIL", "BFIT", "700", "DNP", "APR"]:
            w_sec = f"SEC EDGAR: Titolo quotato su borsa estera ({market}). Nessun filing 8-K/10-K atteso; monitoraggio focalizzato su Web News e VIC."
            ticker_warnings.append(w_sec)
            global_warnings.append({"ticker": ticker, "type": "FOREIGN_SEC_EXEMPT", "message": w_sec})

    # 3. Verifica Ambiguità Ticker e Mappatura Yahoo
    if ticker == "9988":
        w_map = "Mappatura VIC: '9988' è quotato a Hong Kong; su VIC è censito storicamente sotto il simbolo 'BABA' (Alibaba)."
        ticker_warnings.append(w_map)
        global_warnings.append({"ticker": ticker, "type": "MAPPING_NOTE", "message": w_map})
    elif ticker == "700":
        w_map = "Mappatura: Codice numerico '700' normalizzato in '0700.HK' per Yahoo Finance e associato a 'Tencent' per le news."
        ticker_warnings.append(w_map)
        global_warnings.append({"ticker": ticker, "type": "MAPPING_NOTE", "message": w_map})
    elif ticker == "DNP":
        w_amb = "Disambiguazione: 'DNP' risolto come Dino Polska (Polonia, WSE: DNP.WA). Negli USA corrisponde invece a DNP Select Income Fund."
        ticker_warnings.append(w_amb)
        global_warnings.append({"ticker": ticker, "type": "AMBIGUITY", "message": w_amb})
    elif ticker == "APR":
        w_amb = "Disambiguazione: 'APR' risolto come Auto Partner (Polonia, WSE: APR.WA). Negli USA corrisponde a contratti opzioni SOFR / Aprea."
        ticker_warnings.append(w_amb)
        global_warnings.append({"ticker": ticker, "type": "AMBIGUITY", "message": w_amb})
    elif ":" in ticker:
        w_mic = f"Formato Borsa: Rilevato suffisso MIC in '{ticker}'. Mappato su Yahoo Finance come '{yahoo_sym}'."
        ticker_warnings.append(w_mic)
        global_warnings.append({"ticker": ticker, "type": "MIC_MAPPING", "message": w_mic})

    ticker_status["warnings"] = ticker_warnings
    return ticker, ticker_status, global_warnings


def is_vic_reachable() -> bool:
    """Verifica rapida preliminare della raggiungibilità di VIC per evitare timeout multipli."""
    try:
        r = session.get("https://valueinvestorsclub.com", timeout=(2.0, 3.0))
        return r.status_code < 500
    except Exception:
        return False


def validate_watchlist(watchlist: List[Dict[str, any]], check_vic: bool = False) -> Dict[str, any]:
    """
    Esegue la scansione diagnostica concorrente di tutti i ticker della watchlist.
    Rileva incompatibilità di mercato, assenza su VIC (se richiesto) e potenziale ambiguità.
    """
    report = {
        "summary": {
            "total_tickers": len(watchlist),
            "vic_checked": check_vic,
            "vic_recognized": 0,
            "vic_missing": 0,
            "foreign_tickers": 0,
            "total_warnings": 0
        },
        "by_ticker": {},
        "warnings": []
    }

    # Verifica preliminare raggiungibilità VIC solo se esplicitamente richiesto
    vic_online = is_vic_reachable() if check_vic else False
    if check_vic and not vic_online:
        w_vic_down = "Value Investors Club: Connessione temporaneamente non disponibile o in timeout (firewall/rate-limit). I controlli proseguono per Web News e SEC."
        report["warnings"].append({"ticker": "VIC", "type": "VIC_OFFLINE", "message": w_vic_down})

    # Esecuzione parallela con ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=6) as executor:
        future_to_item = {executor.submit(validate_single_ticker, item, check_vic and vic_online): item for item in watchlist}
        for future in as_completed(future_to_item):
            ticker, t_status, g_warnings = future.result()
            if not check_vic:
                t_status["vic_status"] = "Escluso (V1)"
            elif not vic_online:
                t_status["vic_status"] = "Server non raggiungibile"

            report["by_ticker"][ticker] = t_status
            report["warnings"].extend(g_warnings)

            if t_status.get("vic_ideas_count", 0) > 0:
                report["summary"]["vic_recognized"] += 1
            elif check_vic and vic_online:
                report["summary"]["vic_missing"] += 1

            if not t_status.get("is_sec_eligible"):
                report["summary"]["foreign_tickers"] += 1

    report["summary"]["total_warnings"] = len(report["warnings"])
    report["summary"]["vic_online"] = vic_online
    return report


def print_validation_summary(validation_report: Dict[str, any]):
    """Stampa a terminale una vista compatta e dettagliata della diagnosi ticker."""
    summary = validation_report.get("summary", {})
    by_ticker = validation_report.get("by_ticker", {})
    warnings = validation_report.get("warnings", [])

    warn_color = "bold red" if warnings else "bold green"
    vic_checked = summary.get("vic_checked", False)
    vic_online = summary.get("vic_online", False)

    if vic_checked:
        if vic_online:
            vic_summary_text = (
                f"• Con idee su VIC:  [bold green]{summary.get('vic_recognized', 0)}[/bold green]\n"
                f"• Senza idee su VIC: [bold yellow]{summary.get('vic_missing', 0)}[/bold yellow]"
            )
        else:
            vic_summary_text = "• Controllo VIC:    [bold yellow]Non disponibile (Server in timeout/offline)[/bold yellow]"
    else:
        vic_summary_text = "• Controllo VIC:    [dim]Escluso (Modalità V1 Veloce)[/dim]"

    console.print("\n")
    console.print(
        Panel.fit(
            f"[bold cyan]Diagnosi & Compatibilità Watchlist[/bold cyan]\n"
            f"• Ticker esaminati: [bold]{summary.get('total_tickers')}[/bold]\n"
            f"{vic_summary_text}\n"
            f"• Titoli non-USA:   [bold magenta]{summary.get('foreign_tickers')}[/bold magenta]\n"
            f"• Avvisi totali:    [{warn_color}]{len(warnings)}[/{warn_color}]",
            title="Risultato Validazione Ticker",
            border_style="cyan"
        )
    )

    table = Table(title="Stato Riconoscimento Ticker per Canale", header_style="bold magenta")
    table.add_column("Ticker", style="cyan", no_wrap=True)
    table.add_column("Azienda Riconosciuta", style="white")
    table.add_column("Borsa / Mercato", style="dim")
    table.add_column("Simbolo Yahoo", style="blue")
    table.add_column("Filing SEC", justify="center")
    table.add_column("Presenza VIC", justify="center")
    table.add_column("Avvisi", style="yellow")

    for ticker, info in by_ticker.items():
        n_warn = len(info.get("warnings", []))
        warn_badge = f"[bold yellow]⚠️ {n_warn}[/bold yellow]" if n_warn else "[dim]OK[/dim]"

        vic_str = info.get("vic_status", "-")
        if "OK" in vic_str:
            vic_badge = f"[green]{vic_str}[/green]"
        elif "Nessuna" in vic_str:
            vic_badge = f"[yellow]{vic_str}[/yellow]"
        else:
            vic_badge = f"[dim]{vic_str}[/dim]"

        sec_badge = "[green]Attivo[/green]" if info.get("is_sec_eligible") else "[dim]N/A (Estero)[/dim]"

        table.add_row(
            ticker,
            info.get("name", "-")[:26],
            info.get("market", "-")[:22],
            info.get("yahoo_symbol", "-"),
            sec_badge,
            vic_badge,
            warn_badge
        )

    console.print(table)

    # Se ci sono avvisi critici o di assenza VIC, mostra un pannello di alert dedicato
    if warnings:
        console.print("\n")
        warn_lines = []
        for w in warnings:
            warn_lines.append(f"• [bold yellow]{w['ticker']}[/bold yellow]: {w['message']}")

        console.print(
            Panel(
                "\n".join(warn_lines),
                title="[bold yellow]⚠️ Dettaglio Avvisi per Aziende Meno Popolari o Titoli Speciali[/bold yellow]",
                border_style="yellow"
            )
        )
    console.print("\n")
