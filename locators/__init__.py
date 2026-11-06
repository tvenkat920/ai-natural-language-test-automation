"""SmartLocator module for accessibility-first, semantic DOM element location."""
from .exceptions import LocatorAmbiguityError, LocatorNotFoundError, SmartLocatorError
from .smart_locator import SmartLocator

__all__ = [
    "SmartLocator",
    "SmartLocatorError",
    "LocatorAmbiguityError",
    "LocatorNotFoundError",
]

