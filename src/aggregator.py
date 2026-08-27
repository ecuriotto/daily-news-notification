"""
Modulo di aggregazione, normalizzazione e deduplicazione delle informazioni raccolte da VIC e dal web.
Include lo stato di validazione e la tracciatura dei warning per singolo ticker.
"""

from typing import List, Dict, Set, Optional


def deduplicate_news(items: List[Dict]) -> List[Dict]:
    """
    Rimuove notizie duplicate o quasi-identiche per lo stesso ticker
    basandosi su URL e similarità dei titoli.
    """
    seen_urls: Set[str] = set()
    seen_titles: Set[str] = set()
    deduped: List[Dict] = []

    for item in items:
        url = item.get("url", "").strip()
        title = item.get("title", "").strip().lower()

        # Normalizzazione titolo per matching semplice
        simple_title = "".join(ch for ch in title if ch.isalnum() or ch.isspace())[:60]

        if url and url in seen_urls:
            continue
        if simple_title and simple_title in seen_titles:
            continue

        if url:
            seen_urls.add(url)
        if simple_title:
            seen_titles.add(simple_title)

        deduped.append(item)

    return deduped


def aggregate_results(
    watchlist: List[Dict],
    vic_ideas: List[Dict],
    vic_messages: List[Dict],
    web_news: Dict[str, List[Dict]],
    validation_report: Optional[Dict] = None
) -> Dict:
    """
    Raggruppa e organizza tutti i dati raccolti per singolo ticker in modo pulito,
    arricchendoli con metadati di mercato, stato di validazione ed eventuali avvisi (warnings).
    """
    v_report = validation_report or {}
    v_by_ticker = v_report.get("by_ticker", {})

    aggregated = {
        "summary": {
            "total_tickers": len(watchlist),
            "tickers_with_updates": 0,
            "total_vic_ideas": len(vic_ideas),
            "total_vic_messages": len(vic_messages),
            "total_web_news": sum(len(items) for items in web_news.values()),
            "total_warnings": len(v_report.get("warnings", []))
        },
        "warnings": v_report.get("warnings", []),
        "by_ticker": {}
    }

    # Inizializza la struttura per ogni ticker abilitato
    for item in watchlist:
        if not item.get("enabled", True):
            continue
        ticker = item["ticker"]
        name = item.get("name", "")
        meta = item.get("metadata", {})
        diag = v_by_ticker.get(ticker, {})

        ticker_vic_ideas = [i for i in vic_ideas if i.get("ticker") == ticker]
        ticker_vic_msgs = [m for m in vic_messages if m.get("ticker") == ticker]
        raw_news = web_news.get(ticker, [])

        # Separa SEC filings da notizie generali di mercato
        sec_filings = [n for n in raw_news if n.get("category") == "filing"]
        general_news = [n for n in raw_news if n.get("category") != "filing"]

        # Deduplica
        deduped_filings = deduplicate_news(sec_filings)
        deduped_news = deduplicate_news(general_news)

        has_updates = bool(ticker_vic_ideas or ticker_vic_msgs or deduped_filings or deduped_news)
        if has_updates:
            aggregated["summary"]["tickers_with_updates"] += 1

        aggregated["by_ticker"][ticker] = {
            "name": name,
            "market": meta.get("market", diag.get("market", "-")),
            "yahoo_symbol": meta.get("yahoo_symbol", diag.get("yahoo_symbol", ticker)),
            "is_sec_eligible": meta.get("is_sec_eligible", diag.get("is_sec_eligible", True)),
            "has_updates": has_updates,
            "vic_status": diag.get("vic_status", "-"),
            "warnings": diag.get("warnings", []),
            "vic_ideas": ticker_vic_ideas,
            "vic_messages": ticker_vic_msgs,
            "sec_filings": deduped_filings,
            "news": deduped_news
        }

    return aggregated
