"""
AI Natural Language Test Automation — CLI Entry Point.

Usage:
  python -m app --url "https://example.com" --test "Open the website and verify the title"
  python -m app --url "https://example.com" --test "..." --headless --provider gemini
  python -m app --interactive

Run `python -m app --help` for full options.
"""
import argparse
import getpass
import json
import sys
import os
from pathlib import Path

# Ensure project root is on sys.path regardless of invocation method
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

console = Console()


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m app",
        description=(
            "AI Natural Language Test Automation\n"
            "Convert plain-English test cases into Playwright browser automation."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m app --url "https://example.com" --test "Open the site and verify the title is visible"
  python -m app --url "https://books.toscrape.com" --test "Navigate to the books catalogue and verify books are displayed"
  python -m app --interactive
  python -m app --url "https://example.com" --test "..." --headless --slow-mo 0
  python -m app --url "https://app.example.com" --test "Log in and check dashboard" --credentials '{"username":"user@example.com","password":"secret"}'
        """,
    )
    parser.add_argument("--url", "-u", metavar="URL", help="Target base URL (must be http:// or https://)")
    parser.add_argument("--test", "-t", metavar="INSTRUCTION", help="Plain-English test instruction")
    parser.add_argument("--credentials", "-c", metavar="JSON", help='Credentials as JSON, e.g. \'{"username":"u","password":"p"}\'')
    parser.add_argument("--provider", choices=["mock", "gemini", "openai"], default=None,
                        help="LLM provider override (default: from LLM_PROVIDER env var or 'mock')")
    parser.add_argument("--headless", action="store_true", default=None, help="Run browser in headless mode")
    parser.add_argument("--slow-mo", type=int, default=None, metavar="MS", help="Milliseconds delay between actions (default: 250)")
    parser.add_argument("--interactive", "-i", action="store_true", help="Launch interactive session prompting for inputs")
    parser.add_argument("--no-report", action="store_true", help="Skip saving report files (console summary only)")
    parser.add_argument("--env-file", metavar="PATH", default=".env", help="Path to .env file (default: .env)")
    parser.add_argument("--version", action="version", version="AI-NL-TestAuto 1.0.0")
    return parser.parse_args(argv)


def load_config_with_env(env_file: str, provider_override: str = None):
    """Load config, optionally overriding the LLM provider."""
    # Load .env file
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=env_file, override=False)

    if provider_override:
        os.environ["LLM_PROVIDER"] = provider_override

    from config.settings import get_config
    return get_config(reload=True)


def run_interactive(args):
    """Interactive Q&A mode: prompt user for all inputs."""
    console.print(Panel(
        "[bold cyan]AI Natural Language Test Automation[/bold cyan]\n"
        "[dim]Interactive Mode — Press Ctrl+C at any time to exit.[/dim]",
        border_style="cyan",
    ))

    url = Prompt.ask("[bold]Target URL[/bold]", default="https://example.com").strip()
    instruction = Prompt.ask("[bold]Test instruction[/bold] (plain English)").strip()

    creds = {}
    if Confirm.ask("Does this test require login credentials?", default=False):
        username = Prompt.ask("  Username / Email")
        password = getpass.getpass("  Password (input hidden): ")
        creds = {"username": username, "password": password}

    headless = Confirm.ask("Run browser in headless mode?", default=False)
    slow_mo = int(Prompt.ask("Action delay in ms (0 = fast, 250 = visible pacing)", default="250"))

    return url, instruction, creds, headless, slow_mo


def main(argv=None):
    args = parse_args(argv)

    console.print(Panel(
        "[bold cyan]AI Natural Language Test Automation[/bold cyan]  v1.0.0\n"
        "[dim]Powered by Playwright + Pydantic + configurable LLM provider[/dim]",
        border_style="bright_blue",
    ))

    cfg = load_config_with_env(
        env_file=args.env_file,
        provider_override=args.provider,
    )

    # --- Gather inputs ---
    if args.interactive:
        url, instruction, creds, headless, slow_mo = run_interactive(args)
    else:
        url = args.url
        instruction = args.test
        creds = {}
        headless = args.headless if args.headless is not None else cfg.headless
        slow_mo = args.slow_mo if args.slow_mo is not None else cfg.slow_mo_ms

        if not url:
            console.print("[red]Error:[/red] --url is required (or use --interactive mode).")
            sys.exit(1)
        if not instruction:
            console.print("[red]Error:[/red] --test is required (or use --interactive mode).")
            sys.exit(1)

        # Parse credentials if provided
        if args.credentials:
            try:
                creds = json.loads(args.credentials)
                if not isinstance(creds, dict):
                    raise ValueError("Credentials must be a JSON object.")
            except (json.JSONDecodeError, ValueError) as e:
                console.print(f"[red]Invalid credentials JSON:[/red] {e}")
                sys.exit(1)

    console.print(f"\n[bold]URL:[/bold] {url}")
    console.print(f"[bold]Instruction:[/bold] {instruction}")
    console.print(f"[bold]LLM Provider:[/bold] {cfg.llm_provider}")
    console.print(f"[bold]Headless:[/bold] {headless}")
    console.print(f"[bold]Slow-Mo:[/bold] {slow_mo}ms\n")

    # --- Execute ---
    from app.runner import run_test
    result = run_test(
        instruction=instruction,
        base_url=url,
        credentials=creds,
        headless=headless,
        slow_mo=slow_mo,
        config=cfg,
    )

    # Exit code reflects test status
    if result.status == "PASS":
        console.print("[bold green]✓ All assertions passed.[/bold green]")
        sys.exit(0)
    elif result.status == "NEEDS_CLARIFICATION":
        console.print(f"[bold yellow]⚠ Clarification needed:[/bold yellow] {result.clarification_prompt}")
        sys.exit(2)
    else:
        console.print(f"[bold red]✗ Test {result.status}:[/bold red] {result.error_message or 'See report for details.'}")
        sys.exit(1)


if __name__ == "__main__":
    main()

