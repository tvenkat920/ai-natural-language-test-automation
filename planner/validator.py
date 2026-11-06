"""PlanValidator - validates every action, argument, URL and assertion before execution."""
from typing import List, Optional
from urllib.parse import urlparse

from security.manager import SecurityManager, SecurityViolationError
from .models import ActionStep, ActionType, TestPlan


class PlanValidationError(Exception):
    """Raised when a test plan fails semantic, security, or structural validation."""
    pass


class PlanValidator:
    """Validates structured test plans against allowlists, parameter constraints, and security policies."""

    def __init__(
        self,
        security_manager: Optional[SecurityManager] = None,
        max_actions: int = 30,
        enforce_scope: bool = False,
    ):
        self.security_manager = security_manager or SecurityManager()
        self.max_actions = max_actions
        self.enforce_scope = enforce_scope

    def validate_plan(self, plan: TestPlan) -> TestPlan:
        """
        Perform exhaustive validation on a TestPlan.
        Returns the validated TestPlan or raises PlanValidationError.
        """
        if not plan:
            raise PlanValidationError("TestPlan cannot be null or empty.")

        # If plan indicates missing information / clarification needed, allow it through for reporting
        if plan.requires_clarification:
            return plan

        if not plan.base_url:
            raise PlanValidationError("TestPlan must specify a valid 'base_url'.")

        try:
            self.security_manager.validate_url(plan.base_url)
        except SecurityViolationError as e:
            raise PlanValidationError(f"Invalid base URL in test plan: {e}") from e

        if not plan.steps or len(plan.steps) == 0:
            raise PlanValidationError("TestPlan contains no executable steps.")

        if len(plan.steps) > self.max_actions:
            raise PlanValidationError(
                f"TestPlan step count ({len(plan.steps)}) exceeds maximum allowed ({self.max_actions})."
            )

        # Validate each individual step
        for idx, step in enumerate(plan.steps, start=1):
            self.validate_step(step, expected_index=idx, base_url=plan.base_url)

        return plan

    def validate_step(self, step: ActionStep, expected_index: Optional[int] = None, base_url: Optional[str] = None) -> None:
        """Validate an individual action step."""
        if not isinstance(step.action, ActionType):
            raise PlanValidationError(f"Step {step.step_number}: Unknown or unapproved action '{step.action}'.")

        # Check for injection in string parameters
        for attr in ("description", "value", "expected_text", "expected_title", "url"):
            val = getattr(step, attr, None)
            if val and isinstance(val, str):
                try:
                    self.security_manager.ensure_no_dynamic_code(val)
                except SecurityViolationError as e:
                    raise PlanValidationError(
                        f"Step {step.step_number} ({step.action.value}): Insecure pattern detected in '{attr}': {e}"
                    ) from e

        # 1. Navigate
        if step.action == ActionType.NAVIGATE:
            if not step.url:
                raise PlanValidationError(f"Step {step.step_number} (navigate): Missing required 'url' parameter.")
            try:
                self.security_manager.validate_url(step.url)
            except SecurityViolationError as e:
                raise PlanValidationError(f"Step {step.step_number} (navigate): Insecure or invalid URL: {e}") from e

        # 2. Interactive DOM actions requiring target
        elif step.action in {
            ActionType.CLICK,
            ActionType.FILL,
            ActionType.SELECT_OPTION,
            ActionType.CHECK,
            ActionType.UNCHECK,
            ActionType.ASSERT_VISIBLE,
            ActionType.ASSERT_TEXT,
        }:
            if not step.target:
                raise PlanValidationError(
                    f"Step {step.step_number} ({step.action.value}): Missing required locator 'target'."
                )
            if not step.target.value and not step.target.name:
                raise PlanValidationError(
                    f"Step {step.step_number} ({step.action.value}): Target must specify 'value' or 'name'."
                )

            # Specific requirements
            if step.action == ActionType.FILL and step.value is None:
                raise PlanValidationError(
                    f"Step {step.step_number} (fill): Missing required 'value' to type into target."
                )

            if step.action == ActionType.SELECT_OPTION:
                if not step.select_values and not step.value:
                    raise PlanValidationError(
                        f"Step {step.step_number} (select_option): Missing option value in 'select_values' or 'value'."
                    )

            if step.action == ActionType.ASSERT_TEXT:
                if not step.expected_text and not step.value:
                    raise PlanValidationError(
                        f"Step {step.step_number} (assert_text): Missing 'expected_text' to verify."
                    )

        # 3. Press key
        elif step.action == ActionType.PRESS:
            if not step.value:
                raise PlanValidationError(
                    f"Step {step.step_number} (press): Missing key 'value' to press (e.g. 'Enter')."
                )

        # 4. Assert URL
        elif step.action == ActionType.ASSERT_URL:
            if not step.url and not step.expected_text and not step.value:
                raise PlanValidationError(
                    f"Step {step.step_number} (assert_url): Missing target URL substring or pattern."
                )

        # 5. Assert Title
        elif step.action == ActionType.ASSERT_TITLE:
            if not step.expected_title and not step.expected_text and not step.value:
                raise PlanValidationError(
                    f"Step {step.step_number} (assert_title): Missing expected title string in 'expected_title'."
                )

        # 6. Wait For
        elif step.action == ActionType.WAIT_FOR:
            # wait_for can wait for target element or wait_state
            if not step.target and not step.wait_state and not step.timeout_ms:
                raise PlanValidationError(
                    f"Step {step.step_number} (wait_for): Must specify 'target', 'wait_state', or 'timeout_ms'."
                )

