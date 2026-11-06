"""ResultReporter: Generates structured JSON, standalone interactive HTML, and formatted console reports."""
import base64
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table


@dataclass
class StepResult:
    """Outcome and diagnostics for a single executed test step."""
    step_number: int
    action: str
    description: str
    status: Literal["PASS", "FAIL", "SKIPPED", "ERROR"]
    duration_ms: float
    target_info: Optional[str] = None
    input_value: Optional[str] = None
    screenshot_path: Optional[str] = None
    error_message: Optional[str] = None
    assertion_details: Optional[Dict[str, Any]] = None


@dataclass
class TestRunResult:
    """Aggregate result of an entire test run."""
    __test__ = False
    run_id: str
    instruction: str
    base_url: str
    status: Literal["PASS", "FAIL", "ERROR", "NEEDS_CLARIFICATION"]
    start_time: str
    end_time: str
    duration_sec: float
    total_steps: int
    passed_steps: int
    failed_steps: int
    steps: List[StepResult] = field(default_factory=list)
    error_message: Optional[str] = None
    clarification_prompt: Optional[str] = None
    screenshots: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ResultReporter:
    """Generates multi-format test results (JSON, standalone HTML, console)."""

    def __init__(self, reports_dir: Path = Path("reports")):
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.console = Console()

    def generate_json_report(self, result: TestRunResult) -> Path:
        """Serialize test result to a formatted JSON report file."""
        report_path = self.reports_dir / f"report_{result.run_id}.json"
        data = asdict(result)
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return report_path

    def generate_html_report(self, result: TestRunResult) -> Path:
        """Render a clean, modern, standalone HTML report with embedded evidence and styling."""
        report_path = self.reports_dir / f"report_{result.run_id}.html"

        # Status badge colors
        status_colors = {
            "PASS": "#10b981",       # Emerald green
            "FAIL": "#ef4444",       # Coral red
            "ERROR": "#f59e0b",      # Amber
            "NEEDS_CLARIFICATION": "#6366f1", # Indigo
        }
        main_color = status_colors.get(result.status, "#6b7280")

        # Prepare steps table rows
        rows_html = []
        for step in result.steps:
            step_color = status_colors.get(step.status, "#6b7280")
            img_html = ""
            if step.screenshot_path and Path(step.screenshot_path).exists():
                try:
                    with open(step.screenshot_path, "rb") as img_f:
                        encoded = base64.b64encode(img_f.read()).decode("utf-8")
                    img_html = f'<div style="margin-top:8px;"><a href="data:image/png;base64,{encoded}" target="_blank"><img src="data:image/png;base64,{encoded}" style="max-width:240px;border-radius:6px;border:1px solid #cbd5e1;box-shadow:0 1px 3px rgba(0,0,0,0.1);"/></a></div>'
                except Exception:
                    img_html = f'<div style="color:#64748b;font-size:12px;">Screenshot: {step.screenshot_path}</div>'

            err_html = f'<div style="color:#dc2626;font-family:monospace;font-size:12px;margin-top:4px;">{step.error_message}</div>' if step.error_message else ''
            target_str = f'<span style="font-family:monospace;background:#f1f5f9;padding:2px 6px;border-radius:4px;font-size:12px;">{step.target_info}</span>' if step.target_info else '<span style="color:#94a3b8;">-</span>'
            val_str = f'<span style="font-family:monospace;background:#f8fafc;padding:2px 6px;border-radius:4px;font-size:12px;">{step.input_value}</span>' if step.input_value else '<span style="color:#94a3b8;">-</span>'

            rows_html.append(f"""
            <tr style="border-bottom:1px solid #e2e8f0;">
                <td style="padding:12px 16px;font-weight:600;color:#334155;">{step.step_number}</td>
                <td style="padding:12px 16px;">
                    <span style="display:inline-block;padding:2px 8px;border-radius:9999px;font-size:11px;font-weight:700;color:white;background:{step_color};">
                        {step.status}
                    </span>
                </td>
                <td style="padding:12px 16px;font-weight:600;color:#1e293b;">{step.action}</td>
                <td style="padding:12px 16px;color:#475569;">
                    {step.description}
                    {err_html}
                    {img_html}
                </td>
                <td style="padding:12px 16px;">{target_str}</td>
                <td style="padding:12px 16px;">{val_str}</td>
                <td style="padding:12px 16px;color:#64748b;font-size:13px;white-space:nowrap;">{step.duration_ms:.1f} ms</td>
            </tr>
            """)

        clarification_block = ""
        if result.clarification_prompt:
            clarification_block = f"""
            <div style="background:#eef2ff;border-left:4px solid #6366f1;padding:16px 20px;border-radius:0 8px 8px 0;margin-bottom:24px;">
                <h4 style="margin:0 0 6px 0;color:#3730a3;font-size:15px;font-weight:700;">Needs Clarification / Missing Information</h4>
                <p style="margin:0;color:#4338ca;font-size:14px;">{result.clarification_prompt}</p>
            </div>
            """

        error_block = ""
        if result.error_message and result.status in ("FAIL", "ERROR"):
            error_block = f"""
            <div style="background:#fef2f2;border-left:4px solid #ef4444;padding:16px 20px;border-radius:0 8px 8px 0;margin-bottom:24px;">
                <h4 style="margin:0 0 6px 0;color:#991b1b;font-size:15px;font-weight:700;">Execution Failure Diagnostic</h4>
                <p style="margin:0;color:#b91c1c;font-family:monospace;font-size:13px;white-space:pre-wrap;">{result.error_message}</p>
            </div>
            """

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test Run Report - {result.run_id}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #f8fafc;
            color: #0f172a;
            margin: 0;
            padding: 32px 24px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        .card {{
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -2px rgba(0, 0, 0, 0.05);
            border: 1px solid #e2e8f0;
            padding: 24px 28px;
            margin-bottom: 24px;
        }}
        .badge {{
            display: inline-block;
            padding: 4px 14px;
            border-radius: 9999px;
            font-size: 14px;
            font-weight: 700;
            color: white;
            background: {main_color};
            letter-spacing: 0.05em;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-top: 16px;
        }}
        .stat-box {{
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 14px 18px;
        }}
        .stat-label {{
            font-size: 12px;
            color: #64748b;
            text-transform: uppercase;
            font-weight: 600;
            letter-spacing: 0.05em;
        }}
        .stat-value {{
            font-size: 22px;
            font-weight: 700;
            color: #1e293b;
            margin-top: 4px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
            text-align: left;
        }}
        th {{
            background: #f1f5f9;
            padding: 12px 16px;
            color: #475569;
            font-weight: 700;
            text-transform: uppercase;
            font-size: 11px;
            letter-spacing: 0.05em;
            border-bottom: 2px solid #cbd5e1;
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="card">
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;">
                <div>
                    <h1 style="margin:0;font-size:24px;color:#0f172a;">AI Natural Language Test Report</h1>
                    <div style="color:#64748b;font-size:13px;margin-top:4px;">Run ID: {result.run_id} | Completed: {result.end_time}</div>
                </div>
                <div>
                    <span class="badge">{result.status}</span>
                </div>
            </div>

            <div style="margin-top:20px;padding:14px 18px;background:#f8fafc;border-radius:8px;border:1px solid #e2e8f0;">
                <div style="font-size:12px;color:#64748b;text-transform:uppercase;font-weight:600;">Instruction</div>
                <div style="font-size:16px;font-weight:600;color:#1e293b;margin-top:4px;">"{result.instruction}"</div>
                <div style="font-size:13px;color:#64748b;margin-top:4px;">Target URL: <a href="{result.base_url}" target="_blank" style="color:#2563eb;text-decoration:none;">{result.base_url}</a></div>
            </div>

            <!-- Stats -->
            <div class="stats-grid">
                <div class="stat-box">
                    <div class="stat-label">Duration</div>
                    <div class="stat-value">{result.duration_sec:.2f}s</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Total Steps</div>
                    <div class="stat-value">{result.total_steps}</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Passed Steps</div>
                    <div class="stat-value" style="color:#10b981;">{result.passed_steps}</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Failed Steps</div>
                    <div class="stat-value" style="color:{'#ef4444' if result.failed_steps > 0 else '#64748b'};">{result.failed_steps}</div>
                </div>
            </div>
        </div>

        {clarification_block}
        {error_block}

        <!-- Steps Table -->
        <div class="card" style="padding:0;overflow:hidden;">
            <div style="padding:18px 24px;border-bottom:1px solid #e2e8f0;background:#fafafa;">
                <h3 style="margin:0;font-size:16px;color:#1e293b;">Execution Steps & Evidence</h3>
            </div>
            <div style="overflow-x:auto;">
                <table>
                    <thead>
                        <tr>
                            <th style="width:40px;">#</th>
                            <th style="width:90px;">Status</th>
                            <th style="width:120px;">Action</th>
                            <th>Description & Evidence</th>
                            <th>Target</th>
                            <th>Value</th>
                            <th style="width:90px;">Duration</th>
                        </tr>
                    </thead>
                    <tbody>
                        {''.join(rows_html) if rows_html else '<tr><td colspan="7" style="padding:24px;text-align:center;color:#64748b;">No steps executed.</td></tr>'}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</body>
</html>"""

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return report_path

    def print_console_summary(self, result: TestRunResult) -> None:
        """Display an eye-catching, structured terminal summary using Rich."""
        color = "green" if result.status == "PASS" else ("red" if result.status in ("FAIL", "ERROR") else "yellow")

        # Top summary panel
        title = f"[bold {color}]TEST RUN RESULT: {result.status}[/bold {color}]"
        summary_text = (
            f"[bold]Instruction:[/bold] {result.instruction}\n"
            f"[bold]Base URL:[/bold] {result.base_url}\n"
            f"[bold]Duration:[/bold] {result.duration_sec:.2f}s | "
            f"[bold]Steps:[/bold] {result.total_steps} (Passed: {result.passed_steps}, Failed: {result.failed_steps})"
        )
        if result.clarification_prompt:
            summary_text += f"\n[bold yellow]Clarification:[/bold yellow] {result.clarification_prompt}"
        if result.error_message:
            summary_text += f"\n[bold red]Error:[/bold red] {result.error_message}"

        self.console.print(Panel(summary_text, title=title, border_style=color))

        # Steps table
        if result.steps:
            table = Table(title="Step Execution Breakdown", show_header=True, header_style="bold cyan")
            table.add_column("#", justify="right", style="dim", width=4)
            table.add_column("Status", justify="center", width=8)
            table.add_column("Action", style="bold", width=14)
            table.add_column("Description", style="white")
            table.add_column("Duration", justify="right", width=10)

            for step in result.steps:
                st_color = "green" if step.status == "PASS" else ("red" if step.status in ("FAIL", "ERROR") else "dim")
                status_badge = f"[{st_color}]{step.status}[/{st_color}]"
                desc = step.description
                if step.error_message:
                    desc += f"\n[red]-> {step.error_message}[/red]"
                table.add_row(
                    str(step.step_number),
                    status_badge,
                    step.action,
                    desc,
                    f"{step.duration_ms:.1f}ms",
                )

            self.console.print(table)

