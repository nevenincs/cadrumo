"""Real-behavior tests for the external-dependency probes.

Each probe answers "is this external service available right now?" and must
return a typed :class:`DependencyStatus` — never raise — when the dependency is
absent. These tests exercise the real probes against a deliberately-unreachable
Ollama endpoint and a controlled Playwright cache directory; no mocks.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from http import HTTPStatus
from pathlib import Path
from typing import ClassVar, override

import pytest

from ...core import MissingOptionalExtraError, OptionalExtra, require_optional_extra
from ...core.storage_taxonomy import ExternalPathRole
from ...core.config import override_settings
from ...core.errors.hierarchy import CadrumoError, CoreError
from ...tests.loopback_llm import SilentLoopbackHandler, serving_loopback, write_raw_response
from ..provisioning import (
    OPTIONAL_EXTRAS,
    PLAYWRIGHT_BROWSERS_ROOT_ROLE,
    DependencyStatus,
    _playwright_browsers_root,
    probe_ollama_vision,
    probe_optional_extra,
    probe_optional_extras,
    probe_playwright_browser,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _OllamaTagsEndpoint(SilentLoopbackHandler):
    """Loopback Ollama endpoint returning one configured ``/api/tags`` body.

    The body is written verbatim rather than through a well-formed envelope
    builder, because every case here supplies a DELIBERATELY malformed shape --
    a bare list, a null inventory, a numeric model name. A builder that could
    only emit the correct envelope would silently repair the very defect the
    probe is asked to survive.
    """

    payload: ClassVar[object]

    @override
    def do_GET(self) -> None:
        if self.path != "/api/tags":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        write_raw_response(self, json.dumps(self.payload).encode("utf-8"), status=HTTPStatus.OK)


@contextmanager
def _serve_ollama_tags(payload: object) -> Iterator[str]:
    _OllamaTagsEndpoint.payload = payload
    with serving_loopback(_OllamaTagsEndpoint, path="") as endpoint:
        yield endpoint


def test_probe_ollama_vision_unreachable_returns_unavailable_with_remediation() -> None:
    """An unreachable Ollama endpoint yields unavailable + a `serve` remediation, never an exception."""
    # Port 1 is reserved/closed — the connection is refused fast.
    with override_settings(cadrumo_llm_ollama_chat_url="http://127.0.0.1:1/api/chat"):
        status = probe_ollama_vision()
    assert isinstance(status, DependencyStatus)
    assert status.service == "ollama-vision"
    assert status.available is False
    assert status.facts["runtime_reachable"] is False
    assert status.precondition_verdict is not None
    assert status.precondition_verdict.failed_condition_id == "provisioning.runtime.reachable"


@pytest.mark.parametrize("payload", ([], {"models": None}, {"models": [{"name": 7}]}))
def test_probe_ollama_vision_malformed_successful_tags_response_is_unavailable(payload: object) -> None:
    """A real successful tags response with the wrong JSON shape stays a typed unavailable result."""
    with _serve_ollama_tags(payload) as endpoint, override_settings(cadrumo_llm_ollama_chat_url=f"{endpoint}/api/chat"):
        status = probe_ollama_vision()

    assert status.service == "ollama-vision"
    assert status.available is False
    assert status.facts["runtime_reachable"] is False
    assert status.precondition_verdict is not None


def test_probe_playwright_browser_absent_when_cache_empty(
    tmp_path: Path,
) -> None:
    """An empty browsers cache reports unavailable with the install command."""
    status = probe_playwright_browser(cache_root=tmp_path)
    assert status.service == "playwright-chromium"
    assert status.available is False
    assert status.facts["chromium_installed"] is False
    assert status.precondition_verdict is not None
    assert status.precondition_verdict.failed_condition_id == "provisioning.playwright_browser.installed"


def test_probe_playwright_browser_present_when_chromium_build_exists(
    tmp_path: Path,
) -> None:
    """A `chromium-*` build directory in the cache reports available."""
    (tmp_path / "chromium-1234").mkdir()
    status = probe_playwright_browser(cache_root=tmp_path)
    assert status.service == "playwright-chromium"
    assert status.available is True
    assert status.facts["chromium_installed"] is True
    assert status.precondition_verdict is None


def test_probe_playwright_browser_missing_root_is_unavailable_not_an_error(
    tmp_path: Path,
) -> None:
    """A nonexistent cache root reports unavailable rather than raising OSError."""
    status = probe_playwright_browser(cache_root=tmp_path / "does-not-exist")
    assert status.available is False


def test_playwright_browsers_root_escape_is_declared() -> None:
    """The Playwright browser cache carries a positive third-party-cache
    declaration rather than sitting silently outside the storage taxonomy."""
    assert PLAYWRIGHT_BROWSERS_ROOT_ROLE is ExternalPathRole.THIRD_PARTY_CACHE


def test_playwright_browsers_root_still_honours_vendor_env_var(tmp_path: Path) -> None:
    """The declared escape does not change resolution: an explicit
    ``PLAYWRIGHT_BROWSERS_PATH`` still wins over the per-OS default.

    Drives the injectable ``env`` mapping rather than mutating the process
    environment, so the precedence is asserted against a real dict on the same
    branch the live probe takes. ``cache_root`` would not test this: it
    short-circuits before the override is ever read. The absent-override case
    is asserted alongside it, since "the override wins" only means something
    once the default it beats is pinned too.
    """
    vendor_root = tmp_path / "vendor-playwright-cache"

    assert _playwright_browsers_root(env={"PLAYWRIGHT_BROWSERS_PATH": str(vendor_root)}) == vendor_root
    assert _playwright_browsers_root(env={}) != vendor_root


def test_probe_optional_extra_present_for_an_installed_package() -> None:
    """An importable extra reports available with no remediation (dev env has all three)."""
    extra = OptionalExtra(extra="google", import_name="googleapiclient", feature="Google export")
    status = probe_optional_extra(extra)
    assert status.service == "extra:google"
    assert status.available is True
    assert status.facts["importable"] is True
    assert status.precondition_verdict is None


def test_probe_optional_extra_absent_reports_machine_facts_and_closed_outcome() -> None:
    """A missing extra reports its measured identity without manufacturing an install command."""
    extra = OptionalExtra(extra="ghost", import_name="aeat_definitely_not_installed_xyz", feature="a ghost feature")
    status = probe_optional_extra(extra)
    assert status.available is False
    assert status.facts == {"extra": "ghost", "import_name": "aeat_definitely_not_installed_xyz", "importable": False}
    assert status.precondition_verdict is not None
    assert status.precondition_verdict.failed_condition_id == "provisioning.optional_extra.importable"
    assert status.precondition_verdict.no_recovery_outcome == "operator_decision"


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
    # The refusal carries machine identity only: no install command, and no
    # human feature label that would read as operator-facing prose.
    assert "pip install" not in str(raised.value)
    assert raised.value.context == {
        "extra": "ghost",
        "import_name": "aeat_definitely_not_installed_xyz",
        "importable": False,
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
