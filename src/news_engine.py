"""
Motore di raccolta notizie finanziarie e comunicati ufficiali per i ticker in watchlist.
Fonti integrate:
1. SEC EDGAR (Filings ufficiali: 8-K, 10-Q, 10-K, Form 4) - solo per titoli USA/ADR
2. Finviz News Feed (Aggregatore filtrato per ticker da MarketWatch, Bloomberg, Reuters, PR Newswire)
3. Yahoo Finance RSS (con risoluzione suffissi internazionali .MI, .HK, .AS, .WA)
4. Google News Financial RSS (con encoding URL, combinazione ticker+nome e fallback regionale)
5. Seeking Alpha RSS (Titoli e analisi fondamentali, protetto contro sfide bot)
6. Comunicati Societari Borsa Italiana / Circuiti SDIR (per titoli italiani come BEC e TGYM)
"""

import re
import time
import email.utils
import urllib.parse
from datetime import datetime, timezone, timedelta
import requests
import feedparser
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

import config


def parse_datetime(date_str: str) -> Optional[datetime]:
    """Tenta di convertire diversi formati di data RSS/Atom in un oggetto datetime UTC."""
    if not date_str:
        return None
    try:
        parsed_tuple = email.utils.parsedate_to_datetime(date_str)
        if parsed_tuple:
            return parsed_tuple.astimezone(timezone.utc)
    except Exception:
        pass

    try:
        clean_str = date_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass

    return None


def clean_html(text: str) -> str:
    """Rimuove tag HTML e normalizza gli spazi."""
    if not text:
        return ""
    soup = BeautifulSoup(text, "html.parser")
    cleaned = soup.get_text(separator=" ", strip=True)
    return " ".join(cleaned.split())


def is_within_lookback(dt: Optional[datetime], lookback_hours: int) -> bool:
    """Verifica se la data rientra nella finestra temporale richiesta."""
    if not dt:
        return True
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    return dt >= cutoff


def is_title_relevant(title: str, ticker: str, company_name: str = "") -> bool:
    """
    Verifica che il titolo citi esplicitamente il ticker o il nome/brand dell'azienda,
    filtrando le notizie generiche di mercato (es. wrap-up indici o notizie su altri titoli).
    """
    if not title:
        return False
    t_lower = title.lower()
    clean_sym = ticker.split(":")[0].strip().lower()

    # Disambiguazione specifica per JD (JD.com vs JD Sports / JD Vance / JD Power)
    if clean_sym == "jd":
        if any(bad in t_lower for bad in ["jd sports", "jd vance", "jd power", "jd cable", "lse:jd", "al pacino"]):
            return False
        if any(good in t_lower for good in ["jd.com", "jingdong", "$jd", "nasdaq:jd", "(jd)", "jd (jd)"]):
            return True
        if re.search(r"\bjd\b", t_lower) and any(k in t_lower for k in ["china", "ecommerce", "e-commerce", "logistics", "shares", "stock", "retail", "tech", "earnings"]):
            return True
        return False

    # Disambiguazione specifica per LB (LandBridge vs LB Foster)
    if clean_sym == "lb":
        if "foster" in t_lower:
            return False
        if any(good in t_lower for good in ["landbridge", "$lb", "nasdaq:lb", "nyse:lb", "(lb)"]):
            return True
        return False

    # Riconoscimento del simbolo (es. "CRM", "$CRM") come parola isolata
    if clean_sym not in ["se", "it", "or", "in", "on", "as", "to"]:
        if re.search(r"(^|[\s\(\$\[\.,/\-])" + re.escape(clean_sym) + r"([\s\)\],/\.\-]|$)", t_lower):
            return True

    # Riconoscimento del nome/brand aziendale
    if company_name:
        clean_name = company_name
        for sfx in [
            "Holdings Ltd", "Holding Ltd", "Holdings", "Holding", "Group Holding Ltd", "Group",
            "Company LLC", "Company", "Co., Ltd.", "Co. Ltd.", "S.p.A.", "N.V.", "S.A.", "Inc.", "LLC", "Ltd", "Corp.",
            "(ADR)", "ADR"
        ]:
            clean_name = clean_name.replace(sfx, "").strip(",. ")

        words = [w.lower().strip(",.") for w in clean_name.split() if len(w) >= 3]
        for w in words:
            if w in t_lower:
                return True

    return False


