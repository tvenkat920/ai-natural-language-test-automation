"""Unit tests for SmartLocator and locator ambiguity detection."""
import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from locators.smart_locator import SmartLocator
from locators.exceptions import LocatorAmbiguityError, LocatorNotFoundError
from planner.models import LocatorStrategy, SmartLocatorTarget


class TestSmartLocatorUnit:
    def test_explicit_role_locator_called(self):
        page = MagicMock()
        mock_loc = MagicMock()
        mock_loc.first.wait_for.return_value = None
        mock_loc.count.return_value = 1
        page.get_by_role.return_value = mock_loc

        sl = SmartLocator(page=page)
        target = SmartLocatorTarget(
            strategy=LocatorStrategy.ROLE,
            value="Submit",
            role="button",
            name="Submit",
        )
        result = sl.resolve(target)
        page.get_by_role.assert_called_once_with("button", name="Submit", exact=False)
        assert result == mock_loc

    def test_explicit_label_locator_called(self):
        page = MagicMock()
        mock_loc = MagicMock()
        mock_loc.first.wait_for.return_value = None
        mock_loc.count.return_value = 1
        page.get_by_label.return_value = mock_loc

        sl = SmartLocator(page=page)
        target = SmartLocatorTarget(
            strategy=LocatorStrategy.LABEL,
            value="Username",
            exact=True,
        )
        result = sl.resolve(target)
        page.get_by_label.assert_called_once_with("Username", exact=True)
        assert result == mock_loc

    def test_explicit_placeholder_locator_called(self):
        page = MagicMock()
        mock_loc = MagicMock()
        mock_loc.first.wait_for.return_value = None
        mock_loc.count.return_value = 1
        page.get_by_placeholder.return_value = mock_loc

        sl = SmartLocator(page=page)
        target = SmartLocatorTarget(
            strategy=LocatorStrategy.PLACEHOLDER,
            value="Search...",
        )
        result = sl.resolve(target)
        page.get_by_placeholder.assert_called_once_with("Search...", exact=False)
        assert result == mock_loc

    def test_explicit_test_id_locator_called(self):
        page = MagicMock()
        mock_loc = MagicMock()
        mock_loc.first.wait_for.return_value = None
        mock_loc.count.return_value = 1
        page.get_by_test_id.return_value = mock_loc

        sl = SmartLocator(page=page)
        target = SmartLocatorTarget(
            strategy=LocatorStrategy.TEST_ID,
            value="login-btn",
        )
        result = sl.resolve(target)
        page.get_by_test_id.assert_called_once_with("login-btn")
        assert result == mock_loc

    def test_explicit_index_bypasses_ambiguity(self):
        """When index is explicitly provided (e.g., index=0), nth(0) is returned without ambiguity error."""
        page = MagicMock()
        mock_loc = MagicMock()
        mock_nth = MagicMock()
        mock_loc.nth.return_value = mock_nth
        page.locator.return_value = mock_loc

        sl = SmartLocator(page=page)
        target = SmartLocatorTarget(
            strategy=LocatorStrategy.CSS,
            value=".item",
            index=0,
        )
        result = sl.resolve(target)
        mock_loc.nth.assert_called_once_with(0)
        assert result == mock_nth

    def test_ambiguity_raises_locator_ambiguity_error(self):
        """When multiple elements match and no index is provided, LocatorAmbiguityError must be raised."""
        page = MagicMock()
        mock_loc = MagicMock()
        mock_loc.first.wait_for.return_value = None
        mock_loc.count.return_value = 3  # Ambiguous match!

        # When visible=true filter is attempted, still 3 visible
        mock_visible = MagicMock()
        mock_visible.count.return_value = 3
        mock_loc.locator.return_value = mock_visible

        # Candidate element inspection mock
        mock_candidate = MagicMock()
        mock_candidate.evaluate.return_value = "button"
        mock_candidate.text_content.return_value = "Submit Order"
        mock_candidate.get_attribute.return_value = "btn-primary"
        mock_visible.nth.return_value = mock_candidate

        page.get_by_role.return_value = mock_loc

        sl = SmartLocator(page=page)
        target = SmartLocatorTarget(
            strategy=LocatorStrategy.ROLE,
            value="Submit",
            role="button",
        )
        with pytest.raises(LocatorAmbiguityError) as exc_info:
            sl.resolve(target)

        assert exc_info.value.match_count == 3
        assert "Ambiguous target" in str(exc_info.value)
        assert exc_info.value.selector_tried == "Submit"

    def test_locator_not_found_raises_locator_not_found_error(self):
        """When element doesn't exist and wait times out, LocatorNotFoundError is raised."""
        page = MagicMock()
        mock_loc = MagicMock()
        mock_loc.first.wait_for.side_effect = TimeoutError("Timed out waiting for element")
        page.locator.return_value = mock_loc

        sl = SmartLocator(page=page)
        target = SmartLocatorTarget(
            strategy=LocatorStrategy.CSS,
            value="#ghost-element",
        )
        with pytest.raises(LocatorNotFoundError) as exc_info:
            sl.resolve(target)

        assert "#ghost-element" in exc_info.value.selector_tried

