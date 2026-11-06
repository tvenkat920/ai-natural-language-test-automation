"""Security manager module for credential protection and execution safety."""
from .manager import SecurityManager, SecurityViolationError

__all__ = ["SecurityManager", "SecurityViolationError"]

