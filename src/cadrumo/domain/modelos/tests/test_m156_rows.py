"""Independent members and month facts survive the saved detail boundary."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import TypeAdapter, ValidationError

from ...calculations.registry.schema_references import RegistrySnapshotRef
from ..calculation_revision import CalculationRevision, CalculationRevisionState, derive_calculation_revision_id
from ..m156_rows import Modelo156AfiliadoRow, Modelo156MonthlyContribution
from ..row_models import ModeloDetailRow

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _member(*, number: str = "001234567890", amount: Decimal | None = None) -> Modelo156AfiliadoRow:
    return Modelo156AfiliadoRow(
        nif="12345678Z",
        nombre="Persona ficticia",
        numero_afiliacion=number,
        cotizaciones=tuple(
            Modelo156MonthlyContribution(month=m, status="N" if m == 1 else None, amount=amount if m == 1 else None)
            for m in range(1, 13)
        ),
    )


def _identity(*rows: Modelo156AfiliadoRow) -> str:
    return derive_calculation_revision_id(
        work_unit_id="a" * 64,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        detail_rows=rows,
        filing_instance_evidence=None,
        source_provenance=(),
    )


def test_member_union_round_trip_keeps_leading_zero_and_unknown_separate_from_zero() -> None:
    rows = (_member(), _member(number="001234567891", amount=Decimal("0")))
    adapter = TypeAdapter(tuple[ModeloDetailRow, ...])
    restored = adapter.validate_json(adapter.dump_json(rows))
    assert restored == rows
    assert isinstance(restored[0], Modelo156AfiliadoRow)
    assert isinstance(restored[1], Modelo156AfiliadoRow)
    assert restored[0].numero_afiliacion == "001234567890"
    assert restored[0].cotizaciones[0].amount is None
    assert restored[1].cotizaciones[0].amount == Decimal("0")
    assert restored[1].cotizaciones[1].status is None


def test_member_calendar_sorts_explicit_months_without_losing_any() -> None:
    member = _member()
    reordered = Modelo156AfiliadoRow(
        nif=member.nif,
        nombre=member.nombre,
        numero_afiliacion=member.numero_afiliacion,
        cotizaciones=tuple(reversed(member.cotizaciones)),
    )
    assert reordered == member
    with pytest.raises(ValidationError, match="each calendar month"):
        Modelo156AfiliadoRow(
            nif=member.nif,
            numero_afiliacion=member.numero_afiliacion,
            cotizaciones=(*member.cotizaciones[:-1], member.cotizaciones[0]),
        )


@pytest.mark.parametrize("amount", [Decimal("-1"), Decimal("NaN"), Decimal("Infinity"), True, 1.25])
def test_month_refuses_invalid_amount_without_guessing_or_rounding(amount) -> None:
    with pytest.raises(ValidationError):
        Modelo156MonthlyContribution(month=1, amount=amount)


@pytest.mark.parametrize("status", ["", "s", "X", True])
def test_month_refuses_unknown_status(status) -> None:
    with pytest.raises(ValidationError):
        Modelo156MonthlyContribution(month=1, status=status)


def test_status_and_amount_are_independent_facts() -> None:
    month = Modelo156MonthlyContribution(month=1, status="N", amount=Decimal("123.45"))
    assert month.status == "N" and month.amount == Decimal("123.45")


def test_revision_identity_preserves_month_facts_and_ignores_input_order_and_decimal_scale() -> None:
    first = _member(amount=Decimal("1.00"))
    second = _member(number="001234567891", amount=Decimal("2"))
    assert _identity(first, second) == _identity(second, first)
    assert _identity(first) == _identity(_member(amount=Decimal("1")))
    assert _identity(_member()) != _identity(_member(amount=Decimal("0")))
    assert _identity(first) != _identity(_member(amount=Decimal("1.01")))
    months = first.cotizaciones
    changed = first.model_copy(update={"cotizaciones": (months[0].model_copy(update={"status": "S"}), *months[1:])})
    assert _identity(first) != _identity(changed)


@pytest.mark.parametrize("month", range(1, 13))
@pytest.mark.parametrize("field", ["amount", "status"])
def test_each_month_fact_participates_in_revision_identity(month: int, field: str) -> None:
    original = _member()
    changed_months = tuple(
        value.model_copy(update={field: Decimal("1") if field == "amount" else "S"}) if value.month == month else value
        for value in original.cotizaciones
    )
    changed = original.model_copy(update={"cotizaciones": changed_months})
    assert _identity(original) != _identity(changed)


def test_calculation_revision_json_retains_both_member_records() -> None:
    rows = (_member(), _member(number="001234567891", amount=Decimal("0")))
    timestamp = datetime(2025, 12, 31, tzinfo=UTC)
    revision = CalculationRevision(
        calculation_revision_id=_identity(*rows),
        work_unit_id="a" * 64,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo="156",
            revision_id="2003-y-siguientes",
            modelo_year=2025,
            period="0A",
        ),
        state=CalculationRevisionState.BORRADOR,
        detail_rows=rows,
        created_at=timestamp,
        updated_at=timestamp,
        source_provenance=(),
        filing_instance_evidence=None,
    )
    restored = CalculationRevision.model_validate_json(revision.model_dump_json())
    assert restored.detail_rows == rows
    assert restored.calculation_revision_id == revision.calculation_revision_id
