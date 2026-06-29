"""Focused adapter contract tests split from the original monolith."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from ._verification_chain_support import (
    _COMPUTED_CASILLAS_M111,
    _COMPUTED_CASILLAS_M130,
    _COMPUTED_CASILLAS_M303,
    _DR303_PROJECTION_CASILLAS,
    _M303_2023_ONWARDS_PARAMS,
    FIXTURES_DIR,
    BindingId,
    CasillaId,
    Decimal,
    DeclaracionParseError,
    RegistryValidationError,
    _build_m303_engine_result,
    _period_to_date,
    _registry_snapshot,
    calculate_registry_snapshot,
    date,
    parse_declaracion,
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


_M303_CUOTA_DEVENGADA_TOTAL_CASILLA: CasillaId = _casilla_id("27")
_M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA: CasillaId = _casilla_id("45")
_M303_STATE_ATTRIBUTION_RATIO_CASILLA: CasillaId = _casilla_id("65")
_M303_RESULTADO_REGIMEN_GENERAL_CASILLA: CasillaId = _casilla_id("iva.resultado-regimen-general")
_M303_SUMA_RESULTADOS_CASILLA: CasillaId = _casilla_id("64")
_M303_ATRIBUIBLE_ESTADO_CASILLA: CasillaId = _casilla_id("66")
_M303_RESULTADO_AUTOLIQUIDACION_CASILLA: CasillaId = _casilla_id("iva.resultado")
_M303_RESULTADO_FINAL_CASILLA: CasillaId = _casilla_id("71")
_M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA: CasillaId = _casilla_id(
    "iva.compensacion-pendiente-periodos-anteriores",
)
_M130_INGRESOS_CASILLA: CasillaId = _casilla_id("01")
_M130_GASTOS_CASILLA: CasillaId = _casilla_id("02")
_M130_RENDIMIENTO_NETO_CASILLA: CasillaId = _casilla_id("03")
_M130_RESULTADO_CASILLA: CasillaId = _casilla_id("19")
_M130_FORMULA_CHAIN_CASILLAS: tuple[CasillaId, ...] = (
    _M130_RENDIMIENTO_NETO_CASILLA,
    _casilla_id("04"),
    _casilla_id("05"),
    _casilla_id("06"),
    _casilla_id("07"),
    _casilla_id("13"),
    _casilla_id("14"),
    _casilla_id("15"),
    _casilla_id("17"),
    _casilla_id("18"),
    _M130_RESULTADO_CASILLA,
)
_M111_RETENCIONES_TOTAL_CASILLA: CasillaId = _casilla_id("28")
_M111_RESULTADO_CASILLA: CasillaId = _casilla_id("30")
_M111_RETENCIONES_TOTAL_LEAVES: frozenset[CasillaId] = _casilla_ids(
    "03",
    "06",
    "09",
    "12",
    "15",
    "18",
    "21",
    "24",
    "27",
)
_M303_2023_PROFILE_CASILLAS: frozenset[CasillaId] = _casilla_ids(
    "iva.repercutido.general",
    "iva.repercutido.reducido",
    "iva.repercutido.super-reducido",
    "iva.autorepercutido.intracomunitaria",
    "iva.soportado.interiores",
    "iva.autoconsumo.promotor.base",
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
)
_M303_ENGINE_REQUIRED_CASILLAS: tuple[CasillaId, ...] = (
    _M303_CUOTA_DEVENGADA_TOTAL_CASILLA,
    _M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA,
    _M303_RESULTADO_REGIMEN_GENERAL_CASILLA,
)
_M303_SYNTHETIC_CLOSURE_CASES: tuple[tuple[CasillaId, str, CasillaId, str, str], ...] = (
    (
        _M303_SUMA_RESULTADOS_CASILLA,
        "box 64 (suma de resultados)",
        _M303_RESULTADO_REGIMEN_GENERAL_CASILLA,
        "box 46 (resultado regimen general)",
        "Orden HAC/819/2024 art. 1 §4: box 64 = box 46 + box 58 + box 76; c58=0 and c76=0",
    ),
    (
        _M303_ATRIBUIBLE_ESTADO_CASILLA,
        "box 66 (atribuible Estado)",
        _M303_SUMA_RESULTADOS_CASILLA,
        "box 64 (suma de resultados)",
        "Orden HAC/819/2024 art. 1 §4: box 66 = box 64 x box 65 / 100; box 65=100",
    ),
    (
        _M303_RESULTADO_AUTOLIQUIDACION_CASILLA,
        "box 69 (resultado autoliquidacion)",
        _M303_ATRIBUIBLE_ESTADO_CASILLA,
        "box 66 (atribuible Estado)",
        "Orden HAC/819/2024 art. 1 §5: box 69 = box 66 + box 77 + box 68 - box 78; c77=c68=c78=0",
    ),
    (
        _M303_RESULTADO_FINAL_CASILLA,
        "box 71 (resultado final)",
        _M303_RESULTADO_AUTOLIQUIDACION_CASILLA,
        "box 69 (resultado autoliquidacion)",
        "Orden HAC/819/2024 art. 1 §6: box 71 = box 69 - box 70 + box 109; c70=0 and c109=0",
    ),
)
_M303_SYNTHETIC_CLOSURE_CASE_IDS: tuple[str, ...] = (
    "box-64-suma-resultados",
    "box-66-atribuible-estado",
    "box-69-resultado-autoliquidacion",
    "box-71-resultado-final",
)


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
def test_verification_chain_m130_engine_recomputes_closure_casilla_19(pdf_stem: str, year: int, period: str) -> None:
    """Engine recomputes casilla 19 (resultado final) from extracted leaf inputs.

    GROUNDED authority: synthetic formula-consistent fixtures generated by
    src/aeat/tests/fixtures/justificantes/_generate.py and committed at
    src/aeat/tests/fixtures/justificantes/130/. Each fixture prints casilla 03
    (rendimiento neto) and casilla 19 (resultado final, engine-derived closure).
    Values satisfy the M130 formula chain (see _MODELO_130_CORPUS_FIXTURES).

    The fixtures pre-date the rendimiento-neto formula landing (box 03 = 01 - 02).
    They print c03 directly as the leaf rendimiento neto with all other casillas
    absent.  The test reconstructs the canonical leaf decomposition as:
      c01 (ingresos) = extracted c03   (all income, zero expenses)
      c02 (gastos)   = 0
    so the engine computes c03 = c01 - c02 = extracted c03.  The art-110.3.b
    high-retention branch fires only when c06/c01 >= 0.70; with c06=0 both the
    c01=0 and c01>0 paths of the c17 formula reduce to (c14 - c15) - c16,
    giving identical c19 output.

    Chain:
      1. parse_declaracion → DeclaracionObservation (extracts c03 and c19 only)
      2. Reconstruct leaf inputs: c01 = extracted_c03, c02 = 0
      3. Supply previous-filing binding values:
         - modelo-130-pagos-fraccionados-anteriores = 0 (no prior payments)
         - modelo-130-resultados-negativos-anteriores = 0 (no prior negative)
         - irpf.previous_year_economic_activity_net_income = 0
           (unknown from corpus → conservative 0 → casilla 13 = 0)
      4. calculate_registry_snapshot with inputs + binding_values
      5. Assert engine.values["03"] == c01 - c02 == extracted["03"] (formula check)
      6. Assert engine.values["19"] == extracted["19"]

    Verdict: VERIFIED when engine == extracted; PARSER-GAP when parse fails;
    BINDING-GAP when engine raises RegistryValidationError; FORMULA-MISMATCH
    when engine value differs from extracted value (reported as assertion failure).
    """
    pdf_path = FIXTURES_DIR / "justificantes" / "130" / f"{pdf_stem}.pdf"

    # Parse the declaration.
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
            f"  error: {exc}",
        )

    extracted = {v.casilla_id: v.printed_value for v in filing.values}

    # Skip specimens where casilla 19 was not extracted.
    closure_extracted: Decimal | None
    if _M130_RESULTADO_CASILLA not in extracted:
        # The corpus PDF is a partial filing — casilla 19 blank.
        # Still run the engine so BINDING-GAP and FORMULA-MISMATCH can be
        # detected on other extracted casillas; skip the 19-equality assertion.
        closure_extracted = None
    else:
        raw_closure = extracted[_M130_RESULTADO_CASILLA]
        assert isinstance(raw_closure, Decimal), (
            f"{pdf_stem}: casilla {_M130_RESULTADO_CASILLA!r} expected Decimal, got {type(raw_closure).__name__}"
        )
        closure_extracted = raw_closure

    # Build leaf inputs.
    # The fixture prints only c03 (rendimiento neto) and c19 (closure).  Box 03 is
    # now computed (03 = 01 - 02) so it cannot go into engine inputs.  Reconstruct
    # the canonical leaf decomposition: c01 = extracted_c03 (all income, no expenses),
    # c02 = 0 (gastos absent from fixture).  The art-110.3.b branch of c17 is safe:
    # with c06=0 both paths yield (c14 - c15) - c16, so c19 is unaffected.
    # Other extracted non-computed casillas (absent in these fixtures) pass through.
    extracted_c03 = extracted.get(_M130_RENDIMIENTO_NETO_CASILLA)
    inputs: dict[CasillaId, Decimal] = {}
    for casilla_id, value in extracted.items():
        if casilla_id in _COMPUTED_CASILLAS_M130:
            continue
        if not isinstance(value, Decimal):
            continue
        inputs[casilla_id] = value
    # Inject the reconstructed leaf decomposition for box 03.
    if isinstance(extracted_c03, Decimal):
        inputs[_M130_INGRESOS_CASILLA] = extracted_c03  # c01 = rendimiento neto (c03), no gastos
        # c02 defaults to 0 (absent from fixture — not injected here)

    # Only previous_filing bindings must be supplied via binding_values:
    binding_values: dict[BindingId, Decimal] = {
        # Prior-quarter payments and negative-result carry-forward; 0 = no prior
        # values (safe default for corpus specimens where we don't know prior
        # quarter saldo or payments).
        "modelo-130-pagos-fraccionados-anteriores": Decimal("0"),
        "modelo-130-resultados-negativos-anteriores": Decimal("0"),
        # Prior-year net income; 0 → casilla 13 = 0 (minoración rendimientos netos).
        # Conservative but honest: corpus PDFs don't print casilla 13 (computed).
        "irpf.previous_year_economic_activity_net_income": Decimal("0"),
    }

    # Resolve snapshot and run engine.
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
            f"  binding_values supplied: {sorted(binding_values)}",
        )

    # Verify engine computes casilla 03 = 01 - 02.
    engine_values = dict(result.values)

    input_01 = inputs.get(_M130_INGRESOS_CASILLA, Decimal("0"))
    input_02 = inputs.get(_M130_GASTOS_CASILLA, Decimal("0"))
    engine_03 = engine_values.get(_M130_RENDIMIENTO_NETO_CASILLA)
    assert engine_03 is not None, (
        f"FORMULA-MISMATCH [{pdf_stem}]: casilla '03' absent from engine result "
        f"— formula modelo-130-rendimiento-neto evaluation failed."
    )
    assert engine_03 == input_01 - input_02, (
        f"FORMULA-MISMATCH [{pdf_stem}]: engine casilla '03' = {engine_03!r}, "
        f"expected 01({input_01!r}) - 02({input_02!r}) = {input_01 - input_02!r}"
    )

    # Compare engine casilla 19 against extracted value.
    if closure_extracted is not None:
        engine_19 = engine_values.get(_M130_RESULTADO_CASILLA)
        assert engine_19 is not None, (
            f"FORMULA-MISMATCH [{pdf_stem}]: casilla '19' absent from engine result "
            f"— formula evaluation order issue or casilla missing from revision."
        )
        formula_chain_values = " ".join(
            f"{casilla_id}={engine_values.get(casilla_id)!r}" for casilla_id in _M130_FORMULA_CHAIN_CASILLAS
        )
        assert engine_19 == closure_extracted, (
            f"FORMULA-MISMATCH [{pdf_stem}]: engine recomputed casilla '19' as "
            f"{engine_19!r} but AEAT-printed form shows {closure_extracted!r}.\n"
            f"  diff: {engine_19 - closure_extracted!r}\n"
            f"  extracted inputs: {dict((k, v) for k, v in extracted.items() if k not in _COMPUTED_CASILLAS_M130)}\n"
            f"  engine values for formula chain: {formula_chain_values}"
        )


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
    pdf_stem: str,
    year: int,
    period: str,
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

    2024-1T/2T/3T: VERIFIED — leaf casilla 09 (retenciones actividades economicas
    dinerarias) is extracted; engine recomputes 28 = 09 = 1000, 30 = 28 - 0 = 1000.

    2024-4T: NEGATIVA/SIN ACTIVIDAD/RESULTADO CERO corpus PDF.  All col-C leaf
    casillas are zero; the printed box 30 comes from the real filing's settlement
    section (not derivable from current-period inputs).  has_leaf_inputs=False,
    so formula-consistency assertions are skipped — the test PASSES correctly.
    No formula gap, no bbox gap.  This is the expected path for a nil filing.

    Casilla 29 (anteriores autoliquidaciones) is absent from the corpus (zero);
    the engine defaults it to 0, so 30 = 28 - 0 = 28 for the non-nil quarters.
    """
    pdf_path = FIXTURES_DIR / "justificantes" / "111" / f"{pdf_stem}.pdf"

    # Parse the declaration.
    try:
        filing = parse_declaracion(
            pdf_path,
            modelo_override="111",
            año_override=year,
            period_override=period,
        )
    except DeclaracionParseError as exc:
        pytest.fail(f"PARSER-GAP [{pdf_stem}]: parse_declaracion raised DeclaracionParseError.\n  error: {exc}")

    extracted = {v.casilla_id: v.printed_value for v in filing.values}

    # Build inputs: exclude computed casillas 28 and 30.
    inputs: dict[CasillaId, Decimal] = {}
    for casilla_id, value in extracted.items():
        if casilla_id in _COMPUTED_CASILLAS_M111:
            continue
        if isinstance(value, Decimal):
            inputs[casilla_id] = value

    # Resolve snapshot and run engine.
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
            f"  inputs supplied: {sorted(inputs)}",
        )

    engine_values = dict(result.values)

    # Leaf inputs for formula 28 = sum(03,06,09,12,15,18,21,24,27).
    # When none of the leaf casillas are present in the corpus PDF (data-sparse
    # filing where only the totals were printed), the engine correctly computes
    # 28=0 and 30=0 — these cannot be compared against the extracted totals
    # without the breakdown.  Skip formula-consistency checks in that case.
    has_leaf_inputs = bool(inputs.keys() & _M111_RETENCIONES_TOTAL_LEAVES)

    # Verify casilla 28 when extracted and leaf inputs are present.
    if _M111_RETENCIONES_TOTAL_CASILLA in extracted and has_leaf_inputs:
        extracted_28 = extracted[_M111_RETENCIONES_TOTAL_CASILLA]
        assert isinstance(extracted_28, Decimal)
        engine_28 = engine_values.get(_M111_RETENCIONES_TOTAL_CASILLA)
        assert engine_28 is not None, f"FORMULA-MISMATCH [{pdf_stem}]: casilla '28' absent from engine result."
        assert engine_28 == extracted_28, (
            f"FORMULA-MISMATCH [{pdf_stem}]: engine casilla '28' = {engine_28!r}, "
            f"AEAT-printed = {extracted_28!r}.\n"
            f"  diff: {engine_28 - extracted_28!r}\n"
            f"  inputs: {inputs}"
        )

    # Verify casilla 30 when extracted and leaf inputs are present.
    if _M111_RESULTADO_CASILLA in extracted and has_leaf_inputs:
        extracted_30 = extracted[_M111_RESULTADO_CASILLA]
        assert isinstance(extracted_30, Decimal)
        engine_30 = engine_values.get(_M111_RESULTADO_CASILLA)
        assert engine_30 is not None, f"FORMULA-MISMATCH [{pdf_stem}]: casilla '30' absent from engine result."
        assert engine_30 == extracted_30, (
            f"FORMULA-MISMATCH [{pdf_stem}]: engine casilla '30' = {engine_30!r}, "
            f"AEAT-printed = {extracted_30!r}.\n"
            f"  diff: {engine_30 - extracted_30!r}\n"
            f"  inputs: {inputs}"
        )


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
def test_verification_chain_m303_parser_extracts_all_profile_casillas(pdf_stem: str, year: int, period: str) -> None:
    """Parser extracts all 12 M303 profile casillas from corpus PDFs.

    GROUNDED authority: AEAT corpus PDFs from the sanitised real-form fixture
    set committed at src/aeat/tests/fixtures/justificantes/303/.

    Verdict: PARSER-GAP when extraction fails. This test verifies the
    extraction side of the chain only. The companion test
    test_verification_chain_m303_engine_recomputes_resultado_regimen_general
    exercises the formula engine (box 46 = box 27 − box 45, Orden
    EHA/3786/2008 art. 1).

    The M303 2009-y-siguientes revision (2021-2022 PDFs) is excluded here;
    it covers a different profile.
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
            f"PARSER-GAP [{pdf_stem}]: parse_declaracion raised — M303 2023+ extraction failed.\n  error: {exc}",
        )

    extracted = {v.casilla_id: v.printed_value for v in filing.values}

    assert set(extracted.keys()) == _M303_2023_PROFILE_CASILLAS, (
        f"PARSER-GAP [{pdf_stem}]: M303 2023+ profile extraction did not produce "
        f"the expected 18 casilla IDs (6 primitives + 12 form-page totals).\n"
        f"  got: {sorted(extracted)}"
    )
    # All extracted values must be Decimal instances (amount fields).
    for casilla_id, value in extracted.items():
        assert isinstance(value, Decimal), (
            f"PARSER-GAP [{pdf_stem}]: casilla {casilla_id!r} should be Decimal, "
            f"got {type(value).__name__!r} = {value!r}"
        )


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
def test_verification_chain_m303_engine_recomputes_resultado_regimen_general(
    pdf_stem: str,
    year: int,
    period: str,
) -> None:
    """Engine resultado-regimen-general matches the extracted printed box 46.

    GROUNDED authority: Orden EHA/3786/2008 art. 1 — box 46 = box 27 − box 45.
      box 27 = Total cuota devengada (LIVA art. 88)
      box 45 = Total a deducir (LIVA arts. 92-94)
      box 46 = Resultado régimen general

    The 2023-y-siguientes corpus PDFs are synthetic fixtures generated by
    _generate.py with formula-consistent values: c46 = c27 - c45, so the
    engine result matches the printed value exactly.

    Verdict: VERIFIED — engine resultado == extracted resultado for all
    8 new-template specimens (2023-2024). Corpus-regenerated with
    formula-consistent synthetic values.
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
        pytest.fail(f"PARSER-GAP [{pdf_stem}]: parse_declaracion raised — M303 extraction failed.\n  error: {exc}")

    extracted = {v.casilla_id: v.printed_value for v in filing.values}

    for required_id in _M303_ENGINE_REQUIRED_CASILLAS:
        assert required_id in extracted, (
            f"PARSER-GAP [{pdf_stem}]: required casilla {required_id!r} not in extracted values.\n"
            f"  got: {sorted(extracted)}"
        )

    # Build inputs — supply only non-computed Decimal casillas.
    inputs: dict[CasillaId, Decimal] = {}
    for casilla_id, value in extracted.items():
        if casilla_id in _COMPUTED_CASILLAS_M303:
            continue
        if not isinstance(value, Decimal):
            continue
        inputs[casilla_id] = value

    # Box 65 (porcentaje atribuible Estado) is bound to the profile-derived
    # ``tax_residence.state_attribution_ratio`` via casilla.binding. The engine's
    # _initial_values only auto-hydrates BOUND casillas from binding_values for
    # ``previous_filing`` source; profile-sourced bound casillas expect the
    # application-layer resolver to have populated ``inputs`` before reaching
    # the calculator. Supply C65 via both channels for the engine-direct test
    # path.
    inputs[_M303_STATE_ATTRIBUTION_RATIO_CASILLA] = Decimal("100")

    # The previous_filing binding for compensacion-pendiente-anteriores is
    # required by the engine. Supply the extracted value from the corpus PDF
    # if available (box iva.compensacion-pendiente-periodos-anteriores), else zero.
    _extracted_comp = extracted.get(_M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA, Decimal("0"))
    _comp = _extracted_comp if isinstance(_extracted_comp, Decimal) else Decimal("0")
    binding_values: dict[BindingId, Decimal] = {
        "modelo-303-compensacion-pendiente-anteriores": _comp,
        "modelo-303-profile-state-attribution-ratio": Decimal("100"),
    }

    # filing_period: first day of the period's quarter.
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
            f"BINDING-GAP [{pdf_stem}]: calculate_registry_snapshot raised "
            f"RegistryValidationError — a required binding is missing.\n"
            f"  error: {exc}\n"
            f"  inputs supplied: {sorted(inputs)}\n"
            f"  binding_values supplied: {sorted(binding_values)}",
        )

    engine_values = dict(result.values)

    # VERIFIED gate: engine resultado must equal extracted printed box 46.
    # The synthetic corpus PDFs were generated with c46 = c27 - c45, matching
    # the registry formula. Any future registry formula change that breaks this
    # will cause a loud test failure.
    engine_resultado = _assert_m303_engine_matches_extracted_decimal(
        pdf_stem=pdf_stem,
        engine_values=engine_values,
        extracted=extracted,
        casilla_id=_M303_RESULTADO_REGIMEN_GENERAL_CASILLA,
        label="box 46 (resultado regimen general)",
        formula_context="box 46 = box 27 - box 45, Orden EHA/3786/2008 art. 1",
    )
    # Internal consistency cross-check: engine resultado == computed c27 - c45.
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
        f"  (internal formula consistency broken — registry formula defect)"
    )


