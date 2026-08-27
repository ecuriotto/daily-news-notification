"""
Configurazione globale per l'automazione di Value Investors Club, monitoraggio news e invio email.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Percorsi base
BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = BASE_DIR / "src"
REPORTS_DIR = BASE_DIR / "reports"
SESSION_DIR = BASE_DIR / ".vic_session"
STORAGE_STATE_FILE = SESSION_DIR / "storage_state.json"

# Caricamento variabili d'ambiente da file .env se presente
ENV_FILE = BASE_DIR / ".env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)

# File watchlist
WATCHLIST_JSON = BASE_DIR / "watchlist.json"
TICKERS_TXT = BASE_DIR / "tickers.txt"

# Parametri Value Investors Club (facoltativo/su richiesta)
VIC_BASE_URL = "https://valueinvestorsclub.com"
VIC_LOGIN_URL = "https://valueinvestorsclub.com/login"
VIC_IDEAS_URL = "https://valueinvestorsclub.com/ideas"
VIC_MESSAGES_URL = "https://valueinvestorsclub.com/messages"

# User-Agent realistico per richieste web
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# User-Agent per richieste SEC EDGAR (richiesto da policy SEC: User-Agent: Sample Company Name AdminContact@<sample company domain>.com)
SEC_USER_AGENT = "PersonalFinanceWatcher/1.0 (contact: personal.research.watcher@gmail.com)"

# Timeout e impostazioni browser (in millisecondi)
DEFAULT_TIMEOUT_MS = 20000
HUMAN_DELAY_MIN_MS = 800
HUMAN_DELAY_MAX_MS = 2200

# Parametri default lookback (in ore)
DEFAULT_LOOKBACK_HOURS = 48

# Configurazioni Notifiche Email (Gmail SMTP / Secrets)
GMAIL_USER = os.getenv("GMAIL_USER", "").strip()
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "").strip().replace(" ", "")
NOTIFICATION_EMAIL = os.getenv("NOTIFICATION_EMAIL", GMAIL_USER).strip()
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
ENABLE_EMAIL = os.getenv("ENABLE_EMAIL", "false").lower() in ["true", "1", "yes"]
