"""
LLMPlanner: Converts English test instructions into validated, executable TestPlan objects.

Responsibilities:
- Build a strict JSON schema-aware system prompt
- Send the prompt to the configured LLM provider
- Parse and Pydantic-validate the structured response
- Substitute user-supplied credentials safely
- Raise clear errors for malformed or missing LLM responses
"""
import json
import re
from typing import Any, Dict, Optional

from planner.models import ActionStep, ActionType, LocatorStrategy, SmartLocatorTarget, TestCaseInput, TestPlan
from planner.llm.providers.base import BaseLLMProvider
from security.manager import SecurityManager


# ==============================================================================
# System Prompt Template (embedded, not eval'd)
# ==============================================================================
SYSTEM_PROMPT = """You are an expert browser-test automation planner. Convert the user's plain-English test instruction into a strict JSON TestPlan. 

RULES:
1. Return ONLY valid JSON that matches the schema below — no markdown code blocks, no explanations.
2. Use ONLY these allowed actions: navigate, click, fill, select_option, check, uncheck, press, wait_for, assert_visible, assert_text, assert_url, assert_title, screenshot.
3. NEVER invent login credentials. If the instruction requires credentials not provided, set "requires_clarification": true and list what is needed.
4. NEVER generate eval(), exec(), os.system(), subprocess, or any code execution patterns.
5. Only use http:// or https:// URLs.
6. Use semantic locator strategies: prefer role+name, then label, then placeholder, then text, then CSS/XPath as a last resort.
7. If {{USERNAME}} or {{PASSWORD}} appear in the prompt context, use those exact placeholder tokens in fill steps — they will be substituted securely before execution.
8. Number steps starting from 1. Do not skip numbers.
9. Always end with a screenshot step.

JSON SCHEMA:
{
  "title": "string — concise test name",
  "description": "string — what this test does and asserts",
  "base_url": "string — the starting URL",
  "requires_clarification": false,
  "missing_information": [],
  "clarification_prompt": null,
  "steps": [
    {
      "step_number": 1,
      "action": "navigate | click | fill | select_option | check | uncheck | press | wait_for | assert_visible | assert_text | assert_url | assert_title | screenshot",
      "description": "Human-readable step purpose",
      "url": "string — for navigate or assert_url",
      "target": {
        "strategy": "auto | role | label | placeholder | text | test_id | css | xpath",
        "value": "primary selector / text / placeholder / css selector",
        "role": "button | link | textbox | heading | combobox | checkbox | main | navigation | (etc.)",
        "name": "accessible name for role strategy",
        "exact": false,
        "index": null,
        "description": "human label for this element"
      },
      "value": "string — text to fill or key to press",
      "select_values": ["option label or value"],
      "expected_text": "string — for assert_text",
      "expected_title": "string — for assert_title",
      "timeout_ms": null,
      "wait_state": "load | domcontentloaded | networkidle | visible | hidden",
      "screenshot_name": "string — custom name for screenshot action"
    }
  ]
}

LOCATOR STRATEGY GUIDE:
- role+name: use for buttons, links, headings, inputs identified by aria/accessible names
- label: use for form fields associated with <label> elements
- placeholder: use for inputs identified by placeholder text
- text: use for visible text on the page
- css: use sparingly for elements without accessible attributes (e.g. ".nav-brand", "#user-menu")
- xpath: last resort only

Omit null/empty fields. The "target" field is required for: click, fill, select_option, check, uncheck, assert_visible, assert_text. It is optional for press and wait_for.
"""


