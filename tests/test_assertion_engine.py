"""Unit tests for AssertionEngine — verification logic and failure handling."""
import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from assertions.engine import AssertionEngine, AssertionFailureError, AssertionResult


@pytest.fixture
def engine():
    return AssertionEngine(default_timeout_ms=1000)


class TestAssertionVisible:
    def test_visible_passes(self, engine):
        locator = MagicMock()
        locator.wait_for.return_value = None
        locator.is_visible.return_value = True

        res = engine.assert_visible(locator, description="Submit button")
        assert res.passed is True
        assert res.assertion_type == "assert_visible"

    def test_hidden_raises_assertion_failure_error(self, engine):
        locator = MagicMock()
        locator.wait_for.return_value = None
        locator.is_visible.return_value = False

        with pytest.raises(AssertionFailureError) as exc_info:
            engine.assert_visible(locator, description="Hidden dialog")

        assert exc_info.value.assertion_type == "assert_visible"
        assert "not visible" in str(exc_info.value)


class TestAssertionText:
    def test_text_contains_passes(self, engine):
        locator = MagicMock()
        locator.wait_for.return_value = None
        locator.text_content.return_value = "Welcome back, Alice! Your account is active."

        res = engine.assert_text(locator, expected_text="Welcome back", exact=False)
        assert res.passed is True
        assert res.actual == "Welcome back, Alice! Your account is active."

    def test_text_exact_passes(self, engine):
        locator = MagicMock()
        locator.wait_for.return_value = None
        locator.text_content.return_value = "Dashboard"

        res = engine.assert_text(locator, expected_text="Dashboard", exact=True)
        assert res.passed is True

    def test_text_mismatch_raises_assertion_failure_error(self, engine):
        locator = MagicMock()
        locator.wait_for.return_value = None
        locator.text_content.return_value = "Login Failed: Invalid credentials"

        with pytest.raises(AssertionFailureError) as exc_info:
            engine.assert_text(locator, expected_text="Welcome to Dashboard", exact=False)

        assert exc_info.value.assertion_type == "assert_text"
        assert exc_info.value.expected == "Welcome to Dashboard"
        assert "Login Failed" in exc_info.value.actual


class TestAssertionURL:
    def test_url_contains_passes(self, engine):
        page = MagicMock()
        page.wait_for_url.return_value = None
        page.url = "https://example.com/dashboard/overview?tab=stats"

        res = engine.assert_url(page, expected_url_pattern="/dashboard")
        assert res.passed is True

    def test_url_exact_passes(self, engine):
        page = MagicMock()
        page.url = "https://example.com/login"

        res = engine.assert_url(page, expected_url_pattern="https://example.com/login", exact=True)
        assert res.passed is True

    def test_url_exact_mismatch_raises_assertion_failure_error(self, engine):
        page = MagicMock()
        page.url = "https://example.com/404"

        with pytest.raises(AssertionFailureError) as exc_info:
            engine.assert_url(page, expected_url_pattern="https://example.com/dashboard", exact=True)

        assert exc_info.value.assertion_type == "assert_url"
        assert exc_info.value.expected == "https://example.com/dashboard"
        assert exc_info.value.actual == "https://example.com/404"


class TestAssertionTitle:
    def test_title_contains_passes(self, engine):
        page = MagicMock()
        page.title.return_value = "Customer Portal | My Enterprise App"

        res = engine.assert_title(page, expected_title="Customer Portal")
        assert res.passed is True

    def test_title_mismatch_raises_assertion_failure_error(self, engine):
        page = MagicMock()
        page.title.return_value = "Error 500 - Server Error"

        with pytest.raises(AssertionFailureError) as exc_info:
            engine.assert_title(page, expected_title="Customer Dashboard")

        assert exc_info.value.assertion_type == "assert_title"
        assert "Customer Dashboard" in str(exc_info.value)

