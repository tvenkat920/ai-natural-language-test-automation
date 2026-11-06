"""Unit tests for SecurityManager — URL validation, credential masking, and code injection detection."""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from security.manager import SecurityManager, SecurityViolationError


@pytest.fixture
def sec():
    return SecurityManager()


class TestURLValidation:
    def test_valid_https(self, sec):
        result = sec.validate_url("https://example.com")
        assert result == "https://example.com"

    def test_valid_http(self, sec):
        result = sec.validate_url("http://example.com/path?q=1")
        assert result == "http://example.com/path?q=1"

    def test_javascript_blocked(self, sec):
        with pytest.raises(SecurityViolationError, match="javascript"):
            sec.validate_url("javascript:alert('xss')")

    def test_file_protocol_blocked(self, sec):
        with pytest.raises(SecurityViolationError, match="file"):
            sec.validate_url("file:///etc/passwd")

    def test_data_uri_blocked(self, sec):
        with pytest.raises(SecurityViolationError, match="data"):
            sec.validate_url("data:text/html,<h1>XSS</h1>")

    def test_ftp_blocked(self, sec):
        with pytest.raises(SecurityViolationError):
            sec.validate_url("ftp://ftp.example.com/file")

    def test_empty_url_rejected(self, sec):
        with pytest.raises(SecurityViolationError, match="non-empty"):
            sec.validate_url("")

    def test_missing_hostname_rejected(self, sec):
        with pytest.raises(SecurityViolationError, match="hostname"):
            sec.validate_url("https://")

    def test_newline_injection_rejected(self, sec):
        with pytest.raises(SecurityViolationError, match="newline"):
            sec.validate_url("https://example.com\nmalicious: header")

    def test_localhost_allowed_by_default(self, sec):
        result = sec.validate_url("http://localhost:8080/page")
        assert "localhost" in result

    def test_localhost_blocked_when_disabled(self):
        sec = SecurityManager(allow_localhost=False)
        with pytest.raises(SecurityViolationError, match="Localhost"):
            sec.validate_url("http://localhost/api")

    def test_domain_scope_enforcement_pass(self):
        sec = SecurityManager(
            allowed_domains=["example.com"],
            enforce_domain_scope=True,
        )
        result = sec.validate_url("https://example.com/page")
        assert result is not None

    def test_domain_scope_enforcement_subdomain(self):
        sec = SecurityManager(
            allowed_domains=["example.com"],
            enforce_domain_scope=True,
        )
        result = sec.validate_url("https://app.example.com/dashboard")
        assert result is not None

    def test_domain_scope_enforcement_fail(self):
        sec = SecurityManager(
            allowed_domains=["example.com"],
            enforce_domain_scope=True,
            allow_localhost=False,
        )
        with pytest.raises(SecurityViolationError, match="outside the authorized domain"):
            sec.validate_url("https://evil.com/steal")


class TestCredentialMasking:
    def test_secret_registered_and_masked(self, sec):
        sec.register_secret("super_secret_password")
        result = sec.mask_text("User typed super_secret_password in the field")
        assert "super_secret_password" not in result
        assert "********" in result

    def test_multiple_secrets_masked(self, sec):
        sec.register_secret("pass1")
        sec.register_secret("pass2")
        text = "Credentials: pass1 and pass2"
        result = sec.mask_text(text)
        assert "pass1" not in result
        assert "pass2" not in result

    def test_non_secret_text_unchanged(self, sec):
        sec.register_secret("secret123")
        text = "This is public information"
        result = sec.mask_text(text)
        assert result == text

    def test_short_secret_not_registered(self, sec):
        sec.register_secret("ab")  # too short
        result = sec.mask_text("ab is a short string")
        assert result == "ab is a short string"

    def test_none_input_returns_empty_string(self, sec):
        assert sec.mask_text(None) == ""


class TestDynamicCodeDetection:
    @pytest.mark.parametrize("dangerous", [
        "eval(user_input)",
        "__import__('os').system('ls')",
        "exec('malicious code')",
        "os.system('rm -rf')",
        "subprocess.run(['sh', '-c', 'whoami'])",
        "import os",
        "import sys",
    ])
    def test_dangerous_patterns_rejected(self, dangerous):
        with pytest.raises(SecurityViolationError, match="Dynamic code"):
            SecurityManager.ensure_no_dynamic_code(dangerous)

    def test_safe_strings_pass(self):
        safe_strings = [
            "Click the login button",
            "Enter your email address",
            "assert_visible('heading')",
            "Navigate to https://example.com",
        ]
        for s in safe_strings:
            SecurityManager.ensure_no_dynamic_code(s)  # Should not raise

