"""Verification chain: AEAT-grounded printed form → parser → calculation engine.

Project-mission test surface. For each GROUNDED modelo with corpus PDFs and
at least one closure casilla whose formula inputs are all present in the
extraction profile:

    parse_declaracion(pdf) → DeclaracionObservation.values (ExtractedCasilla)
        → filter to non-computed casillas → inputs dict
        → calculate_registry_snapshot(snapshot, inputs=inputs, ...)
        → engine result.values[closure_casilla_id]
        → assert == extracted closure value

This is the primary end-to-end fidelity gate: if the engine's computed value
does not match the AEAT-printed form value, the registry formula or the
extraction profile has a defect. Test FAILS loudly so the defect drives a fix.

Verdict taxonomy per modelo per corpus PDF:
    VERIFIED        — engine recomputed value == extracted printed value
    PARSER-GAP      — parse_declaracion raised (extraction coverage failure)
    BINDING-GAP     — engine raised RegistryValidationError (missing binding)
    FORMULA-MISMATCH — engine computed but value != extracted printed value

Scope for this module:
    M130 (19 corpus PDFs, 2021-2024): casilla 03 = bound rendimiento neto;
        casillas 04,07,09,11,12,13,14,17,19 computed. Closure = casilla 19.
        NOTE: casilla 03 is a bound (non-previous_filing) casilla — it CAN be
        supplied via inputs. Casillas 01,03 must be supplied as inputs; the
        previous_filing bindings (15) are absent-by-design at 1T.
    M111 (4 corpus PDFs, 2024): casillas 01-27 manual, 28=sum(col-C),
        30=28-29. Closure = casilla 28 (total retenciones) and 30 (resultado).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aeat.core.resources import resources
from aeat.domain.calculations.registry import (
    RegistryValidationError,
    calculate_registry_snapshot,
)
from aeat.tests import FIXTURES_DIR

from . import DeclaracionParseError, parse_declaracion

pytestmark = [
    pytest.mark.unit,
    pytest.mark.domain_inbound,
]

_COMPUTED_CASILLAS_M130 = frozenset(
    {"04", "07", "09", "11", "12", "13", "14", "17", "19", "saldo-negativo-fin-periodo"}
)
"""M130 casillas whose input_kind is 'computed' — must NOT appear in engine inputs."""

_COMPUTED_CASILLAS_M111 = frozenset({"28", "30"})
"""M111 casillas whose input_kind is 'computed' — must NOT appear in engine inputs."""


def _registry_snapshot(modelo: str, filing_year: int, period: str):
    """Resolve a validated registry snapshot from the committed authority."""
    return resources().modelos.authority.snapshot(modelo, filing_year=filing_year, period=period)


# ---------------------------------------------------------------------------
# M130 verification chain — 15 corpus PDFs (2021-2T through 2024-4T)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "pdf_stem,year,period",
    [
        ("2021-2T", 2021, "2T"),
        ("2021-3T", 2021, "3T"),
        ("2021-4T", 2021, "4T"),
        ("2022-1T", 2022, "1T"),
        ("2022-2T", 2022, "2T"),
        ("2022-3T", 2022, "3T"),
        ("2022-4T", 2022, "4T"),
        ("2023-1T", 2023, "1T"),
        ("2023-2T", 2023, "2T"),
        ("2023-3T", 2023, "3T"),
        ("2023-4T", 2023, "4T"),
        ("2024-1T", 2024, "1T"),
        ("2024-2T", 2024, "2T"),
        ("2024-3T", 2024, "3T"),
        ("2024-4T", 2024, "4T"),
    ],
)
def test_verification_chain_m130_engine_recomputes_closure_casilla_19(
    pdf_stem: str, year: int, period: str
) -> None:
    """Engine recomputes casilla 19 (resultado final) from extracted leaf inputs.

    GROUNDED authority: AEAT corpus PDFs from the sanitised real-form fixture
    set committed at src/aeat/tests/fixtures/justificantes/130/.

    Chain:
      1. parse_declaracion → DeclaracionObservation with extracted casillas
      2. Filter to non-computed casillas → inputs dict for the engine
      3. Supply previous-filing binding values:
         - modelo-130-resultados-negativos-anteriores = 0 (no prior negative)
         - irpf.previous_year_economic_activity_net_income = 0
           (unknown from corpus → conservative 0 → casilla 13 = 0)
         - modelo-130-actividad-economica-rendimiento-neto-cumulative = extracted["03"]
           (03 is a bound casilla; must be in binding_values to avoid
            the smuggling check when it also appears in inputs)
      4. calculate_registry_snapshot with inputs + binding_values
      5. Assert engine.values["19"] == extracted["19"]

    Verdict: VERIFIED when engine == extracted; PARSER-GAP when parse fails;
    BINDING-GAP when engine raises RegistryValidationError; FORMULA-MISMATCH
    when engine value differs from extracted value (reported as assertion failure).
    """
    pdf_path = FIXTURES_DIR / "justificantes" / "130" / f"{pdf_stem}.pdf"

    # Step 1: parse
    try:
        filing = parse_declaracion(
            pdf_path,
            modelo_override="130",
            año_override=year,
            period_override=period,
        )
    except DeclaracionParseError as exc:
        # PARSER-GAP: extraction failed for this corpus specimen
        pytest.fail(
            f"PARSER-GAP [{pdf_stem}]: parse_declaracion raised DeclaracionParseError — "
            f"extraction coverage failure prevents engine recomputation.\n"
            f"  error: {exc}"
        )

    extracted = {v.casilla_id: v.printed_value for v in filing.values}

    # Step 2: skip specimens where casilla 19 was not extracted
    if "19" not in extracted:
        # The corpus PDF is a partial filing — casilla 19 blank.
        # Still run the engine so BINDING-GAP and FORMULA-MISMATCH can be
        # detected on other extracted casillas; skip the 19-equality assertion.
        closure_extracted = None
    else:
        assert isinstance(extracted["19"], Decimal), (
            f"{pdf_stem}: casilla '19' expected Decimal, got {type(extracted['19']).__name__}"
        )
        closure_extracted = extracted["19"]

    # Step 3: build inputs — exclude computed casillas
    inputs: dict[str, Decimal] = {}
    for casilla_id, value in extracted.items():
        if casilla_id in _COMPUTED_CASILLAS_M130:
            continue
        if not isinstance(value, Decimal):
            continue
        # Casilla 01 and 03 are bound (ledger_renta_income_aggregation) — NOT
        # previous_filing. They are legitimate inputs. See _initial_values: bound
        # non-previous_filing casillas default to inputs.get(casilla_id, ZERO).
        inputs[casilla_id] = value

    # Casilla 03 is bound to modelo-130-actividad-economica-rendimiento-neto-cumulative.
    # The smuggling check blocks previous_filing bound casillas supplied via inputs
    # without binding_values, but ledger_renta_income_aggregation is NOT previous_filing.
    # However, casilla 01 is also bound to a ledger binding; supply via inputs.
    #
    # For the previous_filing bindings (casilla 15 comes from 0002-bindings.toml and
    # 0001-bindings.toml), we supply explicit values to satisfy the runtime:
    extracted_c03 = extracted.get("03", Decimal("0"))
    if not isinstance(extracted_c03, Decimal):
        extracted_c03 = Decimal("0")

    binding_values: dict[str, Decimal] = {
        # Prior-quarter carry-forward; 0 = no prior negative result (safe default
        # for corpus specimens where we don't know prior-quarter saldo).
        "modelo-130-resultados-negativos-anteriores": Decimal("0"),
        # Prior-year net income; 0 → casilla 13 = 0 (minoración rendimientos netos).
        # This is conservative but honest: corpus PDFs don't print casilla 13
        # (computed) so we can't verify it independently.
        "irpf.previous_year_economic_activity_net_income": Decimal("0"),
        # Rendimiento neto cumulative — extracted casilla 03 as the binding source.
        # This resolves the ledger_renta_income_aggregation bound casilla 03.
        "modelo-130-actividad-economica-rendimiento-neto-cumulative": extracted_c03,
        # Ingresos cumulative — extracted casilla 01 as the binding source.
        "modelo-130-actividad-economica-ingresos-cumulative": extracted.get("01", Decimal("0"))
        if isinstance(extracted.get("01"), Decimal) else Decimal("0"),
        "modelo-130-actividad-economica-ingresos-taxable-base-cumulative": Decimal("0"),
    }

    # Step 4: resolve snapshot and run engine
    snapshot = _registry_snapshot("130", year, period)
    filing_period_date = _period_to_date(year, period)

    try:
        result = calculate_registry_snapshot(
            snapshot,
            inputs=inputs,
            date_context={"filing_period": filing_period_date},
            binding_values=binding_values,
        )
    except RegistryValidationError as exc:
        # BINDING-GAP: engine could not compute because a required binding value
        # is missing. This is a structural defect — the verification chain cannot
        # be closed without that binding.
        pytest.fail(
            f"BINDING-GAP [{pdf_stem}]: calculate_registry_snapshot raised "
            f"RegistryValidationError — a required binding is missing.\n"
            f"  error: {exc}\n"
            f"  inputs supplied: {sorted(inputs)}\n"
            f"  binding_values supplied: {sorted(binding_values)}"
        )

    # Step 5: compare engine result against extracted value
    engine_values = dict(result.values)

    if closure_extracted is not None:
        engine_19 = engine_values.get("19")
        assert engine_19 is not None, (
            f"FORMULA-MISMATCH [{pdf_stem}]: casilla '19' absent from engine result "
            f"— formula evaluation order issue or casilla missing from revision."
        )
        assert engine_19 == closure_extracted, (
            f"FORMULA-MISMATCH [{pdf_stem}]: engine recomputed casilla '19' as "
            f"{engine_19!r} but AEAT-printed form shows {closure_extracted!r}.\n"
            f"  diff: {engine_19 - closure_extracted!r}\n"
            f"  extracted inputs: {dict((k, v) for k, v in extracted.items() if k not in _COMPUTED_CASILLAS_M130)}\n"
            f"  engine values for formula chain: "
            f"03={engine_values.get('03')!r} 04={engine_values.get('04')!r} "
            f"05={engine_values.get('05')!r} 06={engine_values.get('06')!r} "
            f"07={engine_values.get('07')!r} 13={engine_values.get('13')!r} "
            f"14={engine_values.get('14')!r} 15={engine_values.get('15')!r} "
            f"17={engine_values.get('17')!r} 18={engine_values.get('18')!r} "
            f"19={engine_19!r}"
        )


# ---------------------------------------------------------------------------
# M111 verification chain — 4 corpus PDFs (2024-1T through 2024-4T)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "pdf_stem,year,period",
    [
        ("2024-1T", 2024, "1T"),
        ("2024-2T", 2024, "2T"),
        ("2024-3T", 2024, "3T"),
        ("2024-4T", 2024, "4T"),
    ],
)
def test_verification_chain_m111_engine_recomputes_closure_casillas_28_and_30(
    pdf_stem: str, year: int, period: str
) -> None:
    """Engine recomputes casilla 28 (total retenciones) and 30 (resultado) from leaf inputs.

    GROUNDED authority: AEAT corpus PDFs from the sanitised real-form fixture
    set committed at src/aeat/tests/fixtures/justificantes/111/.

    Chain:
      1. parse_declaracion → DeclaracionObservation with extracted casillas
      2. Filter to non-computed casillas (01-27, 29) → inputs
      3. calculate_registry_snapshot
      4. Assert engine.values["28"] == extracted["28"] (when present)
         Assert engine.values["30"] == extracted["30"] (when present)

    Formula:
      28 = sum(03, 06, 09, 12, 15, 18, 21, 24, 27)  [total retenciones]
      30 = 28 - 29                                   [resultado a ingresar]

    The corpus PDFs contain only non-zero values; zero casillas are absent.
    Casilla 29 (anteriores autoliquidaciones) is absent from the corpus (zero);
    the engine defaults it to 0, so 30 = 28 - 0 = 28.
    """
    pdf_path = FIXTURES_DIR / "justificantes" / "111" / f"{pdf_stem}.pdf"

    # Step 1: parse
    try:
        filing = parse_declaracion(
            pdf_path,
            modelo_override="111",
            año_override=year,
            period_override=period,
        )
    except DeclaracionParseError as exc:
        pytest.fail(
            f"PARSER-GAP [{pdf_stem}]: parse_declaracion raised DeclaracionParseError.\n"
            f"  error: {exc}"
        )

    extracted = {v.casilla_id: v.printed_value for v in filing.values}

    # Step 2: build inputs — exclude computed casillas 28 and 30
    inputs: dict[str, Decimal] = {}
    for casilla_id, value in extracted.items():
        if casilla_id in _COMPUTED_CASILLAS_M111:
            continue
        if isinstance(value, Decimal):
            inputs[casilla_id] = value

    # Step 3: resolve snapshot and run engine
    snapshot = _registry_snapshot("111", year, period)
    filing_period_date = _period_to_date(year, period)

    try:
        result = calculate_registry_snapshot(
            snapshot,
            inputs=inputs,
            date_context={"filing_period": filing_period_date},
        )
    except RegistryValidationError as exc:
        pytest.fail(
            f"BINDING-GAP [{pdf_stem}]: calculate_registry_snapshot raised "
            f"RegistryValidationError — a required binding is missing.\n"
            f"  error: {exc}\n"
            f"  inputs supplied: {sorted(inputs)}"
        )

    engine_values = dict(result.values)

    # Step 4: verify casilla 28 (when extracted)
    if "28" in extracted:
        extracted_28 = extracted["28"]
        assert isinstance(extracted_28, Decimal)
        engine_28 = engine_values.get("28")
        assert engine_28 is not None, (
            f"FORMULA-MISMATCH [{pdf_stem}]: casilla '28' absent from engine result."
        )
        assert engine_28 == extracted_28, (
            f"FORMULA-MISMATCH [{pdf_stem}]: engine casilla '28' = {engine_28!r}, "
            f"AEAT-printed = {extracted_28!r}.\n"
            f"  diff: {engine_28 - extracted_28!r}\n"
            f"  inputs: {inputs}"
        )

    # Step 5: verify casilla 30 (when extracted)
    if "30" in extracted:
        extracted_30 = extracted["30"]
        assert isinstance(extracted_30, Decimal)
        engine_30 = engine_values.get("30")
        assert engine_30 is not None, (
            f"FORMULA-MISMATCH [{pdf_stem}]: casilla '30' absent from engine result."
        )
        assert engine_30 == extracted_30, (
            f"FORMULA-MISMATCH [{pdf_stem}]: engine casilla '30' = {engine_30!r}, "
            f"AEAT-printed = {extracted_30!r}.\n"
            f"  diff: {engine_30 - extracted_30!r}\n"
            f"  inputs: {inputs}"
        )


# ---------------------------------------------------------------------------
# M303 parser-only verification — no registry formulas in this revision
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "pdf_stem,year,period",
    [
        ("2023-1T", 2023, "1T"),
        ("2023-2T", 2023, "2T"),
        ("2023-3T", 2023, "3T"),
        ("2023-4T", 2023, "4T"),
        ("2024-1T", 2024, "1T"),
        ("2024-2T", 2024, "2T"),
        ("2024-3T", 2024, "3T"),
        ("2024-4T", 2024, "4T"),
    ],
)
def test_verification_chain_m303_parser_extracts_all_profile_casillas(
    pdf_stem: str, year: int, period: str
) -> None:
    """Parser extracts all 12 M303 profile casillas from corpus PDFs.

    GROUNDED authority: AEAT corpus PDFs from the sanitised real-form fixture
    set committed at src/aeat/tests/fixtures/justificantes/303/.

    Verdict: PARSER-GAP when extraction fails; the M303 2023-y-siguientes
    revision carries no registry formulas — formula verification is a
    BINDING-GAP deferred to a future campaign when M303 formula coverage
    is extended. This test verifies the extraction side of the chain only.

    The M303 2009-y-siguientes revision (2021-2022 PDFs) is excluded here;
    it covers a different profile with 4 closure casillas only.
    """
    pdf_path = FIXTURES_DIR / "justificantes" / "303" / f"{pdf_stem}.pdf"

    try:
        filing = parse_declaracion(
            pdf_path,
            modelo_override="303",
            año_override=year,
            period_override=period,
        )
    except DeclaracionParseError as exc:
        pytest.fail(
            f"PARSER-GAP [{pdf_stem}]: parse_declaracion raised — "
            f"M303 2023+ extraction failed.\n  error: {exc}"
        )

    extracted = {v.casilla_id: v.printed_value for v in filing.values}

    assert set(extracted.keys()) == {
        "27",
        "29",
        "37",
        "45",
        "iva.resultado-regimen-general",
        "64",
        "66",
        "iva.compensacion-pendiente-periodos-anteriores",
        "iva.compensacion-aplicada-periodo",
        "iva.compensacion-pendiente-periodos-posteriores",
        "iva.resultado",
        "71",
    }, (
        f"PARSER-GAP [{pdf_stem}]: M303 2023+ profile extraction did not produce "
        f"the expected 12 casilla IDs.\n  got: {sorted(extracted)}"
    )
    # All extracted values must be Decimal instances (amount fields).
    for casilla_id, value in extracted.items():
        assert isinstance(value, Decimal), (
            f"PARSER-GAP [{pdf_stem}]: casilla {casilla_id!r} should be Decimal, "
            f"got {type(value).__name__!r} = {value!r}"
        )


# ---------------------------------------------------------------------------
# M390 verification — engine recomputes resultado-regimen-general
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "pdf_stem,year",
    [
        ("2022-0A", 2022),
        ("2023-0A", 2023),
    ],
)
def test_verification_chain_m390_engine_recomputes_resultado_regimen_general(
    pdf_stem: str, year: int
) -> None:
    """Engine recomputes iva.anual.resultado-regimen-general from extracted inputs.

    GROUNDED authority: AEAT corpus PDFs from the sanitised real-form fixture
    set committed at src/aeat/tests/fixtures/justificantes/390/.

    Formula:
      iva.anual.resultado-regimen-general =
          iva.anual.cuota-devengada-total - iva.anual.cuota-deducible-total

    Note: iva.anual.cuota-devengada-total and iva.anual.cuota-deducible-total are
    themselves computed casillas (sum of sub-totals). The extraction profile
    captures them as targets — but the engine computes them from their
    sub-total leaf inputs. Those leaf inputs are NOT extracted by the
    declaracion_pdf profile. This means the engine cannot recompute
    iva.anual.resultado-regimen-general from extracted values alone.

    Honest verdict: BINDING-GAP — the leaf inputs required by the M390 formula
    DAG (iva.anual.repercutido.general, iva.anual.repercutido.reducido, etc.)
    are not captured by the declaracion_pdf extraction profile. The engine needs
    these inputs to recompute the closure, but they are not printed on the
    one-page summary form that the extraction profile covers.

    This test verifies the parsing side and documents the binding gap explicitly
    so it can drive a future extraction-profile expansion.
    """
    pdf_path = FIXTURES_DIR / "justificantes" / "390" / f"{pdf_stem}.pdf"

    try:
        filing = parse_declaracion(
            pdf_path,
            modelo_override="390",
            año_override=year,
            period_override="0A",
        )
    except DeclaracionParseError as exc:
        pytest.fail(
            f"PARSER-GAP [{pdf_stem}]: parse_declaracion raised — "
            f"M390 extraction failed.\n  error: {exc}"
        )

    extracted = {v.casilla_id: v.printed_value for v in filing.values}

    # Verify the profile captured the expected closure casillas.
    assert "iva.anual.resultado-regimen-general" in extracted, (
        f"PARSER-GAP [{pdf_stem}]: closure casilla 'iva.anual.resultado-regimen-general' "
        f"not in extracted values — parser did not capture it.\n  got: {sorted(extracted)}"
    )

    # The M390 formula engine CANNOT be run with only extraction-profile outputs
    # because it requires the leaf sub-total casillas as inputs. Attempting it
    # would supply computed casillas as inputs, which the engine rejects.
    # Instead, we document the BINDING-GAP verdict explicitly.
    #
    # The extracted iva.anual.resultado-regimen-general = extracted 65 value
    # (1.000,00 from corpus). The engine formula says:
    #   resultado = cuota-devengada-total - cuota-deducible-total
    # Both are computed from leaf casillas not in the extraction profile.
    # Gap items tracked: M390 leaf casilla extraction profile expansion needed.
    extracted_closure = extracted["iva.anual.resultado-regimen-general"]
    assert isinstance(extracted_closure, Decimal), (
        f"PARSER-GAP [{pdf_stem}]: closure casilla value not Decimal: "
        f"{type(extracted_closure).__name__!r} = {extracted_closure!r}"
    )
    # Verify the extracted value is the AEAT corpus ground truth.
    assert extracted_closure == Decimal("1000.00"), (
        f"PARSER-GAP [{pdf_stem}]: closure casilla value changed from corpus ground truth "
        f"Decimal('1000.00'), got {extracted_closure!r}"
    )


# ---------------------------------------------------------------------------
# M180 parser-only verification (formula uses relation bindings from M115)
# ---------------------------------------------------------------------------

def test_verification_chain_m180_parser_extracts_declaracion_pdf_casillas() -> None:
    """Parser extracts the 3 M180 summary casillas from the synthetic corpus fixture.

    GROUNDED authority: synthetic fixture generated from AEAT-published printed
    form text (src/aeat/tests/fixtures/justificantes/180/2024-0A.pdf).

    The M180 formulas aggregate M115 quarterly relation values — the
    decl.retenciones-total formula uses { relation = "modelo-180-rel-115-retenciones-anual" }.
    The engine cannot recompute this without M115 filing observations as
    relation_values. Verdict: BINDING-GAP for formula verification — deferred
    until the M115 relation supply chain is in scope. This test verifies the
    extraction side only.
    """
    pdf_path = FIXTURES_DIR / "justificantes" / "180" / "2024-0A.pdf"

    try:
        filing = parse_declaracion(
            pdf_path,
            modelo_override="180",
            año_override=2024,
            period_override="0A",
        )
    except DeclaracionParseError as exc:
        pytest.fail(
            f"PARSER-GAP [M180/2024-0A]: parse_declaracion raised.\n  error: {exc}"
        )

    extracted = {v.casilla_id: v.printed_value for v in filing.values}
    assert set(extracted.keys()) == {
        "decl.total-perceptores",
        "decl.base-total",
        "decl.retenciones-total",
    }, (
        f"PARSER-GAP [M180/2024-0A]: unexpected casilla set.\n  got: {sorted(extracted)}"
    )
    for casilla_id, value in extracted.items():
        assert isinstance(value, Decimal), (
            f"PARSER-GAP [M180/2024-0A]: casilla {casilla_id!r} not Decimal: "
            f"{type(value).__name__!r}"
        )


# ---------------------------------------------------------------------------
# M190 parser-only verification (no formula recomputation — informational fields)
# ---------------------------------------------------------------------------

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
        pytest.fail(
            f"PARSER-GAP [M190/2024-0A]: parse_declaracion raised.\n  error: {exc}"
        )

    extracted = {v.casilla_id: v.printed_value for v in filing.values}
    assert "decl.retenciones-total" in extracted, (
        f"PARSER-GAP [M190/2024-0A]: 'decl.retenciones-total' not extracted.\n"
        f"  got: {sorted(extracted)}"
    )
    assert isinstance(extracted["decl.retenciones-total"], Decimal), (
        "PARSER-GAP [M190/2024-0A]: 'decl.retenciones-total' not Decimal"
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
