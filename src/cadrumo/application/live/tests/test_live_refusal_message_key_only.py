"""No live-read refusal authors its own sentence; every one renders as its key.

Two independent proofs, because either alone is escapable.

The AST proof walks every module in the live package and refuses any raise of a
live-owned error that supplies message text at all -- positionally or through
``message=``. That shape is the specific defect this guard exists for: an
authored sentence passed *alongside* a registered ``translated_message`` key
hides from every key-and-context assertion, because resolution prefers the key,
while ``str(exc)`` prefers the positional argument and carries the English into
tracebacks, structured logs and every direct rendering, in every locale. A
key-and-context assertion therefore cannot detect it; only an absence check can.

The runtime proof constructs each live error family the way production does and
asserts the *absence* directly: ``str(exc)`` equals the locale key. A refusal
that starts smuggling prose fails here even if it is raised from a module the
AST walk has not been taught about.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ....core import NoRecoveryOutcome
from ....core.directory_scan import scan_directory
from ..borrador_100 import Borrador100SnapshotRepository, BorradorSnapshotNotFoundError
from ..errors import (
    LiveApplicationError,
    LiveApplicationInputError,
    LiveReadPrecondition,
    live_read_no_recovery_verdict,
)
from ..snapshot_base import (
    SnapshotLifecycleState,
    enforce_snapshot_state_invariants,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LIVE_PACKAGE = Path(__file__).resolve().parent.parent

#: Error classes this package owns and raises. Errors from other packages
#: (``AttributeError``, the storage envelope errors) are governed by their own
#: owners' rules, so policing them from here would be reaching outside the
#: package boundary.
_LIVE_OWNED_ERRORS: frozenset[str] = frozenset(
    {
        "BorradorSnapshotNotFoundError",
        "DeudasSnapshotNotFoundError",
        "ExpedientesSnapshotNotFoundError",
        "JustificanteCaptureSnapshotNotFoundError",
        "LiveApplicationError",
        "LiveApplicationInputError",
        "NotificationDocumentNotFoundError",
        "NotificationsSnapshotNotFoundError",
        "SnapshotNotFoundError",
        "VerifyObservationNotFoundError",
    }
)

#: The one live error whose constructor *requires* a message argument, because
#: it routes the surface label through it. One of its raise sites lives outside
#: this package, so retiring that argument is a cross-package change rather
#: than a live-package one and is deliberately not attempted here.
_AUTHORED_MESSAGE_EXEMPT: frozenset[str] = frozenset({"LiveIvaSurfaceTimeoutError"})


def _live_modules() -> tuple[Path, ...]:
    return scan_directory(_LIVE_PACKAGE, pattern="*.py")


def _authored_message_sites(path: Path) -> list[tuple[str, int]]:
    """Return every live-owned raise site in ``path`` that supplies message text."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    offenders: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        name = node.func.id
        if name not in _LIVE_OWNED_ERRORS or name in _AUTHORED_MESSAGE_EXEMPT:
            continue
        authors = bool(node.args) or any(keyword.arg == "message" for keyword in node.keywords)
        if authors:
            offenders.append((name, node.lineno))
    return offenders


def test_the_live_owned_error_roster_still_names_live_errors() -> None:
    """Keep the roster honest: every named class must still exist in this package.

    Without this anchor a rename would silently shrink the scan's reach and the
    gate would pass vacuously on the class it stopped seeing.
    """
    declared: set[str] = set()
    for path in _live_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        declared.update(node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef))

    missing = sorted(_LIVE_OWNED_ERRORS - declared)
    assert missing == [], f"the roster names classes this package no longer declares: {missing}"


def test_no_live_module_raise_site_authors_its_own_message() -> None:
    modules = _live_modules()
    assert modules, "the live package scan found no modules to check"

    offenders = {path.name: sites for path in modules if (sites := _authored_message_sites(path))}
    assert offenders == {}, f"live refusals must carry a locale key, never authored text: {offenders}"


