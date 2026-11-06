"""AssertionEngine: Strict verification of browser DOM states, texts, URLs, and page titles."""
import re
from dataclasses import dataclass
from typing import Any, Optional


class AssertionFailureError(AssertionError):
    """Raised when an explicit assertion expectation fails."""

    def __init__(self, message: str, expected: Any, actual: Any, assertion_type: str):
        super().__init__(message)
        self.expected = expected
        self.actual = actual
        self.assertion_type = assertion_type


@dataclass
class AssertionResult:
    """Detailed outcome of an assertion evaluation."""
    passed: bool
    assertion_type: str
    expected: Any
    actual: Any
    message: str


class AssertionEngine:
    """Verifies visibility, text content, current URL, and document title against expectations."""

    def __init__(self, default_timeout_ms: int = 5000):
        self.default_timeout_ms = default_timeout_ms

    def assert_visible(
        self,
        locator: Any,
        description: str = "",
        timeout_ms: Optional[int] = None,
    ) -> AssertionResult:
        """Verify that the target element is visible in the viewport."""
        timeout = timeout_ms if timeout_ms is not None else self.default_timeout_ms
        try:
            locator.wait_for(state="visible", timeout=timeout)
            is_vis = locator.is_visible()
            if not is_vis:
                raise AssertionFailureError(
                    message=f"Element '{description}' was expected to be visible, but is not visible.",
                    expected="visible",
                    actual="hidden or detached",
                    assertion_type="assert_visible",
                )
            return AssertionResult(
                passed=True,
                assertion_type="assert_visible",
                expected="visible",
                actual="visible",
                message=f"Verified element '{description}' is visible.",
            )
        except Exception as e:
            if isinstance(e, AssertionFailureError):
                raise
            raise AssertionFailureError(
                message=f"Element '{description}' was not visible within {timeout}ms: {e}",
                expected="visible",
                actual="not visible / timed out",
                assertion_type="assert_visible",
            ) from e

    def assert_text(
        self,
        locator: Any,
        expected_text: str,
        exact: bool = False,
        description: str = "",
        timeout_ms: Optional[int] = None,
    ) -> AssertionResult:
        """Verify that the element contains (or exactly matches) the expected text."""
        timeout = timeout_ms if timeout_ms is not None else self.default_timeout_ms
        try:
            locator.wait_for(state="attached", timeout=timeout)
            actual_text = (locator.text_content(timeout=timeout) or "").strip()
            expected_clean = expected_text.strip()

            if exact:
                passed = actual_text == expected_clean
            else:
                passed = expected_clean.lower() in actual_text.lower()

            if not passed:
                raise AssertionFailureError(
                    message=(
                        f"Text assertion failed for '{description}'. "
                        f"Expected {'exact ' if exact else ''}'{expected_clean}', "
                        f"found '{actual_text}'."
                    ),
                    expected=expected_clean,
                    actual=actual_text,
                    assertion_type="assert_text",
                )

            return AssertionResult(
                passed=True,
                assertion_type="assert_text",
                expected=expected_clean,
                actual=actual_text,
                message=f"Verified text for '{description}' matches '{expected_clean}'.",
            )
        except Exception as e:
            if isinstance(e, AssertionFailureError):
                raise
            raise AssertionFailureError(
                message=f"Failed retrieving text for element '{description}': {e}",
                expected=expected_text,
                actual=f"Error: {e}",
                assertion_type="assert_text",
            ) from e

    def assert_url(
        self,
        page: Any,
        expected_url_pattern: str,
        exact: bool = False,
        timeout_ms: Optional[int] = None,
    ) -> AssertionResult:
        """Verify that current page URL contains or matches expected URL substring/regex."""
        timeout = timeout_ms if timeout_ms is not None else self.default_timeout_ms
        expected_clean = expected_url_pattern.strip()

        # If exact match
        if exact:
            current_url = page.url
            if current_url != expected_clean:
                raise AssertionFailureError(
                    message=f"URL assertion failed. Expected exact URL '{expected_clean}', got '{current_url}'.",
                    expected=expected_clean,
                    actual=current_url,
                    assertion_type="assert_url",
                )
            return AssertionResult(
                passed=True,
                assertion_type="assert_url",
                expected=expected_clean,
                actual=current_url,
                message=f"Verified current URL matches '{expected_clean}'.",
            )

        # Wait or poll for URL pattern
        try:
            # Try waiting for URL to contain expected pattern
            page.wait_for_url(re.compile(re.escape(expected_clean), re.IGNORECASE), timeout=timeout)
            current_url = page.url
            return AssertionResult(
                passed=True,
                assertion_type="assert_url",
                expected=expected_clean,
                actual=current_url,
                message=f"Verified current URL '{current_url}' contains '{expected_clean}'.",
            )
        except Exception:
            current_url = page.url
            if expected_clean.lower() in current_url.lower():
                return AssertionResult(
                    passed=True,
                    assertion_type="assert_url",
                    expected=expected_clean,
                    actual=current_url,
                    message=f"Verified current URL '{current_url}' contains '{expected_clean}'.",
                )
            raise AssertionFailureError(
                message=f"URL assertion failed. Expected URL containing '{expected_clean}', actual URL is '{current_url}'.",
                expected=expected_clean,
                actual=current_url,
                assertion_type="assert_url",
            )

    def assert_title(
        self,
        page: Any,
        expected_title: str,
        exact: bool = False,
    ) -> AssertionResult:
        """Verify the document title."""
        current_title = (page.title() or "").strip()
        expected_clean = expected_title.strip()

        if exact:
            passed = current_title == expected_clean
        else:
            passed = expected_clean.lower() in current_title.lower()

        if not passed:
            raise AssertionFailureError(
                message=f"Title assertion failed. Expected '{expected_clean}', found '{current_title}'.",
                expected=expected_clean,
                actual=current_title,
                assertion_type="assert_title",
            )

        return AssertionResult(
            passed=True,
            assertion_type="assert_title",
            expected=expected_clean,
            actual=current_title,
            message=f"Verified page title matches '{expected_clean}'.",
        )

