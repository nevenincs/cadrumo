"""Tests for registry-backed filing draft test helpers."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

import pytest
from pydantic import ValidationError

from ....core import Period
from ....domain.filing._errors import ModeloBuilderError
from ....domain.filing._schema import ModeloDraft, ModeloValueKind
from ....domain.submission import ModeloDraftStatus
from .._testing_registry import build_registry_filing_draft, build_registry_filing_draft_from_decimals

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _period(year: int, code: str) -> Period:
    return Period.from_year_and_code(year, code)


_ANNUAL_2026 = _period(2026, "0A")
_Q1_2024 = _period(2024, "1T")
_Q1_2026 = _period(2026, "1T")


def _valid_inputs(*, ingresos: Decimal = Decimal("10000")) -> dict[str, Decimal]:
    return {
        "01": ingresos,
        "02": Decimal("4000"),
        "05": Decimal("250"),
        "06": Decimal("100"),
        "08": Decimal("2000"),
        "10": Decimal("10"),
        "16": Decimal("0"),
        "18": Decimal("0"),
    }


def _valid_bindings() -> dict[str, Decimal]:
    return {
        "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
        "modelo-130-resultados-negativos-anteriores": Decimal("0"),
    }


def test_builds_frozen_draft_through_registry_runtime() -> None:
    draft = build_registry_filing_draft(
        modelo="130",
        period=_Q1_2026,
        casilla_values=_valid_inputs(),
        binding_values=_valid_bindings(),
    )

    assert isinstance(draft, ModeloDraft)
    assert draft.period == _Q1_2026
    assert draft.schema_version.startswith("registry:130:")
    with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
        draft.status = ModeloDraftStatus.BORRADOR


def test_approved_status_uses_application_approval_path() -> None:
    draft = build_registry_filing_draft(
        modelo="130",
        period=_Q1_2026,
        casilla_values=_valid_inputs(),
        binding_values=_valid_bindings(),
    )

    assert draft.status is ModeloDraftStatus.APROBADO
    assert draft.approved_at is not None
    assert draft.approved_by == "registry"
    assert draft.approval_basis is not None
    assert draft.review_checksum is not None


def test_typed_period_input_is_passed_to_draft_without_string_roundtrip() -> None:
    period = Period.from_year_and_code(2026, "1T")

    draft = build_registry_filing_draft(
        modelo="130",
        period=period,
        casilla_values=_valid_inputs(),
        binding_values=_valid_bindings(),
        status=ModeloDraftStatus.BORRADOR,
    )

    assert draft.period == period
    assert draft.snapshot_ref is not None
    assert draft.snapshot_ref.modelo_year == period.year
    assert draft.snapshot_ref.period == period.registry_token


def test_typed_period_input_uses_period_year() -> None:
    draft = build_registry_filing_draft(
        modelo="130",
        period=_Q1_2024,
        casilla_values=_valid_inputs(),
        binding_values=_valid_bindings(),
        status=ModeloDraftStatus.BORRADOR,
    )

    assert draft.period == _Q1_2024
    assert draft.snapshot_ref is not None
    assert draft.snapshot_ref.modelo_year == 2024
    assert draft.snapshot_ref.period == "1T"


def test_string_period_input_is_rejected_at_helper_boundary() -> None:
    with pytest.raises(ModeloBuilderError, match=r"requires a core\.Period"):
        build_registry_filing_draft(
            modelo="130",
            period="2026Q1",
            casilla_values=_valid_inputs(),
            binding_values=_valid_bindings(),
            status=ModeloDraftStatus.BORRADOR,
        )


def test_non_approved_status_clears_approval_fields() -> None:
    draft = build_registry_filing_draft(
        modelo="130",
        period=_Q1_2026,
        casilla_values=_valid_inputs(),
        binding_values=_valid_bindings(),
        status=ModeloDraftStatus.BORRADOR,
    )

    assert draft.status is ModeloDraftStatus.BORRADOR
    assert draft.approved_at is None
    assert draft.approved_by is None
    assert draft.approval_basis is None
    assert draft.review_checksum is None


def test_unsupported_modelo_fails_at_registry_boundary() -> None:
    with pytest.raises(ModeloBuilderError, match="missing requested modelo definitions"):
        build_registry_filing_draft(
            modelo="999",
            period=_ANNUAL_2026,
            casilla_values={"0511": Decimal("5550.00")},
        )


def test_duplicate_casilla_and_binding_ids_are_rejected() -> None:
    with pytest.raises(ModeloBuilderError, match="duplicate casilla/binding input ids"):
        build_registry_filing_draft(
            modelo="130",
            period=_Q1_2026,
            casilla_values=_valid_inputs(),
            binding_values={**_valid_bindings(), "01": Decimal("99")},
        )


def test_values_are_registry_projected_and_sorted() -> None:
    draft = build_registry_filing_draft(
        modelo="130",
        period=_Q1_2026,
        casilla_values=_valid_inputs(ingresos=Decimal("12000")),
        binding_values=_valid_bindings(),
        status=ModeloDraftStatus.BORRADOR,
    )

    values = {value.casilla_id: value for value in draft.values}
    assert tuple(values) == tuple(sorted(values))
    assert values["01"].kind is ModeloValueKind.INHERITED
    assert values["15"].kind is ModeloValueKind.INHERITED
    assert values["15"].value == Decimal("0")
    assert values["19"].kind is ModeloValueKind.COMPUTED
    assert values["19"].formula_trace == ("17", "18")


def test_draft_id_is_deterministic_for_same_registry_inputs() -> None:
    a = build_registry_filing_draft(
        modelo="130",
        period=_Q1_2026,
        casilla_values=_valid_inputs(),
        binding_values=_valid_bindings(),
    )
    b = build_registry_filing_draft(
        modelo="130",
        period=_Q1_2026,
        casilla_values=_valid_inputs(),
        binding_values=_valid_bindings(),
    )

    assert a.draft_id == b.draft_id


def test_decimal_string_inputs_are_coerced_before_registry_build() -> None:
    draft = build_registry_filing_draft_from_decimals(
        modelo="130",
        period=_Q1_2026,
        casilla_decimals={key: str(value) for key, value in _valid_inputs().items()},
        binding_decimals={key: str(value) for key, value in _valid_bindings().items()},
        status=ModeloDraftStatus.BORRADOR,
    )

    values = {value.casilla_id: value for value in draft.values}
    assert values["01"].value == Decimal("10000")


def test_decimal_passthrough() -> None:
    draft = build_registry_filing_draft_from_decimals(
        modelo="130",
        period=_Q1_2026,
        casilla_decimals=_valid_inputs(ingresos=Decimal("100.50")),
        binding_decimals=_valid_bindings(),
        status=ModeloDraftStatus.BORRADOR,
    )

    values = {value.casilla_id: value for value in draft.values}
    assert values["01"].value == Decimal("100.50")


def test_invalid_decimal_string_raises() -> None:
    bad_inputs = {key: str(value) for key, value in _valid_inputs().items()}
    bad_inputs["01"] = "not-a-decimal"

    with pytest.raises(InvalidOperation, match=r"ConversionSyntax|InvalidOperation|conversion"):
        build_registry_filing_draft_from_decimals(
            modelo="130",
            period=_Q1_2026,
            casilla_decimals=bad_inputs,
            binding_decimals=_valid_bindings(),
        )


def test_spanish_thousands_rejected_at_boundary() -> None:
    bad_inputs = {key: str(value) for key, value in _valid_inputs().items()}
    bad_inputs["01"] = "5.550,00"

    with pytest.raises(InvalidOperation, match=r"ConversionSyntax|InvalidOperation|conversion"):
        build_registry_filing_draft_from_decimals(
            modelo="130",
            period=_Q1_2026,
            casilla_decimals=bad_inputs,
            binding_decimals=_valid_bindings(),
        )
