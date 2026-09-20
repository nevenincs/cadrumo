"""Real-behavior tests for the external-dependency probes.

Each probe answers "is this external service available right now?" and must
return a typed :class:`DependencyStatus` — never raise — when the dependency is
absent. These tests exercise the real probes against a deliberately-unreachable
Ollama endpoint and a controlled Playwright cache directory; no mocks.
"""

from __future__ import annotations

import json
from collections.abc import Generator
from contextlib import contextmanager
from http import HTTPStatus
from pathlib import Path
from typing import ClassVar, override

import pytest

from ...core.config import override_settings
from ...core.errors.hierarchy import CadrumoError, CoreError, CoreValidationError
from ...core.model_catalogue import ModelRole
from ...core.optional_extras import OPTIONAL_EXTRAS, MissingOptionalExtraError, OptionalExtra, require_optional_extra
from ...domain.calculations.registry.authority_store import AuthorityDescriptor, AuthorityStoreError
from ...domain.calculations.registry.errors import AuthorityDescriptorUnavailableError
from ...tests.loopback_llm import SilentLoopbackHandler, serving_loopback, write_raw_response
from ..local_reader import probe_local_reader
from ..provisioning import (
    DependencyStatus,
    ensure_cli_startup_dependencies,
    probe_optional_extra,
    probe_optional_extras,
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
def _serve_ollama_tags(payload: object) -> Generator[str]:
    _OllamaTagsEndpoint.payload = payload
    with serving_loopback(_OllamaTagsEndpoint, path="") as endpoint:
        yield endpoint


def test_local_reader_probe_unreachable_returns_unavailable_with_remediation() -> None:
    """An unreachable runtime yields a typed unavailable result, never an exception."""
    # Port 1 is reserved/closed — the connection is refused fast.
    with override_settings(cadrumo_llm_ollama_chat_url="http://127.0.0.1:1/api/chat"):
        status = probe_local_reader(ModelRole.VISION_TRANSCRIPTION)
    assert isinstance(status, DependencyStatus)
    assert status.service == "local-reader:vision_transcription"
    assert status.available is False
    assert status.facts["runtime_reachable"] is False
    assert status.precondition_verdict is not None
    assert status.precondition_verdict.failed_condition_id == "provisioning.runtime.reachable"


@pytest.mark.parametrize("payload", ([], {"models": None}, {"models": [{"name": 7}]}))
def test_local_reader_probe_malformed_successful_tags_response_is_unavailable(payload: object) -> None:
    """A real successful tags response with the wrong JSON shape stays a typed unavailable result."""
    with _serve_ollama_tags(payload) as endpoint, override_settings(cadrumo_llm_ollama_chat_url=f"{endpoint}/api/chat"):
        status = probe_local_reader(ModelRole.VISION_TRANSCRIPTION)

    assert status.service == "local-reader:vision_transcription"
    assert status.available is False
    assert status.facts["runtime_reachable"] is False
    assert status.precondition_verdict is not None


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
    # A registered refusal, not an import failure: an adapter's bare
    # ``except ImportError`` must not swallow it into a silent fallback.
    assert not isinstance(raised.value, ImportError)


def test_require_optional_extra_absent_is_caught_by_cadrumo_error_boundary() -> None:
    """The central CLI error boundary can catch missing optional extras."""
    extra = OptionalExtra(extra="ghost", import_name="aeat_definitely_not_installed_xyz", feature="a ghost feature")

    caught: CadrumoError | None = None
    try:
        require_optional_extra(extra)
    except CadrumoError as exc:
        caught = exc

    assert isinstance(caught, MissingOptionalExtraError)


def test_missing_optional_extra_is_not_absorbed_by_an_import_error_handler() -> None:
    """A bare ``except ImportError`` around a guarded feature lets the refusal through."""
    extra = OptionalExtra(extra="ghost", import_name="aeat_definitely_not_installed_xyz", feature="a ghost feature")

    with pytest.raises(MissingOptionalExtraError):
        try:
            require_optional_extra(extra)
        except ImportError:
            pytest.fail("the typed refusal was absorbed as an ImportError")


def test_startup_dependencies_refuse_missing_explicit_storage_before_materializing_defaults(tmp_path: Path) -> None:
    """An invalid operator path fails before startup creates application-owned paths."""
    root = tmp_path / "state"
    tokens = tmp_path / "operator-tokens"

    with (
        override_settings(cadrumo_local_storage_root=root, cadrumo_token_dir=tokens),
        pytest.raises(CoreValidationError) as refusal,
    ):
        ensure_cli_startup_dependencies()

    assert refusal.value.context == {
        "state_directory_target": str(tokens),
        "occupied_by_file": False,
        "directory_created": False,
        "explicit_override": True,
    }
    assert not root.exists()


def test_startup_dependencies_require_the_selected_published_authority(tmp_path: Path) -> None:
    """Startup never creates or falls back from an explicitly selected authority root."""
    root = tmp_path / "state"
    authority_root = tmp_path / "absent-authority"

    with (
        override_settings(cadrumo_local_storage_root=root, cadrumo_authority_root=authority_root),
        pytest.raises(AuthorityDescriptorUnavailableError) as refusal,
    ):
        ensure_cli_startup_dependencies()

    assert refusal.value.authority_root_configured is True
    assert refusal.value.searched_path == authority_root / "authority.current.json"
    assert (root / "cache" / "llm-cache").is_dir()
    assert not authority_root.exists(), "runtime startup must not generate or provision authority"


def test_startup_dependencies_require_the_descriptor_selected_database(tmp_path: Path) -> None:
    """A descriptor without its shipped database is an unavailable authority."""
    root = tmp_path / "state"
    authority_root = tmp_path / "authority"
    authority_root.mkdir()
    digest = "0" * 64
    descriptor = AuthorityDescriptor(
        database=f"authority-{digest}.sqlite3",
        database_size=1,
        database_sha256=digest,
        logical_generation="1" * 64,
    )
    (authority_root / "authority.current.json").write_bytes(descriptor.to_bytes())

    with (
        override_settings(cadrumo_local_storage_root=root, cadrumo_authority_root=authority_root),
        pytest.raises(AuthorityStoreError, match="authority database is unavailable"),
    ):
        ensure_cli_startup_dependencies()

    assert not (authority_root / descriptor.database).exists(), "runtime startup must not generate authority bytes"
