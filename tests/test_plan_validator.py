"""Unit tests for PlanValidator."""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from planner.models import ActionStep, ActionType, SmartLocatorTarget, TestPlan, LocatorStrategy
from planner.validator import PlanValidator, PlanValidationError
from security.manager import SecurityManager, SecurityViolationError


@pytest.fixture
def validator():
    return PlanValidator(max_actions=10)


def make_navigate_step(url: str, num: int = 1) -> ActionStep:
    return ActionStep(step_number=num, action=ActionType.NAVIGATE, description=f"Go to {url}", url=url)


def make_click_step(value: str, num: int = 2) -> ActionStep:
    return ActionStep(
        step_number=num,
        action=ActionType.CLICK,
        description=f"Click {value}",
        target=SmartLocatorTarget(value=value, strategy=LocatorStrategy.AUTO),
    )


def make_fill_step(target_value: str, fill_value: str, num: int = 3) -> ActionStep:
    return ActionStep(
        step_number=num,
        action=ActionType.FILL,
        description="Fill input",
        target=SmartLocatorTarget(value=target_value, strategy=LocatorStrategy.AUTO),
        value=fill_value,
    )


def make_assert_text_step(target_value: str, expected: str, num: int = 4) -> ActionStep:
    return ActionStep(
        step_number=num,
        action=ActionType.ASSERT_TEXT,
        description="Assert text",
        target=SmartLocatorTarget(value=target_value, strategy=LocatorStrategy.AUTO),
        expected_text=expected,
    )


def make_simple_plan(steps=None, base_url="https://example.com") -> TestPlan:
    if steps is None:
        steps = [make_navigate_step(base_url)]
    return TestPlan(title="Test", base_url=base_url, steps=steps)


# ---- URL Validation ----

class TestURLValidation:
    def test_valid_https_url_accepted(self, validator):
        plan = make_simple_plan([make_navigate_step("https://example.com")])
        result = validator.validate_plan(plan)
        assert result is not None

    def test_valid_http_url_accepted(self, validator):
        plan = make_simple_plan([make_navigate_step("http://example.com")])
        result = validator.validate_plan(plan)
        assert result is not None

    def test_javascript_url_rejected(self, validator):
        plan = make_simple_plan([make_navigate_step("javascript:alert(1)")])
        with pytest.raises(PlanValidationError, match="Insecure or invalid URL"):
            validator.validate_plan(plan)

    def test_file_url_rejected(self, validator):
        plan = make_simple_plan([make_navigate_step("file:///etc/passwd")])
        with pytest.raises(PlanValidationError, match="Insecure or invalid URL"):
            validator.validate_plan(plan)

    def test_missing_url_in_navigate_rejected(self, validator):
        step = ActionStep(step_number=1, action=ActionType.NAVIGATE, description="go", url=None)
        plan = make_simple_plan([step])
        with pytest.raises(PlanValidationError, match="Missing required 'url'"):
            validator.validate_plan(plan)

    def test_invalid_base_url_rejected(self, validator):
        plan = make_simple_plan(
            steps=[make_navigate_step("https://example.com")],
            base_url="ftp://evil.com"
        )
        with pytest.raises(PlanValidationError, match="Invalid base URL"):
            validator.validate_plan(plan)


# ---- Action Validation ----

