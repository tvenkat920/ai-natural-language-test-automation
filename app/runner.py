"""
App orchestration layer: wires together all components for a single test run.
"""
import sys
import uuid
from pathlib import Path
from typing import Dict, Optional

from config.settings import AppConfig, get_config
from planner.models import TestCaseInput, ExecutionSettings
from planner.llm.llm_planner import LLMPlanner
from planner.llm.providers.mock_provider import MockLLMProvider
from planner.validator import PlanValidator, PlanValidationError
from browser.executor import BrowserExecutor
from reporting.reporter import ResultReporter, TestRunResult
from security.manager import SecurityManager


def _build_provider(config: AppConfig):
    """Instantiate the configured LLM provider. Falls back to mock on missing credentials."""
    provider_name = config.llm_provider.lower()
    if provider_name == "gemini":
        if not config.gemini_api_key:
            print(
                "[WARN] LLM_PROVIDER=gemini but GEMINI_API_KEY is not set. "
                "Falling back to mock provider.",
                file=sys.stderr,
            )
            return MockLLMProvider()
        from planner.llm.providers.gemini_provider import GeminiLLMProvider
        return GeminiLLMProvider(api_key=config.gemini_api_key, model=config.gemini_model)
    elif provider_name == "openai":
        if not config.openai_api_key and not config.openai_base_url:
            print(
                "[WARN] LLM_PROVIDER=openai but OPENAI_API_KEY / OPENAI_BASE_URL is not set. "
                "Falling back to mock provider.",
                file=sys.stderr,
            )
            return MockLLMProvider()
        from planner.llm.providers.openai_provider import OpenAILLMProvider
        return OpenAILLMProvider(
            api_key=config.openai_api_key,
            model=config.openai_model,
            base_url=config.openai_base_url,
        )
    else:
        return MockLLMProvider()


def run_test(
    instruction: str,
    base_url: str,
    credentials: Optional[Dict[str, str]] = None,
    headless: Optional[bool] = None,
    slow_mo: Optional[int] = None,
    config: Optional[AppConfig] = None,
    mock_llm_response: Optional[dict] = None,
) -> TestRunResult:
    """
    Full end-to-end test execution pipeline:
      1. Build TestCaseInput
      2. Plan via LLM
      3. Validate plan
      4. Execute in browser
      5. Generate reports
      6. Return result
    """
    cfg = config or get_config()

    # --- Security ---
    security = SecurityManager(allow_localhost=True)
    security.validate_url(base_url)
    security.add_allowed_domain_from_url(base_url)
    for val in (credentials or {}).values():
        security.register_secret(val)

    # --- TestCaseInput ---
    exec_settings = ExecutionSettings(
        headless=headless if headless is not None else cfg.headless,
        slow_mo_ms=slow_mo if slow_mo is not None else cfg.slow_mo_ms,
        browser_type=cfg.browser_type,
        timeout_ms=cfg.default_timeout_ms,
        max_actions=cfg.max_actions,
        max_duration_sec=cfg.max_duration_sec,
        screenshot_on_failure=cfg.screenshot_on_failure,
        screenshot_on_step=cfg.screenshot_on_step,
    )
    test_input = TestCaseInput(
        instruction=instruction,
        base_url=base_url,
        credentials=credentials or {},
        settings=exec_settings,
    )

    # --- LLM Planning ---
    if mock_llm_response is not None:
        provider = MockLLMProvider(custom_response=mock_llm_response)
    else:
        provider = _build_provider(cfg)

    planner = LLMPlanner(provider=provider, security_manager=security)
    plan = planner.plan(test_input)

    # --- Plan Validation ---
    validator = PlanValidator(
        security_manager=security,
        max_actions=cfg.max_actions,
        enforce_scope=cfg.navigation_scope_enforcement,
    )
    try:
        plan = validator.validate_plan(plan)
    except PlanValidationError as e:
        from reporting.reporter import StepResult
        import datetime
        now = datetime.datetime.now().isoformat()
        return TestRunResult(
            run_id=plan.plan_id,
            instruction=instruction,
            base_url=base_url,
            status="ERROR",
            start_time=now,
            end_time=now,
            duration_sec=0.0,
            total_steps=0,
            passed_steps=0,
            failed_steps=0,
            error_message=f"Plan validation failed: {e}",
        )

    # --- Browser Execution ---
    executor = BrowserExecutor(config=cfg, security_manager=security)
    result = executor.execute_plan(plan, instruction=instruction, settings=exec_settings)

    # --- Reporting ---
    reporter = ResultReporter(reports_dir=cfg.reports_dir)
    json_path = reporter.generate_json_report(result)
    html_path = reporter.generate_html_report(result)
    reporter.print_console_summary(result)

    print(f"\n📄 JSON report: {json_path}")
    print(f"🌐 HTML report: {html_path}\n")

    return result

