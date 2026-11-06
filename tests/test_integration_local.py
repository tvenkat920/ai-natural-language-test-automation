"""
Integration tests against the local sample HTML page.
Runs real Playwright browser automation — requires Playwright installed.
These tests are intentionally marked 'integration' to be runnable separately.
"""
import sys
from pathlib import Path
from datetime import datetime

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def make_plan_dict(base_url: str, steps: list, title: str = "Integration Test") -> dict:
    """Helper to build a valid plan dict for injection into MockLLMProvider."""
    return {
        "title": title,
        "description": "Integration test against local HTML sample page",
        "base_url": base_url,
        "requires_clarification": False,
        "missing_information": [],
        "clarification_prompt": None,
        "steps": steps,
    }


@pytest.mark.integration
class TestSamplePageNavigation:
    """Verifies navigation and page load on the local sample page."""

    def test_navigate_and_title(self, sample_html_url):
        """Navigate to sample page and assert the page title is correct."""
        from app.runner import run_test
        steps = [
            {"step_number": 1, "action": "navigate", "description": "Open sample page", "url": sample_html_url},
            {
                "step_number": 2,
                "action": "assert_title",
                "description": "Verify page title contains 'AI Test Automation'",
                "expected_title": "AI Test Automation",
            },
            {"step_number": 3, "action": "screenshot", "description": "Evidence screenshot", "screenshot_name": "nav_title"},
        ]
        result = run_test(
            instruction="Open the sample page and verify its title",
            base_url=sample_html_url,
            headless=True,
            slow_mo=0,
            mock_llm_response=make_plan_dict(sample_html_url, steps),
        )
        assert result.status == "PASS", f"Test failed: {result.error_message}"
        assert result.passed_steps >= 2

    def test_header_is_visible(self, sample_html_url):
        """Verify the page header banner is visible."""
        from app.runner import run_test
        steps = [
            {"step_number": 1, "action": "navigate", "description": "Open page", "url": sample_html_url},
            {
                "step_number": 2,
                "action": "assert_visible",
                "description": "Verify page heading is visible",
                "target": {
                    "strategy": "role",
                    "value": "banner",
                    "role": "banner",
                    "exact": False,
                    "description": "Page banner/header",
                },
            },
            {"step_number": 3, "action": "screenshot", "description": "Screenshot"},
        ]
        result = run_test(
            instruction="Verify the page header is visible",
            base_url=sample_html_url,
            headless=True,
            slow_mo=0,
            mock_llm_response=make_plan_dict(sample_html_url, steps),
        )
        assert result.status == "PASS", f"Failed: {result.error_message}"


@pytest.mark.integration
class TestSamplePageLoginForm:
    """Verifies login form interaction and success/failure states."""

    def test_valid_login_shows_success(self, sample_html_url):
        """Log in with correct credentials and verify success message appears."""
        from app.runner import run_test
        steps = [
            {"step_number": 1, "action": "navigate", "description": "Open page", "url": sample_html_url},
            {
                "step_number": 2,
                "action": "fill",
                "description": "Enter username",
                "target": {"strategy": "label", "value": "Username", "exact": True, "description": "Username field"},
                "value": "admin",
            },
            {
                "step_number": 3,
                "action": "fill",
                "description": "Enter password",
                "target": {"strategy": "label", "value": "Password", "exact": True, "description": "Password field"},
                "value": "admin123",
            },
            {
                "step_number": 4,
                "action": "click",
                "description": "Click Login button",
                "target": {"strategy": "role", "value": "Login", "role": "button", "name": "Login", "exact": True, "description": "Login button"},
            },
            {
                "step_number": 5,
                "action": "assert_visible",
                "description": "Verify success message is visible",
                "target": {"strategy": "text", "value": "successfully logged in", "exact": False, "description": "Login success text"},
            },
            {"step_number": 6, "action": "screenshot", "description": "Login success screenshot", "screenshot_name": "login_success"},
        ]
        result = run_test(
            instruction="Log in with admin credentials and verify success",
            base_url=sample_html_url,
            headless=True,
            slow_mo=0,
            mock_llm_response=make_plan_dict(sample_html_url, steps, title="Login Success Test"),
        )
        assert result.status == "PASS", f"Login test failed: {result.error_message}"

    def test_invalid_login_shows_error(self, sample_html_url):
        """Log in with wrong credentials and verify error message appears."""
        from app.runner import run_test
        steps = [
            {"step_number": 1, "action": "navigate", "description": "Open page", "url": sample_html_url},
            {
                "step_number": 2,
                "action": "fill",
                "description": "Enter wrong username",
                "target": {"strategy": "label", "value": "Username", "exact": True, "description": "Username field"},
                "value": "wrong_user",
            },
            {
                "step_number": 3,
                "action": "fill",
                "description": "Enter wrong password",
                "target": {"strategy": "label", "value": "Password", "exact": True, "description": "Password field"},
                "value": "wrong_pass",
            },
            {
                "step_number": 4,
                "action": "click",
                "description": "Click Login",
                "target": {"strategy": "role", "value": "Login", "role": "button", "name": "Login", "exact": True, "description": "Login button"},
            },
            {
                "step_number": 5,
                "action": "assert_visible",
                "description": "Verify error message is visible",
                "target": {"strategy": "text", "value": "Invalid credentials", "exact": False, "description": "Error message"},
            },
            {"step_number": 6, "action": "screenshot", "description": "Screenshot"},
        ]
        result = run_test(
            instruction="Log in with wrong credentials and verify error message",
            base_url=sample_html_url,
            headless=True,
            slow_mo=0,
            mock_llm_response=make_plan_dict(sample_html_url, steps, title="Login Failure Test"),
        )
        assert result.status == "PASS", f"Test failed: {result.error_message}"