# ----------------------------------------------------------------------
# 1. SEC EDGAR (Ufficiali USA / ADR)
# ----------------------------------------------------------------------
def fetch_sec_filings(ticker: str, lookback_hours: int = 24, is_sec_eligible: bool = True) -> List[Dict]:
    """
    Recupera i filing recenti della SEC (EDGAR) per il ticker specificato.
    Salta la richiesta se il titolo è quotato esclusivamente all'estero (non-USA).
    """
    if not is_sec_eligible:
        return []

    sec_symbol = ticker.split(":")[0].strip()
    if sec_symbol == "9988":
        sec_symbol = "BABA"

    items = []
    url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={sec_symbol}&type=&dateb=&owner=exclude&start=0&count=15&output=atom"
    headers = {
        "User-Agent": config.SEC_USER_AGENT,
        "Accept": "application/atom+xml,application/xml,text/xml"
    }

    try:
        response = requests.get(url, headers=headers, timeout=8)
        if response.status_code != 200:
            return items

        feed = feedparser.parse(response.content)
        for entry in feed.entries:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            updated_str = entry.get("updated", "")
            summary = clean_html(entry.get("summary", ""))

            dt = parse_datetime(updated_str)
            if not is_within_lookback(dt, lookback_hours):
                continue

            items.append({
                "ticker": ticker,
                "source": "SEC EDGAR",
                "category": "filing",
                "title": title,
                "url": link,
                "published_at": dt.strftime("%Y-%m-%d %H:%M UTC") if dt else updated_str,
                "published_dt": dt,
                "summary": summary[:250] + "..." if len(summary) > 250 else summary
            })
    except Exception:
        pass

    return items


# ----------------------------------------------------------------------
# 2. Finviz News Aggregator (USA / ADR / Ticker Principali)
# ----------------------------------------------------------------------
def fetch_finviz_news(
    ticker: str,
    company_name: str = "",
    is_sec_eligible: bool = True,
    lookback_hours: int = 24
) -> List[Dict]:
    """
    Estrae notizie aggregate da Finviz per ticker compatibili (USA/ADR).
    Filtra rigorosamente i titoli per scartare articoli generici o di altre aziende.
    """
    clean_sym = ticker.split(":")[0].strip()
    if clean_sym == "9988":
        clean_sym = "BABA"

    # Finviz indicizza prevalentemente simboli quotati su mercati USA / ADR
    if not is_sec_eligible and not clean_sym.isalpha():
        return []

    items = []
    url = f"https://finviz.com/quote.ashx?t={clean_sym}"
    headers = {"User-Agent": config.BROWSER_USER_AGENT}

    try:
        response = requests.get(url, headers=headers, timeout=7)
        if response.status_code != 200:
            return items

        soup = BeautifulSoup(response.text, "html.parser")
        table = soup.find("table", id="news-table")
        if not table:
            return items

        current_date_str = datetime.now(timezone.utc).strftime("%b-%d-%y")
        rows = table.find_all("tr")

        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

        for row in rows[:35]:
            tds = row.find_all("td")
            if len(tds) < 2:
                continue

            date_raw = tds[0].text.strip()
            link_tag = tds[1].find("a")
            if not link_tag:
                continue

            title = link_tag.text.strip()
            href = link_tag.get("href", "").strip()
            source_span = tds[1].find("span")
            source_name = source_span.text.strip("()") if source_span else "Finviz"

            # Filtro di pertinenza: scarta articoli generici di borsa che non menzionano l'azienda o il ticker
            if not is_title_relevant(title, ticker, company_name=company_name):
                continue

            # Parsing data Finviz ("Today 04:24PM" o "Aug-27-26 04:24PM" o solo "03:50PM")
            dt = None
            try:
                if " " in date_raw:
                    d_part, t_part = date_raw.split(" ", 1)
                    if d_part.lower() == "today":
                        current_date_str = datetime.now(timezone.utc).strftime("%b-%d-%y")
                    else:
                        current_date_str = d_part
                    time_part = t_part
                else:
                    time_part = date_raw

                dt_str = f"{current_date_str} {time_part}"
                dt = datetime.strptime(dt_str, "%b-%d-%y %I:%M%p").replace(tzinfo=timezone.utc)
            except Exception:
                pass

            if dt and dt < cutoff:
                continue

            items.append({
                "ticker": ticker,
                "source": f"Finviz ({source_name})",
                "category": "news",
                "title": title,
                "url": href,
                "published_at": dt.strftime("%Y-%m-%d %H:%M UTC") if dt else date_raw,
                "published_dt": dt,
                "summary": ""
            })
    except Exception:
        pass

    return items


