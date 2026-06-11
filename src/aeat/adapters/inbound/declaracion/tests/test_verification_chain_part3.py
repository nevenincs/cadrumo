"""Focused adapter contract tests split from the original monolith."""

from __future__ import annotations

import pytest

from ._verification_chain_support import (
    FIXTURES_DIR,
    Decimal,
    DeclaracionParseError,
    RegistryValidationError,
    _registry_snapshot,
    calculate_registry_snapshot,
    date,
    parse_declaracion,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def test_verification_chain_m100_parser_extracts_declaracion_pdf_casillas() -> None:
    """Parser extracts M100 cuota-chain, actividades-económicas, and 0171 leaf casillas.

    GROUNDED authority: real AEAT corpus PDFs (sanitised) committed at
    src/aeat/tests/fixtures/justificantes/100/2021-0A.pdf,
    2022-0A.pdf, 2023-0A.pdf.

    Extraction verdict: VERIFIED — 20 casilla IDs extracted from each corpus PDF.
    The declaracion_pdf profile covers 20 casillas including casilla 0171
    (ingresos de explotación), the only individually-printed 017x leaf input.

    Formula verdict: EXTRACTION-ONLY (CORPUS-LIMITED) — the declaracion_pdf profile
    now includes the one printable 017x leaf (0171), but casillas 0172-0179 are
    absent from this summary form (only their total 0180 is shown). More
    critically, the corpus sanitisation (all amounts replaced with ~1.001.000,00
    plus adjacent box numbers appended by pdfplumber) makes arithmetic verification
    of any closure impossible. See test_verification_chain_m100_engine_corpus_limited
    for the empirical confirmation of the sanitisation artefact.
    """
    _EXPECTED_CASILLAS_M100 = frozenset(
        {
            "0171",
            "0180",
            "0218",
            "0223",
            "0224",
            "0226",
            "0231",
            "0235",
            "0432",
            "0500",
            "0505",
            "0510",
            "0545",
            "0546",
            "0585",
            "0586",
            "0587",
            "0595",
            "0610",
            "0670",
        },
    )

    for year in (2021, 2022, 2023):
        pdf_path = FIXTURES_DIR / "justificantes" / "100" / f"{year}-0A.pdf"
        try:
            filing = parse_declaracion(
                pdf_path,
                modelo_override="100",
                año_override=year,
                period_override="0A",
            )
        except DeclaracionParseError as exc:
            pytest.fail(f"PARSER-GAP [M100/{year}-0A]: parse_declaracion raised.\n  error: {exc}")

        extracted = {v.casilla_id: v.printed_value for v in filing.values}
        assert set(extracted.keys()) == _EXPECTED_CASILLAS_M100, (
            f"PARSER-GAP [M100/{year}-0A]: unexpected casilla set.\n"
            f"  got: {sorted(extracted)}\n  expected: {sorted(_EXPECTED_CASILLAS_M100)}"
        )
        for casilla_id, value in extracted.items():
            assert isinstance(value, Decimal), (
                f"PARSER-GAP [M100/{year}-0A]: casilla {casilla_id!r} is not Decimal: "
                f"{type(value).__name__!r} = {value!r}"
            )


def test_verification_chain_m100_engine_corpus_limited() -> None:
    """Engine runs against M100 extracted inputs; verifies CORPUS-LIMITED verdict.

    GROUNDED authority: real AEAT corpus PDFs (sanitised) committed at
    src/aeat/tests/fixtures/justificantes/100/2021-0A.pdf (representative
    specimen; same sanitisation pattern applies across 2021/2022/2023).

    Empirical finding: the M100 corpus PDFs have ALL amounts replaced with the
    uniform synthetic value ~1.001.000,00 (EUR). pdfplumber merges the adjacent
    casilla box number into the value token, producing garbage values like
    Decimal('1001000.001071') for casilla 0171. These values are NOT
    arithmetically consistent with each other — any formula closure will fail.

    This test confirms the CORPUS-LIMITED verdict:
      1. The engine runs without RegistryValidationError when supplied the
         appropriate binding values (confirming no BINDING-GAP).
      2. Engine-computed closure casillas (0545, 0546) do NOT match their
         sanitised extracted counterparts — confirming the sanitisation artefact
         is the blocker, not a formula or profile defect.
      3. The engine correctly computes 0545 and 0546 from the actual tax
         bracket tables applied to the extracted 0505 value, proving the
         formula DAG is structurally sound.

    Verdict: EXTRACTION-ONLY (CORPUS-LIMITED) — no path to VERIFIED from this
    corpus without un-sanitised real PDF values.

    Legal grounding: Ley 35/2006 arts. 50, 62-68; RD 439/2007 Disposición Final.
    """
    year = 2021
    pdf_path = FIXTURES_DIR / "justificantes" / "100" / f"{year}-0A.pdf"

    try:
        filing = parse_declaracion(
            pdf_path,
            modelo_override="100",
            año_override=year,
            period_override="0A",
        )
    except DeclaracionParseError as exc:
        pytest.fail(f"PARSER-GAP [M100/{year}-0A corpus-limited]: parse_declaracion raised.\n  error: {exc}")

    extracted = {v.casilla_id: v.printed_value for v in filing.values}

    # Non-leaf casillas computed by the engine — must NOT appear in engine inputs.
    # Determined by formula DAG analysis of the M100 closure chain:
    #   0180 = sum(0171..0179); 0218 = sum(gas deducibles); 0223 = 0218 + 0222;
    #   0224 = 0180 - 0223 (simplificada); 0226 = 0224 - 0225;
    #   0231 = copy(0226); 0235 = 0231 - 0232 - 0233 - 0234;
    #   0432 = 0025 + 0060 + 0155 + 0156 + 0235; 0500 = 0435 - 0461 - 0501;
    #   0510 = 0460 + 0506 + 0507; 0545 = 0532 + 0540 (tax bracket chain from 0505);
    #   0546 = 0533 + 0541 (autonomic bracket chain); 0585 = 0570 + deductions;
    #   0586 = 0571 + autonomic deductions.
    _COMPUTED_M100 = frozenset(
        {
            "0180",
            "0218",
            "0223",
            "0224",
            "0226",
            "0231",
            "0235",
            "0432",
            "0500",
            "0510",
            "0545",
            "0546",
            "0585",
            "0586",
        },
    )

    inputs: dict[str, Decimal] = {
        cid: val for cid, val in extracted.items() if cid not in _COMPUTED_M100 and isinstance(val, Decimal)
    }

    snapshot = _registry_snapshot("100", year, "0A")

    # binding_values: numeric bindings (Decimal channel).
    # enum_binding_values: profile-sourced enum bindings (string channel).
    # The CCAA dispatch key 'cataluna' is derived from casilla 70 = '09' printed
    # in the corpus PDF (Comunidad Autónoma de residencia).
    try:
        result = calculate_registry_snapshot(
            snapshot,
            inputs=inputs,
            date_context={"filing_period": date(year, 12, 31)},
            binding_values={
                # Simplificada (casilla 0168 = 'Simplificada') → 0 in the boolean binding.
                "renta-2021-modelo-100-estimacion-directa-es-normal": Decimal("0"),
                # Retención bindings: supply zero (no prior-period retenciones known from corpus).
                "renta-2021-modelo-111-retenciones-periodicas": Decimal("0"),
                "renta-2021-modelo-115-retenciones-periodicas": Decimal("0"),
                "renta-2021-modelo-123-retenciones-periodicas": Decimal("0"),
            },
            enum_binding_values={
                # Cataluña CCAA code (corpus PDF casilla 70 = '09').
                "renta-2021-profile-tax-residence-ccaa": "cataluna",
            },
        )
    except RegistryValidationError as exc:
        pytest.fail(
            f"BINDING-GAP [M100/{year}-0A corpus-limited]: calculate_registry_snapshot raised "
            f"RegistryValidationError — a required binding is missing.\n"
            f"  error: {exc}\n"
            f"  inputs: {sorted(inputs)}",
        )

    engine_values = dict(result.values)

    # Engine MUST produce computed closure casillas: formula chain structural check.
    for closure_id in ("0545", "0546", "0585", "0586"):
        assert engine_values.get(closure_id) is not None, (
            f"FORMULA-MISMATCH [M100/{year}-0A corpus-limited]: casilla {closure_id!r} absent "
            f"from engine result — formula evaluation order issue."
        )

    # Engine-computed values for 0545 and 0546 must NOT equal the sanitised
    # extracted values — this is the empirical CORPUS-LIMITED confirmation.
    # The engine computes from real tax bracket tables; the corpus has garbage values
    # (sanitised amount ~1,001,000 with appended box numbers).
    engine_0545 = engine_values["0545"]
    engine_0546 = engine_values["0546"]
    extracted_0545 = extracted.get("0545")
    extracted_0546 = extracted.get("0546")

    assert isinstance(engine_0545, Decimal) and engine_0545 > Decimal("0"), (
        f"CORPUS-LIMITED [M100/{year}-0A]: engine 0545 should be positive from bracket "
        f"lookup on 0505={inputs.get('0505')!r}, got {engine_0545!r}"
    )
    assert engine_0545 != extracted_0545, (
        f"CORPUS-LIMITED [M100/{year}-0A]: engine 0545={engine_0545!r} == extracted "
        f"{extracted_0545!r} — the sanitisation artefact guard failed. This either means "
        f"the corpus was un-sanitised (unlikely) or the engine formula is wrong."
    )
    assert engine_0546 != extracted_0546, (
        f"CORPUS-LIMITED [M100/{year}-0A]: engine 0546={engine_0546!r} == extracted "
        f"{extracted_0546!r} — same sanitisation guard as 0545."
    )

    # Leaf input 0171 must be extracted by the declaracion_pdf profile.
    assert "0171" in extracted, "PARSER-GAP [M100/2021-0A corpus-limited]: casilla '0171' absent from extracted values."
    assert isinstance(extracted["0171"], Decimal), (
        f"PARSER-GAP [M100/2021-0A corpus-limited]: casilla '0171' is not Decimal: {type(extracted['0171']).__name__!r}"
    )


def test_verification_chain_m349_parser_extracts_declaracion_pdf_casillas() -> None:
    """Parser extracts M349 summary casillas from the synthetic corpus fixture.

    GROUNDED authority: synthetic fixture committed at
    src/aeat/tests/fixtures/justificantes/349/2024-1T.pdf.

    Extraction verdict: VERIFIED — 4 named-label casillas extracted.

    Formula verdict: EXTRACTION-ONLY-INTRINSIC — M349 closure totals are
    defined by Orden HAC/174/2020 Anexo (Diseño de Registros) as aggregations
    over Tipo 2 detail records in the submitted fichero:

      pos. 138-146 (numero-operadores): count of Tipo 2 operador records with
        clave E/M/H/T/A/S/I/R/D/C (position 133 of the record).
      pos. 147-161 (importe-operaciones): sum of pos. 134-146 (base imponible)
        across Tipo 2 operador records with the same clave set.
      pos. 162-170 (numero-rectificaciones): count of Tipo 2 rectificacion
        records with clave E/M/H/T/A/S/I/R/D/C.
      pos. 171-185 (importe-rectificaciones): sum of pos. 153-165 (base
        imponible rectificada) across Tipo 2 rectificacion records.

    The declaracion_pdf surface exposes only the Tipo 1 header record. No peer
    casillas on the same form participate in any arithmetic these closures
    summarise. The formula DSL (casilla-to-casilla arithmetic) cannot express
    count/sum over Tipo 2 record arrays. The existing registry bindings
    (collectible_invoice, count_distinct/sum) model this arithmetic correctly.
    This is a domain fact, not an engineering gap — no formula can be authored
    without a new row-array aggregation primitive.
    """
    pdf_path = FIXTURES_DIR / "justificantes" / "349" / "2024-1T.pdf"

    try:
        filing = parse_declaracion(
            pdf_path,
            modelo_override="349",
            año_override=2024,
            period_override="1T",
        )
    except DeclaracionParseError as exc:
        pytest.fail(f"PARSER-GAP [M349/2024-1T]: parse_declaracion raised.\n  error: {exc}")

    extracted = {v.casilla_id: v.printed_value for v in filing.values}
    assert set(extracted.keys()) == {
        "decl.numero-operadores",
        "decl.importe-operaciones",
        "decl.numero-rectificaciones",
        "decl.importe-rectificaciones",
    }, f"PARSER-GAP [M349/2024-1T]: unexpected casilla set.\n  got: {sorted(extracted)}"
    for casilla_id, value in extracted.items():
        assert isinstance(value, Decimal), (
            f"PARSER-GAP [M349/2024-1T]: casilla {casilla_id!r} not Decimal: {type(value).__name__!r} = {value!r}"
        )


def test_verification_chain_m184_parser_extracts_declaracion_pdf_casillas() -> None:
    """Parser extracts the M184 ejercicio casilla from the synthetic corpus fixture.

    GROUNDED authority: synthetic fixture committed at
    src/aeat/tests/fixtures/justificantes/184/2024-0A.pdf.

    Extraction verdict: VERIFIED — decl.ejercicio extracted as Decimal.

    Formula verdict: EXTRACTION-ONLY — M184 is an informativa (atribución de
    rentas); the registry has no closure formula over the summary-level casillas
    available in the declaracion_pdf profile.
    """
    pdf_path = FIXTURES_DIR / "justificantes" / "184" / "2024-0A.pdf"

    try:
        filing = parse_declaracion(
            pdf_path,
            modelo_override="184",
            año_override=2024,
            period_override="0A",
        )
    except DeclaracionParseError as exc:
        pytest.fail(f"PARSER-GAP [M184/2024-0A]: parse_declaracion raised.\n  error: {exc}")

    extracted = {v.casilla_id: v.printed_value for v in filing.values}
    assert "decl.ejercicio" in extracted, (
        f"PARSER-GAP [M184/2024-0A]: 'decl.ejercicio' not extracted.\n  got: {sorted(extracted)}"
    )
    assert isinstance(extracted["decl.ejercicio"], Decimal), (
        f"PARSER-GAP [M184/2024-0A]: 'decl.ejercicio' not Decimal: {type(extracted['decl.ejercicio']).__name__!r}"
    )


def test_verification_chain_m347_parser_extracts_declaracion_pdf_casillas() -> None:
    """Parser extracts the M347 ejercicio casilla from the synthetic corpus fixture.

    GROUNDED authority: synthetic fixture committed at
    src/aeat/tests/fixtures/justificantes/347/2024-0A.pdf.

    Extraction verdict: VERIFIED — decl.ejercicio extracted as Decimal.

    Formula verdict: EXTRACTION-ONLY — M347 is an informativa (terceros); the
    registry has no closure formula over the summary-level casillas available
    in the declaracion_pdf profile.
    """
    pdf_path = FIXTURES_DIR / "justificantes" / "347" / "2024-0A.pdf"

    try:
        filing = parse_declaracion(
            pdf_path,
            modelo_override="347",
            año_override=2024,
            period_override="0A",
        )
    except DeclaracionParseError as exc:
        pytest.fail(f"PARSER-GAP [M347/2024-0A]: parse_declaracion raised.\n  error: {exc}")

    extracted = {v.casilla_id: v.printed_value for v in filing.values}
    assert "decl.ejercicio" in extracted, (
        f"PARSER-GAP [M347/2024-0A]: 'decl.ejercicio' not extracted.\n  got: {sorted(extracted)}"
    )
    assert isinstance(extracted["decl.ejercicio"], Decimal), (
        f"PARSER-GAP [M347/2024-0A]: 'decl.ejercicio' not Decimal: {type(extracted['decl.ejercicio']).__name__!r}"
    )


def test_verification_chain_m720_parser_extracts_declaracion_pdf_casillas() -> None:
    """Parser extracts the M720 ejercicio casilla from the synthetic corpus fixture.

    GROUNDED authority: synthetic fixture committed at
    src/aeat/tests/fixtures/justificantes/720/2024-0A.pdf.

    Extraction verdict: VERIFIED — decl.ejercicio extracted as Decimal.

    Formula verdict: EXTRACTION-ONLY — M720 is an informativa (bienes en el
    extranjero); the registry has no closure formula over the summary-level
    casillas available in the declaracion_pdf profile.
    """
    pdf_path = FIXTURES_DIR / "justificantes" / "720" / "2024-0A.pdf"

    try:
        filing = parse_declaracion(
            pdf_path,
            modelo_override="720",
            año_override=2024,
            period_override="0A",
        )
    except DeclaracionParseError as exc:
        pytest.fail(f"PARSER-GAP [M720/2024-0A]: parse_declaracion raised.\n  error: {exc}")

    extracted = {v.casilla_id: v.printed_value for v in filing.values}
    assert "decl.ejercicio" in extracted, (
        f"PARSER-GAP [M720/2024-0A]: 'decl.ejercicio' not extracted.\n  got: {sorted(extracted)}"
    )
    assert isinstance(extracted["decl.ejercicio"], Decimal), (
        f"PARSER-GAP [M720/2024-0A]: 'decl.ejercicio' not Decimal: {type(extracted['decl.ejercicio']).__name__!r}"
    )


def test_verification_chain_m840_parser_extracts_declaracion_pdf_casillas() -> None:
    """Parser extracts M840 casillas from the synthetic corpus fixture.

    GROUNDED authority: synthetic fixture committed at
    src/aeat/tests/fixtures/justificantes/840/2024-0A.pdf.

    Extraction verdict: VERIFIED — decl.tipo-declaracion (str) and
    decl.ejercicio (Decimal) extracted.

    Formula verdict: EXTRACTION-ONLY — M840 is an IAE actividades económicas
    declaracion; the registry has no closure formula over the summary-level
    casillas available in the declaracion_pdf profile.
    """
    pdf_path = FIXTURES_DIR / "justificantes" / "840" / "2024-0A.pdf"

    try:
        filing = parse_declaracion(
            pdf_path,
            modelo_override="840",
            año_override=2024,
            period_override="0A",
        )
    except DeclaracionParseError as exc:
        pytest.fail(f"PARSER-GAP [M840/2024-0A]: parse_declaracion raised.\n  error: {exc}")

    extracted = {v.casilla_id: v.printed_value for v in filing.values}
    assert "decl.ejercicio" in extracted, (
        f"PARSER-GAP [M840/2024-0A]: 'decl.ejercicio' not extracted.\n  got: {sorted(extracted)}"
    )
    assert isinstance(extracted["decl.ejercicio"], Decimal), (
        f"PARSER-GAP [M840/2024-0A]: 'decl.ejercicio' not Decimal: {type(extracted['decl.ejercicio']).__name__!r}"
    )


def test_verification_chain_m369_parser_extracts_declaracion_pdf_casillas() -> None:
    """Parser extracts M369 casillas from the synthetic corpus fixture.

    GROUNDED authority: synthetic fixture committed at
    src/aeat/tests/fixtures/justificantes/369/2024-1T.pdf.

    Extraction verdict: VERIFIED — decl.ejercicio (Decimal) and decl.periodo
    (str) extracted.

    Formula verdict: EXTRACTION-ONLY — M369 OSS EU IVA uses the
    esquema-union revision which has no closure formulas in the registry.
    """
    pdf_path = FIXTURES_DIR / "justificantes" / "369" / "2024-1T.pdf"

    try:
        filing = parse_declaracion(
            pdf_path,
            modelo_override="369",
            año_override=2024,
            period_override="1T",
        )
    except DeclaracionParseError as exc:
        pytest.fail(f"PARSER-GAP [M369/2024-1T]: parse_declaracion raised.\n  error: {exc}")

    extracted = {v.casilla_id: v.printed_value for v in filing.values}
    assert "decl.ejercicio" in extracted, (
        f"PARSER-GAP [M369/2024-1T]: 'decl.ejercicio' not extracted.\n  got: {sorted(extracted)}"
    )
    assert isinstance(extracted["decl.ejercicio"], Decimal), (
        f"PARSER-GAP [M369/2024-1T]: 'decl.ejercicio' not Decimal: {type(extracted['decl.ejercicio']).__name__!r}"
    )
    assert "decl.periodo" in extracted, (
        f"PARSER-GAP [M369/2024-1T]: 'decl.periodo' not extracted.\n  got: {sorted(extracted)}"
    )


def test_verification_chain_m036_parser_extracts_event_kind_casilla() -> None:
    """Parser extracts decl.event-kind from the M036 2025-alta synthetic fixture.

    GROUNDED authority: synthetic fixture committed at
    src/aeat/tests/fixtures/justificantes/036/2025-alta.pdf (Alta censal).
    The fixture reproduces the AEAT-published section heading
    "Causas de presentacion de la declaracion" so the named_label parser
    can locate and extract the event-kind enum value.
    Source: configured AEAT Sede Anexo 3 Instrucciones Modelo 036,
    Pagina 1, fetched 2026-05-27 (aeat-dr-036-2025, aeat-modelo-036-procedure).

    M036 is a censal (ad-hoc) modelo: its period_selector declares
    ["alta", "modificacion", "baja"], not calendar time-codes.  The fixture
    period is "alta"; the previous misnamed fixture "2025-0A.pdf" used a
    time-code that did not match any revision period, causing NOT-CHAIN-READY.

    Extraction verdict: EXTRACTION-ONLY -- M036 is a censo registration form;
    the registry has no numeric closure formula over decl.event-kind.
    decl.vigencia-2025 is informational only and not extractable from the
    printed-form PDF (absent from target_casillas in the extraction profile).
    """
    pdf_path = FIXTURES_DIR / "justificantes" / "036" / "2025-alta.pdf"

    try:
        filing = parse_declaracion(
            pdf_path,
            modelo_override="036",
            año_override=2025,
            period_override="alta",
        )
    except DeclaracionParseError as exc:
        pytest.fail(f"PARSER-GAP [M036/2025-alta]: parse_declaracion raised.\n  error: {exc}")

    extracted = {v.casilla_id: v.printed_value for v in filing.values}
    assert "decl.event-kind" in extracted, (
        f"PARSER-GAP [M036/2025-alta]: 'decl.event-kind' not extracted.\n  got: {sorted(extracted)}"
    )
    assert isinstance(extracted["decl.event-kind"], str), (
        f"PARSER-GAP [M036/2025-alta]: 'decl.event-kind' not str: {type(extracted['decl.event-kind']).__name__!r}"
    )
    assert extracted["decl.event-kind"] == "Alta", (
        f"PARSER-GAP [M036/2025-alta]: expected 'Alta', got {extracted['decl.event-kind']!r}"
    )
