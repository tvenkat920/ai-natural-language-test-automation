"""Unit tests for ResultReporter — JSON/HTML generation and console output."""
import json
import pytest
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reporting.reporter import ResultReporter, StepResult, TestRunResult


@pytest.fixture
def tmp_reports(tmp_path):
    return tmp_path / "reports"


def make_result(
    status="PASS",
    steps=None,
    run_id="test-run-001",
    instruction="Open the site and verify title",
    base_url="https://example.com",
    error_message=None,
    clarification_prompt=None,
) -> TestRunResult:
    if steps is None:
        steps = [
            StepResult(
                step_number=1,
                action="navigate",
                description="Go to site",
                status="PASS",
                duration_ms=324.5,
            ),
            StepResult(
                step_number=2,
                action="assert_title",
                description="Check title",
                status=status if status != "PASS" else "PASS",
                duration_ms=55.1,
                error_message=error_message if status != "PASS" else None,
            ),
        ]
    now = datetime.now().isoformat()
    return TestRunResult(
        run_id=run_id,
        instruction=instruction,
        base_url=base_url,
        status=status,
        start_time=now,
        end_time=now,
        duration_sec=0.5,
        total_steps=len(steps),
        passed_steps=sum(1 for s in steps if s.status == "PASS"),
        failed_steps=sum(1 for s in steps if s.status in ("FAIL", "ERROR")),
        steps=steps,
        error_message=error_message,
        clarification_prompt=clarification_prompt,
    )


class TestJSONReport:
    def test_json_file_created(self, tmp_reports):
        reporter = ResultReporter(reports_dir=tmp_reports)
        result = make_result()
        path = reporter.generate_json_report(result)
        assert path.exists()
        assert path.suffix == ".json"

    def test_json_contains_correct_status(self, tmp_reports):
        reporter = ResultReporter(reports_dir=tmp_reports)
        result = make_result(status="FAIL", error_message="Assertion failed")
        path = reporter.generate_json_report(result)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["status"] == "FAIL"
        assert data["error_message"] == "Assertion failed"

    def test_json_contains_all_steps(self, tmp_reports):
        reporter = ResultReporter(reports_dir=tmp_reports)
        result = make_result()
        path = reporter.generate_json_report(result)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert len(data["steps"]) == 2

    def test_json_run_id_in_filename(self, tmp_reports):
        reporter = ResultReporter(reports_dir=tmp_reports)
        result = make_result(run_id="unique-run-xyz")
        path = reporter.generate_json_report(result)
        assert "unique-run-xyz" in path.name


class TestHTMLReport:
    def test_html_file_created(self, tmp_reports):
        reporter = ResultReporter(reports_dir=tmp_reports)
        result = make_result()
        path = reporter.generate_html_report(result)
        assert path.exists()
        assert path.suffix == ".html"

    def test_html_contains_status(self, tmp_reports):
        reporter = ResultReporter(reports_dir=tmp_reports)
        result = make_result(status="PASS")
        path = reporter.generate_html_report(result)
        content = path.read_text(encoding="utf-8")
        assert "PASS" in content

    def test_html_contains_instruction(self, tmp_reports):
        reporter = ResultReporter(reports_dir=tmp_reports)
        result = make_result(instruction="Click the magic button")
        path = reporter.generate_html_report(result)
        content = path.read_text(encoding="utf-8")
        assert "Click the magic button" in content

    def test_html_fail_shows_error(self, tmp_reports):
        reporter = ResultReporter(reports_dir=tmp_reports)
        result = make_result(status="FAIL", error_message="Button not found")
        path = reporter.generate_html_report(result)
        content = path.read_text(encoding="utf-8")
        assert "Button not found" in content

    def test_html_needs_clarification_shows_prompt(self, tmp_reports):
        reporter = ResultReporter(reports_dir=tmp_reports)
        result = make_result(
            status="NEEDS_CLARIFICATION",
            clarification_prompt="Please provide login credentials.",
        )
        path = reporter.generate_html_report(result)
        content = path.read_text(encoding="utf-8")
        assert "Please provide login credentials." in content

    def test_html_is_valid_html(self, tmp_reports):
        reporter = ResultReporter(reports_dir=tmp_reports)
        result = make_result()
        path = reporter.generate_html_report(result)
        content = path.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content
        assert "<html" in content
        assert "</html>" in content


class TestConsoleSummary:
    def test_console_summary_runs_without_error(self, tmp_reports, capsys):
        reporter = ResultReporter(reports_dir=tmp_reports)
        result = make_result()
        # Should not raise
        reporter.print_console_summary(result)

    def test_pass_result_runs_without_error(self, tmp_reports):
        reporter = ResultReporter(reports_dir=tmp_reports)
        result = make_result(status="PASS")
        reporter.print_console_summary(result)

    def test_fail_result_runs_without_error(self, tmp_reports):
        reporter = ResultReporter(reports_dir=tmp_reports)
        result = make_result(
            status="FAIL",
            error_message="Step 2 failed: element not found",
        )
        reporter.print_console_summary(result)

