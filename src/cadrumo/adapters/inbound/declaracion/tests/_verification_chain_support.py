"""Shared support for split adapter tests."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from datetime import date
from decimal import Decimal

import pytest

from .....core import CasillaId, Period, validated_casilla_id
from .....core.resources import resources
from cadrumo.domain.calculations.registry.ids import BindingId, RelationId
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from cadrumo.domain.calculations.registry.bindings import resolve_available_bound_inputs_by_casilla_id
from cadrumo.domain.calculations.registry.bindings import CasillaObservation as CasillaObservation
from cadrumo.domain.calculations.registry.bindings import RegistryModeloObservation as RegistryModeloObservation
from cadrumo.domain.calculations.registry.relations import resolve_relation_values_from_observations as resolve_relation_values_from_observations
from .....domain.period import calculation_filing_date
from .....tests import FIXTURES_DIR
from .....tests.registry_observations import registry_grounded_observations
from .. import DeclaracionParseError, parse_declaracion

pytestmark = [
    pytest.mark.unit,
    pytest.mark.hex_inbound_adapter,
]


def _declaracion_case_label(
    modelo: str,
    fixture_stem: str,
    *,
    year: int,
    period: str,
    template_revision: str | None,
) -> str:
    suffix = f"/yr={year}/period={period}"
    if template_revision is not None:
        suffix += f"/template={template_revision}"
    return f"M{modelo}/{fixture_stem}{suffix}"


def _parse_extracted_declaracion_values(
    *,
    modelo: str,
    fixture_stem: str,
    year: int,
    period: str,
    template_revision: str | None = None,
) -> dict[CasillaId, object]:
    label = _declaracion_case_label(
        modelo,
        fixture_stem,
        year=year,
        period=period,
        template_revision=template_revision,
    )
    pdf_path = FIXTURES_DIR / "justificantes" / modelo / f"{fixture_stem}.pdf"

    try:
        filing = parse_declaracion(
            pdf_path,
            modelo_override=modelo,
            año_override=year,
            period_override=period,
            template_revision_override=template_revision,
        )
    except DeclaracionParseError as exc:
        detail = exc.translated_message or str(exc) or type(exc).__name__
        context = f" (context={exc.context})" if exc.context else ""
        pytest.fail(f"PARSER-GAP [{label}]: parse_declaracion raised.\n  error: {detail}{context}")

    return {value.casilla_id: value.printed_value for value in filing.values}


def _assert_decimal_casilla(
    extracted: Mapping[CasillaId, object],
    casilla_id: CasillaId,
    *,
    label: str,
) -> None:
    assert casilla_id in extracted, f"PARSER-GAP [{label}]: {casilla_id!r} not extracted.\n  got: {sorted(extracted)}"
    value = extracted[casilla_id]
    assert isinstance(value, Decimal), f"PARSER-GAP [{label}]: {casilla_id!r} not Decimal: {type(value).__name__!r}"


def _assert_all_extracted_values_decimal(extracted: Mapping[CasillaId, object], *, label: str) -> None:
    for casilla_id, value in extracted.items():
        assert isinstance(value, Decimal), (
            f"PARSER-GAP [{label}]: casilla {casilla_id!r} not Decimal: {type(value).__name__!r} = {value!r}"
        )


def _assert_engine_closure_matches_extracted_decimal(
    *,
    label: str,
    engine_values: Mapping[CasillaId, object],
    extracted: Mapping[CasillaId, object],
    casilla_id: CasillaId,
    inputs: Mapping[CasillaId, Decimal] | None = None,
) -> None:
    extracted_value = extracted.get(casilla_id)
    assert isinstance(extracted_value, Decimal), (
        f"PARSER-GAP [{label}]: casilla {casilla_id!r} is not Decimal: {type(extracted_value).__name__!r}"
    )
    engine_value = engine_values.get(casilla_id)
    assert engine_value is not None, f"FORMULA-MISMATCH [{label}]: casilla {casilla_id!r} absent from engine result."
    assert isinstance(engine_value, Decimal), (
        f"FORMULA-MISMATCH [{label}]: casilla {casilla_id!r} is not Decimal: {type(engine_value).__name__!r}"
    )
    input_detail = f"\n  inputs: {inputs}" if inputs is not None else ""
    assert engine_value == extracted_value, (
        f"FORMULA-MISMATCH [{label}]: engine casilla {casilla_id!r} = {engine_value!r}, "
        f"AEAT-printed = {extracted_value!r}.\n"
        f"  diff: {engine_value - extracted_value!r}"
        f"{input_detail}"
    )


def _calculate_engine_values_from_inputs(
    *,
    modelo: str,
    year: int,
    period: str,
    label: str,
    inputs: Mapping[CasillaId, Decimal],
    binding_values: Mapping[BindingId, Decimal] | None = None,
    enum_binding_values: Mapping[BindingId, str] | None = None,
    relation_values: Mapping[RelationId, Decimal] | None = None,
) -> dict[CasillaId, object]:
    snapshot = _registry_snapshot(modelo, year, period)
    try:
        result = calculate_registry_snapshot(
            snapshot,
            inputs=inputs,
            date_context={"filing_period": _period_to_date(year, period)},
            binding_values=binding_values,
            enum_binding_values=enum_binding_values,
            relation_values=relation_values,
        )
    except RegistryValidationError as exc:
        detail = f"\n  binding_values: {sorted(binding_values)}" if binding_values is not None else ""
        if enum_binding_values is not None:
            detail += f"\n  enum_binding_values: {sorted(enum_binding_values)}"
        if relation_values is not None:
            detail += f"\n  relation_values: {sorted(relation_values)}"
        pytest.fail(
            f"BINDING-GAP [{label}]: calculate_registry_snapshot raised RegistryValidationError.\n"
            f"  error: {exc}\n"
            f"  inputs: {sorted(inputs)}"
            f"{detail}",
        )
    return dict(result.values)


def _registry_modelo_observations_from_values(
    *,
    modelo: str,
    filing_year: int,
    period_values: Mapping[str, Mapping[CasillaId, Decimal]],
) -> tuple[RegistryModeloObservation, ...]:
    return tuple(
        RegistryModeloObservation(
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            observations=registry_grounded_observations(
                modelo=modelo,
                filing_year=filing_year,
                period=period,
                casilla_values=casilla_values,
            ),
        )
        for period, casilla_values in sorted(period_values.items())
    )


_DECL_TOTAL_PERCEPTORES_CASILLA: CasillaId = validated_casilla_id("decl.total-perceptores")
_DECL_BASE_TOTAL_CASILLA: CasillaId = validated_casilla_id("decl.base-total")
_DECL_RETENCIONES_TOTAL_CASILLA: CasillaId = validated_casilla_id("decl.retenciones-total")
_DECL_MONETARY_SUMMARY_CASILLAS: tuple[CasillaId, ...] = (
    _DECL_BASE_TOTAL_CASILLA,
    _DECL_RETENCIONES_TOTAL_CASILLA,
)


def _assert_annual_relation_closure_chain(
    *,
    annual_modelo: str,
    source_modelo: str,
    fixture_stem: str,
    year: int,
    period: str,
    source_period_values: Mapping[str, Mapping[CasillaId, Decimal]],
    perceptor_binding_id: BindingId,
    perceptor_binding_value: Decimal,
    retired_perceptor_relation_id: str,
) -> None:
    case_label = f"M{annual_modelo}/{fixture_stem} engine"
    relation_label = f"M{source_modelo}->M{annual_modelo}"

    extracted = _parse_extracted_declaracion_values(
        modelo=annual_modelo,
        fixture_stem=fixture_stem,
        year=year,
        period=period,
    )
    extracted_perceptors = extracted.get(_DECL_TOTAL_PERCEPTORES_CASILLA)
    assert extracted_perceptors == perceptor_binding_value, (
        f"PARSER-GAP [{case_label}]: fixture printed {_DECL_TOTAL_PERCEPTORES_CASILLA!r} "
        f"as {extracted_perceptors!r}, expected {perceptor_binding_value!r}."
    )

    observations = _registry_modelo_observations_from_values(
        modelo=source_modelo,
        filing_year=year,
        period_values=source_period_values,
    )
    snapshot = _registry_snapshot(annual_modelo, year, period)
    try:
        relation_values = resolve_relation_values_from_observations(
            snapshot.revision,
            observations,
            filing_year=year,
            period=period,
        )
    except RegistryValidationError as exc:
        pytest.fail(
            f"BINDING-GAP [{case_label}]: resolve_relation_values_from_observations raised "
            f"RegistryValidationError - {relation_label} relation chain is structurally broken.\n"
            f"  error: {exc}",
        )
    assert retired_perceptor_relation_id not in relation_values, (
        f"BINDING-GAP [{case_label}]: retired quarterly perceptor relation "
        f"{retired_perceptor_relation_id!r} was resolved. Perceptor count must flow through "
        f"{perceptor_binding_id!r}."
    )

    binding_values: dict[BindingId, Decimal] = {perceptor_binding_id: perceptor_binding_value}
    try:
        result = calculate_registry_snapshot(
            snapshot,
            inputs=resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values),
            date_context={"filing_period": _period_to_date(year, period)},
            binding_values=binding_values,
            relation_values=relation_values,
        )
    except RegistryValidationError as exc:
        pytest.fail(
            f"BINDING-GAP [{case_label}]: calculate_registry_snapshot raised "
            f"RegistryValidationError - engine could not recompute from supplied relation_values.\n"
            f"  error: {exc}\n"
            f"  binding_values keys: {sorted(binding_values)}\n"
            f"  relation_values keys: {sorted(relation_values)}",
        )

    engine_values = dict(result.values)
    entries_by_target = {entry.target_casilla_id: entry for entry in result.entries}

    assert _DECL_TOTAL_PERCEPTORES_CASILLA not in entries_by_target, (
        f"FORMULA-MISMATCH [{case_label}]: {_DECL_TOTAL_PERCEPTORES_CASILLA!r} was produced "
        "by a formula entry, but this casilla must be bound."
    )
    assert engine_values.get(_DECL_TOTAL_PERCEPTORES_CASILLA) == perceptor_binding_value, (
        f"FORMULA-MISMATCH [{case_label}]: engine resolved {_DECL_TOTAL_PERCEPTORES_CASILLA!r} "
        f"as {engine_values.get(_DECL_TOTAL_PERCEPTORES_CASILLA)!r}, expected binding "
        f"{perceptor_binding_id!r} value {perceptor_binding_value!r}."
    )

    for casilla_id in _DECL_MONETARY_SUMMARY_CASILLAS:
        extracted_value = extracted.get(casilla_id)
        engine_value = engine_values.get(casilla_id)
        assert extracted_value is not None, (
            f"PARSER-GAP [{case_label}]: closure casilla {casilla_id!r} absent from extracted values"
        )
        assert isinstance(extracted_value, Decimal), (
            f"PARSER-GAP [{case_label}]: {casilla_id!r} is not Decimal: {type(extracted_value).__name__!r}"
        )
        assert engine_value is not None, (
            f"FORMULA-MISMATCH [{case_label}]: casilla {casilla_id!r} absent from engine result - "
            f"formula evaluation order issue or casilla missing from revision."
        )
        assert isinstance(engine_value, Decimal), (
            f"FORMULA-MISMATCH [{case_label}]: casilla {casilla_id!r} is not Decimal: {type(engine_value).__name__!r}"
        )
        assert engine_value == extracted_value, (
            f"FORMULA-MISMATCH [{case_label}]: engine recomputed {casilla_id!r} as "
            f"{engine_value!r} but AEAT-printed fixture shows {extracted_value!r}.\n"
            f"  diff: {engine_value - extracted_value!r}\n"
            f"  binding_values supplied: {binding_values}\n"
            f"  relation_values supplied: {relation_values}"
        )


def _decimal_inputs_from_extracted_values(
    extracted: Mapping[CasillaId, object],
    *,
    excluding: Collection[CasillaId],
) -> dict[CasillaId, Decimal]:
    return {
        casilla_id: value
        for casilla_id, value in extracted.items()
        if casilla_id not in excluding and isinstance(value, Decimal)
    }


_M303_STATE_ATTRIBUTION_RATIO_CASILLA: CasillaId = validated_casilla_id("65")
_M303_CUOTA_DEVENGADA_TOTAL_CASILLA: CasillaId = validated_casilla_id("27")
_M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA: CasillaId = validated_casilla_id("45")
_M303_RESULTADO_REGIMEN_GENERAL_CASILLA: CasillaId = validated_casilla_id("iva.resultado-regimen-general")
_M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA: CasillaId = validated_casilla_id(
    "iva.compensacion-pendiente-periodos-anteriores"
)
_COMPUTED_CASILLAS_M130: frozenset[CasillaId] = frozenset(
    validated_casilla_id(_v)
    for _v in ("03", "04", "07", "09", "11", "12", "13", "14", "17", "19", "saldo-negativo-fin-periodo")
)

_COMPUTED_CASILLAS_M111: frozenset[CasillaId] = frozenset(validated_casilla_id(_v) for _v in ("28", "30"))


def _registry_snapshot(modelo: str, filing_year: int, period: str):
    """Resolve a validated registry snapshot from the committed authority."""
    return resources().modelos.authority.snapshot(modelo, filing_year=filing_year, period=period)


_M303_2023_ONWARDS_PARAMS = [
    ("2023-1T", 2023, "1T"),
    ("2023-2T", 2023, "2T"),
    ("2023-3T", 2023, "3T"),
    ("2023-4T", 2023, "4T"),
    ("2024-1T", 2024, "1T"),
    ("2024-2T", 2024, "2T"),
    ("2024-3T", 2024, "3T"),
    ("2024-4T", 2024, "4T"),
]


def _calculate_m303_engine_values_from_inputs(
    *,
    inputs: Mapping[CasillaId, Decimal],
    year: int,
    period: str,
    binding_values: Mapping[BindingId, Decimal],
    label: str,
) -> dict[CasillaId, object]:
    _period_month = {"1T": 1, "2T": 4, "3T": 7, "4T": 10}[period]
    snapshot = _registry_snapshot("303", year, period)
    try:
        result = calculate_registry_snapshot(
            snapshot,
            inputs=inputs,
            date_context={"filing_period": date(year, _period_month, 1)},
            binding_values=binding_values,
        )
    except RegistryValidationError as exc:
        pytest.fail(
            f"BINDING-GAP [{label}]: calculate_registry_snapshot raised RegistryValidationError.\n"
            f"  error: {exc}\n"
            f"  inputs supplied: {sorted(inputs)}\n"
            f"  binding_values supplied: {sorted(binding_values)}",
        )
    return dict(result.values)


def _extracted_m303_decimal(
    *,
    pdf_stem: str,
    extracted: Mapping[CasillaId, object],
    casilla_id: CasillaId,
    label: str,
) -> Decimal:
    """Read one printed amount off the parsed declaración, refusing anything else."""
    value = extracted.get(casilla_id)
    assert isinstance(value, Decimal), (
        f"PARSER-GAP [{pdf_stem}]: printed {label} missing or non-Decimal: {value!r}\n  extracted: {sorted(extracted)}"
    )
    return value


def _assert_m303_printed_resultado_regimen_general_arithmetic(
    *,
    pdf_stem: str,
    extracted: Mapping[CasillaId, object],
) -> None:
    """The declaración's own printed arithmetic must hold: box 46 == box 27 - box 45.

    GROUNDED authority: Orden EHA/3786/2008 art. 1 — box 46 = box 27 - box 45,
    where box 27 is Total cuota devengada (LIVA art. 88) and box 45 is Total a
    deducir (LIVA arts. 92-94).

    This is a check on the DOCUMENT, not on the engine, and that is deliberate.
    The three values are printed independently by AEAT, so a render whose own
    totals disagree is caught here. The assertion is falsifiable by construction:
    perturbing any one of the three printed amounts makes it fail.

    The engine deliberately does not participate. Boxes 27 and 45 are
    projections of ``iva.cuota-devengada-total`` and
    ``iva.cuota-deducible-total``, which the engine computes by summing the
    per-rate cuota primitives — and the printed form does not carry those
    primitives, so the parse path cannot supply them. Supplying the printed
    totals instead is refused by the engine (``computed registry casillas cannot
    be supplied as inputs``), a guard that exists so pull and calculate cannot
    diverge. Engine coverage of the summation formulas therefore lives on the
    calculate path, where the primitives arrive from ledger aggregation.
    """
    printed_27 = _extracted_m303_decimal(
        pdf_stem=pdf_stem,
        extracted=extracted,
        casilla_id=_M303_CUOTA_DEVENGADA_TOTAL_CASILLA,
        label="box 27 (total cuota devengada)",
    )
    printed_45 = _extracted_m303_decimal(
        pdf_stem=pdf_stem,
        extracted=extracted,
        casilla_id=_M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA,
        label="box 45 (total a deducir)",
    )
    printed_46 = _extracted_m303_decimal(
        pdf_stem=pdf_stem,
        extracted=extracted,
        casilla_id=_M303_RESULTADO_REGIMEN_GENERAL_CASILLA,
        label="box 46 (resultado regimen general)",
    )
    assert printed_46 == printed_27 - printed_45, (
        f"DOCUMENT-INCONSISTENT [{pdf_stem}]: printed box 46 {printed_46!r} != "
        f"box 27 {printed_27!r} - box 45 {printed_45!r} = {printed_27 - printed_45!r}\n"
        f"  (box 46 = box 27 - box 45, Orden EHA/3786/2008 art. 1)"
    )


_COMPUTED_CASILLAS_M390: frozenset[CasillaId] = frozenset(
    validated_casilla_id(_v)
    for _v in (
        "iva.anual.cuota-devengada-total",
        "iva.anual.cuota-deducible-total",
        "iva.anual.resultado-regimen-general",
    )
)

_M390_PREVIOUS_FILING_BINDING_IDS = (
    "modelo-390-prev-303-cuota-devengada-total",
    "modelo-390-prev-303-cuota-deducible-total",
    "modelo-390-prev-303-resultado-regimen-general",
    "modelo-390-prev-303-compensacion-ultimo-periodo",
    "modelo-390-prev-303-compensacion-generada-ejercicio-no-97",
)

_COMPUTED_CASILLAS_M115: frozenset[CasillaId] = frozenset(validated_casilla_id(_v) for _v in ("03", "05"))

_COMPUTED_CASILLAS_M123_2019: frozenset[CasillaId] = frozenset(validated_casilla_id(_v) for _v in ("06", "08"))

_COMPUTED_CASILLAS_M123_2024: frozenset[CasillaId] = frozenset(
    validated_casilla_id(_v) for _v in ("03", "06", "09", "12", "14")
)

_COMPUTED_CASILLAS_M131: frozenset[CasillaId] = frozenset(
    validated_casilla_id(_v) for _v in ("04", "06", "07", "10", "13", "15", "saldo-negativo-fin-periodo")
)


def _period_to_date(year: int, period: str) -> date:
    """Resolve verification context through the typed period/date authority."""
    return calculation_filing_date(Period.from_year_and_code(year, period))
