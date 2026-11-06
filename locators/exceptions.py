"""Exceptions raised by SmartLocator during element resolution."""
from typing import List, Optional


class SmartLocatorError(Exception):
    """Base exception for SmartLocator resolution errors."""
    pass


class LocatorAmbiguityError(SmartLocatorError):
    """Raised when a locator matches multiple elements and cannot be resolved unambiguously."""

    def __init__(
        self,
        message: str,
        match_count: int,
        selector_tried: str,
        candidate_elements: Optional[List[str]] = None,
    ):
        super().__init__(message)
        self.match_count = match_count
        self.selector_tried = selector_tried
        self.candidate_elements = candidate_elements or []


class LocatorNotFoundError(SmartLocatorError):
    """Raised when an element cannot be found after exhausting all priority strategies."""

    def __init__(
        self,
        message: str,
        selector_tried: str,
        strategies_attempted: Optional[List[str]] = None,
    ):
        super().__init__(message)
        self.selector_tried = selector_tried
        self.strategies_attempted = strategies_attempted or []

