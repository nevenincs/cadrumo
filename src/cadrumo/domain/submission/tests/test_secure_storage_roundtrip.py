"""Strict roundtrip across the encrypted SubmissionRepository boundary.

``SubmissionRepository`` persists :class:`ModeloPresentado` records at
``SensitivityClass.AUDIT`` — historical attested-filing records that
must survive verbatim across the encrypted-storage boundary.

Anti-tautology discipline: every defaultable field is set to a
non-default value. ``status``
is ACEPTADA (the most-constrained state — its model_validator
requires both justificante_csv AND justificante_pdf_path), so the
typed contract proves the boundary actually carries those values
end-to-end.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....adapters.persistence.profile.submission import SubmissionRepository
from ....core.period import Period
from ....tests.secure_sql import isolated_runtime_profile, mutate_encrypted_secure_object_json
from .._models import (
    ModeloPresentado,
    SubmissionAttempt,
    SubmissionStatus,
    make_submission_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PERIOD = Period.from_year_and_code(2025, "1T")
_ACKNOWLEDGED_AT = datetime(2026, 5, 27, 10, 30, 0, tzinfo=UTC)


def _populated_filing() -> ModeloPresentado:
    """Build a ModeloPresentado with every defaultable field non-default.

    Anti-tautology: status=ACEPTADA forces justificante_csv +
    justificante_pdf_path to be populated; acknowledged_at also set.
    Two attempts so the tuple-of-attempts surface is exercised, with
    distinct status / error fields per attempt.  ``period`` is a typed
    :class:`~cadrumo.core.Period` (non-default) so the persistence boundary
    is proven to carry the structured value end-to-end.
    """

    now = _ACKNOWLEDGED_AT
    draft_id = "d" * 64
    submission_id = make_submission_id(draft_id, attempt_ordinal=2)
    return ModeloPresentado(
        submission_id=submission_id,
        draft_id=draft_id,
        modelo="303",
        period=_PERIOD,
        profile_tax_id="12345678Z",
        status=SubmissionStatus.ACEPTADA,
        justificante_csv="ABCD12345678EFGH",
        justificante_pdf_path=Path("justificantes/303-2025Q1-ABCD.pdf"),
        submitted_at=now - timedelta(minutes=10),
        acknowledged_at=now,
        attempts=(
            SubmissionAttempt(
                attempt_id=f"{submission_id}.1",
                started_at=now - timedelta(minutes=10),
                ended_at=now - timedelta(minutes=8),
                status=SubmissionStatus.FALLIDA,
                error_code="TLS_HANDSHAKE_TIMEOUT",
                error_message="connection to sede timed out",
                browser_trace_path=Path("traces/attempt-1.zip"),
            ),
            SubmissionAttempt(
                attempt_id=f"{submission_id}.2",
                started_at=now - timedelta(minutes=5),
                ended_at=now,
                status=SubmissionStatus.ACEPTADA,
            ),
        ),
    )


def test_submitted_filing_survives_encrypted_storage_roundtrip(tmp_path: Path) -> None:
    """A populated ModeloPresentado roundtrips strictly across AUDIT-class storage."""

    with isolated_runtime_profile(tmp_path=tmp_path):
        original = _populated_filing()
        repo = SubmissionRepository()
        repo.save(original)
        loaded = repo.load(original.submission_id)

        assert loaded is not None
        assert loaded == original
        assert loaded.status is SubmissionStatus.ACEPTADA
        assert loaded.period == _PERIOD
        assert loaded.period.filing_year == 2025
        assert loaded.period.registry_token == _PERIOD.registry_token
        assert loaded.justificante_csv == "ABCD12345678EFGH"
        assert loaded.justificante_pdf_path == Path("justificantes/303-2025Q1-ABCD.pdf")
        assert len(loaded.attempts) == 2
        assert loaded.attempts[0].status is SubmissionStatus.FALLIDA
        assert loaded.attempts[0].error_code == "TLS_HANDSHAKE_TIMEOUT"
        assert loaded.attempts[0].browser_trace_path == Path("traces/attempt-1.zip")
        assert loaded.attempts[1].status is SubmissionStatus.ACEPTADA
        assert loaded.submitted_at is not None
        assert loaded.acknowledged_at is not None
        assert loaded.submitted_at < loaded.acknowledged_at


def test_submission_dropped_justificante_csv_surfaces_at_load(tmp_path: Path) -> None:
    """Anti-tautology proof: deleting ``justificante_csv`` on ACEPTADA must surface.

    The :class:`ModeloPresentado` model_validator enforces that an
    ACEPTADA submission carries both ``justificante_csv`` AND
    ``justificante_pdf_path``. Surgically delete the CSV from the
    persisted JSON envelope; the load path must reject the rehydrated
    record via either a ValidationError or strict inequality.

    Submission records are historical filing evidence at
    ``SensitivityClass.AUDIT``. A silent grounding drop on this
    boundary would invalidate the operator's filed-with-AEAT trail.
    If this test passes silently with the CSV stripped, every
    submission roundtrip in the suite is tautological.
    """

    from sqlalchemy import select

    from ....adapters.persistence.storage.sql._orm import SecureObjectRow

    submission_namespace = SubmissionRepository.namespace

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        original = _populated_filing()
        repo = SubmissionRepository()
        repo.save(original)

        stmt = select(SecureObjectRow).where(
            SecureObjectRow.namespace == submission_namespace,
            SecureObjectRow.object_key == original.submission_id,
        )

        def mutate(envelope):
            payload = envelope["payload"]
            assert payload.get("justificante_csv"), (
                "fixture must serialise justificante_csv onto the ACEPTADA record for this proof test to be meaningful"
            )
            payload["justificante_csv"] = None

        mutate_encrypted_secure_object_json(
            profile.repository._engine,
            row_statement=stmt,
            mutate=mutate,
        )

        try:
            mutated = repo.load(original.submission_id)
        except ValidationError:
            return
        assert mutated != original, (
            "anti-tautology proof failed: deleting justificante_csv "
            "from an ACEPTADA submission did NOT surface on load. "
            "The submission boundary is tautological and every "
            "submission roundtrip in the suite is suspect."
        )


def test_submission_corrupted_period_surfaces_at_load(tmp_path: Path) -> None:
    """Anti-tautology proof: corrupting the ``period`` payload must surface.

    :class:`ModeloPresentado` now stores ``period`` as a typed
    :class:`~cadrumo.core.Period` serialised to ``{"filing_year": int,
    "code": str}``.  Surgically replace the persisted ``code`` with an
    invalid value; the load path must either raise :class:`ValidationError`
    or produce a record that differs from the original — proving that the
    period field is actually read and validated on deserialisation, not
    silently ignored or defaulted.

    If this test passes without raising or detecting inequality, the period
    sub-field is not enforced on the persistence boundary and every period
    roundtrip assertion in the suite is tautological.
    """

    from sqlalchemy import select

    from ....adapters.persistence.storage.sql._orm import SecureObjectRow

    submission_namespace = SubmissionRepository.namespace

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        original = _populated_filing()
        repo = SubmissionRepository()
        repo.save(original)

        stmt = select(SecureObjectRow).where(
            SecureObjectRow.namespace == submission_namespace,
            SecureObjectRow.object_key == original.submission_id,
        )

        def mutate(envelope):
            payload = envelope["payload"]
            assert isinstance(payload.get("period"), dict), (
                "fixture must serialise period as a dict for this proof test to be meaningful"
            )
            # Corrupt the period code to an invalid value that will fail Period validation.
            payload["period"]["code"] = "INVALID_CODE_XYZ"

        mutate_encrypted_secure_object_json(
            profile.repository._engine,
            row_statement=stmt,
            mutate=mutate,
        )

        try:
            mutated = repo.load(original.submission_id)
        except ValidationError:
            return
        assert mutated != original, (
            "anti-tautology proof failed: corrupting the period code "
            "did NOT surface on load.  The period field is not enforced "
            "at the persistence boundary; every period roundtrip assertion "
            "in the suite is suspect."
        )
