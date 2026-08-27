"""
Gestione dell'autenticazione, sessioni persistenti e bypass Cloudflare per Value Investors Club.
"""

import sys
from pathlib import Path
from typing import Optional
from playwright.sync_api import sync_playwright, BrowserContext, Playwright
from rich.console import Console
from rich.panel import Panel

import config

console = Console()


def get_stealth_args() -> list[str]:
    """Argomenti browser per ridurre l'impronta di automazione e superare Cloudflare."""
    return [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-infobars",
        "--window-position=0,0",
        "--ignore-certificate-errors",
        "--ignore-certificate-errors-spki-list",
    ]


def apply_stealth_scripts(context: BrowserContext):
    """Inietta script di stealth prima del caricamento di qualsiasi pagina."""
    stealth_js = """
    // Rimuove la proprietà navigator.webdriver
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined
    });

    // Maschera chrome runtime
    window.chrome = {
        runtime: {}
    };

    // Plugins simulati
    Object.defineProperty(navigator, 'plugins', {
        get: () => [1, 2, 3, 4, 5]
    });

    // Lingue realistiche
    Object.defineProperty(navigator, 'languages', {
        get: () => ['en-US', 'en', 'it']
    });
    """
    context.add_init_script(stealth_js)


def launch_vic_context(p: Playwright, headless: bool = True) -> BrowserContext:
    """
    Avvia un BrowserContext persistente per Value Investors Club.
    Mantiene cookie, token di autenticazione e cache locale.
    """
    config.SESSION_DIR.mkdir(parents=True, exist_ok=True)

    context = p.chromium.launch_persistent_context(
        user_data_dir=str(config.SESSION_DIR),
        headless=headless,
        user_agent=config.BROWSER_USER_AGENT,
        viewport={"width": 1280, "height": 850},
        locale="en-US",
        timezone_id="America/New_York",
        args=get_stealth_args(),
        ignore_default_args=["--enable-automation"],
    )
    apply_stealth_scripts(context)
    return context


def is_session_authenticated(context: BrowserContext) -> bool:
    """Verifica rapida se la sessione salvata ha accesso autenticato a VIC."""
    try:
        page = context.new_page()
        page.goto(config.VIC_BASE_URL, timeout=config.DEFAULT_TIMEOUT_MS, wait_until="domcontentloaded")
        page.wait_for_timeout(1500)
        
        # Indicatori di login: presenza di link logout, profilo o assenza del tasto 'Log In'
        content = page.content().lower()
        is_logged_in = ("logout" in content or "log out" in content or "my account" in content)
        page.close()
        return is_logged_in
    except Exception as e:
        console.print(f"[yellow]Attenzione durante la verifica sessione VIC: {e}[/yellow]")
        return False


def run_interactive_login():
    """
    Avvia una sessione del browser a finestra (headful) per consentire
    all'utente di eseguire il login manuale su Value Investors Club.
    Salva la sessione nel profilo persistente per le esecuzioni future.
    """
    console.print(
        Panel.fit(
            "[bold cyan]Value Investors Club - Setup Autenticazione[/bold cyan]\n"
            "Si sta aprendo il browser per l'accesso a VIC.\n"
            "1. Inserisci le tue credenziali sul sito.\n"
            "2. Completa eventuali verifiche di sicurezza/Cloudflare.\n"
            "3. Una volta completato il login, torna qui e premi [bold green]INVIO[/bold green].",
            title="Setup Sessione",
            border_style="cyan"
        )
    )

    with sync_playwright() as p:
        context = launch_vic_context(p, headless=False)
        page = context.pages[0] if context.pages else context.new_page()

        try:
            console.print(f"[dim]Navigazione verso {config.VIC_LOGIN_URL}...[/dim]")
            page.goto(config.VIC_LOGIN_URL, timeout=config.DEFAULT_TIMEOUT_MS)
        except Exception as e:
            console.print(f"[yellow]Nota: timeout o caricamento parziale durante goto ({e}). Procedi pure nel browser.[/yellow]")

        input("\n>>> Premi INVIO dopo aver completato l'accesso nel browser: ")

        # Verifica e salvataggio stato
        console.print("[dim]Salvataggio della sessione persistente...[/dim]")
        try:
            # Salva anche uno snapshot storage_state.json come backup
            context.storage_state(path=str(config.STORAGE_STATE_FILE))
            console.print(f"[green]✓ Stato salvato con successo in {config.STORAGE_STATE_FILE}[/green]")
        except Exception as e:
            console.print(f"[yellow]Nota salvataggio storage_state: {e}[/yellow]")

        content = page.content().lower()
        if "logout" in content or "log out" in content or "my account" in content:
            console.print("[bold green]✓ Login verificato con successo![/bold green]")
        else:
            console.print("[bold yellow]! Sessione salvata nel profilo. Verifica se il login è attivo durante la prima scansione.[/bold yellow]")

        context.close()
