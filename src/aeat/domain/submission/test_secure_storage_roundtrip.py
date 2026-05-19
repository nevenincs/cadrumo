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

from ...adapters.persistence.storage import (
    EphemeralMasterKeyProvider,
)
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...adapters.persistence.storage.sql._orm import Base
from ...adapters.persistence.storage.sql.engine import create_engine_from_settings
from ...core.config import Settings
from ._models import (
    SubmissionAttempt,
    SubmissionStatus,
    ModeloPresentado,
    make_submission_id,
)
from ._repository import SubmissionRepository

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


def _populated_filing() -> ModeloPresentado:
    """Build a ModeloPresentado with every defaultable field non-default.

    Anti-tautology: status=ACEPTADA forces justificante_csv +
    justificante_pdf_path to be populated; acknowledged_at also set.
    Two attempts so the tuple-of-attempts surface is exercised, with
    distinct status / error fields per attempt.
    """

    now = datetime.now(UTC).replace(microsecond=0)
    draft_id = "d" * 64
    submission_id = make_submission_id(draft_id, attempt_ordinal=2)
    return ModeloPresentado(
        submission_id=submission_id,
        draft_id=draft_id,
        modelo="303",
        period="2025Q1",
        profile_tax_id="12345678Z",
        status=SubmissionStatus.ACEPTADA,
        justificante_csv="ABCD12345678EFGH",
        justificante_pdf_path=Path("justificantes/303-2025Q1-ABCD.pdf"),
        submitted_at=now - timedelta(minutes=5),
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


def test_submitted_filing_survives_encrypted_storage_roundtrip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A populated ModeloPresentado roundtrips strictly across AUDIT-class storage."""

    provider = EphemeralMasterKeyProvider()
    with provider:
        db_path = tmp_path / "submission-roundtrip.db"
        monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
        engine = create_engine_from_settings(
            Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"),
        )
        Base.metadata.create_all(engine)
        try:
            SecureObjectRepository(engine=engine)

            original = _populated_filing()
            repo = SubmissionRepository()
            repo.save(original)
            loaded = repo.load(original.submission_id)

            assert loaded is not None
            assert loaded == original
            # Per-field witnesses for the most fragile pieces:
            # the SubmissionStatus enum, the nested attempts tuple
            # with distinct statuses per attempt, and the typed Path
            # field (browser_trace_path) which serialises as str on
            # the wire and must reconstitute back to Path on load.
            assert loaded.status is SubmissionStatus.ACEPTADA
            assert loaded.justificante_csv == "ABCD12345678EFGH"
            assert loaded.justificante_pdf_path == Path("justificantes/303-2025Q1-ABCD.pdf")
            assert len(loaded.attempts) == 2
            assert loaded.attempts[0].status is SubmissionStatus.FALLIDA
            assert loaded.attempts[0].error_code == "TLS_HANDSHAKE_TIMEOUT"
            assert loaded.attempts[0].browser_trace_path == Path("traces/attempt-1.zip")
            assert loaded.attempts[1].status is SubmissionStatus.ACEPTADA
            # The first-attempt-ended-before-submitted invariant survives.
            assert loaded.submitted_at < loaded.acknowledged_at  # type: ignore[operator]
        finally:
            engine.dispose()


def test_submission_dropped_justificante_csv_surfaces_at_load(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

    import json as _json

    from sqlalchemy import select

    from ...adapters.persistence.storage.sql._orm import SecureObjectRow
    from ...adapters.persistence.storage.sql.session import session_scope
    _SUBMISSION_NAMESPACE = SubmissionRepository.namespace

    provider = EphemeralMasterKeyProvider()
    with provider:
        db_path = tmp_path / "submission-anti-tautology.db"
        monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
        engine = create_engine_from_settings(
            Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"),
        )
        Base.metadata.create_all(engine)
        try:
            SecureObjectRepository(engine=engine)

            original = _populated_filing()
            repo = SubmissionRepository()
            repo.save(original)

            with session_scope(engine) as session:
                stmt = select(SecureObjectRow).where(
                    SecureObjectRow.namespace == _SUBMISSION_NAMESPACE,
                    SecureObjectRow.object_key == original.submission_id,
                )
                row = session.execute(stmt).scalar_one()
                envelope = _json.loads(row.payload.decode("utf-8"))
                payload = envelope["payload"]
                assert payload.get("justificante_csv"), (
                    "fixture must serialise justificante_csv onto the "
                    "ACEPTADA record for this proof test to be meaningful"
                )
                payload["justificante_csv"] = None
                row.payload = _json.dumps(envelope).encode("utf-8")

            regression_caught = False
            try:
                mutated = repo.load(original.submission_id)
            except Exception:  # noqa: BLE001 - boundary may raise different types
                regression_caught = True
            else:
                if mutated != original:
                    regression_caught = True
            assert regression_caught, (
                "anti-tautology proof failed: deleting justificante_csv "
                "from an ACEPTADA submission did NOT surface on load. "
                "The submission boundary is tautological and every "
                "submission roundtrip in the suite is suspect."
            )
        finally:
            engine.dispose()
