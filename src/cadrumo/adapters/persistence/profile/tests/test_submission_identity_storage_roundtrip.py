"""Canonical submission identities survive the encrypted repository boundary.

The domain model validates the identity shapes; this adapter-facing case proves
that the canonical ``modelo`` identity is preserved by a real encrypted
``SubmissionRepository`` roundtrip.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from .....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from .....core.modelo import Modelo
from .....core.period import Period
from .....domain.submission.models import ModeloPresentado, SubmissionAttempt, SubmissionStatus
from ..submission import SubmissionRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_PERIOD = Period.from_year_and_code(2025, "1T")
_SUBMITTED_AT = datetime(2026, 5, 27, 10, 0, 0, tzinfo=UTC)
_DRAFT_ID = "d" * 64


def _filing(*, modelo: object = Modelo("303")) -> ModeloPresentado:
    """Build a valid presented filing with a steerable canonical modelo."""
    submission_id = "0123456789abcdef"
    return ModeloPresentado(
        submission_id=submission_id,
        draft_id=_DRAFT_ID,
        modelo=modelo,
        period=_PERIOD,
        profile_tax_id="12345678Z",
        status=SubmissionStatus.PRESENTADA,
        submitted_at=_SUBMITTED_AT,
        attempts=(
            SubmissionAttempt(
                attempt_id=f"{submission_id}.1",
                started_at=_SUBMITTED_AT,
                ended_at=_SUBMITTED_AT + timedelta(seconds=30),
                status=SubmissionStatus.PRESENTADA,
            ),
        ),
    )


def test_canonical_modelo_identity_survives_encrypted_storage(tmp_path: Path) -> None:
    """A canonical modelo identity survives a real encrypted repository cycle."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        original = _filing(modelo=Modelo("130"))
        repository = SubmissionRepository()
        repository.save(original)
        loaded = repository.load(original.submission_id)

    assert loaded is not None
    assert loaded == original
    assert loaded.modelo == Modelo("130")
