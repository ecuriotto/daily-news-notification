# 📊 Personal Finance Watcher & Daily Digest

Un sistema automatizzato, leggero e intelligente per il monitoraggio quotidiano di portafogli e watchlist azionarie.  
Raccoglie in pochi secondi la rassegna stampa finanziaria globale, le analisi fondamentali e le tesi di investimento, applica un **algoritmo di Quality Scoring** per filtrare il rumore e invia ogni giorno un **digest email HTML responsive (ultra-snello e ottimizzato per smartphone)** tramite Gmail.

Funziona sia in **locale** sul tuo computer che in modo **100% autonomo nel cloud tramite GitHub Actions** (gratuito e a PC spento).

---

## 🎯 Filosofia: Zero Rumore, Solo Informazioni ad Alto Valore

A differenza dei tradizionali aggregatori finanziari che intasano la casella con dozzine di articoli generici, template algoritmici o bollettini statistici giornalieri, Personal Finance Watcher:
- Seleziona **esattamente al massimo 2 articoli per azienda** (il meglio della giornata in una lettura da 60 secondi).
- **Esclude categoricamente dall'email i filing burocratici SEC e i comunicati SDIR** (consultabili separatamente o archiviati nei report locali completi).
- Assegna la **priorità assoluta alle tesi di Seeking Alpha** ed estrae il **nome dell'analista/autore**.
- **Disambigua i ticker brevi o internazionali** (es. isola *JD.com* escludendo *JD Sports / JD Vance*, isola *LandBridge (LB)* escludendo *L.B. Foster*).
- **Ordina le aziende e le notizie in ordine decrescente di rilevanza** (in cima all'email trovi subito i titoli con le notizie più impattanti della giornata).

---

## ⚖️ Come si Calcola lo Score Qualitativo (Ranking)

Ogni notizia o analisi raccolta riceve un punteggio trasparente determinato da 5 fattori:

```
Punteggio Finale = Punteggio Fonte (Tier) + Evento Materiale + Freschezza - Penalità Clickbait
```

| Livello / Regola | Punti | Descrizione |
| :--- | :---: | :--- |
| **Tier 0: Seeking Alpha** | **+40 pt** | **Priorità assoluta**. Tesi fondamentali long/short e valutazioni degli analisti (con badge dedicato e nome autore). |
| **Tier 1: Grandi Testate** | **+25 pt** | *Reuters, Bloomberg, The Wall Street Journal, Financial Times, Barron's, MarketWatch, CNBC*. |
| **Tier 2: Business & Research** | **+15 pt** | *Investor's Business Daily (IBD), GuruFocus, Forbes, Fortune, Quartz*. |
| **Tier 3: Web Generico** | **0 pt** | Fonti web secondarie e notizie di agenzia standard. |
| **Bonus Evento Materiale** | **+15 pt** | Titoli con dati concreti di bilancio o M&A (*Earnings, Guidance, Revenue, Results, Profit, Acquisizioni, Merger, Dividendi, Buyback, CEO*). |
| **Bonus Freschezza** | **+5 pt** | Articoli pubblicati nelle ultime **12 ore** rispetto a quelli delle 12-24h precedenti. |
| **Penalità Anti-Clickbait** | **-20 pt** | Titoli generati da bot (*"Should you buy...", "Why is ... down", "Forget X, buy Y", "3 reasons to..."*). |
| **Esclusione Totale** | **-999 pt** | **Scartati dall'email**: SEC Filings, bollettini algoritmici di broker (*Southbound Capital Flows, short selling turnover*), spam legale/class action e notizie non pertinenti. |

All'interno dell'email:
- Ogni articolo mostra la pill con il suo punteggio (es. `+60 pt`, `+40 pt`, `+25 pt`).
- I blocchi delle aziende sono ordinati dall'azienda con il punteggio più alto a quella con meno novità.
- Gli articoli secondari in eccesso non vengono persi: vengono archiviati nel file Markdown e JSON di archivio.

---

## 🌐 Fonti di Informazione Monitorate

1. **Seeking Alpha RSS**: Analisi fondamentali e tesi d'investimento con estrazione dell'autore originale.
2. **Finviz News Feed**: Flusso in tempo reale per azioni USA e ADR con copertura delle grandi testate.
3. **Yahoo Finance RSS**: Notizie ticker-specifiche su mercati USA ed esteri con suffissi di borsa (`.MI`, `.HK`, `.AS`, `.WA`).
4. **Google News Mirato**: Rassegna stampa globale e locale filtrata per brand aziendale e ticker.
5. **Value Investors Club (Opzionale con `--with-vic`)**: Tesi di investimento approfondite della community di VIC.
6. **Borsa Italiana / SEC EDGAR (Archivio locale)**: Monitorati e archiviati nei report per tracciabilità storica, ma esclusi dal digest email quotidiano per non creare rumore.

---

## 📋 Configurazione Watchlist

La tua lista personale di titoli è mantenuta **privata** e non viene caricata su Git.

### 1. In Locale: File `tickers.txt`
Copia il file di esempio e inserisci i ticker da monitorare:
```bash
cp tickers.example.txt tickers.txt
```

Modifica `tickers.txt` inserendo un ticker per riga:
```text
# Azioni USA o ADR
AAPL
CRM
MELI

# Borse internazionali (con codice MIC o suffisso Yahoo)
0700.HK       # Tencent (Hong Kong)
BEC:xmil      # B&C Speakers (Borsa Italiana Milano)
BFIT:xams     # Basic-Fit (Amsterdam)
DNP.WA        # Dino Polska (Varsavia)
```

*(Il file `tickers.txt` è inserito nel `.gitignore`: i tuoi titoli rimarranno rigorosamente privati sul tuo computer).*

---

## 💻 Utilizzo da Riga di Comando (Locale)

Attiva l'ambiente virtuale:
```bash
source .venv/bin/activate
```

### 1. Scansione Rapida (Genera i report in `reports/`)
```bash
python main.py --run
```
Genera in pochi secondi `reports/report_YYYY-MM-DD.md` e `reports/report_YYYY-MM-DD.json`.

### 2. Scansione ed Invio Digest Email (Gmail)
```bash
python main.py --run --email
```
Invia al tuo indirizzo email il digest sintetico con le notizie Top 2 ordinate per score.

### 3. Opzioni Utili
- **Test su singoli ticker estemporanei:**
  ```bash
  python main.py --run --tickers CRM,META,0700.HK
  ```
- **Finestra temporale personalizzata (default 1 giorno / 24h):**
  ```bash
  python main.py --run --days 2
  ```
- **Diagnosi e validazione della watchlist:**
  ```bash
  python main.py --validate
  ```

---

## 📧 Configurazione Email (Gmail SMTP)

Per consentire l'invio delle notifiche, Google richiede una **Password per le app** a 16 caratteri:
1. Accedi al tuo account Google: [https://myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)  
   *(Assicurati di avere la verifica in due passaggi attiva).*
2. Crea una password denominata `Finance Watcher`.
3. Copia la password di 16 caratteri generata.

### Setup Locale (`.env`)
```bash
cp .env.example .env
```
Inserisci i tuoi dati nel file `.env`:
```env
GMAIL_USER=latuamail@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
NOTIFICATION_EMAIL=latuamail@gmail.com
ENABLE_EMAIL=true
```

---

## ☁️ Automazione Cloud 100% Gratuita (GitHub Actions)

Il repository include il workflow [`.github/workflows/daily_scan.yml`](.github/workflows/daily_scan.yml) che esegue automaticamente il monitoraggio e spedisce l'email **dal lunedì al venerdì alle 07:30 UTC e alle 17:30 UTC** (a computer spento).

### Come configurare i Secrets su GitHub:
1. Nel tuo repository su GitHub, vai su **Settings** ➔ **Secrets and variables** ➔ **Actions**;
2. Clicca su **New repository secret** e aggiungi:
   - `GMAIL_USER`: la tua email Gmail (es. `tua.email@gmail.com`)
   - `GMAIL_APP_PASSWORD`: la password per le app a 16 caratteri
   - `NOTIFICATION_EMAIL`: l'indirizzo dove desideri ricevere il digest
   - `WATCHLIST_TICKERS` *(Opzionale per la massima privacy)*: se non vuoi inserire i tuoi ticker nel codice, puoi incollare l'elenco dei tuoi ticker direttamente qui come secret (separati da virgola, es. `AAPL, MSFT, CRM, MELI, 0700.HK`).

3. **Esecuzione Manuale**: Dal tab **Actions** di GitHub puoi cliccare in qualunque momento su **"Run workflow"** per ricevere subito un'email aggiornata.

---

## 🔒 Sicurezza & Controllo Vulnerabilità

Il repository adotta i migliori standard di sicurezza per le dipendenze Python:
- **Dependabot**: Abilitabile su GitHub (**Settings > Code security and analysis**) per ricevere aggiornamenti automatici sulle dipendenze e avvisi CVE.
- **Audit locale con `pip-audit`** (standard ufficiale PyPA):
  ```bash
  .venv/bin/pip-audit -r requirements.txt
  ```
- **Controllo pacchetti obsoleti**:
  ```bash
  .venv/bin/pip list --outdated
  ```
