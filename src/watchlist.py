"""
Gestione della Watchlist: lettura, validazione, normalizzazione e arricchimento dei ticker.
Supporta sia watchlist.json che tickers.txt (con rilevamento automatico del file più recente).
Include dizionario di metadata e normalizzazione per mercati internazionali (Yahoo, SEC, VIC).
"""

import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
import config

# Dizionario di arricchimento intelligente per ticker noti (inclusi internazionali e meno popolari)
KNOWN_TICKER_METADATA: Dict[str, Dict[str, Any]] = {
    "700": {
        "name": "Tencent Holdings Ltd",
        "yahoo_symbol": "0700.HK",
        "alt_yahoo_symbols": ["TCEHY"],
        "vic_symbols": ["700", "0700", "Tencent"],
        "is_sec_eligible": False,
        "market": "Hong Kong (HKEX)",
        "type": "FOREIGN_EXCHANGE"
    },
    "9988": {
        "name": "Alibaba Group Holding Ltd",
        "yahoo_symbol": "9988.HK",
        "alt_yahoo_symbols": ["BABA"],
        "vic_symbols": ["BABA", "Alibaba"],
        "is_sec_eligible": True,  # Tramite ADR BABA
        "market": "Hong Kong (HKEX) / NYSE (BABA)",
        "type": "FOREIGN_EXCHANGE"
    },
    "BFIT": {
        "name": "Basic-Fit N.V.",
        "yahoo_symbol": "BFIT.AS",
        "vic_symbols": ["BFIT", "Basic-Fit"],
        "is_sec_eligible": False,
        "market": "Euronext Amsterdam",
        "type": "FOREIGN_EXCHANGE"
    },
    "BEC": {
        "name": "B&C Speakers S.p.A.",
        "yahoo_symbol": "BEC.MI",
        "vic_symbols": ["BEC", "B&C Speakers"],
        "is_sec_eligible": False,
        "market": "Borsa Italiana (Euronext Milan)",
        "type": "FOREIGN_EXCHANGE"
    },
    "TGYM": {
        "name": "Technogym S.p.A.",
        "yahoo_symbol": "TGYM.MI",
        "vic_symbols": ["TGYM", "Technogym"],
        "is_sec_eligible": False,
        "market": "Borsa Italiana (Euronext Milan)",
        "type": "FOREIGN_EXCHANGE"
    },
    "DNP": {
        "name": "Dino Polska S.A.",
        "yahoo_symbol": "DNP.WA",
        "alt_yahoo_symbols": ["DNP"],
        "vic_symbols": ["DNP", "Dino Polska"],
        "is_sec_eligible": False,  # Se Dino Polska; notare DNP Select Fund negli USA
        "market": "Warsaw Stock Exchange (WSE)",
        "type": "FOREIGN_EXCHANGE"
    },
    "APR": {
        "name": "Auto Partner S.A.",
        "yahoo_symbol": "APR.WA",
        "vic_symbols": ["APR.PW", "Auto Partner", "APR"],
        "is_sec_eligible": False,
        "market": "Warsaw Stock Exchange (WSE)",
        "type": "FOREIGN_EXCHANGE"
    },
    "KSPI": {
        "name": "JSC Kaspi.kz",
        "yahoo_symbol": "KSPI",
        "vic_symbols": ["KSPI", "Kaspi"],
        "is_sec_eligible": True,
        "market": "NASDAQ (ADR)",
        "type": "ADR"
    },
    "CPNG": {
        "name": "Coupang Inc.",
        "yahoo_symbol": "CPNG",
        "vic_symbols": ["CPNG", "Coupang"],
        "is_sec_eligible": True,
        "market": "NYSE",
        "type": "US_EQUITY"
    },
    "CRM": {
        "name": "Salesforce Inc.",
        "yahoo_symbol": "CRM",
        "vic_symbols": ["CRM", "Salesforce"],
        "is_sec_eligible": True,
        "market": "NYSE",
        "type": "US_EQUITY"
    },
    "JD": {
        "name": "JD.com Inc.",
        "yahoo_symbol": "JD",
        "vic_symbols": ["JD", "JD.com"],
        "is_sec_eligible": True,
        "market": "NASDAQ (ADR)",
        "type": "ADR"
    },
    "LB": {
        "name": "LandBridge Company LLC",
        "yahoo_symbol": "LB",
        "vic_symbols": ["LB", "LandBridge"],
        "is_sec_eligible": True,
        "market": "NYSE",
        "type": "US_EQUITY"
    },
    "MELI": {
        "name": "MercadoLibre Inc.",
        "yahoo_symbol": "MELI",
        "vic_symbols": ["MELI", "MercadoLibre"],
        "is_sec_eligible": True,
        "market": "NASDAQ",
        "type": "US_EQUITY"
    },
    "META": {
        "name": "Meta Platforms Inc.",
        "yahoo_symbol": "META",
        "vic_symbols": ["META", "Meta"],
        "is_sec_eligible": True,
        "market": "NASDAQ",
        "type": "US_EQUITY"
    },
    "MSCI": {
        "name": "MSCI Inc.",
        "yahoo_symbol": "MSCI",
        "vic_symbols": ["MSCI"],
        "is_sec_eligible": True,
        "market": "NYSE",
        "type": "US_EQUITY"
    },
    "OKE": {
        "name": "ONEOK Inc.",
        "yahoo_symbol": "OKE",
        "vic_symbols": ["OKE", "ONEOK"],
        "is_sec_eligible": True,
        "market": "NYSE",
        "type": "US_EQUITY"
    },
    "PYPL": {
        "name": "PayPal Holdings Inc.",
        "yahoo_symbol": "PYPL",
        "vic_symbols": ["PYPL", "PayPal"],
        "is_sec_eligible": True,
        "market": "NASDAQ",
        "type": "US_EQUITY"
    },
    "QXO": {
        "name": "QXO Inc.",
        "yahoo_symbol": "QXO",
        "vic_symbols": ["QXO"],
        "is_sec_eligible": True,
        "market": "NASDAQ",
        "type": "US_EQUITY"
    },
    "SE": {
        "name": "Sea Ltd",
        "yahoo_symbol": "SE",
        "vic_symbols": ["SE", "Sea Ltd"],
        "is_sec_eligible": True,
        "market": "NYSE (ADR)",
        "type": "ADR"
    },
    "SLDP": {
        "name": "Solid Power Inc.",
        "yahoo_symbol": "SLDP",
        "vic_symbols": ["SLDP", "Solid Power"],
        "is_sec_eligible": True,
        "market": "NASDAQ",
        "type": "US_EQUITY"
    }
}