def test_the_authored_message_scan_detects_the_defect_it_guards_against(tmp_path: Path) -> None:
    """Prove the AST scan bites on both shapes of the defect it exists for."""
    positional = tmp_path / "positional.py"
    positional.write_text(
        "raise LiveApplicationInputError(\n"
        '    "bucket_id must not be blank",\n'
        '    translated_message="application.live.borrador.errors.bucket_id_blank",\n'
        ")\n",
        encoding="utf-8",
    )
    keyword = tmp_path / "keyword.py"
    keyword.write_text(
        "raise LiveApplicationInputError(\n"
        '    message="bucket_id must not be blank",\n'
        '    translated_message="application.live.borrador.errors.bucket_id_blank",\n'
        ")\n",
        encoding="utf-8",
    )
    clean = tmp_path / "clean.py"
    clean.write_text(
        "raise LiveApplicationInputError(\n"
        '    translated_message="application.live.borrador.errors.bucket_id_blank",\n'
        ")\n",
        encoding="utf-8",
    )

    assert _authored_message_sites(positional) == [("LiveApplicationInputError", 1)]
    assert _authored_message_sites(keyword) == [("LiveApplicationInputError", 1)]
    assert _authored_message_sites(clean) == []


@pytest.mark.parametrize(
    "key",
    [
        "application.live.borrador.errors.bucket_id_blank",
        "application.live.justificante.errors.csv_mismatch",
        "application.live.snapshot_base.errors.service_bucket_mismatch",
    ],
)
def test_live_refusal_renders_as_its_key_and_never_as_prose(key: str) -> None:
    error = LiveApplicationInputError(translated_message=key, context={"probe": True})

    assert str(error) == key
    assert error.translated_message == key
    assert error.args == (key,)


def test_snapshot_state_invariant_refusal_renders_as_its_key() -> None:
    with pytest.raises(LiveApplicationInputError) as excinfo:
        enforce_snapshot_state_invariants(
            state=SnapshotLifecycleState.SUPERSEDED,
            has_supersession_pointer=False,
            discarded_at=None,
            discarded_by="",
        )

    key = "application.live.snapshot_base.errors.state_supersession_pointer_required"
    assert str(excinfo.value) == key


def test_borrador_object_key_refusal_renders_as_its_key() -> None:
    from ..borrador_100 import borrador_100_snapshot_object_key

    with pytest.raises(LiveApplicationInputError) as excinfo:
        borrador_100_snapshot_object_key("  ", "snapshot")

    assert str(excinfo.value) == "application.live.borrador.errors.bucket_id_blank"


def test_borrador_repository_constructor_refusal_renders_as_its_key() -> None:
    with pytest.raises(LiveApplicationInputError) as excinfo:
        Borrador100SnapshotRepository(bucket_id="   ")

    assert str(excinfo.value) == "application.live.borrador.errors.bucket_id_blank"


def test_borrador_snapshot_not_found_renders_as_its_key() -> None:
    """The snapshot-miss family renders its key, quoted by ``KeyError.__str__``.

    ``SnapshotNotFoundError`` inherits :class:`KeyError` so a lookup miss stays a
    mapping-style miss, and ``KeyError.__str__`` returns ``repr(args[0])`` rather
    than the argument itself. The rendered text is therefore the quoted key, and
    the absence check has to compare against ``repr(key)``. What matters is
    unchanged: no locale-specific prose survives anywhere in the rendering.
    """
    key = "application.live.borrador.errors.snapshot_not_found"
    error = BorradorSnapshotNotFoundError(translated_message=key, context={"snapshot_id": "a" * 64})

    assert str(error) == repr(key)
    assert error.args == (key,)
    assert error.translated_message == key
    assert error.context == {"snapshot_id": "a" * 64}


def test_a_live_refusal_carries_an_explicit_safety_disposition_not_a_retry_action() -> None:
    """A live-read failure with no safe retry states that, and binds no action."""
    verdict = live_read_no_recovery_verdict(
        LiveReadPrecondition.JUSTIFICANTE_MATCHES_FILING_RECORD,
        facts={"filing_record_id": "filing-1", "matches_filing_record": False},
    )
    error = LiveApplicationInputError(
        translated_message="application.live.justificante.errors.filing_record_mismatch",
        context={"filing_record_id": "filing-1"},
        precondition_verdict=verdict,
    )

    assert error.terminal_precondition_verdict is verdict
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.SAFETY
    assert verdict.action is None
    assert verdict.argument_bindings == ()
    assert verdict.failed_condition_id == "live.justificante.matches_filing_record"


def test_a_live_refusal_without_a_safety_disposition_carries_no_verdict() -> None:
    error = LiveApplicationError(translated_message="application.live.iva_wallet.errors.decision_reload_diverged")

    assert error.terminal_precondition_verdict is None
