"""Persisted submission records carry canonical identities, not shape-only strings.

``ModeloPresentado`` is a durable filing identity that the listing engine
filters by raw equality, and its ``submission_id`` / ``attempt_id`` fields are
documented coordinates (a content-derived digest, and a parent-plus-ordinal
pair). All three were length-only strings, so an unknown modelo code, a
whitespace-spelled known one, and an arbitrary identifier all became historical
filing records that no canonical lookup would ever match.

Real model construction and a real encrypted repository round-trip, no mocks.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....adapters.persistence.profile.submission import SubmissionRepository
from ....core import Modelo, Period
from ....tests.secure_sql import isolated_runtime_profile
from .._models import (
    ModeloPresentado,
    SubmissionAttempt,
    SubmissionStatus,
    make_submission_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PERIOD = Period.from_year_and_code(2025, "1T")
_SUBMITTED_AT = datetime(2026, 5, 27, 10, 0, 0, tzinfo=UTC)
_DRAFT_ID = "d" * 64


def _filing(
    *,
    modelo: object = Modelo.M303,
    submission_id: str | None = None,
    attempt_id: str | None = None,
) -> ModeloPresentado:
    """Build a valid presented filing, with the identity axes steerable."""
    resolved_submission_id = submission_id if submission_id is not None else make_submission_id(_DRAFT_ID, 1)
    return ModeloPresentado(
        submission_id=resolved_submission_id,
        draft_id=_DRAFT_ID,
        modelo=modelo,
        period=_PERIOD,
        profile_tax_id="12345678Z",
        status=SubmissionStatus.PRESENTADA,
        submitted_at=_SUBMITTED_AT,
        attempts=(
            SubmissionAttempt(
                attempt_id=attempt_id if attempt_id is not None else f"{resolved_submission_id}.1",
                started_at=_SUBMITTED_AT,
                ended_at=_SUBMITTED_AT + timedelta(seconds=30),
                status=SubmissionStatus.PRESENTADA,
            ),
        ),
    )


@pytest.mark.parametrize(
    "malformed_modelo",
    ("999", " 303 ", "303 ", "", "3030"),
    ids=("unknown-code", "padded-both", "trailing-space", "empty", "four-digit"),
)
def test_persisted_filing_refuses_non_canonical_modelo_identities(malformed_modelo: str) -> None:
    """A filing identity must name a modelo the rest of the system can look up."""
    with pytest.raises(ValidationError):
        _filing(modelo=malformed_modelo)


def test_canonical_modelo_identity_is_stored_as_the_enum_member() -> None:
    """The record carries the closed identity, so equality holds against Modelo."""
    filing = _filing(modelo="303")

    assert filing.modelo is Modelo.M303
    assert filing.modelo == "303"


def test_canonical_modelo_identity_survives_encrypted_storage(tmp_path: Path) -> None:
    """Valid parity: the canonical identity round-trips through the real repository."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        original = _filing(modelo=Modelo.M130)
        repository = SubmissionRepository()
        repository.save(original)
        loaded = repository.load(original.submission_id)

    assert loaded is not None
    assert loaded == original
    assert loaded.modelo is Modelo.M130