# Mappatura dei Market Identifier Codes (MIC) su suffissi Yahoo Finance
MIC_TO_YAHOO_SUFFIX = {
    "XMIL": ".MI",  # Borsa Italiana Milano
    "XAMS": ".AS",  # Euronext Amsterdam
    "XPAR": ".PA",  # Euronext Parigi
    "XFRA": ".DE",  # XETRA / Francoforte
    "XLON": ".L",   # London Stock Exchange
    "XWAR": ".WA",  # Borsa di Varsavia
    "XHKG": ".HK",  # Hong Kong
    "XTKS": ".T",   # Tokyo
    "XSWX": ".SW",  # SIX Swiss Exchange
}


def parse_raw_ticker(raw_line: str) -> Tuple[str, str, Dict[str, Any]]:
    """
    Analizza una riga di ticker grezza, estraendo:
    - Simbolo primario pulito (es. 'BEC:xmil' -> ticker 'BEC:XMIL', base 'BEC', mic 'XMIL')
    - Nome aziendale (se specificato inline dopo virgola o pipe)
    - Metadata di arricchimento (simbolo Yahoo normalizzato, idoneità SEC, query VIC)
    """
    clean_line = raw_line.strip()
    explicit_name = ""

    # Supporto per "TICKER, Company Name" o "TICKER | Company Name"
    if "," in clean_line:
        parts = clean_line.split(",", 1)
        clean_line = parts[0].strip()
        explicit_name = parts[1].strip()
    elif "|" in clean_line:
        parts = clean_line.split("|", 1)
        clean_line = parts[0].strip()
        explicit_name = parts[1].strip()

    clean_line = clean_line.replace("$", "").strip()
    raw_upper = clean_line.upper()

    # Rileva eventuale MIC o borsa (es. BEC:xmil o BEC.MI)
    base_symbol = raw_upper
    mic = None
    if ":" in raw_upper:
        symbol_part, mic_part = raw_upper.split(":", 1)
        base_symbol = symbol_part.strip()
        mic = mic_part.strip()

    # Recupera metadati conosciuti o costruisce default intelligenti
    meta = KNOWN_TICKER_METADATA.get(base_symbol, {}).copy()

    # Se non c'è match su base_symbol, prova con raw_upper
    if not meta and raw_upper in KNOWN_TICKER_METADATA:
        meta = KNOWN_TICKER_METADATA[raw_upper].copy()

    # Se ancora assente, genera metadati euristici
    if not meta:
        yahoo_sym = raw_upper
        is_sec = True
        t_type = "US_EQUITY"

        if mic and mic in MIC_TO_YAHOO_SUFFIX:
            yahoo_sym = f"{base_symbol}{MIC_TO_YAHOO_SUFFIX[mic]}"
            is_sec = False
            t_type = "FOREIGN_EXCHANGE"
        elif any(raw_upper.endswith(suf) for suf in [".MI", ".AS", ".PA", ".DE", ".L", ".WA", ".HK"]):
            yahoo_sym = raw_upper
            is_sec = False
            t_type = "FOREIGN_EXCHANGE"
        elif raw_upper.isdigit():
            # Codice numerico (tipico di HK o Asia)
            yahoo_sym = f"{raw_upper.zfill(4)}.HK"
            is_sec = False
            t_type = "FOREIGN_EXCHANGE"

        meta = {
            "name": explicit_name or base_symbol,
            "yahoo_symbol": yahoo_sym,
            "vic_symbols": [base_symbol],
            "is_sec_eligible": is_sec,
            "market": f"MIC:{mic}" if mic else ("Non-US" if not is_sec else "US Market"),
            "type": t_type
        }
    else:
        # Se abbiamo un MIC esplicito (es. :xmil), rafforziamo il suffisso Yahoo
        if mic and mic in MIC_TO_YAHOO_SUFFIX:
            meta["yahoo_symbol"] = f"{base_symbol}{MIC_TO_YAHOO_SUFFIX[mic]}"
            meta["is_sec_eligible"] = False

    # Sovrascrive il nome se l'utente lo ha inserito esplicitamente
    if explicit_name:
        meta["name"] = explicit_name

    return raw_upper, meta.get("name", ""), meta