class LLMPlanner:
    """
    Orchestrates natural language → structured TestPlan conversion.
    
    Strictly validates all LLM output via Pydantic. Never executes
    or eval()'s any LLM-generated content.
    """

    def __init__(
        self,
        provider: BaseLLMProvider,
        security_manager: Optional[SecurityManager] = None,
    ):
        self.provider = provider
        self.security_manager = security_manager or SecurityManager()

    def plan(self, test_input: TestCaseInput) -> TestPlan:
        """
        Convert a TestCaseInput into a structured, validated TestPlan.
        
        Raises:
            ValueError: If the LLM returns malformed JSON or the response fails schema validation.
        """
        # Validate base URL first
        self.security_manager.validate_url(test_input.base_url)

        # Register any secrets so they can be masked in logs
        for val in (test_input.credentials or {}).values():
            self.security_manager.register_secret(val)

        # Build user context with credential placeholders
        user_prompt = self._build_user_prompt(test_input)

        # Call the LLM provider
        raw_response = self.provider.generate(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )

        # Parse and validate the JSON response
        plan = self._parse_and_validate(raw_response, test_input)

        # Substitute credential placeholders with actual values
        plan = self._substitute_credentials(plan, test_input.credentials or {})

        return plan

    def _build_user_prompt(self, test_input: TestCaseInput) -> str:
        """Construct the user-facing prompt with all context."""
        cred_context = ""
        credentials = test_input.credentials or {}
        if credentials:
            # Provide placeholder tokens, not actual values
            tokens = {k: f"{{{{{k.upper()}}}}}" for k in credentials.keys()}
            cred_context = (
                f"\n\nCREDENTIALS AVAILABLE (use these placeholder tokens exactly in fill steps):\n"
                + "\n".join(f"  - {k}: {v}" for k, v in tokens.items())
            )

        return (
            f"BASE URL: {test_input.base_url}\n"
            f"TEST INSTRUCTION: {test_input.instruction}"
            f"{cred_context}\n\n"
            f"Generate the JSON TestPlan for this instruction."
        )

    def _parse_and_validate(self, raw_response: str, test_input: TestCaseInput) -> TestPlan:
        """Parse JSON from LLM response and validate with Pydantic. Handles markdown code fences."""
        if not raw_response or not raw_response.strip():
            raise ValueError("LLM returned an empty response. Cannot generate test plan.")

        # Strip markdown code fences if present (```json ... ```)
        cleaned = raw_response.strip()
        fence_match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", cleaned)
        if fence_match:
            cleaned = fence_match.group(1).strip()

        # Find the first JSON object in the response
        json_match = re.search(r"\{[\s\S]*\}", cleaned)
        if not json_match:
            raise ValueError(
                f"LLM response does not contain a JSON object. "
                f"Raw response (first 500 chars): {raw_response[:500]}"
            )

        try:
            raw_dict: Dict[str, Any] = json.loads(json_match.group(0))
        except json.JSONDecodeError as e:
            raise ValueError(
                f"LLM returned invalid JSON: {e}. "
                f"Raw response (first 500 chars): {raw_response[:500]}"
            ) from e

        # Ensure base_url is set from input if LLM omitted it
        if not raw_dict.get("base_url"):
            raw_dict["base_url"] = test_input.base_url

        # Validate the schema using Pydantic
        try:
            plan = TestPlan.model_validate(raw_dict)
        except Exception as e:
            raise ValueError(
                f"LLM response failed schema validation: {e}\n"
                f"Parsed dict keys: {list(raw_dict.keys())}"
            ) from e

        return plan

    def _substitute_credentials(
        self,
        plan: TestPlan,
        credentials: Dict[str, str],
    ) -> TestPlan:
        """
        Safely replace {{KEY}} placeholder tokens in step values with actual credential values.
        Never logs or exposes the actual credential values.
        """
        if not credentials:
            return plan

        for step in plan.steps:
            if step.value and "{{" in step.value:
                new_val = step.value
                for key, secret_val in credentials.items():
                    placeholder = f"{{{{{key.upper()}}}}}"
                    if placeholder in new_val:
                        new_val = new_val.replace(placeholder, secret_val)
                        # Register as secret for log masking
                        self.security_manager.register_secret(secret_val)
                step.value = new_val

        return plan

