"""Boundary gates for the modelo history envelope and the M130 accumulated totals.

Two transports that re-declared what their canonical models close:

* the modelo lifecycle history row restated ``BucketEvent``'s identity, closed
  event/object types, timestamp and actor as free strings, and its envelope
  accepted an empty modelo, a negative year and a negative count;
* ``M130AccumulatedPayload`` carried four unconstrained strings, so
  ``not-decimal``, ``NaN`` and ``Infinity`` could cross the wire as totals.

The negative-total case is deliberately asserted as ACCEPTED. The canonical
``ModeloProjectM130Accumulated`` types all four as bare ``Decimal`` with no
non-negative bound, and a quarter that ran at a loss has a negative
``rendimiento_neto``. Constraining the wire to non-negative would refuse a real
filing, so the boundary matches the canonical contract rather than exceeding it.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ....domain.buckets.event import BucketEventObjectType, BucketEventType
from .._modelo_payloads import M130AccumulatedPayload, ModeloHistoryResult, ModeloLifecycleEventPayload

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_HEX64 = "a" * 64


def _event(**overrides: object) -> dict[str, object]:
    fields: dict[str, object] = {
        "event_id": _HEX64,
        "event_type": BucketEventType.MODELO_FILED,
        "occurred_at": datetime(2026, 4, 1, 9, 0, tzinfo=UTC),
        "actor": "cadrumo.app.modelo.file",
        "object_type": BucketEventObjectType.WORK_UNIT,
        "object_id": "work-1",
        "payload": {},
    }
    fields.update(overrides)
    return fields


def _totals(**overrides: object) -> dict[str, object]:
    fields: dict[str, object] = {
        "ingresos": "1000.00",
        "gastos": "400.00",
        "rendimiento_neto": "600.00",
        "pagos_fraccionados": "120.00",
    }
    fields.update(overrides)
    return fields


# --- M130 accumulated totals -------------------------------------------------


@pytest.mark.parametrize("bad", ["not-decimal", "NaN", "Infinity", "1E+3", "1,000.00", ""])
def test_m130_totals_refuse_non_canonical_decimal_text(bad: str) -> None:
    """A total that is not a canonical decimal string must not reach the wire."""
    with pytest.raises(ValidationError):
        M130AccumulatedPayload.model_validate(_totals(rendimiento_neto=bad))


def test_m130_rendimiento_neto_accepts_a_loss_quarter() -> None:
    """A negative net result is a real filing, not malformed input.

    The canonical projection model applies no non-negative bound, so neither
    does the boundary.
    """
    payload = M130AccumulatedPayload.model_validate(_totals(rendimiento_neto="-500.00"))

    assert payload.rendimiento_neto == "-500.00"


def test_m130_totals_keep_their_string_wire_form() -> None:
    """The validated wire type must not turn the totals into JSON numbers."""
    wire = M130AccumulatedPayload.model_validate(_totals()).model_dump(mode="json")

    assert wire["ingresos"] == "1000.00"
    assert isinstance(wire["gastos"], str)


# --- modelo lifecycle history -----------------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        {"event_id": "bad"},
        {"event_id": "A" * 64},
        {"occurred_at": "not-date"},
        {"event_type": "not-an-event-type"},
        {"object_type": "not-an-object-type"},
        {"actor": ""},
        {"actor": "z" * 100},
        {"object_id": ""},
    ],
)
def test_history_event_refuses_values_bucket_event_refuses(overrides: dict[str, object]) -> None:
    """Every identity/time/actor value the canonical event rejects is rejected here."""
    with pytest.raises(ValidationError):
        ModeloLifecycleEventPayload.model_validate(_event(**overrides))


def test_history_event_wire_form_is_unchanged() -> None:
    """Enum members and datetimes must render as the strings the CLI already emitted."""
    wire = ModeloLifecycleEventPayload.model_validate(_event()).model_dump(mode="json")

    assert wire["event_type"] == "modelo.filed"
    assert wire["object_type"] == BucketEventObjectType.WORK_UNIT.value
    assert wire["occurred_at"].startswith("2026-04-01T09:00:00")


@pytest.mark.parametrize(
    "overrides",
    [
        {"modelo": ""},
        {"year": -1},
        {"year": 1900},
        {"count": -1},
        {"period": ""},
    ],
)
def test_history_envelope_refuses_impossible_filters_and_counts(overrides: dict[str, object]) -> None:
    """The envelope's own scalar fields must not carry impossible values."""
    fields: dict[str, object] = {"modelo": "130", "year": 2024, "period": "1T", "count": 0, "events": []}
    fields.update(overrides)

    with pytest.raises(ValidationError):
        ModeloHistoryResult.model_validate(fields)


def test_history_envelope_accepts_a_censo_lifecycle_period_token() -> None:
    """``period`` stays a free token: the censo words are valid filters, not codes."""
    result = ModeloHistoryResult(modelo="036", year=2026, period="alta", count=0, events=[])

    assert result.period == "alta"
