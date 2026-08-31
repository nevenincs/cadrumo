"""Real-boundary tests for the read-only submission engine."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ......adapters.persistence.profile.submission import SubmissionRepository
from ......core.config import Settings
from ......domain.submission.engine import SubmissionEngine
from ......domain.submission.errors import SubmissionError
from ......domain.submission.models import ModeloPresentado, SubmissionAttempt, SubmissionStatus, make_submission_id
from ......tests.secure_sql import isolated_runtime_profile
from ._preflight_support import clave_movil_provider, deadline_checker, modelo_draft

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_SUBMITTED_AT = datetime(2026, 5, 28, 12, 55, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _secure_database(tmp_path: Path) -> Iterator[None]:
    """Run historical-record tests against a real active profile runtime."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="32c5a791-4b7d-4347-bae1-8d3c84e15ce0"):
        yield


def _build_engine(tmp_path: Path) -> SubmissionEngine:
    """Compose the engine with production persistence, deadline, and auth boundaries."""
    return SubmissionEngine(
        auth_provider=clave_movil_provider(identity="12345678Z"),
        deadline_checker=deadline_checker(),
        repository=SubmissionRepository(),
        settings=Settings(cadrumo_submissions_dir=tmp_path / "submissions"),
    )


def _historical_filing(draft_label: str = "draft-1", modelo: str = "130") -> ModeloPresentado:
    """Build a production historical filing record for encrypted persistence."""
    submission_id = make_submission_id(draft_label, 1)
    return ModeloPresentado(
        submission_id=submission_id,
        draft_id="draft-1",
        modelo=modelo,
        period=modelo_draft().period,
        profile_tax_id="X1234567L",
        status=SubmissionStatus.PENDIENTE_DE_PRESENTAR,
        submitted_at=_SUBMITTED_AT,
        attempts=(
            SubmissionAttempt(
                attempt_id=f"{submission_id}.1",
                started_at=_SUBMITTED_AT,
                ended_at=_SUBMITTED_AT,
                status=SubmissionStatus.PENDIENTE_DE_PRESENTAR,
            ),
        ),
    )


def test_engine_preflight_uses_real_production_boundaries(tmp_path: Path) -> None:
    assert _build_engine(tmp_path).preflight(modelo_draft(), today=modelo_draft().created_at.date()) is None


def test_engine_exposes_no_remote_write_methods(tmp_path: Path) -> None:
    engine = _build_engine(tmp_path)

    assert not hasattr(engine, "submit_draft")
    assert not hasattr(engine, "submit_amendment")
    assert not (tmp_path / "submissions").exists()


def test_load_submission_roundtrips_real_encrypted_record(tmp_path: Path) -> None:
    engine = _build_engine(tmp_path)
    filing = _historical_filing()
    SubmissionRepository().save(filing)

    assert engine.load_submission(filing.submission_id) == filing


def test_load_submission_rejects_traversal_id(tmp_path: Path) -> None:
    with pytest.raises(SubmissionError, match="path separators"):
        _build_engine(tmp_path).load_submission("../escape")


def test_list_submissions_filters_real_encrypted_records(tmp_path: Path) -> None:
    engine = _build_engine(tmp_path)
    first = _historical_filing(draft_label="draft-1", modelo="130")
    second = _historical_filing(draft_label="draft-2", modelo="303")
    repository = SubmissionRepository()
    repository.save(first)
    repository.save(second)

    assert engine.list_submissions(modelo="130") == (first,)
    assert engine.list_submissions(modelo="999") == ()
