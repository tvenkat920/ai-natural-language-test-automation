"""Security manager for safe URL validation, credential masking, and execution boundaries."""
import ipaddress
import re
from typing import Iterable, Optional, Set
from urllib.parse import urlparse


class SecurityViolationError(Exception):
    """Raised when an operation violates security policy (e.g. unsafe URL, forbidden protocol)."""
    pass


class SecurityManager:
    """Enforces safety rules: protocol allowlist, domain bounds, secret masking, and no dynamic code execution."""

    ALLOWED_SCHEMES = {"http", "https"}
    BLOCKED_SCHEMES = {"file", "javascript", "data", "ftp", "chrome", "about", "vbscript"}

    def __init__(
        self,
        allowed_domains: Optional[Iterable[str]] = None,
        enforce_domain_scope: bool = False,
        allow_localhost: bool = True,
    ):
        self.enforce_domain_scope = enforce_domain_scope
        self.allow_localhost = allow_localhost
        self.allowed_domains: Set[str] = set()
        if allowed_domains:
            for domain in allowed_domains:
                clean = domain.strip().lower()
                if "://" in clean:
                    clean = urlparse(clean).netloc
                self.allowed_domains.add(clean.split(":")[0])  # Strip port for domain match

        self._masked_secrets: Set[str] = set()

    def register_secret(self, secret: Optional[str]) -> None:
        """Register a sensitive string to be masked across logs and reports."""
        if secret and len(secret.strip()) >= 3:
            self._masked_secrets.add(secret.strip())

    def mask_text(self, text: Optional[str]) -> str:
        """Replace registered secrets with asterisks in any text."""
        if not text:
            return ""
        result = str(text)
        for secret in self._masked_secrets:
            if secret in result:
                result = result.replace(secret, "********")
        return result

    def validate_url(self, url: str) -> str:
        """
        Validate URL scheme, structure, and optional domain scope.
        Returns the sanitized URL if valid, or raises SecurityViolationError.
        """
        if not url or not isinstance(url, str):
            raise SecurityViolationError("URL must be a non-empty string.")

        clean_url = url.strip()

        # Reject disallowed characters or multi-line injection
        if "\n" in clean_url or "\r" in clean_url:
            raise SecurityViolationError("URL contains illegal newline characters.")

        parsed = urlparse(clean_url)
        scheme = parsed.scheme.lower()

        if scheme in self.BLOCKED_SCHEMES:
            raise SecurityViolationError(
                f"Protocol '{scheme}://' is strictly prohibited for security reasons."
            )

        if scheme not in self.ALLOWED_SCHEMES:
            raise SecurityViolationError(
                f"Protocol '{scheme}://' is not allowed. Only HTTP and HTTPS are permitted."
            )

        if not parsed.netloc:
            raise SecurityViolationError(f"URL '{clean_url}' is missing a valid hostname.")

        hostname = (parsed.hostname or "").lower()

        # Check localhost handling
        is_local = hostname in {"localhost", "127.0.0.1", "::1"} or hostname.endswith(".local")
        if not self.allow_localhost and is_local:
            raise SecurityViolationError("Localhost navigation is restricted by security policy.")

        # If domain scope enforcement is active and allowed_domains is configured:
        if self.enforce_domain_scope and self.allowed_domains:
            # Check if hostname matches or is a subdomain of any allowed domain
            matched = any(
                hostname == d or hostname.endswith(f".{d}")
                for d in self.allowed_domains
            )
            if not matched and not (self.allow_localhost and is_local):
                raise SecurityViolationError(
                    f"Navigation target '{hostname}' is outside the authorized domain scope: {sorted(self.allowed_domains)}"
                )

        return clean_url

    def add_allowed_domain_from_url(self, base_url: str) -> None:
        """Extract domain from base URL and add to authorized domain scope."""
        parsed = urlparse(base_url)
        if parsed.hostname:
            self.allowed_domains.add(parsed.hostname.lower())

    @staticmethod
    def ensure_no_dynamic_code(value: str) -> None:
        """Inspect strings to ensure no dangerous shell/python execution patterns."""
        dangerous_patterns = [
            r"__import__",
            r"eval\s*\(",
            r"exec\s*\(",
            r"os\.system",
            r"subprocess\.",
            r"import\s+os",
            r"import\s+sys",
        ]
        for pattern in dangerous_patterns:
            if re.search(pattern, value):
                raise SecurityViolationError(
                    f"Dynamic code or execution pattern detected and rejected: '{pattern}'"
                )

