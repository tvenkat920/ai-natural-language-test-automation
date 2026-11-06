"""Strict Pydantic schemas for test inputs, action steps, locators, and execution plans."""
import uuid
from enum import Enum
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


class ActionType(str, Enum):
    """Allowlisted actions supported by the browser automation engine."""
    NAVIGATE = "navigate"
    CLICK = "click"
    FILL = "fill"
    SELECT_OPTION = "select_option"
    CHECK = "check"
    UNCHECK = "uncheck"
    PRESS = "press"
    WAIT_FOR = "wait_for"
    ASSERT_VISIBLE = "assert_visible"
    ASSERT_TEXT = "assert_text"
    ASSERT_URL = "assert_url"
    ASSERT_TITLE = "assert_title"
    SCREENSHOT = "screenshot"


class LocatorStrategy(str, Enum):
    """Heuristic strategies for locating elements in the DOM."""
    AUTO = "auto"
    ROLE = "role"
    LABEL = "label"
    PLACEHOLDER = "placeholder"
    TEXT = "text"
    TEST_ID = "test_id"
    CSS = "css"
    XPATH = "xpath"


class SmartLocatorTarget(BaseModel):
    """Descriptor for locating an interactive or visible element semantically."""
    strategy: LocatorStrategy = Field(
        default=LocatorStrategy.AUTO,
        description="Locator strategy to use. 'auto' uses intelligent priority fallback.",
    )
    value: str = Field(
        ...,
        description="The primary selector, text, placeholder, or label value to look for.",
    )
    role: Optional[str] = Field(
        default=None,
        description="Accessible ARIA role (e.g. 'button', 'link', 'textbox', 'heading', 'combobox', 'checkbox').",
    )
    name: Optional[str] = Field(
        default=None,
        description="Accessible name associated with the role (e.g. button label or accessible text).",
    )
    exact: bool = Field(
        default=False,
        description="Whether text or name matching should be exact (True) or substring (False).",
    )
    index: Optional[int] = Field(
        default=None,
        description="Optional 0-based index if multiple matching elements exist and disambiguation is explicit.",
    )
    description: Optional[str] = Field(
        default=None,
        description="Human-friendly label describing the element purpose (e.g. 'Login submit button').",
    )


class ActionStep(BaseModel):
    """A single atomic, validated test action step to be executed in the browser."""
    step_number: int = Field(..., ge=1, description="Sequential 1-based step index.")
    action: ActionType = Field(..., description="Allowlisted browser action.")
    description: str = Field(..., description="Clear human-readable description of what this step does.")
    target: Optional[SmartLocatorTarget] = Field(
        default=None,
        description="Semantic locator target required for DOM interaction and element assertion steps.",
    )
    url: Optional[str] = Field(
        default=None,
        description="Target URL for 'navigate' or expected URL substring/regex for 'assert_url'.",
    )
    value: Optional[str] = Field(
        default=None,
        description="Text content for 'fill', key name for 'press' (e.g. 'Enter'), or custom input.",
    )
    select_values: Optional[List[str]] = Field(
        default=None,
        description="Values, labels, or indices to select for 'select_option'.",
    )
    expected_text: Optional[str] = Field(
        default=None,
        description="Expected text string or substring for 'assert_text'.",
    )
    expected_title: Optional[str] = Field(
        default=None,
        description="Expected page title string or substring for 'assert_title'.",
    )
    timeout_ms: Optional[int] = Field(
        default=None,
        ge=100,
        le=60000,
        description="Optional override timeout in milliseconds for this specific step.",
    )
    wait_state: Optional[Literal["load", "domcontentloaded", "networkidle", "visible", "hidden"]] = Field(
        default=None,
        description="Page lifecycle state to wait for with 'wait_for'.",
    )
    screenshot_name: Optional[str] = Field(
        default=None,
        description="Custom identifier or file name for explicit 'screenshot' actions.",
    )


class ExecutionSettings(BaseModel):
    """Execution parameters configured per test run."""
    headless: bool = Field(default=False, description="Whether to run headless (False = visible browser).")
    slow_mo_ms: int = Field(default=250, ge=0, description="Delay between actions for visible pacing.")
    browser_type: Literal["chromium", "firefox", "webkit"] = Field(default="chromium")
    timeout_ms: int = Field(default=10000, ge=500, description="Default timeout in milliseconds.")
    max_actions: int = Field(default=30, ge=1, le=100, description="Safety limit on step count.")
    max_duration_sec: int = Field(default=120, ge=5, le=600, description="Total timeout in seconds.")
    screenshot_on_failure: bool = Field(default=True)
    screenshot_on_step: bool = Field(default=False)


class TestCaseInput(BaseModel):
    """User input representing a natural language test case and execution context."""
    __test__ = False
    instruction: str = Field(
        ...,
        min_length=3,
        description="Natural language plain English test case instructions.",
    )
    base_url: str = Field(
        ...,
        description="Starting target URL (must be valid HTTP or HTTPS).",
    )
    credentials: Optional[Dict[str, str]] = Field(
        default_factory=dict,
        description="Optional secure user/password pairs (e.g. {'username': '...', 'password': '...'}).",
    )
    settings: ExecutionSettings = Field(
        default_factory=ExecutionSettings,
        description="Optional execution runtime configuration.",
    )

    @field_validator("base_url")
    @classmethod
    def validate_base_url_scheme(cls, v: str) -> str:
        clean = v.strip()
        if not (clean.startswith("http://") or clean.startswith("https://")):
            raise ValueError(f"Base URL must start with 'http://' or 'https://', received: '{clean}'")
        return clean


class TestPlan(BaseModel):
    """Structured executable test plan generated by the LLM Planner and validated by PlanValidator."""
    __test__ = False
    plan_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str = Field(..., description="Concise summary title of the test plan.")
    description: str = Field(default="", description="Detailed summary of test intentions.")
    base_url: str = Field(..., description="Target base URL.")
    steps: List[ActionStep] = Field(
        default_factory=list,
        description="Ordered list of executable action steps.",
    )
    requires_clarification: bool = Field(
        default=False,
        description="True if mandatory information (e.g., credentials or expected outcome) is missing.",
    )
    missing_information: List[str] = Field(
        default_factory=list,
        description="List of specific information pieces needed from the user before execution.",
    )
    clarification_prompt: Optional[str] = Field(
        default=None,
        description="Helpful message explaining what information is needed to proceed.",
    )

