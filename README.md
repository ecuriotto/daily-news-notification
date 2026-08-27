# 📈 Personal Finance Watcher & Daily Digest (V1)

Sistema automatizzato per il monitoraggio quotidiano di portafogli e watchlist azionarie.  
Raccoglie in pochi secondi comunicati ufficiali, filing SEC, rassegna stampa finanziaria globale e analisi fondamentali, generando un **report Markdown/JSON** e inviando un **digest via email (HTML responsive)** su Gmail/Smartphone.

Funziona sia in **locale** sul tuo computer che in modo **100% autonomo nel cloud tramite GitHub Actions** (anche a PC spento).

---

## 🚀 Canali & Fonti di Notizie Integrate

1. **SEC EDGAR (USA / ADR)**: Filing societari legali obbligatori (Form 8-K, 10-Q, 10-K, Form 4 insider trading) per i titoli quotati a Wall Street. Salta in automatico i titoli esteri.
2. **Finviz News Feed**: Aggregatore filtrato per ticker che indicizza testate di primo piano (MarketWatch, Bloomberg, Reuters, PR Newswire, Business Wire).
3. **Yahoo Finance RSS**: Notizie ticker-specifiche con supporto suffissi internazionali (`.MI`, `.HK`, `.AS`, `.WA`).
4. **Google News Mirato**: Rassegna stampa globale e locale (testate internazionali e italiane con query anti-falsi positivi).
5. **Seeking Alpha RSS**: Titoli delle tesi di investimento e delle analisi fondamentali della community (protetto da bot challenge).
6. **Borsa Italiana / Circuiti SDIR**: Notizie e comunicati societari per i titoli italiani (es. `BEC:xmil`, `TGYM:xmil`).
7. **Value Investors Club (Opzionale)**: Tesi approfondite di value investing attivabile su richiesta con `--with-vic`.

---

## ⚙️ Configurazione Watchlist

I ticker possono essere gestiti direttamente nel file **`tickers.txt`**, un ticker per riga:

```text
700          # Tencent (Hong Kong HKEX -> 0700.HK)
9988         # Alibaba (Hong Kong HKEX / ADR BABA)
BFIT         # Basic-Fit (Euronext Amsterdam -> BFIT.AS)
CPNG         # Coupang (NYSE)
CRM          # Salesforce (NYSE)
JD           # JD.com (NASDAQ ADR)
KSPI         # Kaspi.kz (NASDAQ ADR)
LB           # LandBridge (NYSE)
MELI         # MercadoLibre (NASDAQ)
META         # Meta Platforms (NASDAQ)
MSCI         # MSCI Inc. (NYSE)
OKE          # ONEOK (NYSE)
PYPL         # PayPal (NASDAQ)
QXO          # QXO Inc. (NASDAQ)
SE           # Sea Ltd (NYSE ADR)
SLDP         # Solid Power (NASDAQ)
DNP          # Dino Polska (WSE Varsavia -> DNP.WA)
APR          # Auto Partner (WSE Varsavia -> APR.WA)
BEC:xmil     # B&C Speakers (Borsa Italiana Milano -> BEC.MI)
TGYM:xmil    # Technogym (Borsa Italiana Milano -> TGYM.MI)
```

---

## 🛠️ Utilizzo da Riga di Comando (Locale)

Attiva l'ambiente virtuale:
```bash
source .venv/bin/activate
```

### 1. Diagnosi preventiva dei ticker (Validazione)
Mostra la tabella con le aziende riconosciute, il mercato, il simbolo Yahoo e i warning:
```bash
python main.py --validate
```

### 2. Scansione Quotidiana V1 (Veloce ~5-10 secondi)
Raccoglie notizie, SEC filings e genera i report locali in `reports/`:
```bash
python main.py --run
```

### 3. Scansione ed Invio Notifica Email (Gmail)
Esegue la scansione e spedisce il digest formattato in HTML al tuo indirizzo email:
```bash
python main.py --run --email
```

### 4. Altre opzioni utili:
- **Controllo su ticker specifici estemporanei:**
  ```bash
  python main.py --run --tickers CRM,TGYM:xmil
  ```
- **Finestra temporale personalizzata (es. 3 giorni):**
  ```bash
  python main.py --run --days 3
  ```
- **Includere lo scraping di Value Investors Club (Playwright):**
  ```bash
  python main.py --run --with-vic
  ```

---

## 📧 Configurazione Notifiche Email (Gmail SMTP)

Per consentire a Python di inviare l'email dal tuo account Gmail, Google richiede una **Password per le app** a 16 caratteri:

1. Vai sul tuo account Google: [https://myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)  
   *(Assicurati di avere la verifica in due passaggi attiva).*
2. Crea una nuova password chiamandola ad esempio `Finance Watcher`.
3. Copia la password di 16 caratteri generata (es. `abcd efgh ijkl mnop`).

### In Locale (File `.env`)
Crea un file chiamato `.env` nella cartella principale del progetto:
```bash
cp .env.example .env
```
Inserisci i tuoi dati:
```env
GMAIL_USER=latuamail@gmail.com
GMAIL_APP_PASSWORD=abcdefghijklmnop
NOTIFICATION_EMAIL=latuamail@gmail.com
ENABLE_EMAIL=false
```

---

## ☁️ Automazione Cloud 100% Gratuita (GitHub Actions)

Il progetto include già il file [`.github/workflows/daily_scan.yml`](.github/workflows/daily_scan.yml) che esegue automaticamente la scansione e ti invia l'email **dal lunedì al venerdì alle 07:30 UTC e alle 17:30 UTC** (anche a computer spento).

### Come attivarlo sulla tua repository GitHub:
1. Carica il progetto su una repository GitHub (privata o pubblica);
2. Su GitHub, vai in **Settings** -> **Secrets and variables** -> **Actions**;
3. Clicca su **New repository secret** e aggiungi le 3 chiavi:
   - `GMAIL_USER`: la tua email Gmail (es. `mario.rossi@gmail.com`)
   - `GMAIL_APP_PASSWORD`: la password per le app di 16 caratteri
   - `NOTIFICATION_EMAIL`: l'email dove vuoi ricevere il digest quotidiano
4. Fatto! La scansione partirà in automatico ogni giorno feriale. Puoi anche avviarla manualmente dal tab **Actions** con il pulsante **"Run workflow"**.
