"""Focused adapter contract tests split from the original monolith."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from ._verification_chain_support import (
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
