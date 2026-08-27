"""
Modulo di Scoring e Selezione Top Articoli per l'Email Digest.
Configurato secondo le preferenze dell'investitore:
- Tier 0 (+40 punti): Esclusivamente Seeking Alpha (analisi fondamentale e tesi d'investimento)
- Tier 1 (+25 punti): Grandi testate di riferimento (Reuters, Bloomberg, WSJ, Barron's, MarketWatch, CNBC, Financial Times)
- Tier 2 (+15 punti): Testate economiche e analisi (Investor's Business Daily, GuruFocus, Forbes, Fortune, Quartz)
- Rilevanza Evento (+15 punti): Parole chiave di eventi societari materiali (Earnings, Results, Revenue, Guidance, Acquisizioni, Partnership, Dividendi, CEO)
- Penalità Clickbait (-20 punti): Titoli con pattern speculativi o template automatici
- Esclusione Filings SEC e Comunicati Borsa Italiana (non desiderati nell'email digest)
- Selezione: Massimo 2 articoli top per ticker, rigorosamente deduplicati per tema.
"""

import re
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional

TIER_1_SOURCES = [
    "reuters", "bloomberg", "the wall street journal", "wsj",
    "barron's", "barrons", "marketwatch", "cnbc", "financial times", "ft"
]

TIER_2_SOURCES = [
    "investor's business daily", "ibd", "gurufocus", "forbes", "fortune", "quartz"
]

CLICKBAIT_PATTERNS = [
    r"should you buy",
    r"why is .* down",
    r"why .* stock (plunged|sank|dropped)",
    r"forget .*, buy",
    r"\b[0-9]+\s+reasons\b",
    r"\b[0-9]+\s+stocks to\b",
    r"is it too late to buy",
    r"options alert",
    r"here's why",
    r"what's next for"
]

BOT_PATTERNS = [
    r"southbound capital",
    r"northbound capital",
    r"capital flows",
    r"short selling turnover",
    r"deposited shares for",
    r"peer comparison",
    r"class action lawsuit",
    r"investors urged to contact",
    r"reminds .* investors",
    r"lead plaintiff deadline"
]

MATERIAL_KEYWORDS = [
    "earnings", "quarterly", "results", "guidance", "revenue", "profit",
    "ebitda", "bilancio", "trimestrale", "utile", "acquire", "acquisition",
    "merger", "partnership", "deal", "contract", "accordo", "ceo", "cfo",
    "dividend", "dividendo", "buyback", "share repurchase"
]


def score_article(item: Dict, ticker: str = "", company_name: str = "") -> float:
    """Calcola il punteggio qualitativo per un singolo articolo."""
    source_lower = item.get("source", "").lower()
    title_lower = item.get("title", "").lower()
    category = item.get("category", "")

    # 1. Esclusione categorica di Filing SEC e Comunicati Borsa Italiana
    if category == "filing" or "sec edgar" in source_lower or "borsa it" in source_lower or "sdir" in source_lower:
        return -999.0

    # 2. Esclusione categorica di bollettini statistici giornalieri di borsa, bot e avvisi legali spam
    for bp in BOT_PATTERNS:
        if re.search(bp, title_lower):
            return -999.0

    # Controllo di coerenza per ticker brevi (es. JD.com vs JD Sports / JD Vance / JD Power)
    if ticker.upper() == "JD":
        if any(bad in title_lower for bad in ["jd sports", "jd vance", "jd power", "jd cable", "lse:jd", "al pacino"]):
            return -999.0
        if not any(good in title_lower for good in ["jd.com", "jingdong", "$jd", "nasdaq:jd", "(jd)", "jd (jd)", "china", "ecommerce", "e-commerce", "logistics"]):
            return -999.0

    # Controllo di coerenza per ticker brevi (es. LandBridge vs LB Foster)
    if ticker.upper() in ["LB", "SE", "IT"] and company_name:
        main_word = company_name.split()[0].lower()
        if main_word not in title_lower and f"${ticker.lower()}" not in title_lower:
            return -999.0

    score = 0.0

    # 1. Tier 0: Seeking Alpha (+40 punti esclusivo)
    if "seeking alpha" in source_lower:
        score += 40.0

    # 2. Tier 1: Grandi Testate di Riferimento (+25 punti)
    elif any(src in source_lower for src in TIER_1_SOURCES):
        score += 25.0

    # 3. Tier 2: Analisi Fondamentale e Portali Finanziari (+15 punti)
    elif any(src in source_lower for src in TIER_2_SOURCES):
        score += 15.0

    # 4. Rilevanza Evento Societario (+15 punti)
    if any(kw in title_lower for kw in MATERIAL_KEYWORDS):
        score += 15.0

    # 5. Penalità Clickbait (-20 punti)
    for p in CLICKBAIT_PATTERNS:
        if re.search(p, title_lower):
            score -= 20.0
            break

    # 6. Bonus Freschezza (notizie delle ultime 12 ore: +5 punti)
    dt = item.get("published_dt")
    if dt:
        try:
            if datetime.now(timezone.utc) - dt <= timedelta(hours=12):
                score += 5.0
        except Exception:
            pass

    return score


def select_top_articles_for_ticker(
    items: List[Dict],
    ticker: str,
    company_name: str = "",
    max_items: int = 2
) -> List[Dict]:
    """
    Filtra, valuta e restituisce al massimo i migliori `max_items` articoli (default: 2)
    garantendo diversità tematica e scartando ripetizioni.
    """
    scored = []
    for it in items:
        s = score_article(it, ticker=ticker, company_name=company_name)
        if s > -50.0:  # Scarta elementi esclusi o clickbait estremo
            scored.append((s, it))

    # Ordina per punteggio decrescente e secondariamente per data più recente
    scored.sort(
        key=lambda x: (
            x[0],
            x[1].get("published_dt") or datetime.min.replace(tzinfo=timezone.utc)
        ),
        reverse=True
    )

    selected = []
    seen_signatures = []

    for s, it in scored:
        title = it.get("title", "").strip()
        # Genera una firma tematica pulita per evitare due articoli identici sullo stesso annuncio
        sig = "".join(c for c in title.lower() if c.isalnum())[:32]

        if any(sig in prev or prev in sig for prev in seen_signatures):
            continue

        item_with_score = dict(it)
        item_with_score["quality_score"] = s
        selected.append(item_with_score)
        seen_signatures.append(sig)

        if len(selected) >= max_items:
            break

    return selected
