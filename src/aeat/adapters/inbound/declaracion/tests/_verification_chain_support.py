"""Shared support for split adapter tests."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from datetime import date
from decimal import Decimal

import pytest

from .....core.resources import resources
from .....domain.calculations.registry import (
    BindingId,
    CasillaId,
    RegistryValidationError,
    RelationId,
    calculate_registry_snapshot,
    validated_casilla_id,
)
from .....domain.calculations.registry import (
    CasillaObservation as CasillaObservation,
)
from .....domain.calculations.registry import (
    RegistryModeloObservation as RegistryModeloObservation,
)
from .....domain.calculations.registry import (
    resolve_bound_inputs_by_casilla_id as resolve_bound_inputs_by_casilla_id,
)
from .....domain.calculations.registry import (
    resolve_relation_values_from_observations as resolve_relation_values_from_observations,
)
from .....tests import FIXTURES_DIR
from .....tests.registry_observations import registry_grounded_observations
from .. import DeclaracionParseError, parse_declaracion

pytestmark = [
    pytest.mark.unit,
    pytest.mark.hex_inbound_adapter,
]


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="test casilla id")
    except ValueError as exc:
        raise AssertionError(f"verification fixture casilla key {value!r} is not a canonical casilla.id") from exc


def _casilla_ids(*values: object) -> frozenset[CasillaId]:
    return frozenset(_casilla_id(value) for value in values)


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
    assert casilla_id in extracted, (
        f"PARSER-GAP [{label}]: {casilla_id!r} not extracted.\n  got: {sorted(extracted)}"
    )
    value = extracted[casilla_id]
    assert isinstance(value, Decimal), (
        f"PARSER-GAP [{label}]: {casilla_id!r} not Decimal: {type(value).__name__!r}"
    )


def _assert_all_extracted_values_decimal(extracted: Mapping[CasillaId, object], *, label: str) -> None:
    for casilla_id, value in extracted.items():
        assert isinstance(value, Decimal), (
            f"PARSER-GAP [{label}]: casilla {casilla_id!r} not Decimal: "
            f"{type(value).__name__!r} = {value!r}"
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
        f"PARSER-GAP [{label}]: casilla {casilla_id!r} is not Decimal: "
        f"{type(extracted_value).__name__!r}"
    )
    engine_value = engine_values.get(casilla_id)
    assert engine_value is not None, (
        f"FORMULA-MISMATCH [{label}]: casilla {casilla_id!r} absent from engine result."
    )
    assert isinstance(engine_value, Decimal), (
        f"FORMULA-MISMATCH [{label}]: casilla {casilla_id!r} is not Decimal: "
        f"{type(engine_value).__name__!r}"
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


_DECL_TOTAL_PERCEPTORES_CASILLA: CasillaId = _casilla_id("decl.total-perceptores")
_DECL_BASE_TOTAL_CASILLA: CasillaId = _casilla_id("decl.base-total")
_DECL_RETENCIONES_TOTAL_CASILLA: CasillaId = _casilla_id("decl.retenciones-total")
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
            inputs=resolve_bound_inputs_by_casilla_id(snapshot.revision, binding_values),
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
            f"FORMULA-MISMATCH [{case_label}]: casilla {casilla_id!r} is not Decimal: "
            f"{type(engine_value).__name__!r}"
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


_M303_STATE_ATTRIBUTION_RATIO_CASILLA: CasillaId = _casilla_id("65")
_M303_CUOTA_DEVENGADA_TOTAL_CASILLA: CasillaId = _casilla_id("27")
_M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA: CasillaId = _casilla_id("45")
_M303_RESULTADO_REGIMEN_GENERAL_CASILLA: CasillaId = _casilla_id("iva.resultado-regimen-general")
_M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA: CasillaId = _casilla_id(
    "iva.compensacion-pendiente-periodos-anteriores",
)
_M303_ENGINE_REQUIRED_CASILLAS: tuple[CasillaId, ...] = (
    _M303_CUOTA_DEVENGADA_TOTAL_CASILLA,
    _M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA,
    _M303_RESULTADO_REGIMEN_GENERAL_CASILLA,
)
_COMPUTED_CASILLAS_M130: frozenset[CasillaId] = _casilla_ids(
    "03",
    "04",
    "07",
    "09",
    "11",
    "12",
    "13",
    "14",
    "17",
    "19",
    "saldo-negativo-fin-periodo",
)

_COMPUTED_CASILLAS_M111: frozenset[CasillaId] = _casilla_ids("28", "30")


def _registry_snapshot(modelo: str, filing_year: int, period: str):
    """Resolve a validated registry snapshot from the committed authority."""
    return resources().modelos.authority.snapshot(modelo, filing_year=filing_year, period=period)


_DR303_PROJECTION_CASILLAS: frozenset[CasillaId] = _casilla_ids(
    "03",
    "06",
    "09",
    "11",
    "13",
    "27",
    "29",
    "33",
    "37",
    "45",
)

_COMPUTED_CASILLAS_M303: frozenset[CasillaId] = frozenset(
    {
        _casilla_id("iva.cuota-devengada-total"),
        _casilla_id("iva.cuota-deducible-total"),
        _casilla_id("iva.resultado-regimen-general"),
        *_DR303_PROJECTION_CASILLAS,
        _casilla_id("64"),  # suma de resultados (46 + 58 + 76) — Orden HAC/819/2024 art. 1
        _casilla_id("66"),  # atribuible Estado (64 × 65 / 100) — Orden HAC/819/2024 art. 1
        _casilla_id("iva.compensacion-aplicada-periodo"),
        _casilla_id("iva.compensacion-pendiente-periodos-posteriores"),
        _casilla_id("iva.resultado"),  # resultado autoliquidación (66 + 77 + 68 - 78)
        _casilla_id("71"),  # resultado final (69 - 70 + 109) — Orden HAC/819/2024 art. 1
        _casilla_id("iva.compensacion-generada-periodo"),
        _casilla_id("iva.compensacion-disponible-fin-periodo"),
    },
)

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


def _build_m303_engine_result(pdf_stem: str, year: int, period: str):  # type: ignore[return]
    """Parse the corpus PDF and run the registry engine.  Returns (extracted, engine_values)."""
    extracted = _parse_extracted_declaracion_values(modelo="303", fixture_stem=pdf_stem, year=year, period=period)
    for required_id in _M303_ENGINE_REQUIRED_CASILLAS:
        assert required_id in extracted, (
            f"PARSER-GAP [{pdf_stem}]: required casilla {required_id!r} not in extracted values.\n"
            f"  got: {sorted(extracted)}"
        )

    inputs = _decimal_inputs_from_extracted_values(extracted, excluding=_COMPUTED_CASILLAS_M303)

    # Box 65 — % atribuible Estado; bound to the profile-derived
    # ``tax_residence.state_attribution_ratio`` via casilla.binding. The engine's
    # _initial_values only auto-hydrates BOUND casillas from binding_values when
    # the binding's source is ``previous_filing``; profile-sourced bound casillas
    # expect the application-layer resolver to have populated ``inputs`` with the
    # resolved value before reaching the calculator. This test path bypasses
    # the application layer, so we supply C65 via both channels: inputs hydrates
    # the casilla value for the formula multiplier; binding_values satisfies
    # any explicit binding-fact lookups.
    # Grounded in Orden HAC/819/2024 art. 1 (casilla 65 instrucciones).
    inputs[_M303_STATE_ATTRIBUTION_RATIO_CASILLA] = Decimal("100")

    _extracted_comp = extracted.get(_M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA, Decimal("0"))
    _comp = _extracted_comp if isinstance(_extracted_comp, Decimal) else Decimal("0")
    binding_values: dict[BindingId, Decimal] = {
        "modelo-303-compensacion-pendiente-anteriores": _comp,
        "modelo-303-profile-state-attribution-ratio": Decimal("100"),
    }

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
            f"BINDING-GAP [{pdf_stem}]: calculate_registry_snapshot raised RegistryValidationError.\n"
            f"  error: {exc}\n"
            f"  inputs supplied: {sorted(inputs)}\n"
            f"  binding_values supplied: {sorted(binding_values)}",
        )
    return extracted, dict(result.values), inputs


def _assert_m303_engine_matches_extracted_decimal(
    *,
    pdf_stem: str,
    engine_values: Mapping[CasillaId, object],
    extracted: Mapping[CasillaId, object],
    casilla_id: CasillaId,
    label: str,
    formula_context: str,
) -> Decimal:
    engine_value = engine_values.get(casilla_id)
    assert isinstance(engine_value, Decimal), (
        f"VERIFIED-FAIL [{pdf_stem}]: engine {label} missing or non-Decimal: {engine_value!r}"
    )
    extracted_value = extracted.get(casilla_id)
    assert isinstance(extracted_value, Decimal), (
        f"VERIFIED-FAIL [{pdf_stem}]: extracted {label} missing or non-Decimal: {extracted_value!r}"
    )
    assert engine_value == extracted_value, (
        f"VERIFIED-FAIL [{pdf_stem}]: engine {label} {engine_value!r} != extracted {extracted_value!r}\n"
        f"  ({formula_context})"
    )
    return engine_value


def _assert_m303_resultado_regimen_general_consistency(
    *,
    pdf_stem: str,
    engine_values: Mapping[CasillaId, object],
    extracted: Mapping[CasillaId, object],
) -> None:
    engine_resultado = _assert_m303_engine_matches_extracted_decimal(
        pdf_stem=pdf_stem,
        engine_values=engine_values,
        extracted=extracted,
        casilla_id=_M303_RESULTADO_REGIMEN_GENERAL_CASILLA,
        label="box 46 (resultado regimen general)",
        formula_context="box 46 = box 27 - box 45, Orden EHA/3786/2008 art. 1",
    )
    engine_27 = engine_values.get(_M303_CUOTA_DEVENGADA_TOTAL_CASILLA)
    engine_45 = engine_values.get(_M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA)
    assert isinstance(engine_27, Decimal), (
        f"VERIFIED-FAIL [{pdf_stem}]: engine-computed box 27 missing or non-Decimal: {engine_27!r}"
    )
    assert isinstance(engine_45, Decimal), (
        f"VERIFIED-FAIL [{pdf_stem}]: engine-computed box 45 missing or non-Decimal: {engine_45!r}"
    )
    expected_resultado = engine_27 - engine_45
    assert engine_resultado == expected_resultado, (
        f"VERIFIED-FAIL [{pdf_stem}]: engine resultado-regimen-general "
        f"{engine_resultado!r} != box27({engine_27!r}) - box45({engine_45!r}) = {expected_resultado!r}\n"
        f"  (internal formula consistency broken - registry formula defect)"
    )


_COMPUTED_CASILLAS_M390: frozenset[CasillaId] = _casilla_ids(
    "iva.anual.cuota-devengada-total",
    "iva.anual.cuota-deducible-total",
    "iva.anual.resultado-regimen-general",
)

_M390_PREVIOUS_FILING_BINDING_IDS = (
    "modelo-390-prev-303-cuota-devengada-total",
    "modelo-390-prev-303-cuota-deducible-total",
    "modelo-390-prev-303-resultado-regimen-general",
    "modelo-390-prev-303-compensacion-ultimo-periodo",
    "modelo-390-prev-303-compensacion-generada-ejercicio-no-97",
)

_COMPUTED_CASILLAS_M115: frozenset[CasillaId] = _casilla_ids("03", "05")

_COMPUTED_CASILLAS_M123_2019: frozenset[CasillaId] = _casilla_ids("06", "08")

_COMPUTED_CASILLAS_M123_2024: frozenset[CasillaId] = _casilla_ids("03", "06", "09", "12", "14")

_COMPUTED_CASILLAS_M131: frozenset[CasillaId] = _casilla_ids(
    "04",
    "06",
    "07",
    "10",
    "13",
    "15",
    "saldo-negativo-fin-periodo",
)


def _period_to_date(year: int, period: str) -> date:
    """Convert a filing year and AEAT period string to the last date of that period.

    Used as the ``filing_period`` date context for ``calculate_registry_snapshot``.
    """
    period_upper = period.upper()
    if period_upper == "1T":
        return date(year, 3, 31)
    if period_upper == "2T":
        return date(year, 6, 30)
    if period_upper == "3T":
        return date(year, 9, 30)
    if period_upper in ("4T", "0A"):
        return date(year, 12, 31)
    if len(period_upper) == 2 and period_upper.isdigit():
        month = int(period_upper)
        import calendar

        last_day = calendar.monthrange(year, month)[1]
        return date(year, month, last_day)
    return date(year, 12, 31)