# ----------------------------------------------------------------------
# 3. Yahoo Finance RSS
# ----------------------------------------------------------------------
def fetch_yahoo_finance_news(
    ticker: str,
    company_name: str = "",
    yahoo_symbol: Optional[str] = None,
    lookback_hours: int = 24
) -> List[Dict]:
    """
    Recupera le ultime notizie da Yahoo Finance RSS per il simbolo specificato.
    Utilizza il simbolo normalizzato (es. BEC.MI, 0700.HK, BFIT.AS, TGYM.MI).
    """
    sym = yahoo_symbol or ticker
    items = []
    url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={sym}&region=US&lang=en-US"
    headers = {"User-Agent": config.BROWSER_USER_AGENT}

    try:
        response = requests.get(url, headers=headers, timeout=6)
        if response.status_code != 200:
            return items

        feed = feedparser.parse(response.content)
        for entry in feed.entries:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            pub_date = entry.get("published", "")
            summary = clean_html(entry.get("summary", ""))

            # Filtro di pertinenza
            if not is_title_relevant(title, ticker, company_name=company_name):
                continue

            dt = parse_datetime(pub_date)
            if not is_within_lookback(dt, lookback_hours):
                continue

            author = (entry.get("author") or entry.get("creator") or "").strip()
            items.append({
                "ticker": ticker,
                "source": "Yahoo Finance",
                "category": "news",
                "title": title,
                "url": link,
                "author": author,
                "published_at": dt.strftime("%Y-%m-%d %H:%M UTC") if dt else pub_date,
                "published_dt": dt,
                "summary": summary[:280] + "..." if len(summary) > 280 else summary
            })
    except Exception:
        pass

    return items


# ----------------------------------------------------------------------
# 4. Google News Financial (Rassegna Globale)
# ----------------------------------------------------------------------
def fetch_google_news(ticker: str, company_name: str = "", yahoo_symbol: str = "", lookback_hours: int = 24) -> List[Dict]:
    """
    Recupera rassegna stampa finanziaria da Google News RSS.
    Costruisce query mirate per evitare falsi positivi.
    """
    items = []
    seen_urls = set()

    clean_sym = ticker.split(":")[0] if ":" in ticker else ticker
    short_company = company_name
    for sfx in [
        "Holdings Ltd", "Holding Ltd", "Holdings", "Holding", "Group Holding Ltd", "Group",
        "Company LLC", "Company", "Co., Ltd.", "Co. Ltd.", "S.p.A.", "N.V.", "S.A.", "Inc.", "LLC", "Ltd", "Corp."
    ]:
        if short_company.endswith(sfx):
            short_company = short_company[:-len(sfx)].strip(",. ")

    if short_company:
        if clean_sym.isdigit():
            query = f'"{short_company}" stock'
        elif ":" in ticker or clean_sym in ["BEC", "BFIT", "DNP", "APR", "TGYM"]:
            query = f'("{short_company}" OR "{yahoo_symbol or clean_sym}")'
        else:
            query = f'({clean_sym} OR "{short_company}") stock'
    else:
        query = f'{clean_sym} stock'

    lookback_days_str = f"when:{max(1, lookback_hours // 24)}d"
    encoded_q = urllib.parse.quote_plus(f"{query} {lookback_days_str}")

    endpoints = [
        f"https://news.google.com/rss/search?q={encoded_q}&hl=en-US&gl=US&ceid=US:en"
    ]

    headers = {"User-Agent": config.BROWSER_USER_AGENT}

    for ep_url in endpoints:
        try:
            response = requests.get(ep_url, headers=headers, timeout=8)
            if response.status_code != 200:
                continue

            feed = feedparser.parse(response.content)
            for entry in feed.entries:
                raw_title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                pub_date = entry.get("published", "")

                if not link or link in seen_urls:
                    continue
                seen_urls.add(link)

                source_name = "Google News"
                title = raw_title
                if " - " in raw_title:
                    parts = raw_title.rsplit(" - ", 1)
                    title = parts[0].strip()
                    source_name = f"Web ({parts[1].strip()})"

                # Filtro di precisione per B&C Speakers per evitare articoli sportivi su Serie B
                if clean_sym == "BEC" and not any(k in title.lower() for k in ["speaker", "b&c", "bec"]):
                    continue

                # Filtro di pertinenza (scarta articoli che non menzionano il ticker o l'azienda)
                if not is_title_relevant(title, ticker, company_name=company_name):
                    continue

                dt = parse_datetime(pub_date)
                if not is_within_lookback(dt, lookback_hours):
                    continue

                items.append({
                    "ticker": ticker,
                    "source": source_name,
                    "category": "news",
                    "title": title,
                    "url": link,
                    "published_at": dt.strftime("%Y-%m-%d %H:%M UTC") if dt else pub_date,
                    "published_dt": dt,
                    "summary": ""
                })
        except Exception:
            pass

    return items


