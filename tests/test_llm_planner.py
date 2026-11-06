"""Unit tests for MockLLMProvider and LLMPlanner — schema validation, malformed responses, credential handling."""
import json
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from planner.llm.llm_planner import LLMPlanner
from planner.llm.providers.mock_provider import MockLLMProvider
from planner.models import TestCaseInput, TestPlan, ActionType
from security.manager import SecurityManager


@pytest.fixture
def planner():
    return LLMPlanner(provider=MockLLMProvider())


@pytest.fixture
def simple_input():
    return TestCaseInput(
        instruction="Open the website and verify the title is visible",
        base_url="https://example.com",
    )


class TestMockProviderOutput:
    def test_navigate_instruction_produces_navigate_step(self, planner, simple_input):
        plan = planner.plan(simple_input)
        actions = [s.action for s in plan.steps]
        assert ActionType.NAVIGATE in actions

    def test_plan_title_is_non_empty(self, planner, simple_input):
        plan = planner.plan(simple_input)
        assert len(plan.title) > 0

    def test_plan_base_url_matches_input(self, planner, simple_input):
        plan = planner.plan(simple_input)
        assert plan.base_url == simple_input.base_url

    def test_steps_have_sequential_numbers(self, planner, simple_input):
        plan = planner.plan(simple_input)
        for i, step in enumerate(plan.steps, start=1):
            assert step.step_number == i

    def test_screenshot_step_at_end(self, planner, simple_input):
        plan = planner.plan(simple_input)
        assert plan.steps[-1].action == ActionType.SCREENSHOT

    def test_all_actions_are_allowed_types(self, planner, simple_input):
        plan = planner.plan(simple_input)
        allowed = set(ActionType)
        for step in plan.steps:
            assert step.action in allowed

    def test_login_instruction_produces_fill_steps(self):
        provider = MockLLMProvider()
        planner = LLMPlanner(provider=provider)
        ti = TestCaseInput(
            instruction="Log in with the given credentials and check the dashboard",
            base_url="https://app.example.com",
            credentials={"username": "admin", "password": "secret123"},
        )
        plan = planner.plan(ti)
        actions = [s.action for s in plan.steps]
        assert ActionType.FILL in actions


class TestMalformedLLMResponses:
    def test_empty_response_raises_value_error(self):
        provider = MockLLMProvider(custom_response=None)
        # Simulate empty response by overriding generate
        class EmptyProvider(MockLLMProvider):
            def generate(self, system_prompt: str = "", user_prompt: str = "", **kwargs): return ""
        planner = LLMPlanner(provider=EmptyProvider())
        ti = TestCaseInput(instruction="test", base_url="https://example.com")
        with pytest.raises(ValueError, match="empty response"):
            planner.plan(ti)

    def test_non_json_response_raises_value_error(self):
        class GarbageProvider(MockLLMProvider):
            def generate(self, system_prompt: str = "", user_prompt: str = "", **kwargs): return "This is not JSON at all!"
        planner = LLMPlanner(provider=GarbageProvider())
        ti = TestCaseInput(instruction="test", base_url="https://example.com")
        with pytest.raises(ValueError, match="JSON"):
            planner.plan(ti)

    def test_json_missing_required_fields_raises_value_error(self):
        class BadSchemaProvider(MockLLMProvider):
            def generate(self, system_prompt: str = "", user_prompt: str = "", **kwargs): return json.dumps({"random": "data"})
        planner = LLMPlanner(provider=BadSchemaProvider())
        ti = TestCaseInput(instruction="test", base_url="https://example.com")
        with pytest.raises(ValueError, match="schema validation"):
            planner.plan(ti)

    def test_json_with_markdown_fence_is_parsed(self):
        """LLM sometimes wraps JSON in markdown code fences — planner must handle it."""
        valid_plan = {
            "title": "Test",
            "base_url": "https://example.com",
            "steps": [
                {"step_number": 1, "action": "navigate", "description": "Go to site", "url": "https://example.com"}
            ],
        }
        fenced_response = f"```json\n{json.dumps(valid_plan)}\n```"
        class FencedProvider(MockLLMProvider):
            def generate(self, system_prompt: str = "", user_prompt: str = "", **kwargs): return fenced_response
        planner = LLMPlanner(provider=FencedProvider())
        ti = TestCaseInput(instruction="test", base_url="https://example.com")
        plan = planner.plan(ti)
        assert plan.title == "Test"

    def test_plan_with_extra_json_text_before_object(self):
        """LLM sometimes prepends text before JSON — should still parse."""
        valid_plan = {
            "title": "Test",
            "base_url": "https://example.com",
            "steps": [
                {"step_number": 1, "action": "navigate", "description": "Go to site", "url": "https://example.com"}
            ],
        }
        response_with_preamble = f"Here is the plan:\n{json.dumps(valid_plan)}"
        class PreambleProvider(MockLLMProvider):
            def generate(self, system_prompt: str = "", user_prompt: str = "", **kwargs): return response_with_preamble
        planner = LLMPlanner(provider=PreambleProvider())
        ti = TestCaseInput(instruction="test", base_url="https://example.com")
        plan = planner.plan(ti)
        assert plan.title == "Test"


