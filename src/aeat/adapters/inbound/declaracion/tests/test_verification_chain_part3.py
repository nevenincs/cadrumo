"""Focused adapter contract tests split from the original monolith."""

from __future__ import annotations

import pytest

from ._verification_chain_support import (
    FIXTURES_DIR,
    CasillaId,
    Decimal,
    DeclaracionParseError,
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


_M349_SUMMARY_CASILLAS: frozenset[CasillaId] = _casilla_ids(
    "decl.numero-operadores",
    "decl.importe-operaciones",
    "decl.numero-rectificaciones",
    "decl.importe-rectificaciones",
)
_DECL_EJERCICIO_CASILLA: CasillaId = _casilla_id("decl.ejercicio")
_DECL_PERIODO_CASILLA: CasillaId = _casilla_id("decl.periodo")
_DECL_EVENT_KIND_CASILLA: CasillaId = _casilla_id("decl.event-kind")


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
    assert set(extracted.keys()) == _M349_SUMMARY_CASILLAS, (
        f"PARSER-GAP [M349/2024-1T]: unexpected casilla set.\n  got: {sorted(extracted)}"
    )
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
    assert _DECL_EJERCICIO_CASILLA in extracted, (
        f"PARSER-GAP [M184/2024-0A]: {_DECL_EJERCICIO_CASILLA!r} not extracted.\n  got: {sorted(extracted)}"
    )
    assert isinstance(extracted[_DECL_EJERCICIO_CASILLA], Decimal), (
        f"PARSER-GAP [M184/2024-0A]: {_DECL_EJERCICIO_CASILLA!r} not Decimal: "
        f"{type(extracted[_DECL_EJERCICIO_CASILLA]).__name__!r}"
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
    assert _DECL_EJERCICIO_CASILLA in extracted, (
        f"PARSER-GAP [M347/2024-0A]: {_DECL_EJERCICIO_CASILLA!r} not extracted.\n  got: {sorted(extracted)}"
    )
    assert isinstance(extracted[_DECL_EJERCICIO_CASILLA], Decimal), (
        f"PARSER-GAP [M347/2024-0A]: {_DECL_EJERCICIO_CASILLA!r} not Decimal: "
        f"{type(extracted[_DECL_EJERCICIO_CASILLA]).__name__!r}"
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
    assert _DECL_EJERCICIO_CASILLA in extracted, (
        f"PARSER-GAP [M720/2024-0A]: {_DECL_EJERCICIO_CASILLA!r} not extracted.\n  got: {sorted(extracted)}"
    )
    assert isinstance(extracted[_DECL_EJERCICIO_CASILLA], Decimal), (
        f"PARSER-GAP [M720/2024-0A]: {_DECL_EJERCICIO_CASILLA!r} not Decimal: "
        f"{type(extracted[_DECL_EJERCICIO_CASILLA]).__name__!r}"
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
    assert _DECL_EJERCICIO_CASILLA in extracted, (
        f"PARSER-GAP [M840/2024-0A]: {_DECL_EJERCICIO_CASILLA!r} not extracted.\n  got: {sorted(extracted)}"
    )
    assert isinstance(extracted[_DECL_EJERCICIO_CASILLA], Decimal), (
        f"PARSER-GAP [M840/2024-0A]: {_DECL_EJERCICIO_CASILLA!r} not Decimal: "
        f"{type(extracted[_DECL_EJERCICIO_CASILLA]).__name__!r}"
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
    assert _DECL_EJERCICIO_CASILLA in extracted, (
        f"PARSER-GAP [M369/2024-1T]: {_DECL_EJERCICIO_CASILLA!r} not extracted.\n  got: {sorted(extracted)}"
    )
    assert isinstance(extracted[_DECL_EJERCICIO_CASILLA], Decimal), (
        f"PARSER-GAP [M369/2024-1T]: {_DECL_EJERCICIO_CASILLA!r} not Decimal: "
        f"{type(extracted[_DECL_EJERCICIO_CASILLA]).__name__!r}"
    )
    assert _DECL_PERIODO_CASILLA in extracted, (
        f"PARSER-GAP [M369/2024-1T]: {_DECL_PERIODO_CASILLA!r} not extracted.\n  got: {sorted(extracted)}"
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
    assert _DECL_EVENT_KIND_CASILLA in extracted, (
        f"PARSER-GAP [M036/2025-alta]: {_DECL_EVENT_KIND_CASILLA!r} not extracted.\n  got: {sorted(extracted)}"
    )
    event_kind = extracted[_DECL_EVENT_KIND_CASILLA]
    assert isinstance(event_kind, str), (
        f"PARSER-GAP [M036/2025-alta]: {_DECL_EVENT_KIND_CASILLA!r} not str: {type(event_kind).__name__!r}"
    )
    assert event_kind == "Alta", f"PARSER-GAP [M036/2025-alta]: expected 'Alta', got {event_kind!r}"
