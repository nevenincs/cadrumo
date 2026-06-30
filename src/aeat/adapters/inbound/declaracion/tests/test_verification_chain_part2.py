"""Focused adapter contract tests split from the original monolith."""

from __future__ import annotations

import pytest

from .....tests.registry_observations import registry_grounded_observations
from ._verification_chain_support import (
    FIXTURES_DIR,
    BindingId,
    CasillaId,
    Decimal,
    DeclaracionParseError,
    RegistryModeloObservation,
    RegistryValidationError,
    _registry_snapshot,
    calculate_registry_snapshot,
    date,
    parse_declaracion,
    resolve_bound_inputs_by_casilla_id,
    resolve_relation_values_from_observations,
    validated_casilla_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="test casilla id")
    except ValueError as exc:
        raise AssertionError(f"test fixture casilla key {value!r} is not a canonical casilla.id") from exc


def _casilla_ids(*values: object) -> frozenset[CasillaId]:
    return frozenset(_casilla_id(value) for value in values)


_DECL_TOTAL_PERCEPTORES_CASILLA: CasillaId = _casilla_id("decl.total-perceptores")
_DECL_BASE_TOTAL_CASILLA: CasillaId = _casilla_id("decl.base-total")
_DECL_RETENCIONES_TOTAL_CASILLA: CasillaId = _casilla_id("decl.retenciones-total")
_DECL_SUMMARY_CASILLAS: frozenset[CasillaId] = _casilla_ids(
    "decl.total-perceptores",
    "decl.base-total",
    "decl.retenciones-total",
)
_DECL_SUMMARY_ASSERTION_CASILLAS: tuple[CasillaId, ...] = (
    _DECL_TOTAL_PERCEPTORES_CASILLA,
    _DECL_BASE_TOTAL_CASILLA,
    _DECL_RETENCIONES_TOTAL_CASILLA,
)
_DECL_MONETARY_SUMMARY_CASILLAS: tuple[CasillaId, ...] = (
    _DECL_BASE_TOTAL_CASILLA,
    _DECL_RETENCIONES_TOTAL_CASILLA,
)
_M115_TOTAL_PERCEPTORES_CASILLA: CasillaId = _casilla_id("01")
_M115_BASE_TOTAL_CASILLA: CasillaId = _casilla_id("02")
_M115_RETENCIONES_CASILLA: CasillaId = _casilla_id("03")
_M123_TOTAL_RENTAS_CASILLA: CasillaId = _casilla_id("03")
_M123_TOTAL_BASE_CASILLA: CasillaId = _casilla_id("06")
_M123_TOTAL_RETENCIONES_CASILLA: CasillaId = _casilla_id("09")
_M180_PERCEPTORES_BINDING: BindingId = "modelo-180-115-perceptores-anual"
_M180_RETIRED_PERCEPTORES_RELATION = "modelo-180-rel-115-perceptores-anual"
_M193_PERCEPTORES_BINDING: BindingId = "modelo-193-123-perceptores-anual"
_M193_RETIRED_PERCEPTORES_RELATION = "modelo-193-rel-123-perceptores-anual"


_ANNUAL_SUMMARY_PARSER_CASES: tuple[tuple[str, str], ...] = (
    ("180", "M180/2024-0A"),
    ("193", "M193/2024-0A"),
)


@pytest.mark.parametrize(
    ("modelo", "case_label"),
    _ANNUAL_SUMMARY_PARSER_CASES,
    ids=("m180", "m193"),
)
def test_verification_chain_annual_summary_parser_extracts_declaracion_pdf_casillas(
    modelo: str,
    case_label: str,
) -> None:
    pdf_path = FIXTURES_DIR / "justificantes" / modelo / "2024-0A.pdf"

    try:
        filing = parse_declaracion(
            pdf_path,
            modelo_override=modelo,
            año_override=2024,
            period_override="0A",
        )
    except DeclaracionParseError as exc:
        pytest.fail(f"PARSER-GAP [{case_label}]: parse_declaracion raised.\n  error: {exc}")

    extracted = {v.casilla_id: v.printed_value for v in filing.values}
    assert set(extracted.keys()) == _DECL_SUMMARY_CASILLAS, (
        f"PARSER-GAP [{case_label}]: unexpected casilla set.\n  got: {sorted(extracted)}"
    )
    for casilla_id, value in extracted.items():
        assert isinstance(value, Decimal), (
            f"PARSER-GAP [{case_label}]: casilla {casilla_id!r} not Decimal: {type(value).__name__!r}"
        )