class TestActionValidation:
    def test_click_without_target_rejected(self, validator):
        step = ActionStep(step_number=2, action=ActionType.CLICK, description="click")
        plan = make_simple_plan([make_navigate_step("https://ex.com", 1), step])
        with pytest.raises(PlanValidationError, match="Missing required locator 'target'"):
            validator.validate_plan(plan)

    def test_fill_without_value_rejected(self, validator):
        step = ActionStep(
            step_number=2,
            action=ActionType.FILL,
            description="fill",
            target=SmartLocatorTarget(value="input", strategy=LocatorStrategy.AUTO),
            value=None,  # missing
        )
        plan = make_simple_plan([make_navigate_step("https://ex.com", 1), step])
        with pytest.raises(PlanValidationError, match="Missing required 'value'"):
            validator.validate_plan(plan)

    def test_assert_text_without_expected_rejected(self, validator):
        step = ActionStep(
            step_number=2,
            action=ActionType.ASSERT_TEXT,
            description="assert text",
            target=SmartLocatorTarget(value="h1", strategy=LocatorStrategy.AUTO),
            expected_text=None,
        )
        plan = make_simple_plan([make_navigate_step("https://ex.com", 1), step])
        with pytest.raises(PlanValidationError, match="Missing 'expected_text'"):
            validator.validate_plan(plan)

    def test_valid_press_step(self, validator):
        step = ActionStep(step_number=2, action=ActionType.PRESS, description="Press Enter", value="Enter")
        plan = make_simple_plan([make_navigate_step("https://ex.com", 1), step])
        result = validator.validate_plan(plan)
        assert result is not None

    def test_press_without_value_rejected(self, validator):
        step = ActionStep(step_number=2, action=ActionType.PRESS, description="Press key", value=None)
        plan = make_simple_plan([make_navigate_step("https://ex.com", 1), step])
        with pytest.raises(PlanValidationError, match="Missing key 'value'"):
            validator.validate_plan(plan)

    def test_assert_url_without_pattern_rejected(self, validator):
        step = ActionStep(step_number=2, action=ActionType.ASSERT_URL, description="assert url")
        plan = make_simple_plan([make_navigate_step("https://ex.com", 1), step])
        with pytest.raises(PlanValidationError, match="Missing target URL"):
            validator.validate_plan(plan)

    def test_assert_title_without_expected_rejected(self, validator):
        step = ActionStep(step_number=2, action=ActionType.ASSERT_TITLE, description="assert title")
        plan = make_simple_plan([make_navigate_step("https://ex.com", 1), step])
        with pytest.raises(PlanValidationError, match="Missing expected title"):
            validator.validate_plan(plan)


# ---- Plan Structural Validation ----

class TestPlanStructure:
    def test_empty_steps_rejected(self, validator):
        plan = TestPlan(title="Empty", base_url="https://example.com", steps=[])
        with pytest.raises(PlanValidationError, match="no executable steps"):
            validator.validate_plan(plan)

    def test_too_many_steps_rejected(self):
        v = PlanValidator(max_actions=3)
        steps = [make_navigate_step("https://ex.com", i + 1) for i in range(4)]
        plan = make_simple_plan(steps)
        with pytest.raises(PlanValidationError, match="exceeds maximum allowed"):
            v.validate_plan(plan)

    def test_clarification_plan_passes_through(self, validator):
        plan = TestPlan(
            title="Needs info",
            base_url="https://example.com",
            steps=[],
            requires_clarification=True,
            missing_information=["username", "password"],
        )
        result = validator.validate_plan(plan)
        assert result.requires_clarification is True


# ---- Security Checks ----

class TestSecurityValidation:
    def test_eval_in_description_rejected(self, validator):
        step = ActionStep(
            step_number=1,
            action=ActionType.NAVIGATE,
            description="eval(malicious_code())",
            url="https://example.com",
        )
        plan = make_simple_plan([step])
        with pytest.raises(PlanValidationError):
            validator.validate_plan(plan)

    def test_exec_in_value_rejected(self, validator):
        step = ActionStep(
            step_number=2,
            action=ActionType.FILL,
            description="fill",
            target=SmartLocatorTarget(value="input", strategy=LocatorStrategy.AUTO),
            value="exec(something)",
        )
        plan = make_simple_plan([make_navigate_step("https://ex.com", 1), step])
        with pytest.raises(PlanValidationError):
            validator.validate_plan(plan)

    def test_safe_plan_passes(self, validator):
        steps = [
            make_navigate_step("https://example.com", 1),
            make_click_step("Login", 2),
            make_fill_step("Username", "admin", 3),
            make_assert_text_step("h1", "Welcome", 4),
        ]
        plan = make_simple_plan(steps)
        result = validator.validate_plan(plan)
        assert len(result.steps) == 4