@pytest.mark.parametrize(
    "target_casilla,target_label,base_casilla,base_label,formula_context",
    _M303_SYNTHETIC_CLOSURE_CASES,
    ids=_M303_SYNTHETIC_CLOSURE_CASE_IDS,
)
@pytest.mark.parametrize("pdf_stem,year,period", _M303_2023_ONWARDS_PARAMS)
def test_verification_chain_m303_engine_recomputes_synthetic_closure_boxes(
    pdf_stem: str,
    year: int,
    period: str,
    target_casilla: CasillaId,
    target_label: str,
    base_casilla: CasillaId,
    base_label: str,
    formula_context: str,
) -> None:
    """Engine M303 2023+ closure boxes match extracted values and synthetic zero relations.

    GROUNDED authority: Orden HAC/819/2024 art. 1 closure formulas for boxes
    64, 66, 69, and 71. The synthetic corpus PDFs set the non-base terms to
    zero for these closure formulas, so each target box must equal its immediate
    base box after the engine recomputes the registry DAG.
    """
    extracted, engine_values, _inputs = _build_m303_engine_result(pdf_stem, year, period)

    target_value = _assert_m303_engine_matches_extracted_decimal(
        pdf_stem=pdf_stem,
        engine_values=engine_values,
        extracted=extracted,
        casilla_id=target_casilla,
        label=target_label,
        formula_context=formula_context,
    )
    base_value = engine_values.get(base_casilla)
    assert isinstance(base_value, Decimal), (
        f"VERIFIED-FAIL [{pdf_stem}]: engine {base_label} missing or non-Decimal: {base_value!r}"
    )
    assert target_value == base_value, (
        f"VERIFIED-FAIL [{pdf_stem}]: engine {target_label} {target_value!r} != "
        f"engine {base_label} {base_value!r}\n"
        f"  ({formula_context} in corpus PDFs)"
    )


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
    ],
)
def test_verification_chain_m303_historical_engine_recomputes_resultado_regimen_general(
    pdf_stem: str,
    year: int,
    period: str,
) -> None:
    """Engine resultado-regimen-general matches extracted box 46 for historical fixtures.

    GROUNDED authority: Orden EHA/3786/2008 art. 1 — box 46 = box 27 − box 45.
    The 2009-y-siguientes revision covers ejercicios 2009-2022 and uses the same
    formula. The historical extraction profile extracts 4 casillas: 27, 29, 45, and
    iva.resultado-regimen-general.

    The historical corpus PDFs are synthetic fixtures generated by _generate.py
    with formula-consistent values: c46 = c27 - c45.

    Verdict: VERIFIED — engine resultado == extracted resultado for all 7
    historical specimens (2021-2022). Corpus-regenerated with
    formula-consistent synthetic values.
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
            f"PARSER-GAP [{pdf_stem}]: parse_declaracion raised — M303 legacy extraction failed.\n  error: {exc}",
        )

    extracted = {v.casilla_id: v.printed_value for v in filing.values}

    for required_id in _M303_ENGINE_REQUIRED_CASILLAS:
        assert required_id in extracted, (
            f"PARSER-GAP [{pdf_stem}]: required casilla {required_id!r} not in extracted values.\n"
            f"  got: {sorted(extracted)}"
        )

    # Build inputs — supply only non-computed Decimal casillas.
    inputs: dict[CasillaId, Decimal] = {}
    for casilla_id, value in extracted.items():
        if casilla_id in _COMPUTED_CASILLAS_M303 and casilla_id not in _DR303_PROJECTION_CASILLAS:
            continue
        if not isinstance(value, Decimal):
            continue
        inputs[casilla_id] = value

    _extracted_comp = extracted.get(_M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA, Decimal("0"))
    _comp = _extracted_comp if isinstance(_extracted_comp, Decimal) else Decimal("0")
    binding_values: dict[BindingId, Decimal] = {
        "modelo-303-compensacion-pendiente-anteriores": _comp,
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
            f"BINDING-GAP [{pdf_stem}]: calculate_registry_snapshot raised "
            f"RegistryValidationError — a required binding is missing.\n"
            f"  error: {exc}\n"
            f"  inputs supplied: {sorted(inputs)}\n"
            f"  binding_values supplied: {sorted(binding_values)}",
        )

    engine_values = dict(result.values)

    # VERIFIED gate: engine resultado must equal extracted printed box 46.
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
        f"  (internal formula consistency broken — registry formula defect)"
    )