def test_verification_chain_m180_engine_recomputes_closure_casillas_from_m115_relations_and_binding() -> None:
    """Engine recomputes M180 annual closure casillas from M115 relations and binding values.

    GROUNDED authority: synthetic M180 fixture at
    src/aeat/tests/fixtures/justificantes/180/2024-0A.pdf, derived from
    AEAT Orden HAP/1732/2014 printed form structure.  The fixture prints:
      decl.total-perceptores = 3       (dedicated annual perceptor binding)
      decl.base-total        = 12000.00 (sum of M115 casilla 02 across 4 quarters)
      decl.retenciones-total =  2280.00 (sum of M115 casilla 03 across 4 quarters)

    Legal grounding: Ley 35/2006 art.99; RD 439/2007 arts.100,108,109;
    Orden HAP/1732/2014 art.2; Orden HFP/1284/2023 art.7.

    Chain:
      1. Parse the 2024-0A M180 fixture → extracted closure values.
      2. Build M115 quarterly observations whose monetary sums match the M180 totals.
      3. Resolve relation_values via resolve_relation_values_from_observations.
      4. Supply decl.total-perceptores through modelo-180-115-perceptores-anual.
      5. calculate_registry_snapshot(M180 snapshot, bound inputs, binding_values, relation_values).
      6. Assert perceptor count is bound, and monetary totals are relation-derived.

    Verdict: VERIFIED — the M115→M180 monetary relation chain resolves without
    resurrecting the retired quarterly perceptor-count relation.
    """
    pdf_path = FIXTURES_DIR / "justificantes" / "180" / "2024-0A.pdf"

    # Parse the printed M180 form: these are the AEAT-grounded expected values.
    try:
        filing = parse_declaracion(
            pdf_path,
            modelo_override="180",
            año_override=2024,
            period_override="0A",
        )
    except DeclaracionParseError as exc:
        pytest.fail(f"PARSER-GAP [M180/2024-0A engine]: parse_declaracion raised.\n  error: {exc}")

    extracted = {v.casilla_id: v.printed_value for v in filing.values}

    perceptor_binding_value = Decimal("3")
    extracted_perceptors = extracted.get(_DECL_TOTAL_PERCEPTORES_CASILLA)
    assert extracted_perceptors == perceptor_binding_value, (
        f"PARSER-GAP [M180/2024-0A engine]: fixture printed {_DECL_TOTAL_PERCEPTORES_CASILLA!r} "
        f"as {extracted_perceptors!r}, expected {perceptor_binding_value!r}."
    )

    # Build M115 quarterly observations whose monetary sums match the M180 fixture totals.
    # The quarterly perceptor source casilla is intentionally present in the observations
    # to prove the resolver does not emit the retired perceptor-count relation.
    _m115_quarterly: dict[str, dict[CasillaId, Decimal]] = {
        "1T": {
            _M115_TOTAL_PERCEPTORES_CASILLA: Decimal("1"),
            _M115_BASE_TOTAL_CASILLA: Decimal("3000.00"),
            _M115_RETENCIONES_CASILLA: Decimal("570.00"),
        },
        "2T": {
            _M115_TOTAL_PERCEPTORES_CASILLA: Decimal("1"),
            _M115_BASE_TOTAL_CASILLA: Decimal("3000.00"),
            _M115_RETENCIONES_CASILLA: Decimal("570.00"),
        },
        "3T": {
            _M115_TOTAL_PERCEPTORES_CASILLA: Decimal("1"),
            _M115_BASE_TOTAL_CASILLA: Decimal("3000.00"),
            _M115_RETENCIONES_CASILLA: Decimal("570.00"),
        },
        "4T": {
            _M115_TOTAL_PERCEPTORES_CASILLA: Decimal("0"),
            _M115_BASE_TOTAL_CASILLA: Decimal("3000.00"),
            _M115_RETENCIONES_CASILLA: Decimal("570.00"),
        },
    }
    observations = tuple(
        RegistryModeloObservation(
            modelo="115",
            filing_year=2024,
            period=period,
            observations=registry_grounded_observations(
                modelo="115",
                filing_year=2024,
                period=period,
                casilla_values=casilla_values,
            ),
        )
        for period, casilla_values in sorted(_m115_quarterly.items())
    )

    # Resolve relation_values for the M180 2023-y-siguientes snapshot.
    snapshot = _registry_snapshot("180", 2024, "0A")
    try:
        relation_values = resolve_relation_values_from_observations(
            snapshot.revision,
            observations,
            filing_year=2024,
            period="0A",
        )
    except RegistryValidationError as exc:
        pytest.fail(
            f"BINDING-GAP [M180/2024-0A engine]: resolve_relation_values_from_observations raised "
            f"RegistryValidationError — M115→M180 relation chain is structurally broken.\n"
            f"  error: {exc}",
        )
    assert _M180_RETIRED_PERCEPTORES_RELATION not in relation_values, (
        f"BINDING-GAP [M180/2024-0A engine]: retired quarterly perceptor relation "
        f"{_M180_RETIRED_PERCEPTORES_RELATION!r} was resolved. Perceptor count must flow through "
        f"{_M180_PERCEPTORES_BINDING!r}."
    )

    # Run the calculation engine.
    binding_values: dict[BindingId, Decimal] = {_M180_PERCEPTORES_BINDING: perceptor_binding_value}
    try:
        result = calculate_registry_snapshot(
            snapshot,
            inputs=resolve_bound_inputs_by_casilla_id(snapshot.revision, binding_values),
            date_context={"filing_period": date(2024, 12, 31)},
            binding_values=binding_values,
            relation_values=relation_values,
        )
    except RegistryValidationError as exc:
        pytest.fail(
            f"BINDING-GAP [M180/2024-0A engine]: calculate_registry_snapshot raised "
            f"RegistryValidationError — engine could not recompute from supplied relation_values.\n"
            f"  error: {exc}\n"
            f"  binding_values keys: {sorted(binding_values)}\n"
            f"  relation_values keys: {sorted(relation_values)}",
        )

    # Assert engine closure values match AEAT-grounded extracted values.
    engine_values = dict(result.values)
    entries_by_target = {entry.target_casilla_id: entry for entry in result.entries}

    assert _DECL_TOTAL_PERCEPTORES_CASILLA not in entries_by_target, (
        f"FORMULA-MISMATCH [M180/2024-0A engine]: {_DECL_TOTAL_PERCEPTORES_CASILLA!r} was produced "
        "by a formula entry, but this casilla must be bound."
    )
    assert engine_values.get(_DECL_TOTAL_PERCEPTORES_CASILLA) == perceptor_binding_value, (
        f"FORMULA-MISMATCH [M180/2024-0A engine]: engine resolved {_DECL_TOTAL_PERCEPTORES_CASILLA!r} "
        f"as {engine_values.get(_DECL_TOTAL_PERCEPTORES_CASILLA)!r}, expected binding "
        f"{_M180_PERCEPTORES_BINDING!r} value {perceptor_binding_value!r}."
    )

    for casilla_id in _DECL_MONETARY_SUMMARY_CASILLAS:
        extracted_value = extracted.get(casilla_id)
        engine_value = engine_values.get(casilla_id)
        assert extracted_value is not None, (
            f"PARSER-GAP [M180/2024-0A engine]: closure casilla {casilla_id!r} absent from extracted values"
        )
        assert isinstance(extracted_value, Decimal), (
            f"PARSER-GAP [M180/2024-0A engine]: {casilla_id!r} is not Decimal: {type(extracted_value).__name__!r}"
        )
        assert engine_value is not None, (
            f"FORMULA-MISMATCH [M180/2024-0A engine]: casilla {casilla_id!r} absent from engine result — "
            f"formula evaluation order issue or casilla missing from revision."
        )
        assert engine_value == extracted_value, (
            f"FORMULA-MISMATCH [M180/2024-0A engine]: engine recomputed {casilla_id!r} as "
            f"{engine_value!r} but AEAT-printed fixture shows {extracted_value!r}.\n"
            f"  diff: {engine_value - extracted_value!r}\n"
            f"  binding_values supplied: {binding_values}\n"
            f"  relation_values supplied: {relation_values}"
        )


