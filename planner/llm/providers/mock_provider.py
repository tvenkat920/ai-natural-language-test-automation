"""Mock LLM provider for deterministic offline testing without any API calls."""
import json
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from planner.llm.providers.base import BaseLLMProvider


class MockLLMProvider(BaseLLMProvider):
    """
    Deterministic mock provider for unit/integration testing.

    Generates realistic, structured JSON TestPlan output based on
    keyword analysis of the user prompt — no API key required.
    
    Supports injection of a custom response dict for precise test control.
    """

    def __init__(self, custom_response: Optional[Dict[str, Any]] = None):
        self._custom_response = custom_response

    @property
    def provider_name(self) -> str:
        return "mock"

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Return deterministic JSON based on keyword matching or injected response."""
        if self._custom_response is not None:
            return json.dumps(self._custom_response)

        # Parse base URL from user prompt for realistic mock output
        base_url = self._extract_url(user_prompt)
        instruction_lower = user_prompt.lower()

        # Build a contextual mock plan based on keywords
        steps = []
        step_num = 1

        # Always start with navigate
        steps.append({
            "step_number": step_num,
            "action": "navigate",
            "description": f"Navigate to the target website",
            "url": base_url,
            "timeout_ms": 15000,
        })
        step_num += 1

        # Login scenario
        if any(kw in instruction_lower for kw in ["login", "log in", "sign in", "signin", "authenticate"]):
            if "credentials" in user_prompt.lower() or "username" in user_prompt.lower():
                steps.append({
                    "step_number": step_num,
                    "action": "fill",
                    "description": "Enter username into the login field",
                    "target": {
                        "strategy": "auto",
                        "value": "Username",
                        "role": "textbox",
                        "name": "Username",
                        "exact": False,
                        "description": "Username input field",
                    },
                    "value": "{{USERNAME}}",
                })
                step_num += 1
                steps.append({
                    "step_number": step_num,
                    "action": "fill",
                    "description": "Enter password into the password field",
                    "target": {
                        "strategy": "auto",
                        "value": "Password",
                        "role": "textbox",
                        "name": "Password",
                        "exact": False,
                        "description": "Password input field",
                    },
                    "value": "{{PASSWORD}}",
                })
                step_num += 1
                steps.append({
                    "step_number": step_num,
                    "action": "click",
                    "description": "Click the Login or Sign In button to submit credentials",
                    "target": {
                        "strategy": "auto",
                        "value": "Login",
                        "role": "button",
                        "name": "Login",
                        "exact": False,
                        "description": "Login submit button",
                    },
                })
                step_num += 1

        # Search scenario
        if any(kw in instruction_lower for kw in ["search", "find", "look for", "query"]):
            steps.append({
                "step_number": step_num,
                "action": "fill",
                "description": "Enter search query into the search input",
                "target": {
                    "strategy": "auto",
                    "value": "Search",
                    "role": "textbox",
                    "name": "Search",
                    "exact": False,
                    "description": "Search input field",
                },
                "value": "test query",
            })
            step_num += 1
            steps.append({
                "step_number": step_num,
                "action": "press",
                "description": "Submit the search by pressing Enter",
                "value": "Enter",
            })
            step_num += 1

        # Click a button/link
        if any(kw in instruction_lower for kw in ["click", "press", "tap", "select", "navigate to", "go to"]):
            if "button" in instruction_lower:
                steps.append({
                    "step_number": step_num,
                    "action": "click",
                    "description": "Click the main call-to-action button on the page",
                    "target": {
                        "strategy": "auto",
                        "value": "Get Started",
                        "role": "button",
                        "exact": False,
                        "description": "Primary CTA button",
                    },
                })
                step_num += 1

        # Title assertion
        if any(kw in instruction_lower for kw in ["title", "heading"]):
            import re
            quoted = re.findall(r"['\"]([^'\"]+)['\"]", user_prompt)
            expected_title = quoted[0] if quoted else (urlparse(base_url).hostname or "Home")
            steps.append({
                "step_number": step_num,
                "action": "assert_title",
                "description": f"Verify the page title contains '{expected_title}'",
                "expected_title": expected_title,
                "value": expected_title,
            })
            step_num += 1

        # Specific section assertions
        if "demo access" in instruction_lower:
            steps.append({
                "step_number": step_num,
                "action": "assert_visible",
                "description": "Verify 'Get your demo access' section is visible",
                "target": {
                    "strategy": "auto",
                    "value": "Get your demo access",
                    "role": "heading",
                    "exact": False,
                    "description": "Demo access section heading",
                },
            })
            step_num += 1
        elif any(kw in instruction_lower for kw in ["visible", "appear", "show", "see", "displayed", "check", "verify", "confirm"]):
            # Check if there is a quoted element to verify
            import re
            quoted = re.findall(r"['\"]([^'\"]+)['\"]", user_prompt)
            # If multiple quotes and first was used for title, use second
            target_val = quoted[1] if len(quoted) > 1 else (quoted[0] if quoted and "title" not in instruction_lower else "body")
            steps.append({
                "step_number": step_num,
                "action": "assert_visible",
                "description": f"Verify element '{target_val}' is visible on the page",
                "target": {
                    "strategy": "auto",
                    "value": target_val,
                    "exact": False,
                    "description": f"Target element '{target_val}'",
                },
            })
            step_num += 1

        # Dashboard assertion
        if any(kw in instruction_lower for kw in ["dashboard", "home", "profile", "account", "portal"]):
            steps.append({
                "step_number": step_num,
                "action": "assert_visible",
                "description": "Verify user has been taken to the dashboard / home area",
                "target": {
                    "strategy": "auto",
                    "value": "dashboard",
                    "role": "heading",
                    "exact": False,
                    "description": "Dashboard heading or landmark",
                },
            })
            step_num += 1

        # Screenshot at end
        steps.append({
            "step_number": step_num,
            "action": "screenshot",
            "description": "Capture final state screenshot as evidence",
            "screenshot_name": "final_state",
        })

        # Detect missing credentials scenario
        needs_clarification = False
        missing_info = []
        clarification_prompt = None

        if any(kw in instruction_lower for kw in ["login", "log in", "sign in"]):
            if "{{USERNAME}}" in json.dumps(steps) or "{{PASSWORD}}" in json.dumps(steps):
                # Credentials are referenced but not provided — flag clarification
                if "username" not in user_prompt and "password" not in user_prompt:
                    needs_clarification = True
                    missing_info = ["username or email to log in with", "password for the account"]
                    clarification_prompt = (
                        "This test requires login credentials. "
                        "Please provide the username/email and password via --credentials or interactive input."
                    )

        plan = {
            "title": self._generate_title(instruction_lower),
            "description": f"Auto-generated mock plan for: {user_prompt[:120]}",
            "base_url": base_url,
            "steps": steps,
            "requires_clarification": needs_clarification,
            "missing_information": missing_info,
            "clarification_prompt": clarification_prompt,
        }

        return json.dumps(plan, indent=2)

    @staticmethod
    def _extract_url(user_prompt: str) -> str:
        """Extract the first HTTP/S URL found in the prompt, or return a placeholder."""
        import re
        matches = re.findall(r"https?://[^\s\"']+", user_prompt)
        return matches[0].rstrip(".,;)") if matches else "https://example.com"

    @staticmethod
    def _generate_title(instruction_lower: str) -> str:
        """Generate a concise plan title from instruction keywords."""
        if "login" in instruction_lower or "sign in" in instruction_lower:
            return "Login and Authentication Verification"
        elif "search" in instruction_lower:
            return "Search Functionality Test"
        elif "title" in instruction_lower:
            return "Page Title Verification"
        elif "navigate" in instruction_lower or "open" in instruction_lower:
            return "Navigation and Visibility Test"
        return "Generic Browser Interaction Test"