def extract_raw_ticker_entries(raw_content: str) -> List[str]:
    """
    Estrae le singole voci ticker da un testo grezzo (da tickers.txt o dalla variabile WATCHLIST_TICKERS).
    Supporta in modo 100% uniforme e intercambiabile:
    - Formato multilinea (un ticker per riga)
    - Formato separato da virgole (es. 'AAPL, MSFT, 0700.HK, BEC:xmil')
    - Righe di commento con '#' o righe vuote (ignorate)
    - Definizione facoltativa nome con pipe (es. 'TGYM:xmil | Technogym')
    """
    entries = []
    for line in raw_content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "|" in line:
            entries.append(line)
        elif "," in line:
            for item in line.split(","):
                item = item.strip()
                if item and not item.startswith("#"):
                    entries.append(item)
        else:
            entries.append(line)
    return entries


def load_watchlist(file_path: Optional[Path] = None, override_tickers: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """
    Carica e normalizza la lista di ticker monitorati.
    
    Risoluzione priorità intelligente:
    1. override_tickers (se specificati da CLI)
    2. Variabile d'ambiente WATCHLIST_TICKERS (GitHub Secrets / .env)
    3. Se specificato un file esplicito via file_path, usa quello.
    4. Altrimenti, confronta 'tickers.txt' e 'watchlist.json':
       - Se tickers.txt ha timestamp di modifica più recente (o watchlist.json contiene solo i demo predefiniti),
         usa prioritariamente 'tickers.txt'.
       - Altrimenti usa 'watchlist.json'.
    """
    import os
    env_tickers = os.getenv("WATCHLIST_TICKERS", "").strip()
    if env_tickers and not override_tickers:
        raw_list = extract_raw_ticker_entries(env_tickers)
        if raw_list:
            override_tickers = raw_list

    if override_tickers:
        watchlist = []
        for t in override_tickers:
            t = t.strip()
            if not t:
                continue
            symbol, name, meta = parse_raw_ticker(t)
            watchlist.append({
                "ticker": symbol,
                "name": name,
                "enabled": True,
                "metadata": meta
            })
        return watchlist

    target_txt = config.TICKERS_TXT
    target_json = file_path or config.WATCHLIST_JSON

    # Decisione sulla sorgente
    use_txt_first = False
    if target_txt.exists() and target_json.exists():
        txt_mtime = target_txt.stat().st_mtime
        json_mtime = target_json.stat().st_mtime
        # Se tickers.txt è stato modificato più di recente, usalo come sorgente primaria
        if txt_mtime >= json_mtime:
            use_txt_first = True
        else:
            # Verifica se watchlist.json contiene solo i vecchi demo ("AAPL", "MSFT", "GOOGL", "AMZN", "META")
            try:
                with open(target_json, "r", encoding="utf-8") as f:
                    jdata = json.load(f)
                    demo_set = {"AAPL", "MSFT", "GOOGL", "AMZN", "META"}
                    loaded_set = {item.get("ticker", "").upper() for item in jdata if isinstance(item, dict)}
                    if loaded_set == demo_set:
                        use_txt_first = True
            except Exception:
                pass
    elif target_txt.exists():
        use_txt_first = True

    # 1. Lettura da tickers.txt
    if use_txt_first and target_txt.exists():
        try:
            tickers = []
            with open(target_txt, "r", encoding="utf-8") as f:
                content = f.read()
            raw_entries = extract_raw_ticker_entries(content)
            for entry in raw_entries:
                symbol, name, meta = parse_raw_ticker(entry)
                tickers.append({
                    "ticker": symbol,
                    "name": name,
                    "enabled": True,
                    "metadata": meta
                })
            if tickers:
                return tickers
        except Exception as e:
            print(f"[!] Errore nella lettura di {target_txt}: {e}")

    # 2. Lettura da watchlist.json
    if target_json.exists():
        try:
            with open(target_json, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    tickers = []
                    for item in data:
                        if isinstance(item, dict) and item.get("enabled", True):
                            raw_ticker = item.get("ticker", "")
                            if raw_ticker.strip():
                                symbol, name, meta = parse_raw_ticker(raw_ticker)
                                # Se nel json era indicato un nome esplicito, prevale
                                if item.get("name"):
                                    name = item.get("name")
                                    meta["name"] = name
                                tickers.append({
                                    "ticker": symbol,
                                    "name": name,
                                    "enabled": True,
                                    "metadata": meta
                                })
                        elif isinstance(item, str) and item.strip():
                            symbol, name, meta = parse_raw_ticker(item)
                            tickers.append({
                                "ticker": symbol,
                                "name": name,
                                "enabled": True,
                                "metadata": meta
                            })
                    if tickers:
                        return tickers
        except Exception as e:
            print(f"[!] Errore nella lettura di {target_json}: {e}")

    # 3. Fallback di sicurezza
    symbol, name, meta = parse_raw_ticker("AAPL")
    return [{"ticker": symbol, "name": name, "enabled": True, "metadata": meta}]


def get_ticker_symbols(watchlist: List[Dict[str, Any]]) -> List[str]:
    """Restituisce solo i simboli dei ticker univoci in maiuscolo."""
    seen = set()
    result = []
    for item in watchlist:
        t = item["ticker"]
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result