def test_verification_chain_m190_parser_extracts_declaracion_pdf_casillas() -> None:
    """Parser extracts the 3 M190 summary casillas from the real corpus PDF.

    GROUNDED authority: real AEAT corpus PDF (sanitised) committed at
    src/aeat/tests/fixtures/justificantes/190/2024-0A.pdf.

    The M190 registry has no formulas — retenciones-total is an aggregation of
    perceptor-level withholding records, not a computed formula. Verdict:
    BINDING-GAP for formula verification — no formula to exercise. This test
    verifies the extraction side of the chain.
    """
    pdf_path = FIXTURES_DIR / "justificantes" / "190" / "2024-0A.pdf"

    try:
        filing = parse_declaracion(
            pdf_path,
            modelo_override="190",
            año_override=2024,
            period_override="0A",
        )
    except DeclaracionParseError as exc:
        pytest.fail(f"PARSER-GAP [M190/2024-0A]: parse_declaracion raised.\n  error: {exc}")

    extracted = {v.casilla_id: v.printed_value for v in filing.values}
    assert _DECL_RETENCIONES_TOTAL_CASILLA in extracted, (
        f"PARSER-GAP [M190/2024-0A]: 'decl.retenciones-total' not extracted.\n  got: {sorted(extracted)}"
    )
    assert isinstance(extracted[_DECL_RETENCIONES_TOTAL_CASILLA], Decimal), (
        "PARSER-GAP [M190/2024-0A]: 'decl.retenciones-total' not Decimal"
    )

