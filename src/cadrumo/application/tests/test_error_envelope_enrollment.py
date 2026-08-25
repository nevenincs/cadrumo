"""Real-behavior enrollment test for application-layer regression error classes.

Asserts that every application-layer regression error class is enrolled in
:data:`cadrumo.core.errors.ERROR_REGISTRY` and produces a valid
:class:`cadrumo.core.errors.ErrorEnvelope` through
:func:`cadrumo.core.errors.build_error_envelope`.

No mocks, no skips. The test imports the real error classes, raises them,
and calls the real registry machinery. A missing registration causes a
hard failure in :func:`~cadrumo.core.errors.get_registered_error_code` — the
test will surface it rather than silently return a placeholder.
"""

from __future__ import annotations

import pytest

from ...core.errors import (
    ERROR_REGISTRY,
    CadrumoError,
    ErrorEnvelope,
    build_error_envelope,
    get_registered_error_code,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _assert_enrolled(error_cls: type[CadrumoError], message: str = "test trigger") -> ErrorEnvelope:
    """Raise *error_cls*, catch it, and assert registry round-trip."""
    assert issubclass(error_cls, CadrumoError), f"{error_cls} is not an CadrumoError subclass"
    try:
        raise error_cls(message)
    except error_cls as exc:
        code = get_registered_error_code(exc)
        assert code.code in ERROR_REGISTRY, (
            f"{error_cls.__qualname__} maps to code {code.code!r} which is not present in ERROR_REGISTRY"
        )
        envelope = build_error_envelope(exc)
        assert isinstance(envelope, ErrorEnvelope)
        assert envelope.code == code.code
        return envelope
    # unreachable — satisfies type checker
    raise AssertionError("unreachable")  # pragma: no cover


# ---------------------------------------------------------------------------
# contract — RepositorySetupError
# ---------------------------------------------------------------------------


def test_repository_setup_error_enrolled() -> None:
    from ...adapters.persistence.storage.errors import RepositorySetupError

    envelope = _assert_enrolled(RepositorySetupError, "missing class attribute 'namespace'")
    assert envelope.code == "FAIL_STORAGE_REPOSITORY_SETUP"


# ---------------------------------------------------------------------------
# contract — ProfileLabelAmbiguousError
# ---------------------------------------------------------------------------


def test_profile_label_ambiguous_error_enrolled() -> None:
    from cadrumo.application.workflow.errors import ProfileLabelAmbiguousError

    envelope = _assert_enrolled(ProfileLabelAmbiguousError, "profile label 'test' is ambiguous: 2 buckets carry it")
    assert envelope.code == "REFUSED_PROFILE_LABEL_AMBIGUOUS"


# ---------------------------------------------------------------------------
# contract — RepairIntegrityError and RepairDecisionNotFoundError
# ---------------------------------------------------------------------------


def test_repair_integrity_error_enrolled() -> None:
    from ..repair_integrity import RepairIntegrityError

    envelope = _assert_enrolled(RepairIntegrityError, "decision_id mismatch")
    assert envelope.code == "INTEGRITY_REPAIR_INTEGRITY"


def test_repair_decision_not_found_error_enrolled() -> None:
    from ..repair_integrity import RepairDecisionNotFoundError

    envelope = _assert_enrolled(RepairDecisionNotFoundError, "repair-remediation decision 'abc' does not exist")
    assert envelope.code == "FAIL_REPAIR_DECISION_NOT_FOUND"


def test_repair_decision_not_found_is_subtype_of_repair_integrity() -> None:
    from ..repair_integrity import RepairDecisionNotFoundError, RepairIntegrityError

    assert issubclass(RepairDecisionNotFoundError, RepairIntegrityError)


# ---------------------------------------------------------------------------
# contract — SnapshotNotFoundError (now CadrumoError + KeyError)
# ---------------------------------------------------------------------------


def test_snapshot_not_found_error_enrolled() -> None:
    from ..live import SnapshotNotFoundError

    assert issubclass(SnapshotNotFoundError, CadrumoError), "SnapshotNotFoundError must inherit CadrumoError"
    assert issubclass(SnapshotNotFoundError, KeyError), "SnapshotNotFoundError must still inherit KeyError"
    envelope = _assert_enrolled(SnapshotNotFoundError, "snapshot abc not found")
    assert envelope.code == "FAIL_SNAPSHOT_NOT_FOUND"


def test_snapshot_not_found_subclasses_still_work() -> None:
    """Per-service subclasses remain catchable as both CadrumoError and KeyError."""
    from ..live import BorradorSnapshotNotFoundError, SnapshotNotFoundError

    assert issubclass(BorradorSnapshotNotFoundError, SnapshotNotFoundError)
    assert issubclass(BorradorSnapshotNotFoundError, CadrumoError)
    assert issubclass(BorradorSnapshotNotFoundError, KeyError)


# ---------------------------------------------------------------------------
# ModeloApplicabilityFilterError — pre-existing, asserted here for coverage
# ---------------------------------------------------------------------------


def test_modelo_applicability_filter_error_enrolled() -> None:
    from ..modelo import ModeloApplicabilityFilterError

    envelope = _assert_enrolled(ModeloApplicabilityFilterError, "Unknown applicability filter: 'bad_filter'")
    assert envelope.code is not None
    assert envelope.code in ERROR_REGISTRY
