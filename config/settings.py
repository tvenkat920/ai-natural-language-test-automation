"""Application configuration using Pydantic Settings."""
from pathlib import Path
from typing import Literal, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """Central configuration for AI Natural Language Test Automation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # LLM Provider Configuration
    llm_provider: Literal["mock", "gemini", "openai"] = Field(
        default="mock",
        description="LLM provider: 'mock' for deterministic/offline testing, 'gemini', or 'openai'",
    )
    gemini_api_key: Optional[str] = Field(
        default=None,
        description="Google Gemini API key",
    )
    gemini_model: str = Field(
        default="gemini-2.5-flash",
        description="Gemini model identifier",
    )
    openai_api_key: Optional[str] = Field(
        default=None,
        description="OpenAI API key",
    )
    openai_model: str = Field(
        default="gpt-4o-mini",
        description="OpenAI model identifier",
    )
    openai_base_url: Optional[str] = Field(
        default=None,
        description="Custom base URL for OpenAI-compatible endpoints (e.g., local Ollama or vLLM)",
    )

    # Browser Execution Settings
    headless: bool = Field(
        default=False,
        description="Run browser in headless mode. Defaults to False for visible demonstration.",
    )
    slow_mo_ms: int = Field(
        default=250,
        description="Slow-motion delay in milliseconds between Playwright actions for visual clarity.",
    )
    browser_type: Literal["chromium", "firefox", "webkit"] = Field(
        default="chromium",
        description="Browser engine to use.",
    )
    default_timeout_ms: int = Field(
        default=10000,
        description="Default timeout in milliseconds for Playwright operations.",
    )
    viewport_width: int = Field(
        default=1280,
        description="Browser viewport width in pixels.",
    )
    viewport_height: int = Field(
        default=720,
        description="Browser viewport height in pixels.",
    )

    # Execution Safeguards & Limits
    max_actions: int = Field(
        default=30,
        description="Maximum permitted actions per test plan to prevent runaway execution.",
    )
    max_duration_sec: int = Field(
        default=120,
        description="Maximum total test execution time in seconds.",
    )
    navigation_scope_enforcement: bool = Field(
        default=True,
        description="Enforce that navigations remain within the target domain/origin.",
    )

    # Reporting & Artifacts
    reports_dir: Path = Field(
        default=Path("reports"),
        description="Directory where JSON and HTML reports are saved.",
    )
    screenshots_dir: Path = Field(
        default=Path("reports/screenshots"),
        description="Directory where failure and step screenshots are saved.",
    )
    screenshot_on_failure: bool = Field(
        default=True,
        description="Capture screenshot automatically whenever an action or assertion fails.",
    )
    screenshot_on_step: bool = Field(
        default=False,
        description="Capture screenshot after every single action step.",
    )


_config_instance: Optional[AppConfig] = None


def get_config(reload: bool = False) -> AppConfig:
    """Get the cached configuration instance or initialize a new one."""
    global _config_instance
    if _config_instance is None or reload:
        _config_instance = AppConfig()
        _config_instance.reports_dir.mkdir(parents=True, exist_ok=True)
        _config_instance.screenshots_dir.mkdir(parents=True, exist_ok=True)
    return _config_instance