def test_verification_chain_m193_engine_recomputes_closure_casillas_from_m123_relations_and_binding() -> None:
    """Engine recomputes M193 annual closure casillas from M123 relations and binding values.

    GROUNDED authority: synthetic M193 fixture at
    src/aeat/tests/fixtures/justificantes/193/2024-0A.pdf.  The fixture prints:
      decl.total-perceptores = 2      (dedicated annual perceptor binding)
      decl.base-total        = 8000.00 (sum of M123 casilla 06 across 4 quarters)
      decl.retenciones-total = 1520.00 (sum of M123 casilla 09 across 4 quarters)

    Legal grounding: Ley 35/2006 art.25, art.99; RD 439/2007 art.109, art.108,
    art.90, art.101; Orden EHA/3377/2011 art.1; Ley 58/2003 art.93.

    Chain:
      1. Parse the 2024-0A M193 fixture → extracted closure values.
      2. Build M123 quarterly observations whose monetary sums match the M193 totals.
      3. Resolve relation_values via resolve_relation_values_from_observations.
      4. Supply decl.total-perceptores through modelo-193-123-perceptores-anual.
      5. calculate_registry_snapshot(M193 snapshot, bound inputs, binding_values, relation_values).
      6. Assert perceptor count is bound, and monetary totals are relation-derived.

    NOTE: The relation uses M123 2024-y-siguientes casillas 03, 06, 09 which are
    all computed by the engine (not manual inputs). The observations must supply
    them directly as CasillaObservation (representing engine-computed outputs from
    prior quarterly filing runs), not as engine inputs for the current run.

    Verdict: VERIFIED — the M123→M193 monetary relation chain resolves without
    resurrecting the retired quarterly perceptor-count relation.
    """
    pdf_path = FIXTURES_DIR / "justificantes" / "193" / "2024-0A.pdf"

    try:
        filing = parse_declaracion(
            pdf_path,
            modelo_override="193",
            año_override=2024,
            period_override="0A",
        )
    except DeclaracionParseError as exc:
        pytest.fail(f"PARSER-GAP [M193/2024-0A engine]: parse_declaracion raised.\n  error: {exc}")

    extracted = {v.casilla_id: v.printed_value for v in filing.values}

    perceptor_binding_value = Decimal("2")
    extracted_perceptors = extracted.get(_DECL_TOTAL_PERCEPTORES_CASILLA)
    assert extracted_perceptors == perceptor_binding_value, (
        f"PARSER-GAP [M193/2024-0A engine]: fixture printed {_DECL_TOTAL_PERCEPTORES_CASILLA!r} "
        f"as {extracted_perceptors!r}, expected {perceptor_binding_value!r}."
    )

    # Build M123 quarterly observations whose monetary sums match the M193 fixture totals.
    # M123 casilla 03 = total-rentas (01+02); casilla 06 = total-base (04+05);
    # casilla 09 = total-retenciones (07+08).
    # The total-rentas source is intentionally present to prove the resolver does
    # not emit the retired perceptor-count relation.
    # Q1: 03=2, 06=2000.00, 09=380.00
    # Q2-Q4: 03=0, 06=2000.00, 09=380.00
    # Sums: 03 → 2, 06 → 8000.00, 09 → 1520.00
    _m123_quarterly: dict[str, dict[CasillaId, Decimal]] = {
        "1T": {
            _M123_TOTAL_RENTAS_CASILLA: Decimal("2"),
            _M123_TOTAL_BASE_CASILLA: Decimal("2000.00"),
            _M123_TOTAL_RETENCIONES_CASILLA: Decimal("380.00"),
        },
        "2T": {
            _M123_TOTAL_RENTAS_CASILLA: Decimal("0"),
            _M123_TOTAL_BASE_CASILLA: Decimal("2000.00"),
            _M123_TOTAL_RETENCIONES_CASILLA: Decimal("380.00"),
        },
        "3T": {
            _M123_TOTAL_RENTAS_CASILLA: Decimal("0"),
            _M123_TOTAL_BASE_CASILLA: Decimal("2000.00"),
            _M123_TOTAL_RETENCIONES_CASILLA: Decimal("380.00"),
        },
        "4T": {
            _M123_TOTAL_RENTAS_CASILLA: Decimal("0"),
            _M123_TOTAL_BASE_CASILLA: Decimal("2000.00"),
            _M123_TOTAL_RETENCIONES_CASILLA: Decimal("380.00"),
        },
    }
    observations = tuple(
        RegistryModeloObservation(
            modelo="123",
            filing_year=2024,
            period=period,
            observations=registry_grounded_observations(
                modelo="123",
                filing_year=2024,
                period=period,
                casilla_values=casilla_values,
            ),
        )
        for period, casilla_values in sorted(_m123_quarterly.items())
    )

    snapshot = _registry_snapshot("193", 2024, "0A")
    try:
        relation_values = resolve_relation_values_from_observations(
            snapshot.revision,
            observations,
            filing_year=2024,
            period="0A",
        )
    except RegistryValidationError as exc:
        pytest.fail(
            f"BINDING-GAP [M193/2024-0A engine]: resolve_relation_values_from_observations raised "
            f"RegistryValidationError — M123→M193 relation chain is structurally broken.\n"
            f"  error: {exc}",
        )
    assert _M193_RETIRED_PERCEPTORES_RELATION not in relation_values, (
        f"BINDING-GAP [M193/2024-0A engine]: retired quarterly perceptor relation "
        f"{_M193_RETIRED_PERCEPTORES_RELATION!r} was resolved. Perceptor count must flow through "
        f"{_M193_PERCEPTORES_BINDING!r}."
    )

    binding_values: dict[BindingId, Decimal] = {_M193_PERCEPTORES_BINDING: perceptor_binding_value}
    try:
        result = calculate_registry_snapshot(
            snapshot,
            inputs=resolve_bound_inputs_by_casilla_id(snapshot.revision, binding_values),
            date_context={"filing_period": date(2024, 12, 31)},
            binding_values=binding_values,
            relation_values=relation_values,
        )
    except RegistryValidationError as exc:
        pytest.fail(
            f"BINDING-GAP [M193/2024-0A engine]: calculate_registry_snapshot raised "
            f"RegistryValidationError — engine could not recompute from supplied relation_values.\n"
            f"  error: {exc}\n"
            f"  binding_values keys: {sorted(binding_values)}\n"
            f"  relation_values keys: {sorted(relation_values)}",
        )

    engine_values = dict(result.values)
    entries_by_target = {entry.target_casilla_id: entry for entry in result.entries}

    assert _DECL_TOTAL_PERCEPTORES_CASILLA not in entries_by_target, (
        f"FORMULA-MISMATCH [M193/2024-0A engine]: {_DECL_TOTAL_PERCEPTORES_CASILLA!r} was produced "
        "by a formula entry, but this casilla must be bound."
    )
    assert engine_values.get(_DECL_TOTAL_PERCEPTORES_CASILLA) == perceptor_binding_value, (
        f"FORMULA-MISMATCH [M193/2024-0A engine]: engine resolved {_DECL_TOTAL_PERCEPTORES_CASILLA!r} "
        f"as {engine_values.get(_DECL_TOTAL_PERCEPTORES_CASILLA)!r}, expected binding "
        f"{_M193_PERCEPTORES_BINDING!r} value {perceptor_binding_value!r}."
    )

    for casilla_id in _DECL_MONETARY_SUMMARY_CASILLAS:
        extracted_value = extracted.get(casilla_id)
        engine_value = engine_values.get(casilla_id)
        assert extracted_value is not None, (
            f"PARSER-GAP [M193/2024-0A engine]: closure casilla {casilla_id!r} absent from extracted values"
        )
        assert isinstance(extracted_value, Decimal), (
            f"PARSER-GAP [M193/2024-0A engine]: {casilla_id!r} is not Decimal: {type(extracted_value).__name__!r}"
        )
        assert engine_value is not None, (
            f"FORMULA-MISMATCH [M193/2024-0A engine]: casilla {casilla_id!r} absent from engine result — "
            f"formula evaluation order issue or casilla missing from revision."
        )
        assert engine_value == extracted_value, (
            f"FORMULA-MISMATCH [M193/2024-0A engine]: engine recomputed {casilla_id!r} as "
            f"{engine_value!r} but AEAT-printed fixture shows {extracted_value!r}.\n"
            f"  diff: {engine_value - extracted_value!r}\n"
            f"  binding_values supplied: {binding_values}\n"
            f"  relation_values supplied: {relation_values}"
        )