@pytest.mark.integration
class TestSamplePageCounter:
    """Verifies the interactive counter element on the sample page."""

    def test_increment_counter(self, sample_html_url):
        """Click Increment and verify counter value changes."""
        from app.runner import run_test
        steps = [
            {"step_number": 1, "action": "navigate", "description": "Open page", "url": sample_html_url},
            {
                "step_number": 2,
                "action": "click",
                "description": "Click Increment button",
                "target": {"strategy": "role", "value": "Increment counter", "role": "button", "name": "Increment counter", "exact": False, "description": "Increment button"},
            },
            {
                "step_number": 3,
                "action": "assert_text",
                "description": "Verify counter shows 1",
                "target": {"strategy": "css", "value": "#counter-value", "exact": True, "description": "Counter display"},
                "expected_text": "1",
            },
            {"step_number": 4, "action": "screenshot", "description": "Counter screenshot"},
        ]
        result = run_test(
            instruction="Click increment and verify counter increases",
            base_url=sample_html_url,
            headless=True,
            slow_mo=0,
            mock_llm_response=make_plan_dict(sample_html_url, steps, title="Counter Increment Test"),
        )
        assert result.status == "PASS", f"Counter test failed: {result.error_message}"


@pytest.mark.integration
class TestAssertionFailureReporting:
    """Verifies that FAIL is correctly reported when assertions do not pass — no fabricated PASS."""

    def test_wrong_title_assertion_reports_fail(self, sample_html_url):
        """Assert an intentionally wrong title — must report FAIL, never PASS."""
        from app.runner import run_test
        steps = [
            {"step_number": 1, "action": "navigate", "description": "Open page", "url": sample_html_url},
            {
                "step_number": 2,
                "action": "assert_title",
                "description": "Assert wrong title (intentional FAIL)",
                "expected_title": "This Title Does Not Exist XYZ987",
            },
            {"step_number": 3, "action": "screenshot", "description": "Screenshot"},
        ]
        result = run_test(
            instruction="Verify the page title is 'This Title Does Not Exist XYZ987'",
            base_url=sample_html_url,
            headless=True,
            slow_mo=0,
            mock_llm_response=make_plan_dict(sample_html_url, steps),
        )
        # The assertion MUST fail — a PASS here would be a bug
        assert result.status == "FAIL", (
            f"Expected FAIL for impossible assertion, got {result.status}. "
            "This indicates fabricated results — a critical defect."
        )
        assert result.failed_steps >= 1

    def test_missing_element_reports_fail(self, sample_html_url):
        """Try to find an element that doesn't exist — must report FAIL."""
        from app.runner import run_test
        steps = [
            {"step_number": 1, "action": "navigate", "description": "Open page", "url": sample_html_url},
            {
                "step_number": 2,
                "action": "assert_visible",
                "description": "Assert non-existent element is visible",
                "target": {"strategy": "css", "value": "#this-element-does-not-exist", "exact": True, "description": "Ghost element"},
            },
            {"step_number": 3, "action": "screenshot", "description": "Screenshot"},
        ]
        result = run_test(
            instruction="Verify a non-existent element is visible",
            base_url=sample_html_url,
            headless=True,
            slow_mo=0,
            mock_llm_response=make_plan_dict(sample_html_url, steps),
        )
        assert result.status in ("FAIL", "ERROR"), (
            f"Expected FAIL/ERROR for non-existent element, got {result.status}."
        )

