"""BrowserExecutor: Runs validated test actions in Playwright with robust error handling and diagnostics."""
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

from assertions.engine import AssertionEngine, AssertionFailureError
from config.settings import AppConfig, get_config
from locators.exceptions import LocatorAmbiguityError, LocatorNotFoundError, SmartLocatorError
from locators.smart_locator import SmartLocator
from planner.models import ActionStep, ActionType, ExecutionSettings, TestPlan
from reporting.reporter import StepResult, TestRunResult
from security.manager import SecurityManager


class BrowserExecutor:
    """Executes validated ActionSteps through Playwright with diagnostic capture and timeout management."""

    def __init__(
        self,
        config: Optional[AppConfig] = None,
        security_manager: Optional[SecurityManager] = None,
    ):
        self.config = config or get_config()
        self.security_manager = security_manager or SecurityManager()
        self.assertion_engine = AssertionEngine(default_timeout_ms=self.config.default_timeout_ms)

    def execute_plan(
        self,
        plan: TestPlan,
        instruction: str,
        settings: Optional[ExecutionSettings] = None,
    ) -> TestRunResult:
        """
        Execute an approved TestPlan in a Playwright browser session.
        Collects detailed step-level timings, screenshots, and logs.
        """
        start_time_iso = datetime.now().isoformat()
        start_time_perf = time.perf_counter()

        exec_settings = settings or ExecutionSettings(
            headless=self.config.headless,
            slow_mo_ms=self.config.slow_mo_ms,
            browser_type=self.config.browser_type,
            timeout_ms=self.config.default_timeout_ms,
            max_actions=self.config.max_actions,
            max_duration_sec=self.config.max_duration_sec,
            screenshot_on_failure=self.config.screenshot_on_failure,
            screenshot_on_step=self.config.screenshot_on_step,
        )

        step_results: List[StepResult] = []
        captured_screenshots: List[str] = []
        overall_error: Optional[str] = None
        run_status = "PASS"

        # If plan required clarification, return immediately without opening browser
        if plan.requires_clarification:
            return TestRunResult(
                run_id=plan.plan_id,
                instruction=instruction,
                base_url=plan.base_url,
                status="NEEDS_CLARIFICATION",
                start_time=start_time_iso,
                end_time=datetime.now().isoformat(),
                duration_sec=0.0,
                total_steps=0,
                passed_steps=0,
                failed_steps=0,
                steps=[],
                clarification_prompt=plan.clarification_prompt or "Additional required information is needed.",
            )

        with sync_playwright() as p:
            # Select browser engine
            browser_launcher = getattr(p, exec_settings.browser_type, p.chromium)
            browser: Browser = browser_launcher.launch(
                headless=exec_settings.headless,
                slow_mo=exec_settings.slow_mo_ms,
            )

            context: BrowserContext = browser.new_context(
                viewport={"width": self.config.viewport_width, "height": self.config.viewport_height},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                ignore_https_errors=False,
            )
            page: Page = context.new_page()
            page.set_default_timeout(exec_settings.timeout_ms)

            smart_locator = SmartLocator(page, default_timeout_ms=exec_settings.timeout_ms)

            try:
                for idx, step in enumerate(plan.steps):
                    # Check overall max duration safeguard
                    elapsed = time.perf_counter() - start_time_perf
                    if elapsed > exec_settings.max_duration_sec:
                        overall_error = f"Test execution exceeded maximum timeout of {exec_settings.max_duration_sec}s."
                        run_status = "ERROR"
                        self._mark_remaining_skipped(plan.steps, idx, step_results)
                        break

                    step_res = self._execute_step(
                        page=page,
                        smart_locator=smart_locator,
                        step=step,
                        run_id=plan.plan_id,
                        exec_settings=exec_settings,
                    )
                    step_results.append(step_res)

                    if step_res.screenshot_path:
                        captured_screenshots.append(step_res.screenshot_path)

                    if step_res.status in ("FAIL", "ERROR"):
                        run_status = step_res.status
                        overall_error = step_res.error_message
                        # Mark remaining steps as SKIPPED
                        self._mark_remaining_skipped(plan.steps, idx + 1, step_results)
                        break

            except Exception as e:
                run_status = "ERROR"
                overall_error = str(e)
            finally:
                context.close()
                browser.close()

        total_perf = time.perf_counter() - start_time_perf
        end_time_iso = datetime.now().isoformat()

        passed_count = sum(1 for s in step_results if s.status == "PASS")
        failed_count = sum(1 for s in step_results if s.status in ("FAIL", "ERROR"))

        return TestRunResult(
            run_id=plan.plan_id,
            instruction=instruction,
            base_url=plan.base_url,
            status=run_status,
            start_time=start_time_iso,
            end_time=end_time_iso,
            duration_sec=total_perf,
            total_steps=len(plan.steps),
            passed_steps=passed_count,
            failed_steps=failed_count,
            steps=step_results,
            error_message=overall_error,
            screenshots=captured_screenshots,
        )

    def _execute_step(
        self,
        page: Page,
        smart_locator: SmartLocator,
        step: ActionStep,
        run_id: str,
        exec_settings: ExecutionSettings,
    ) -> StepResult:
        """Execute a single approved action step."""
        t0 = time.perf_counter()
        target_repr = f"{step.target.strategy.value}:{step.target.value}" if step.target else None
        val_masked = self.security_manager.mask_text(step.value) if step.value else None
        step_timeout = step.timeout_ms or exec_settings.timeout_ms
        screenshot_path: Optional[str] = None
        error_msg: Optional[str] = None
        status = "PASS"
        assertion_data: Optional[Dict[str, Any]] = None

        try:
            # 1. NAVIGATE
            if step.action == ActionType.NAVIGATE:
                self.security_manager.validate_url(step.url)
                nav_timeout = max(step_timeout, 25000)
                try:
                    page.goto(step.url, timeout=nav_timeout, wait_until="domcontentloaded")
                except Exception:
                    page.goto(step.url, timeout=nav_timeout, wait_until="commit")

            # 2. CLICK
            elif step.action == ActionType.CLICK:
                loc = smart_locator.resolve(step.target, timeout_ms=step_timeout)
                loc.click(timeout=step_timeout)

            # 3. FILL
            elif step.action == ActionType.FILL:
                loc = smart_locator.resolve(step.target, timeout_ms=step_timeout)
                loc.fill(step.value or "", timeout=step_timeout)

            # 4. SELECT OPTION
            elif step.action == ActionType.SELECT_OPTION:
                loc = smart_locator.resolve(step.target, timeout_ms=step_timeout)
                select_args = step.select_values or ([step.value] if step.value else [])
                loc.select_option(select_args, timeout=step_timeout)

            # 5. CHECK / UNCHECK
            elif step.action == ActionType.CHECK:
                loc = smart_locator.resolve(step.target, timeout_ms=step_timeout)
                loc.check(timeout=step_timeout)

            elif step.action == ActionType.UNCHECK:
                loc = smart_locator.resolve(step.target, timeout_ms=step_timeout)
                loc.uncheck(timeout=step_timeout)

            # 6. PRESS
            elif step.action == ActionType.PRESS:
                if step.target:
                    loc = smart_locator.resolve(step.target, timeout_ms=step_timeout)
                    loc.press(step.value or "Enter", timeout=step_timeout)
                else:
                    page.keyboard.press(step.value or "Enter")

            # 7. WAIT FOR
            elif step.action == ActionType.WAIT_FOR:
                if step.target:
                    loc = smart_locator.resolve(step.target, timeout_ms=step_timeout)
                    loc.wait_for(state="visible", timeout=step_timeout)
                elif step.wait_state:
                    page.wait_for_load_state(step.wait_state, timeout=step_timeout)
                elif step.timeout_ms:
                    page.wait_for_timeout(step.timeout_ms)

            # 8. ASSERT VISIBLE
            elif step.action == ActionType.ASSERT_VISIBLE:
                loc = smart_locator.resolve(step.target, timeout_ms=step_timeout)
                res = self.assertion_engine.assert_visible(
                    loc,
                    description=step.target.description or step.target.value,
                    timeout_ms=step_timeout,
                )
                assertion_data = {"expected": res.expected, "actual": res.actual}

            # 9. ASSERT TEXT
            elif step.action == ActionType.ASSERT_TEXT:
                loc = smart_locator.resolve(step.target, timeout_ms=step_timeout)
                res = self.assertion_engine.assert_text(
                    loc,
                    expected_text=step.expected_text or step.value or "",
                    exact=step.target.exact if step.target else False,
                    description=step.target.description or step.target.value,
                    timeout_ms=step_timeout,
                )
                assertion_data = {"expected": res.expected, "actual": res.actual}

            # 10. ASSERT URL
            elif step.action == ActionType.ASSERT_URL:
                url_pattern = step.url or step.expected_text or step.value or ""
                res = self.assertion_engine.assert_url(
                    page,
                    expected_url_pattern=url_pattern,
                    timeout_ms=step_timeout,
                )
                assertion_data = {"expected": res.expected, "actual": res.actual}

            # 11. ASSERT TITLE
            elif step.action == ActionType.ASSERT_TITLE:
                expected_title = step.expected_title or step.expected_text or step.value or ""
                res = self.assertion_engine.assert_title(page, expected_title=expected_title)
                assertion_data = {"expected": res.expected, "actual": res.actual}

            # 12. SCREENSHOT
            elif step.action == ActionType.SCREENSHOT:
                custom_name = step.screenshot_name or f"step_{step.step_number}"
                screenshot_path = str(self.config.screenshots_dir / f"{run_id}_{custom_name}.png")
                page.screenshot(path=screenshot_path, full_page=False)

            # Capture step screenshot if enabled
            if exec_settings.screenshot_on_step and not screenshot_path:
                screenshot_path = str(self.config.screenshots_dir / f"{run_id}_step_{step.step_number}.png")
                page.screenshot(path=screenshot_path, full_page=False)

        except AssertionFailureError as afe:
            status = "FAIL"
            error_msg = str(afe)
            assertion_data = {"expected": afe.expected, "actual": afe.actual, "type": afe.assertion_type}
            if exec_settings.screenshot_on_failure:
                screenshot_path = self._capture_failure_screenshot(page, run_id, step.step_number)

        except LocatorAmbiguityError as lae:
            status = "ERROR"
            error_msg = f"Locator Ambiguity: {lae}"
            if exec_settings.screenshot_on_failure:
                screenshot_path = self._capture_failure_screenshot(page, run_id, step.step_number)

        except LocatorNotFoundError as lnf:
            status = "FAIL"
            error_msg = f"Element Not Found: {lnf}"
            if exec_settings.screenshot_on_failure:
                screenshot_path = self._capture_failure_screenshot(page, run_id, step.step_number)

        except Exception as e:
            status = "ERROR"
            error_msg = self.security_manager.mask_text(str(e))
            if exec_settings.screenshot_on_failure:
                try:
                    screenshot_path = self._capture_failure_screenshot(page, run_id, step.step_number)
                except Exception:
                    pass

        duration_ms = (time.perf_counter() - t0) * 1000.0

        return StepResult(
            step_number=step.step_number,
            action=step.action.value,
            description=step.description,
            status=status,
            duration_ms=duration_ms,
            target_info=target_repr,
            input_value=val_masked,
            screenshot_path=screenshot_path,
            error_message=error_msg,
            assertion_details=assertion_data,
        )

    def _capture_failure_screenshot(self, page: Page, run_id: str, step_num: int) -> str:
        """Capture screenshot on failure and return path."""
        file_path = self.config.screenshots_dir / f"fail_{run_id}_step_{step_num}.png"
        try:
            page.screenshot(path=str(file_path), full_page=False)
            return str(file_path)
        except Exception:
            return ""

    @staticmethod
    def _mark_remaining_skipped(steps: List[ActionStep], start_idx: int, results: List[StepResult]) -> None:
        """Mark remaining steps as SKIPPED after a failure or error."""
        for step in steps[start_idx:]:
            results.append(
                StepResult(
                    step_number=step.step_number,
                    action=step.action.value,
                    description=step.description,
                    status="SKIPPED",
                    duration_ms=0.0,
                    target_info=f"{step.target.strategy.value}:{step.target.value}" if step.target else None,
                    input_value=None,
                    screenshot_path=None,
                    error_message="Skipped due to earlier step failure.",
                )
            )

