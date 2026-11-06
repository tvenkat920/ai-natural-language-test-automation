"""SmartLocator: Priority-based accessible, semantic element resolution with ambiguity detection."""
import re
from typing import Any, List, Optional, Tuple
from planner.models import LocatorStrategy, SmartLocatorTarget
from .exceptions import LocatorAmbiguityError, LocatorNotFoundError, SmartLocatorError


class SmartLocator:
    """
    Resolves DOM elements using prioritized accessibility strategies:
    1. Test IDs (data-testid, id)
    2. Accessible Roles & Names (role='button', 'textbox', etc.)
    3. Associated Labels
    4. Input Placeholders
    5. Exact / Substring Text
    6. Semantic CSS / XPath selectors

    Safely detects and reports ambiguity if multiple conflicting elements match.
    """

    def __init__(self, page: Any, default_timeout_ms: int = 5000):
        self.page = page
        self.default_timeout_ms = default_timeout_ms

    def resolve(
        self,
        target: SmartLocatorTarget,
        timeout_ms: Optional[int] = None,
    ) -> Any:
        """
        Resolve a SmartLocatorTarget to a single unique Playwright Locator.
        Raises LocatorAmbiguityError if ambiguous, or LocatorNotFoundError if not found.
        """
        timeout = timeout_ms if timeout_ms is not None else self.default_timeout_ms
        strategy = target.strategy

        if strategy != LocatorStrategy.AUTO:
            loc = self._build_single_strategy_locator(strategy, target)
            return self._verify_and_disambiguate(loc, target, str(strategy.value), timeout)

        # AUTO strategy: try prioritized heuristics
        attempts: List[Tuple[str, Any]] = []

        # 1. Explicit Role + Name if provided
        if target.role:
            name = target.name
            if not name and target.value and target.value.lower() != target.role.lower():
                name = target.value
            if name:
                role_loc = self.page.get_by_role(target.role, name=name, exact=target.exact)
            else:
                role_loc = self.page.get_by_role(target.role)
            attempts.append((f"role:{target.role}", role_loc))

        # 2. Test ID
        test_id_val = target.value.strip()
        if test_id_val.startswith("data-testid=") or test_id_val.startswith("test-"):
            clean_id = test_id_val.replace("data-testid=", "").strip("\"'")
            attempts.append(("test_id", self.page.get_by_test_id(clean_id)))
        else:
            attempts.append(("test_id", self.page.get_by_test_id(test_id_val)))

        # 3. Label
        attempts.append(("label", self.page.get_by_label(target.value, exact=target.exact)))

        # 4. Placeholder
        attempts.append(("placeholder", self.page.get_by_placeholder(target.value, exact=target.exact)))

        # 5. Role fallback for common elements (button, link, textbox) if not already specified
        if not target.role:
            attempts.append(("role:button", self.page.get_by_role("button", name=target.value, exact=target.exact)))
            attempts.append(("role:link", self.page.get_by_role("link", name=target.value, exact=target.exact)))
            attempts.append(("role:textbox", self.page.get_by_role("textbox", name=target.value, exact=target.exact)))

        # 6. Text content
        attempts.append(("text", self.page.get_by_text(target.value, exact=target.exact)))

        # 7. CSS / XPath fallback
        attempts.append(("css/xpath", self.page.locator(target.value)))

        # Evaluate attempts in order with short per-strategy probe
        probe_timeout = min(1200, max(250, timeout // len(attempts)))
        strategies_tried: List[str] = []

        for strat_name, loc in attempts:
            strategies_tried.append(strat_name)
            try:
                # Wait briefly for presence
                loc.first.wait_for(state="attached", timeout=probe_timeout)
                count = loc.count()
                if count > 0:
                    return self._verify_and_disambiguate(loc, target, strat_name, timeout)
            except Exception:
                continue

        # If we reached here, no strategy found the element
        raise LocatorNotFoundError(
            f"Could not locate element with target value '{target.value}'. "
            f"Strategies attempted: {', '.join(strategies_tried)}.",
            selector_tried=target.value,
            strategies_attempted=strategies_tried,
        )

    def _build_single_strategy_locator(self, strategy: LocatorStrategy, target: SmartLocatorTarget) -> Any:
        """Build locator according to an explicit strategy."""
        if strategy == LocatorStrategy.ROLE:
            role = target.role or target.value
            name = target.name
            if not name and target.value and target.role and target.value.lower() != target.role.lower():
                name = target.value
            if name:
                return self.page.get_by_role(role, name=name, exact=target.exact)
            return self.page.get_by_role(role)
        elif strategy == LocatorStrategy.LABEL:
            return self.page.get_by_label(target.value, exact=target.exact)
        elif strategy == LocatorStrategy.PLACEHOLDER:
            return self.page.get_by_placeholder(target.value, exact=target.exact)
        elif strategy == LocatorStrategy.TEST_ID:
            clean_id = target.value.replace("data-testid=", "").strip("\"'")
            return self.page.get_by_test_id(clean_id)
        elif strategy == LocatorStrategy.TEXT:
            return self.page.get_by_text(target.value, exact=target.exact)
        elif strategy in (LocatorStrategy.CSS, LocatorStrategy.XPATH):
            return self.page.locator(target.value)
        else:
            return self.page.locator(target.value)

    def _verify_and_disambiguate(
        self,
        locator: Any,
        target: SmartLocatorTarget,
        strategy_name: str,
        timeout_ms: int,
    ) -> Any:
        """
        Verify locator match count and enforce strict uniqueness unless index is explicitly provided.
        """
        # If caller explicitly provided an index (e.g. index=0), honor it directly
        if target.index is not None:
            return locator.nth(target.index)

        try:
            locator.first.wait_for(state="attached", timeout=timeout_ms)
        except Exception as e:
            raise LocatorNotFoundError(
                f"Element '{target.value}' not found using strategy '{strategy_name}' within {timeout_ms}ms.",
                selector_tried=target.value,
                strategies_attempted=[strategy_name],
            ) from e

        count = locator.count()
        if count == 1:
            return locator

        # If count > 1, check visibility filter: maybe only one of them is currently visible
        try:
            visible_locator = locator.locator("visible=true")
            visible_count = visible_locator.count()
            if visible_count == 1:
                return visible_locator
            if visible_count > 1:
                count = visible_count
                locator = visible_locator
        except Exception:
            pass

        # Inspect candidate elements for diagnostic reporting
        candidates: List[str] = []
        try:
            sample_count = min(count, 5)
            for i in range(sample_count):
                el = locator.nth(i)
                tag = el.evaluate("e => e.tagName.toLowerCase()")
                txt = (el.text_content() or "").strip()[:40]
                cls = el.get_attribute("class") or ""
                candidates.append(f"<{tag} class='{cls}'>{txt}</{tag}>")
        except Exception:
            pass

        raise LocatorAmbiguityError(
            f"Ambiguous target: {count} elements matched '{target.value}' using '{strategy_name}'. "
            f"Candidates: {candidates}. Please refine locator with a more specific label, role, or unique selector.",
            match_count=count,
            selector_tried=target.value,
            candidate_elements=candidates,
        )

