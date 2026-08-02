"""Real-behavior tests for the external-dependency probes.

Each probe answers "is this external service available right now?" and must
return a typed :class:`DependencyStatus` — never raise — when the dependency is
absent. These tests exercise the real probes against a deliberately-unreachable
Ollama endpoint and a controlled Playwright cache directory; no mocks.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar, override

import pytest

from ...core import MissingOptionalExtraError, OptionalExtra, require_optional_extra
from ...core.config import override_settings
from ...core.errors import CadrumoError, CoreError
from ..provisioning import (
    OPTIONAL_EXTRAS,
    DependencyStatus,
    probe_ollama_vision,
    probe_optional_extra,
    probe_optional_extras,
    probe_playwright_browser,
    probe_subprocess_providers,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _OllamaTagsEndpoint(BaseHTTPRequestHandler):
    """Loopback Ollama endpoint returning one configured ``/api/tags`` body."""

    payload: ClassVar[object]

    def do_GET(self) -> None:
        if self.path != "/api/tags":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        encoded = json.dumps(self.payload).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    @override
    def log_message(self, format: str, *args: object) -> None:
        """Silence loopback-server request logging during tests."""


@contextmanager
def _serve_ollama_tags(payload: object) -> Iterator[str]:
    _OllamaTagsEndpoint.payload = payload
    server = ThreadingHTTPServer(("127.0.0.1", 0), _OllamaTagsEndpoint)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_probe_ollama_vision_unreachable_returns_unavailable_with_remediation() -> None:
    """An unreachable Ollama endpoint yields unavailable + a `serve` remediation, never an exception."""
    # Port 1 is reserved/closed — the connection is refused fast.
    with override_settings(cadrumo_llm_ollama_chat_url="http://127.0.0.1:1/api/chat"):
        status = probe_ollama_vision()
    assert isinstance(status, DependencyStatus)
    assert status.service == "ollama-vision"
    assert status.available is False
    assert "not reachable" in status.detail
    assert "ollama serve" in status.remediation


@pytest.mark.parametrize("payload", ([], {"models": None}, {"models": [{"name": 7}]}))
def test_probe_ollama_vision_malformed_successful_tags_response_is_unavailable(payload: object) -> None:
    """A real successful tags response with the wrong JSON shape stays a typed unavailable result."""
    with _serve_ollama_tags(payload) as endpoint, override_settings(cadrumo_llm_ollama_chat_url=f"{endpoint}/api/chat"):
        status = probe_ollama_vision()

    assert status.service == "ollama-vision"
    assert status.available is False
    assert "not reachable" in status.detail
    assert "ollama serve" in status.remediation


def test_probe_playwright_browser_absent_when_cache_empty(
    tmp_path: Path,
) -> None:
    """An empty browsers cache reports unavailable with the install command."""
    status = probe_playwright_browser(cache_root=tmp_path)
    assert status.service == "playwright-chromium"
    assert status.available is False
    assert status.remediation == "playwright install chromium"


def test_probe_playwright_browser_present_when_chromium_build_exists(
    tmp_path: Path,
) -> None:
    """A `chromium-*` build directory in the cache reports available."""
    (tmp_path / "chromium-1234").mkdir()
    status = probe_playwright_browser(cache_root=tmp_path)
    assert status.service == "playwright-chromium"
    assert status.available is True
    assert status.remediation == ""


def test_probe_playwright_browser_missing_root_is_unavailable_not_an_error(
    tmp_path: Path,
) -> None:
    """A nonexistent cache root reports unavailable rather than raising OSError."""
    status = probe_playwright_browser(cache_root=tmp_path / "does-not-exist")
    assert status.available is False


def test_probe_subprocess_providers_returns_typed_statuses_and_never_raises() -> None:
    """Each subprocess provider yields one DependencyStatus; the probe never raises on absence."""
    statuses = probe_subprocess_providers()
    assert isinstance(statuses, tuple)
    assert statuses, "expected at least one subprocess LLM provider to be probed"
    for status in statuses:
        assert isinstance(status, DependencyStatus)
        assert status.service.startswith("llm-provider:")
        # A reachable provider carries no remediation; an absent one names the fix.
        if not status.available:
            assert "PATH" in status.remediation


def test_probe_optional_extra_present_for_an_installed_package() -> None:
    """An importable extra reports available with no remediation (dev env has all three)."""
    extra = OptionalExtra(extra="google", import_name="googleapiclient", feature="Google export")
    status = probe_optional_extra(extra)
    assert status.service == "extra:google"
    assert status.available is True
    assert status.remediation == ""


def test_probe_optional_extra_absent_names_the_install_command() -> None:
    """A missing extra reports unavailable with a `pip install cadrumo[<extra>]` remediation, never raising."""
    extra = OptionalExtra(extra="ghost", import_name="aeat_definitely_not_installed_xyz", feature="a ghost feature")
    status = probe_optional_extra(extra)
    assert status.available is False
    assert status.remediation == "pip install cadrumo[ghost]"


def test_probe_optional_extras_covers_every_declared_extra() -> None:
    """The doctor probe enumerates exactly the declared OPTIONAL_EXTRAS, one status each."""
    statuses = probe_optional_extras()
    assert {s.service for s in statuses} == {f"extra:{e.extra}" for e in OPTIONAL_EXTRAS}


def test_require_optional_extra_present_is_a_noop() -> None:
    """An installed extra passes the require-guard without raising."""
    require_optional_extra(OptionalExtra(extra="google", import_name="googleapiclient", feature="Google export"))


def test_require_optional_extra_absent_raises_instructive_import_error() -> None:
    """A missing extra raises one typed Cadrumo error."""
    extra = OptionalExtra(extra="ghost", import_name="aeat_definitely_not_installed_xyz", feature="a ghost feature")
    with pytest.raises(MissingOptionalExtraError) as raised:
        require_optional_extra(extra)
    assert raised.value.extra is extra
    assert raised.value.install_hint == "pip install cadrumo[ghost]"
    assert "pip install cadrumo[ghost]" in str(raised.value)
    assert raised.value.suggestion == "pip install cadrumo[ghost]"
    assert raised.value.context == {
        "extra": "ghost",
        "import_name": "aeat_definitely_not_installed_xyz",
        "feature": "a ghost feature",
    }
    assert raised.value.name == "aeat_definitely_not_installed_xyz"
    assert raised.value.path is None
    assert isinstance(raised.value, CadrumoError)
    assert isinstance(raised.value, CoreError)
    assert isinstance(raised.value, ImportError)


def test_require_optional_extra_absent_is_caught_by_cadrumo_error_boundary() -> None:
    """The central CLI error boundary can catch missing optional extras."""
    extra = OptionalExtra(extra="ghost", import_name="aeat_definitely_not_installed_xyz", feature="a ghost feature")

    caught: CadrumoError | None = None
    try:
        require_optional_extra(extra)
    except CadrumoError as exc:
        caught = exc

    assert isinstance(caught, MissingOptionalExtraError)
    assert isinstance(caught, ImportError)