class TestCredentialHandling:
    def test_credential_placeholders_substituted(self):
        custom_plan = {
            "title": "Login Test",
            "base_url": "https://example.com",
            "steps": [
                {"step_number": 1, "action": "navigate", "description": "Go", "url": "https://example.com"},
                {
                    "step_number": 2,
                    "action": "fill",
                    "description": "Enter username",
                    "target": {"strategy": "auto", "value": "Username"},
                    "value": "{{USERNAME}}",
                },
                {
                    "step_number": 3,
                    "action": "fill",
                    "description": "Enter password",
                    "target": {"strategy": "auto", "value": "Password"},
                    "value": "{{PASSWORD}}",
                },
                {"step_number": 4, "action": "screenshot", "description": "Screenshot"},
            ],
        }
        provider = MockLLMProvider(custom_response=custom_plan)
        sec = SecurityManager()
        planner = LLMPlanner(provider=provider, security_manager=sec)
        ti = TestCaseInput(
            instruction="Login",
            base_url="https://example.com",
            credentials={"username": "admin", "password": "secret"},
        )
        plan = planner.plan(ti)
        fill_steps = [s for s in plan.steps if s.action == ActionType.FILL]
        assert any(s.value == "admin" for s in fill_steps)
        assert any(s.value == "secret" for s in fill_steps)

    def test_credentials_registered_as_secrets(self):
        custom_plan = {
            "title": "T",
            "base_url": "https://example.com",
            "steps": [
                {"step_number": 1, "action": "navigate", "description": "Go", "url": "https://example.com"},
                {
                    "step_number": 2,
                    "action": "fill",
                    "description": "Password",
                    "target": {"strategy": "auto", "value": "Password"},
                    "value": "{{PASSWORD}}",
                },
                {"step_number": 3, "action": "screenshot", "description": "Screenshot"},
            ],
        }
        provider = MockLLMProvider(custom_response=custom_plan)
        sec = SecurityManager()
        planner = LLMPlanner(provider=provider, security_manager=sec)
        ti = TestCaseInput(
            instruction="Login",
            base_url="https://example.com",
            credentials={"password": "my_super_secret"},
        )
        planner.plan(ti)
        # Secret should now be masked
        masked = sec.mask_text("The password my_super_secret was used")
        assert "my_super_secret" not in masked

    def test_missing_credentials_flag_clarification(self):
        """LLM indicates clarification needed — planner should return plan with requires_clarification=True."""
        clarification_plan = {
            "title": "Login needs info",
            "base_url": "https://example.com",
            "requires_clarification": True,
            "missing_information": ["username", "password"],
            "clarification_prompt": "Please provide login credentials.",
            "steps": [],
        }
        provider = MockLLMProvider(custom_response=clarification_plan)
        planner = LLMPlanner(provider=provider)
        ti = TestCaseInput(instruction="Login and check dashboard", base_url="https://example.com")
        plan = planner.plan(ti)
        assert plan.requires_clarification is True
        assert len(plan.missing_information) > 0


class TestInputValidation:
    def test_invalid_base_url_raises_on_input_creation(self):
        with pytest.raises(Exception):  # Pydantic validator
            TestCaseInput(instruction="test", base_url="ftp://example.com")

    def test_short_instruction_raises(self):
        with pytest.raises(Exception):
            TestCaseInput(instruction="", base_url="https://example.com")

    def test_valid_input_creates_successfully(self):
        ti = TestCaseInput(instruction="Open the page", base_url="https://example.com")
        assert ti.instruction == "Open the page"