# ----------------------------------------------------------------------
# 5. Seeking Alpha (Solo Titoli & Link Analisi - Protetto da Bot Challenge)
# ----------------------------------------------------------------------
def fetch_seeking_alpha_news(ticker: str, is_sec_eligible: bool = True, lookback_hours: int = 24) -> List[Dict]:
    """
    Recupera titoli di analisi da Seeking Alpha RSS per i titoli compatibili.
    Mostra rigorosamente solo titolo e URL per evitare blocchi bot o payload protetti.
    """
    clean_ticker = ticker.split(":")[0]
    if clean_ticker == "9988":
        clean_ticker = "BABA"

    if not is_sec_eligible and not clean_ticker.isalpha():
        return []

    items = []
    url = f"https://seekingalpha.com/api/sa/combined/{clean_ticker}.xml"
    headers = {"User-Agent": config.BROWSER_USER_AGENT}

    try:
        response = requests.get(url, headers=headers, timeout=6)
        if response.status_code != 200:
            return items

        feed = feedparser.parse(response.content)
        for entry in feed.entries:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            pub_date = entry.get("published", "")

            dt = parse_datetime(pub_date)
            if not is_within_lookback(dt, lookback_hours):
                continue

            author = (entry.get("sa_author_name") or entry.get("author") or "").strip()
            items.append({
                "ticker": ticker,
                "source": "Seeking Alpha",
                "category": "analysis",
                "title": title,
                "url": link,
                "author": author,
                "published_at": dt.strftime("%Y-%m-%d %H:%M UTC") if dt else pub_date,
                "published_dt": dt,
                "summary": ""  # Omette volutamente il testo per evitare bot challenge
            })
    except Exception:
        pass

    return items


