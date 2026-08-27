# 📊 Personal Finance Watcher & Daily Digest

<p align="left">
  <a href="https://github.com/ecuriotto/daily-news-notification/actions"><img src="https://github.com/ecuriotto/daily-news-notification/actions/workflows/daily_scan.yml/badge.svg" alt="Daily Scan Status" /></a>
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white" alt="Python 3.11+" />
  <img src="https://img.shields.io/badge/Digest-Gmail%20SMTP-EA4335?logo=gmail&logoColor=white" alt="Gmail" />
  <img src="https://img.shields.io/badge/Tier%200-Seeking%20Alpha-FF8800" alt="Seeking Alpha Tier 0" />
  <img src="https://img.shields.io/badge/Scan%20Speed-%3C10s%20Parallel-00C853" alt="Scan Speed" />
  <img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License" />
</p>

| ⏱️ Frequency | ⚡ Execution Speed | 🎯 Selection | 📧 Delivery | ☁️ Cost |
| :---: | :---: | :---: | :---: | :---: |
| **Twice daily** (Mon-Fri) | **~5-8 seconds** (multithreaded) | **Max 2 news** per ticker | **HTML Responsive** mobile | **100% Free** (GitHub Actions) |

An automated, lightweight, and intelligent monitoring system for stock portfolios and equity watchlists.  
In just seconds, it scans global financial press, fundamental research, and investment theses, applies an algorithmic **Quality Scoring Engine** to eliminate market noise, and delivers a curated **responsive HTML email digest (optimized for smartphones)** via Gmail.

Runs both **locally** on your computer and **100% autonomously in the cloud via GitHub Actions** (completely free, zero server maintenance required).

---

## 🎯 Philosophy: Zero Noise, Only High-Conviction Insights

Unlike generic financial aggregators that flood your inbox with dozens of macro wrap-ups, algorithmic bot templates, or daily transaction dumps, Personal Finance Watcher:
- Selects **strictly at most 2 top articles per company** (a focused 60-second read).
- **Excludes routine regulatory filings (SEC EDGAR & Italian SDIR) from the email digest** (they remain archived in local reports for auditing).
- Prioritizes **in-depth fundamental theses from Seeking Alpha (Tier 0)** and extracts the **author/analyst name**.
- **Disambiguates short and international tickers** (e.g. isolates *JD.com* from *JD Sports / JD Vance*, isolates *LandBridge (LB)* from *L.B. Foster*).
- **Ranks companies and articles in descending order of quality score** (the most impactful corporate developments and theses appear at the very top of your email).

---

## ⚖️ Quality Scoring Engine (Ranking Formula)

Each collected headline or research article receives a transparent score based on 5 core factors:

```
Final Score = Source Tier + Material Event Bonus + Freshness Bonus - Clickbait Penalty
```

| Tier / Rule | Points | Description |
| :--- | :---: | :--- |
| **Tier 0: Seeking Alpha** | **+40 pts** | **Highest priority**. Deep fundamental research, long/short investment theses, and community valuations (with dedicated badge and author name). |
| **Tier 1: Global Financial Media** | **+25 pts** | *Reuters, Bloomberg, The Wall Street Journal, Financial Times, Barron's, MarketWatch, CNBC*. |
| **Tier 2: Business & Fundamental Research** | **+15 pts** | *Investor's Business Daily (IBD), GuruFocus, Forbes, Fortune, Quartz*. |
| **Tier 3: Generic Web** | **0 pts** | Standard syndicated web news and general feeds. |
| **Material Event Bonus** | **+15 pts** | Headlines containing tangible financial data or strategic actions (*Earnings, Guidance, Revenue, Results, Profit, Acquisitions, Mergers, Dividends, Buybacks, CEO*). |
| **Freshness Bonus** | **+5 pts** | Articles published within the last **12 hours** (prioritized over earlier intraday items). |
| **Anti-Clickbait Penalty** | **-20 pts** | Algorithmic and speculative bot templates (*"Should you buy...", "Why is ... down", "Forget X, buy Y", "3 reasons to..."*). |
| **Categorical Exclusion** | **-999 pts** | **Discarded from email**: SEC Filings, daily broker transaction dumps (*Southbound Capital Flows, short selling turnover*), class action lawsuit spam, and off-topic tickers. |

Inside the email digest:
- Every article displays a distinct score pill (e.g. `+60 pt`, `+40 pt`, `+25 pt`).
- Company cards are ordered from the highest-scoring business down to routine updates.
- Secondary articles are not lost: they are preserved in the Markdown and JSON audit archives.

---

## 🌐 Monitored Data Channels

