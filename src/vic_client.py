"""
Client Playwright per Value Investors Club (valueinvestorsclub.com).
Estrae nuove idee di investimento ("ideas") e nuovi messaggi di discussione ("messages")
filtrando rigorosamente sui ticker della watchlist.
"""

import re
import time
import random
from typing import List, Dict, Optional, Set
from playwright.sync_api import Page, BrowserContext
from rich.console import Console

import config

console = Console()


class VICClient:
    """Client per la navigazione automatizzata e lo scraping di Value Investors Club."""

    def __init__(self, context: BrowserContext):
        self.context = context
        self.page: Optional[Page] = None

    def _ensure_page(self) -> Page:
        """Restituisce una pagina attiva configurata o ne apre una nuova."""
        if not self.page or self.page.is_closed():
            self.page = self.context.new_page()
            self.page.set_default_timeout(config.DEFAULT_TIMEOUT_MS)
        return self.page

    def _random_delay(self, min_ms: int = config.HUMAN_DELAY_MIN_MS, max_ms: int = config.HUMAN_DELAY_MAX_MS):
        """Attesa casuale per simulare comportamento umano ed evitare rate limiting."""
        delay = random.uniform(min_ms / 1000.0, max_ms / 1000.0)
        time.sleep(delay)

    def verify_login_status(self) -> bool:
        """Controlla se l'utente è attualmente autenticato su VIC."""
        page = self._ensure_page()
        try:
            page.goto(config.VIC_BASE_URL, wait_until="domcontentloaded", timeout=config.DEFAULT_TIMEOUT_MS)
            self._random_delay(1000, 2000)
            content = page.content().lower()
            
            # Se è presente logout o il nome profilo utente, siamo autenticati
            logged_in = any(k in content for k in ["logout", "log out", "my profile", "my account"])
            if logged_in:
                console.print("[bold green]✓ Connessione a VIC: Sessione utente autenticata attiva.[/bold green]")
            else:
                console.print(
                    "[bold yellow]! Attenzione: Nessuna sessione attiva rilevata su VIC.\n"
                    "  Alcune idee recenti per i soli membri potrebbero richiedere login.\n"
                    "  Suggerimento: Esegui `python main.py --login` per salvare le tue credenziali.[/bold yellow]"
                )
            return logged_in
        except Exception as e:
            console.print(f"[red]Errore durante il controllo dello stato di login su VIC: {e}[/red]")
            return False

    def _build_term_mapping(self, watchlist_or_tickers) -> Dict[str, str]:
        """Costruisce una mappa da termine di ricerca/alias al ticker principale normalizzato."""
        term_to_ticker = {}
        if isinstance(watchlist_or_tickers, (set, list)):
            for item in watchlist_or_tickers:
                if isinstance(item, dict):
                    main_t = item.get("ticker", "").upper()
                    meta = item.get("metadata", {})
                    name = item.get("name", "")
                    term_to_ticker[main_t] = main_t
                    if ":" in main_t:
                        term_to_ticker[main_t.split(":", 1)[0]] = main_t
                    for s in meta.get("vic_symbols", []):
                        term_to_ticker[s] = main_t
                    if name and len(name) > 3:
                        term_to_ticker[name] = main_t
                elif isinstance(item, str):
                    t = item.strip().upper()
                    term_to_ticker[t] = t
                    if ":" in t:
                        term_to_ticker[t.split(":", 1)[0]] = t
        return term_to_ticker

    def scrape_recent_ideas(self, watchlist_or_tickers) -> List[Dict]:
        """
        Naviga nella sezione /ideas di VIC, scansiona le idee recenti
        e filtra quelle relative ai ticker in watchlist (inclusi alias e nomi azienda).
        """
        page = self._ensure_page()
        found_ideas = []
        term_map = self._build_term_mapping(watchlist_or_tickers)

        try:
            console.print(f"[dim]Accesso a {config.VIC_IDEAS_URL}...[/dim]")
            page.goto(config.VIC_IDEAS_URL, wait_until="domcontentloaded", timeout=config.DEFAULT_TIMEOUT_MS)
            self._random_delay()

            # Attende il caricamento della tabella o degli elementi delle idee
            try:
                page.wait_for_selector("table, .idea-item, .ideas-list, a[href*='/idea/']", timeout=10000)
            except Exception:
                pass

            idea_links = page.query_selector_all("a[href*='/idea/']")
            seen_urls = set()

            for link_elem in idea_links:
                try:
                    href = link_elem.get_attribute("href") or ""
                    if not href or href in seen_urls:
                        continue

                    full_url = href if href.startswith("http") else f"{config.VIC_BASE_URL}{href}"
                    seen_urls.add(href)

                    container = link_elem.evaluate_handle(
                        "el => el.closest('tr') || el.closest('.idea-item') || el.closest('li') || el"
                    )
                    container_text = container.as_element().inner_text() if container.as_element() else link_elem.inner_text()

                    matched_ticker = None
                    for term, ticker in term_map.items():
                        pattern = rf"(?:\$|\b){re.escape(term)}\b"
                        if re.search(pattern, container_text, re.IGNORECASE):
                            matched_ticker = ticker
                            break

                    if matched_ticker:
                        title = link_elem.inner_text().strip() or f"Idea per {matched_ticker}"
                        lines = [line.strip() for line in container_text.splitlines() if line.strip()]

                        author = ""
                        date_str = ""
                        for line in lines:
                            if any(m in line.lower() for m in ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec", "2024", "2025", "2026"]):
                                date_str = line
                            elif line != title and len(line) < 30 and not author:
                                author = line

                        found_ideas.append({
                            "ticker": matched_ticker,
                            "type": "VIC Idea",
                            "title": title,
                            "url": full_url,
                            "author": author,
                            "date": date_str,
                            "snippet": " | ".join(lines[:3])
                        })
                except Exception:
                    continue

        except Exception as e:
            console.print(f"[red]Errore durante lo scraping di /ideas su VIC: {e}[/red]")

        return found_ideas

    def search_ticker_ideas(self, ticker: str, vic_symbols: Optional[List[str]] = None, company_name: str = "") -> List[Dict]:
        """
        Cerca idee specifiche per un ticker o azienda su VIC utilizzando l'endpoint nativo di ricerca POST /search.
        """
        page = self._ensure_page()
        ideas = []
        seen_urls = set()

        search_terms = list(vic_symbols) if vic_symbols else [ticker]
        if company_name and company_name not in search_terms:
            search_terms.append(company_name)

        for term in search_terms:
            if not term or len(term) < 2:
                continue
            try:
                # Esegue la ricerca tramite API nativa nel contesto della pagina Playwright autenticata
                results = page.evaluate("""async (query) => {
                    try {
                        const formData = new URLSearchParams();
                        formData.append("query", query);
                        formData.append("tab", "ideas");
                        const resp = await fetch("/search", {
                            method: "POST",
                            body: formData,
                            headers: {"Content-Type": "application/x-www-form-urlencoded"}
                        });
                        if (resp.ok) {
                            return await resp.json();
                        }
                    } catch (e) {}
                    return {result: []};
                }""", term)

                items = results.get("result", []) if isinstance(results, dict) else []
                for item in items:
                    link = item.get("link", "")
                    if not link or link in seen_urls:
                        continue
                    seen_urls.add(link)
                    full_url = f"{config.VIC_BASE_URL}{link}" if link.startswith("/") else link
                    comp = item.get("comp", "")
                    sym = item.get("symbol", "")
                    title = f"{comp} ({sym})" if comp and sym else (comp or sym or f"Idea {ticker}")
                    date_str = item.get("add_date", "")

                    ideas.append({
                        "ticker": ticker.upper(),
                        "type": "VIC Idea",
                        "title": title,
                        "url": full_url,
                        "author": "",
                        "date": date_str,
                        "snippet": f"Azienda: {comp} | Simbolo: {sym} | Data: {date_str}"
                    })

                if ideas:
                    break
            except Exception as e:
                console.print(f"[dim yellow]Ricerca VIC per '{term}' non riuscita: {e}[/dim yellow]")

        return ideas

    def scrape_recent_messages(self, watchlist_or_tickers) -> List[Dict]:
        """
        Naviga nella sezione /messages di VIC (discussioni e commenti),
        estraendo i messaggi associati ai ticker o alias in watchlist.
        """
        page = self._ensure_page()
        found_messages = []
        term_map = self._build_term_mapping(watchlist_or_tickers)

        try:
            console.print(f"[dim]Accesso a {config.VIC_MESSAGES_URL}...[/dim]")
            page.goto(config.VIC_MESSAGES_URL, wait_until="domcontentloaded", timeout=config.DEFAULT_TIMEOUT_MS)
            self._random_delay()

            message_elements = page.query_selector_all("tr, .message-item, .comment-item, li.discussion")
            if not message_elements:
                message_elements = page.query_selector_all("a[href*='/idea/']")

            seen_snippets = set()

            for elem in message_elements:
                try:
                    text = elem.inner_text().strip()
                    if not text or len(text) < 15:
                        continue

                    matched_ticker = None
                    for term, ticker in term_map.items():
                        pattern = rf"(?:\$|\b){re.escape(term)}\b"
                        if re.search(pattern, text, re.IGNORECASE):
                            matched_ticker = ticker
                            break

                    if matched_ticker:
                        link = elem.query_selector("a[href*='/idea/']") or elem.query_selector("a")
                        href = link.get_attribute("href") if link else ""
                        full_url = (href if href.startswith("http") else f"{config.VIC_BASE_URL}{href}") if href else config.VIC_MESSAGES_URL

                        lines = [line.strip() for line in text.splitlines() if line.strip()]
                        headline = lines[0] if lines else f"Nuovo messaggio per {matched_ticker}"
                        snippet = " | ".join(lines[1:4]) if len(lines) > 1 else text[:200]

                        key = f"{matched_ticker}_{headline[:40]}"
                        if key in seen_snippets:
                            continue
                        seen_snippets.add(key)

                        found_messages.append({
                            "ticker": matched_ticker,
                            "type": "VIC Message",
                            "title": headline,
                            "url": full_url,
                            "author": "",
                            "date": "",
                            "snippet": snippet
                        })
                except Exception:
                    continue

        except Exception as e:
            console.print(f"[yellow]Nota durante l'accesso a /messages su VIC: {e}[/yellow]")

        return found_messages

    def close(self):
        """Chiude la pagina attiva se presente."""
        if self.page and not self.page.is_closed():
            self.page.close()