# ----------------------------------------------------------------------
# 6. Comunicati Ufficiali Borsa Italiana / SDIR (per Titoli Italiani)
# ----------------------------------------------------------------------
def fetch_italian_corporate_news(ticker: str, company_name: str, lookback_hours: int = 24) -> List[Dict]:
    """
    Canale prioritario per titoli quotati su Borsa Italiana (es. BEC:xmil, TGYM:xmil).
    Interroga i comunicati societari ufficiali, trimestrali, bilanci e delibere CDA.
    """
    clean_sym = ticker.split(":")[0]
    if ":" not in ticker and clean_sym not in ["BEC", "TGYM"]:
        return []

    name = company_name or clean_sym
    clean_name = name.replace("S.p.A.", "").replace("SpA", "").strip(",. ")

    items = []
    lookback_days = max(1, lookback_hours // 24)
    query = f'"{clean_name}" (comunicato OR bilancio OR trimestrale OR ricavi OR dividendo OR CDA OR assemblea) when:{lookback_days}d'
    encoded_q = urllib.parse.quote_plus(query)
    url = f"https://news.google.com/rss/search?q={encoded_q}&hl=it&gl=IT&ceid=IT:it"

    headers = {"User-Agent": config.BROWSER_USER_AGENT}
    try:
        response = requests.get(url, headers=headers, timeout=6)
        if response.status_code != 200:
            return items

        feed = feedparser.parse(response.content)
        for entry in feed.entries:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            pub_date = entry.get("published", "")

            # Filtro per evitare falsi positivi su B&C
            if clean_sym == "BEC" and not any(k in title.lower() for k in ["speaker", "b&c", "bec"]):
                continue

            source_name = "Borsa Italiana / Stampa IT"
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                title = parts[0].strip()
                source_name = f"Borsa IT ({parts[1].strip()})"

            dt = parse_datetime(pub_date)
            if not is_within_lookback(dt, lookback_hours):
                continue

            items.append({
                "ticker": ticker,
                "source": source_name,
                "category": "filing" if "comunicato" in title.lower() else "news",
                "title": title,
                "url": link,
                "published_at": dt.strftime("%Y-%m-%d %H:%M UTC") if dt else pub_date,
                "published_dt": dt,
                "summary": ""
            })
    except Exception:
        pass

    return items


# ----------------------------------------------------------------------
# Orchestratore per Singolo Ticker & Watchlist
# ----------------------------------------------------------------------
def fetch_all_news_for_ticker(
    ticker: str,
    company_name: str = "",
    metadata: Optional[Dict] = None,
    lookback_hours: int = 24
) -> List[Dict]:
    """
    Raccoglie in parallelo/sequenza le notizie da tutte le fonti attive per il ticker.
    """
    meta = metadata or {}
    yahoo_sym = meta.get("yahoo_symbol", ticker)
    is_sec = meta.get("is_sec_eligible", True)

    results = []

    # 1. SEC Filings (se applicabile)
    sec_filings = fetch_sec_filings(ticker, lookback_hours=lookback_hours, is_sec_eligible=is_sec)
    results.extend(sec_filings)
    time.sleep(0.1)

    # 2. Seeking Alpha (Priorità Tier 0: Titolo, Link originale e Autore)
    sa_news = fetch_seeking_alpha_news(ticker, is_sec_eligible=is_sec, lookback_hours=lookback_hours)
    results.extend(sa_news)

    # 3. Finviz News Feed (USA / ADR)
    finviz_news = fetch_finviz_news(
        ticker,
        company_name=company_name,
        is_sec_eligible=is_sec,
        lookback_hours=lookback_hours
    )
    results.extend(finviz_news)

    # 4. Yahoo Finance RSS
    yahoo_news = fetch_yahoo_finance_news(
        ticker,
        company_name=company_name,
        yahoo_symbol=yahoo_sym,
        lookback_hours=lookback_hours
    )
    results.extend(yahoo_news)

    # 5. Google News (Mirato Globale)
    google_news = fetch_google_news(
        ticker,
        company_name=company_name,
        yahoo_symbol=yahoo_sym,
        lookback_hours=lookback_hours
    )
    results.extend(google_news)

    # 6. Comunicati Borsa Italiana (per titoli italiani come BEC, TGYM)
    it_news = fetch_italian_corporate_news(ticker, company_name=company_name, lookback_hours=lookback_hours)
    results.extend(it_news)

    return results


def fetch_news_for_watchlist(watchlist: List[Dict], lookback_hours: int = 24) -> Dict[str, List[Dict]]:
    """
    Raccoglie le notizie e i filing per tutti i ticker abilitati nella watchlist in parallelo (ultra-rapido).
    """
    all_news: Dict[str, List[Dict]] = {}
    active_items = [item for item in watchlist if item.get("enabled", True)]

    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_ticker = {
            executor.submit(
                fetch_all_news_for_ticker,
                item["ticker"],
                item.get("name", ""),
                item.get("metadata", {}),
                lookback_hours
            ): item["ticker"]
            for item in active_items
        }

        for future in as_completed(future_to_ticker):
            ticker = future_to_ticker[future]
            try:
                all_news[ticker] = future.result()
            except Exception:
                all_news[ticker] = []

    return all_news
