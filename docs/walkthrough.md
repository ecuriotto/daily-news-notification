# Walkthrough: Monitoraggio Value Investors Club & News Finanziarie

Implementazione completa dello strumento di monitoraggio quotidiano per **Value Investors Club (VIC)** e aggregazione di notizie e comunicati societari da fonti web finanziarie autorevoli.

---

## Struttura del Progetto Creata

- [`config.py`](file:///Users/ricardesco/progetti/100-finance-notifications/config.py): configurazione globale dei percorsi, URL, user agent e timeout.
- [`watchlist.json`](file:///Users/ricardesco/progetti/100-finance-notifications/watchlist.json) e [`tickers.txt`](file:///Users/ricardesco/progetti/100-finance-notifications/tickers.txt): definizione della watchlist personale (con supporto di abilitazione/disabilitazione ticker e metadati).
- [`requirements.txt`](file:///Users/ricardesco/progetti/100-finance-notifications/requirements.txt): dipendenze (`playwright`, `feedparser`, `requests`, `beautifulsoup4`, `rich`, `python-dateutil`).
- [`src/auth.py`](file:///Users/ricardesco/progetti/100-finance-notifications/src/auth.py): gestione del profilo browser persistente Playwright (`.vic_session/`), bypass Cloudflare tramite argomenti e script di stealth (`navigator.webdriver` mascherato), e procedura di login interattivo con salvataggio cookie.
- [`src/vic_client.py`](file:///Users/ricardesco/progetti/100-finance-notifications/src/vic_client.py): client Playwright per Value Investors Club (estrazione idee recenti `/ideas`, commenti/discussioni `/messages`, ricerca diretta per ticker, jitter randomizzato anti-bot).
- [`src/news_engine.py`](file:///Users/ricardesco/progetti/100-finance-notifications/src/news_engine.py): motore multi-fonte per il web:
  - **SEC EDGAR**: Filings ufficiali (8-K, 10-Q, 10-K, Form 4) con User-Agent conforme alle policy SEC.
  - **Yahoo Finance RSS**: Notizie d'agenzia e analisi in tempo reale.
  - **Google News RSS (Financial)**: Rassegna stampa aggregata con filtro temporale.
  - **Seeking Alpha RSS**: Articoli di approfondimento e analisi.
- [`src/aggregator.py`](file:///Users/ricardesco/progetti/100-finance-notifications/src/aggregator.py): filtraggio stretto sui ticker in watchlist, normalizzazione e deduplicazione per URL e similarità titoli.
- [`src/reporter.py`](file:///Users/ricardesco/progetti/100-finance-notifications/src/reporter.py): generatore di report:
  - **Markdown** (`reports/report_YYYY-MM-DD.md`) formattato con tabelle ed estratti.
  - **JSON** (`reports/report_YYYY-MM-DD.json`) per archivio o integrazioni.
  - Visualizzazione a terminale con tabelle `rich`.
- [`main.py`](file:///Users/ricardesco/progetti/100-finance-notifications/main.py): CLI principale con supporto per `--login`, `--run`, `--news-only`, `--vic-only`, `--tickers`, `--days`, `--headful`.
- [`README.md`](file:///Users/ricardesco/progetti/100-finance-notifications/README.md): guida dettagliata all'uso e all'automazione tramite cron.

---

## Verifiche e Risultati dei Test

### 1. Test Raccolta Notizie Web & SEC Filings
Eseguito con successo su ticker di prova (`AAPL`, `MSFT`) su una finestra temporale di 3 giorni:
```bash
python main.py --news-only --tickers AAPL,MSFT --days 3
```
- Raccolti **188 articoli e comunicati** totali.
- Generati correttamente i report Markdown e JSON.

### 2. Test Client Playwright per Value Investors Club
Eseguito in modalità headless:
```bash
python main.py --vic-only --tickers AAPL
```
- Inizializzazione del browser Chromium con profilo persistente.
- Rilevamento dello stato di sessione (notifica visiva per effettuare il login).
- Navigazione di sicurezza e scansione delle sezioni `/ideas` e `/messages` senza blocchi o eccezioni.

### 3. Test Combinato (VIC + Notizie Web)
Eseguito con successo su `AAPL, GOOGL`:
```bash
python main.py --tickers AAPL,GOOGL --days 2
```
- Esecuzione fluida della scansione Playwright su VIC e contemporaneo scaricamento e deduplicazione delle notizie web (**171 notizie aggregate**).
- Tabella riassuntiva visualizzata a terminale e report aggiornati in [`reports/`](file:///Users/ricardesco/progetti/100-finance-notifications/reports/).

---

## Prossimi Passi Consigliati per l'Utente

1. **Primo login su VIC**:
   Esegui nel terminale:
   ```bash
   source .venv/bin/activate
   python main.py --login
   ```
   Accedi con il tuo account nella finestra che si apre e premi INVIO per memorizzare la sessione in `.vic_session/`.
2. **Personalizza la Watchlist**:
   Aggiungi i tuoi ticker di interesse in [`watchlist.json`](file:///Users/ricardesco/progetti/100-finance-notifications/watchlist.json) o in [`tickers.txt`](file:///Users/ricardesco/progetti/100-finance-notifications/tickers.txt).
3. **Esecuzione Quotidiana**:
   ```bash
   python main.py --run
   ```
