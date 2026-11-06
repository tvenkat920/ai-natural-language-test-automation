"""conftest.py — shared fixtures for all tests, including a local HTTP server for integration tests."""
import functools
import http.server
import socket
import sys
import threading
from pathlib import Path

# Ensure project root is importable from any test file
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from planner.llm.providers.mock_provider import MockLLMProvider


@pytest.fixture
def mock_provider():
    return MockLLMProvider()


@pytest.fixture(scope="session")
def local_http_server():
    """
    Spins up a lightweight local HTTP server serving the tests/ directory.
    Enforces HTTP/HTTPS protocol compliance required by the security policy.
    """
    tests_dir = Path(__file__).parent.resolve()

    # Find a free port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(tests_dir))
    server = http.server.HTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    yield f"http://127.0.0.1:{port}"

    server.shutdown()
    server.server_close()


@pytest.fixture
def sample_html_url(local_http_server):
    """HTTP URL pointing to the local sample HTML page via the local HTTP server."""
    return f"{local_http_server}/sample_page.html"
