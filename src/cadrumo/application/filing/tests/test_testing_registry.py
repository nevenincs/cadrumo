"""Tests for registry-backed filing draft test helpers."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

import pytest
from pydantic import ValidationError

from ....core.period import Period
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....domain.filing.errors import ModeloBuilderError
from ....domain.filing.schema import ModeloDraft, ModeloValueKind
from ....domain.submission import ModeloDraftStatus
from ....tests.filing import build_registry_filing_draft, build_registry_filing_draft_from_decimals

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _period(year: int, code: str) -> Period:
    return Period.from_year_and_code(year, code)


_ANNUAL_2026 = _period(2026, "0A")
_Q1_2024 = _period(2024, "1T")
_Q1_2026 = _period(2026, "1T")
_M130_INGRESOS_CASILLA: CasillaId = validated_casilla_id("01")
_M130_GASTOS_CASILLA: CasillaId = validated_casilla_id("02")
_M130_PAGO_FRACCIONADO_CASILLA: CasillaId = validated_casilla_id("05")
_M130_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("06")
_M130_RENDIMIENTO_NETO_PREVIO_CASILLA: CasillaId = validated_casilla_id("08")
_M130_MINORACION_CASILLA: CasillaId = validated_casilla_id("10")
_M130_RESULTADOS_NEGATIVOS_CASILLA: CasillaId = validated_casilla_id("15")
_M130_DEDUCCION_ART_110_3_CASILLA: CasillaId = validated_casilla_id("16")
_M130_RETENCIONES_ARRENDAMIENTOS_CASILLA: CasillaId = validated_casilla_id("18")
_M130_RESULTADO_CASILLA: CasillaId = validated_casilla_id("19")
_RENTA_MINIMO_ESTATAL_CASILLA: CasillaId = validated_casilla_id("0511")


def _valid_inputs(*, ingresos: Decimal = Decimal("10000")) -> dict[CasillaId, Decimal]:
    return {
        _M130_INGRESOS_CASILLA: ingresos,
        _M130_GASTOS_CASILLA: Decimal("4000"),
        _M130_PAGO_FRACCIONADO_CASILLA: Decimal("250"),
        _M130_RETENCIONES_CASILLA: Decimal("100"),
        _M130_RENDIMIENTO_NETO_PREVIO_CASILLA: Decimal("2000"),
        _M130_MINORACION_CASILLA: Decimal("10"),
        _M130_DEDUCCION_ART_110_3_CASILLA: Decimal("0"),
        _M130_RETENCIONES_ARRENDAMIENTOS_CASILLA: Decimal("0"),
    }


def _valid_bindings() -> dict[str, Decimal]:
    return {
        "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
        "modelo-130-pagos-fraccionados-anteriores": Decimal("250"),
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


@pytest.mark.parametrize(
    "period",
    (_Q1_2026, _Q1_2024),
    ids=("2026-q1", "2024-q1"),
)
def test_typed_period_input_is_passed_to_draft_without_string_roundtrip(period: Period) -> None:
    draft = build_registry_filing_draft(
        modelo="130",
        period=period,
        casilla_values=_valid_inputs(),
        binding_values=_valid_bindings(),
        status=ModeloDraftStatus.BORRADOR,
    )

    assert draft.period == period
    assert draft.snapshot_ref is not None
    assert draft.snapshot_ref.modelo_year == period.filing_year
    assert draft.snapshot_ref.period == period.registry_token


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
    with pytest.raises(ModeloBuilderError) as refusal:
        build_registry_filing_draft(
            modelo="999",
            period=_ANNUAL_2026,
            casilla_values={_RENTA_MINIMO_ESTATAL_CASILLA: Decimal("5550.00")},
        )

    assert refusal.value.translated_message == "application.filing.runtime.errors.registry_missing_requested_modelos"


def test_duplicate_casilla_and_binding_ids_are_rejected() -> None:
    with pytest.raises(ModeloBuilderError, match="duplicate casilla/binding input ids"):
        build_registry_filing_draft(
            modelo="130",
            period=_Q1_2026,
            casilla_values=_valid_inputs(),
            binding_values={**_valid_bindings(), _M130_INGRESOS_CASILLA: Decimal("99")},
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
    assert values[_M130_INGRESOS_CASILLA].kind is ModeloValueKind.INHERITED
    assert values[_M130_RESULTADOS_NEGATIVOS_CASILLA].kind is ModeloValueKind.COMPUTED
    assert values[_M130_RESULTADOS_NEGATIVOS_CASILLA].value == Decimal("0")
    assert (
        values[_M130_RESULTADOS_NEGATIVOS_CASILLA].source
        == "registry formula modelo-130-resultados-negativos-anteriores-cap"
    )
    assert values[_M130_RESULTADOS_NEGATIVOS_CASILLA].formula_trace_casilla_ids == ("14",)
    assert values[_M130_RESULTADO_CASILLA].kind is ModeloValueKind.COMPUTED
    assert values[_M130_RESULTADO_CASILLA].formula_trace_casilla_ids == ("17", "18")


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


@pytest.mark.parametrize(
    ("ingresos", "expected"),
    (
        ("10000", Decimal("10000")),
        (Decimal("100.50"), Decimal("100.50")),
    ),
    ids=("decimal-string", "decimal-passthrough"),
)
def test_decimal_inputs_are_coerced_before_registry_build(ingresos: str | Decimal, expected: Decimal) -> None:
    casilla_decimals: dict[CasillaId, str | Decimal] = {key: str(value) for key, value in _valid_inputs().items()}
    casilla_decimals[_M130_INGRESOS_CASILLA] = ingresos

    draft = build_registry_filing_draft_from_decimals(
        modelo="130",
        period=_Q1_2026,
        casilla_decimals=casilla_decimals,
        binding_decimals={key: str(value) for key, value in _valid_bindings().items()},
        status=ModeloDraftStatus.BORRADOR,
    )

    values = {value.casilla_id: value for value in draft.values}
    assert values[_M130_INGRESOS_CASILLA].value == expected


def test_decimal_helper_rejects_noncanonical_casilla_keys() -> None:
    bad_inputs: dict[object, str | Decimal] = {key: value for key, value in _valid_inputs().items()}
    bad_inputs["bad key"] = Decimal("1")

    with pytest.raises(
        ValueError,
        match=r"registry filing test helper casilla id 'bad key' is not a canonical casilla\.id",
    ):
        build_registry_filing_draft_from_decimals(
            modelo="130",
            period=_Q1_2026,
            casilla_decimals=bad_inputs,
            binding_decimals=_valid_bindings(),
        )


@pytest.mark.parametrize(
    "raw_value",
    ("not-a-decimal", "5.550,00"),
    ids=("invalid-token", "spanish-thousands"),
)
def test_invalid_decimal_strings_raise(raw_value: str) -> None:
    bad_inputs = {key: str(value) for key, value in _valid_inputs().items()}
    bad_inputs[_M130_INGRESOS_CASILLA] = raw_value

    with pytest.raises(InvalidOperation, match=r"ConversionSyntax|InvalidOperation|conversion"):
        build_registry_filing_draft_from_decimals(
            modelo="130",
            period=_Q1_2026,
            casilla_decimals=bad_inputs,
            binding_decimals=_valid_bindings(),
        )
