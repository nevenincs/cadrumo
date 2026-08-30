"""Contract parity between the local-observation application result and its CLI shell.

``FilingRecordLocalObservationResult`` must refuse the malformed source-kind,
non-Decimal casilla value, timestamp, count, and non-official-flag shapes
the canonical ``ModeloLocalObservationResult`` already refuses or the
producing action never emits.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ....application.calculations import ObservationSourceKind
from ....core.period import Period
from .._modelo_payloads import FilingRecordLocalObservationResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_CAPTURED_AT = datetime(2026, 6, 1, 8, 0, tzinfo=UTC)


def _kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "modelo": "130",
        "filing_year": 2026,
        "period": Period.from_year_and_code(2026, "1T"),
        "revision_id": "2020-y-siguientes",
        "observation_key": "obs-1",
        "source_kind": ObservationSourceKind.OPERATOR_MANUAL,
        "casilla_values": {"0001": "100.00"},
        "casilla_count": 1,
        "captured_at": _CAPTURED_AT,
        "captured_by": "operator-manual",
        "official_evidence": False,
        "filing_record_created": False,
        "aeat_accepted": False,
    }
    base.update(overrides)
    return base


def test_accepts_a_real_projection() -> None:
    """A genuine local-observation result projects and validates cleanly."""
    result = FilingRecordLocalObservationResult.model_validate(_kwargs())

    assert result.source_kind is ObservationSourceKind.OPERATOR_MANUAL


def test_rejects_an_unknown_source_kind() -> None:
    """A source kind outside the closed vocabulary is refused."""
    with pytest.raises(ValidationError):
        FilingRecordLocalObservationResult.model_validate({**_kwargs(), "source_kind": "bogus-source"})


def test_rejects_a_non_decimal_casilla_value() -> None:
    """A non-Decimal casilla value string is refused, matching the canonical Decimal type."""
    with pytest.raises(ValidationError):
        FilingRecordLocalObservationResult.model_validate(
            {**_kwargs(), "casilla_values": {"0001": "not-a-decimal"}},
        )


def test_rejects_a_malformed_captured_at() -> None:
    """A non-ISO ``captured_at`` is refused."""
    with pytest.raises(ValidationError):
        FilingRecordLocalObservationResult.model_validate({**_kwargs(), "captured_at": "not-a-time"})


def test_rejects_a_negative_casilla_count() -> None:
    """A negative ``casilla_count`` is refused."""
    with pytest.raises(ValidationError):
        FilingRecordLocalObservationResult.model_validate({**_kwargs(), "casilla_count": -1})


def test_rejects_a_blank_captured_by() -> None:
    """A blank ``captured_by`` is refused."""
    with pytest.raises(ValidationError):
        FilingRecordLocalObservationResult.model_validate({**_kwargs(), "captured_by": ""})


@pytest.mark.parametrize("field", ["official_evidence", "filing_record_created", "aeat_accepted"])
def test_rejects_a_true_non_official_flag(field: str) -> None:
    """Every non-official flag is pinned False; this action never produces AEAT evidence."""
    with pytest.raises(ValidationError):
        FilingRecordLocalObservationResult.model_validate({**_kwargs(), field: True})