1. **Seeking Alpha RSS**: Fundamental analyses and investment theses with native author extraction (`<sa:author_name>`).
2. **Finviz News Feed**: Real-time ticker news stream covering major Wall Street and ADR headlines.
3. **Yahoo Finance RSS**: Ticker-specific coverage across US and international markets (`.MI`, `.HK`, `.AS`, `.WA`).
4. **Targeted Google News**: Global and local news queries filtered by corporate brand and ticker symbol.
5. **Value Investors Club (Optional with `--with-vic`)**: In-depth value investing theses from the VIC community.
6. **SEC EDGAR & Borsa Italiana SDIR (Local Archive)**: Tracked and archived in local reports for regulatory compliance, but omitted from the email digest to maintain brevity.

---

## 📋 Watchlist Setup & Privacy

Your personal stock portfolio is kept **private** and never committed to Git.

### 1. Local Setup: `tickers.txt`
Copy the example template and customize with your own symbols:
```bash
cp tickers.example.txt tickers.txt
```

Edit `tickers.txt` with one ticker per line:
```text
# US Equities or ADRs
AAPL
CRM
MELI

# International exchanges (via MIC code or Yahoo suffix)
0700.HK       # Tencent (Hong Kong)
BEC:xmil      # B&C Speakers (Milan - Euronext)
BFIT:xams     # Basic-Fit (Amsterdam)
DNP.WA        # Dino Polska (Warsaw)
```

*(The file `tickers.txt` is listed in `.gitignore`: your holdings will always remain strictly on your local disk).*

---

## 💻 Command-Line Interface (Local Usage)

Activate your Python virtual environment:
```bash
source .venv/bin/activate
```

### 1. Fast Scan (Generates local reports in `reports/`)
```bash
python main.py --run
```
Produces `reports/report_YYYY-MM-DD.md` and `reports/report_YYYY-MM-DD.json` in under 10 seconds.

### 2. Scan & Send Email Digest (Gmail)
```bash
python main.py --run --email
```
Dispatches the curated Top 2 digest directly to your inbox.

### 3. Helpful CLI Options
- **Ad-hoc scan on specific tickers:**
  ```bash
  python main.py --run --tickers CRM,META,0700.HK
  ```
- **Custom lookback window (default: 1 day / 24 hours):**
  ```bash
  python main.py --run --days 2
  ```
- **Ticker validation and diagnostic summary:**
  ```bash
  python main.py --validate
  ```

---

## 📧 Email Notification Setup (Gmail SMTP)

To allow Python to send emails securely, Google requires a 16-character **App Password**:
1. Log in to your Google Account: [https://myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)  
   *(Ensure 2-Step Verification is enabled).*
2. Generate a new App Password named `Finance Watcher`.
3. Copy the generated 16-character password.

### Local Environment (`.env`)
```bash
cp .env.example .env
```
Populate `.env` with your credentials:
```env
GMAIL_USER=your.email@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
NOTIFICATION_EMAIL=your.email@gmail.com
ENABLE_EMAIL=true
```

---

## ☁️ 100% Free Cloud Automation (GitHub Actions)

The repository includes a ready-to-use GitHub Actions workflow [`.github/workflows/daily_scan.yml`](.github/workflows/daily_scan.yml) that executes the scan and dispatches the digest **Monday through Friday at 07:30 UTC and 17:30 UTC** (even when your PC is turned off).

### Setting up Repository Secrets:
1. In your GitHub repository, navigate to **Settings** ➔ **Secrets and variables** ➔ **Actions**;
2. Click **New repository secret** and add:
   - `GMAIL_USER`: your Gmail address (e.g. `your.email@gmail.com`)
   - `GMAIL_APP_PASSWORD`: the 16-character Google App Password
   - `NOTIFICATION_EMAIL`: the address where you want to receive the digest
   - `WATCHLIST_TICKERS` *(Optional for maximum privacy)*: paste your comma-separated ticker list here (e.g. `AAPL, MSFT, CRM, MELI, 0700.HK`) so your portfolio never appears in Git code or commits.

3. **Manual Trigger**: From the **Actions** tab in your repository, you can click **"Run workflow"** anytime to receive an immediate update on demand.

---

## 🔒 Security & Dependency Auditing

The repository complies with modern Python security practices:
- **Dependabot**: Enable in GitHub (**Settings > Code security and analysis**) for automated dependency PRs and vulnerability alerts.
- **Local Vulnerability Audit via `pip-audit`** (official PyPA standard):
  ```bash
  .venv/bin/pip-audit -r requirements.txt
  ```
- **Outdated Package Inspection**:
  ```bash
  .venv/bin/pip list --outdated
  ```
