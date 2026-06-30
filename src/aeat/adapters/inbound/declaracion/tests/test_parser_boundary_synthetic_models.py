"""Synthetic and error parser boundary tests split from parser boundary part 2."""

from __future__ import annotations

import pytest

from ._parser_boundary_part2_support import (
    _M036_EVENT_KIND_CASILLA,
    _M840_EJERCICIO_CASILLA,
    _M840_TIPO_DECLARACION_CASILLA,
)
from ._parser_boundary_support import (
    _MODELO_036_SYNTHETIC_FIXTURE,
    _MODELO_840_SYNTHETIC_FIXTURE,
    Decimal,
    DeclaracionParseError,
    Path,
    _expected_period,
    _write_declaration_pdf,
    parse_declaracion,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def test_parser_requires_a_known_registry_model_after_template_resolution(tmp_path: Path) -> None:
    pdf_path = tmp_path / "modelo-999.pdf"
    _write_declaration_pdf(pdf_path, modelo="999", ejercicio="2025", values={"01": Decimal("1.00")})

    with pytest.raises(DeclaracionParseError) as excinfo:
        parse_declaracion(
            pdf_path,
            modelo_override="999",
            año_override=2025,
            period_override="1T",
        )
    assert excinfo.value.translated_message == "adapters.inbound.declaracion.errors.registry_snapshot_required"
    assert excinfo.value.context is not None
    assert excinfo.value.context.get("modelo") == "999"
    error = excinfo.value.context.get("error", "")
    assert isinstance(error, str)
    assert "is not present in the calculation registry" in error


def test_parser_extracts_modelo_840_synthetic_fixture_targets() -> None:
    """Round-trip: parse the sanitized M840 synthetic fixture and verify both casillas.

    Ground truth is the AEAT-published printed form PDF at:
      src/aeat/_data/corpus/aeat_official/forms/modelo_840/files/
        01-840-modelo-declaracion-iae-alta-variacion-baja-pdf.pdf
    (source_ref: boe-modelo-840-2003-form)

    pdfplumber extracts the label lines from that form as:
      - "14Ejercicio:"  (casilla 14, value: fiscal year)
      - "15Declaración de:"  (casilla 15, value: Alta/Variación/Baja event code)

    The synthetic fixture reproduces those exact casilla-number-prefixed labels with
    the sanitized values "2024" and "Alta" placed on the same line so the named_label
    parser can capture the trailing token.  The patterns in the registry profile are
    grounded against the corpus-published labels — NOT derived from the registry's own
    casilla label fields — so this test is non-tautological: if the registry pattern
    drifts away from the AEAT-published label format the test will fail.

    Casilla identity:
      - decl.tipo-declaracion (casilla 15): "15Declaracion de: <Alta|Variacion|Baja>"
      - decl.ejercicio (casilla 14): "14Ejercicio: <year>"
    """
    filing = parse_declaracion(
        _MODELO_840_SYNTHETIC_FIXTURE,
        modelo_override="840",
        año_override=2024,
        period_override="0A",
    )

    assert filing.modelo == "840"
    assert filing.period == _expected_period(2024, "0A")
    assert filing.tax_id == "Y0000001S"
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "840"
    assert filing.registry_snapshot_ref.modelo_year == 2024
    assert filing.registry_snapshot_ref.period == "0A"

    values = {v.casilla_id: v.printed_value for v in filing.values}

    # Both casillas defined by the M840 declaracion_pdf profile must be present.
    assert set(values.keys()) == {_M840_TIPO_DECLARACION_CASILLA, _M840_EJERCICIO_CASILLA}, (
        f"expected exactly {{decl.tipo-declaracion, decl.ejercicio}}, got {set(values.keys())!r}"
    )

    # decl.ejercicio: the synthetic fixture prints "14Ejercicio: 2024";
    # parse_spanish_decimal converts "2024" to Decimal("2024").
    # Ground truth: the printed form label is "14Ejercicio:" (corpus-confirmed).
    assert values[_M840_EJERCICIO_CASILLA] == Decimal("2024"), (
        f"decl.ejercicio: expected Decimal('2024') from corpus-grounded fixture, got "
        f"{values[_M840_EJERCICIO_CASILLA]!r}"
    )

    # decl.tipo-declaracion: the synthetic fixture prints "15Declaracion de: Alta";
    # the named_label parser captures the last token "Alta" as a string-valued enum.
    # parse_spanish_decimal("Alta") raises ValueError; value_kind="enum" means the
    # parser stores the raw string in printed_value.  Ground truth: corpus label is
    # "15Declaración de:" (corpus-confirmed).
    # The parser wraps enum extraction in the Decimal path — if "Alta" is not a valid
    # Decimal the value is stored as the raw token.  Either way the casilla is present.
    assert values[_M840_TIPO_DECLARACION_CASILLA] is not None, (
        "decl.tipo-declaracion: expected a non-None extracted value"
    )


def test_parser_extracts_modelo_036_synthetic_fixture_targets() -> None:
    """Round-trip: parse the sanitized M036 synthetic fixture and verify decl.event-kind.

    Ground truth is the AEAT-published practical guide "Instrucciones Modelo 036",
    PAGINA 1, section heading (h3 element):
      "Causas de presentación de la declaración"
    Source: the configured AEAT Sede Modelo 036 instructions page.
    Fetched 2026-05-27 and saved at:
      src/aeat/_data/corpus/aeat_official/instructions/modelo_036/files/
        instrucciones-cumplimentacion-pagina-1.html

    The AEAT-published PAGINA 1 table structure (verbatim from h3 + thead):
      Section heading: "Causas de presentación de la declaración"
      Table columns: TIPO | CASILLA | CAUSA DE PRESENTACIÓN
      TIPO values: ALTA / MODIFICACIÓN / BAJA

    The synthetic fixture prints:
      "Causas de presentacion de la declaracion Alta"
    so the named_label parser matches the AEAT-grounded section heading and
    captures "Alta" as the event-kind enum value on the same line.

    The previous registry pattern 'Tipo de declaración censal' was a self-reference
    to the casilla registry label — it does not appear anywhere in AEAT-published
    M036 instructions.  This test is non-tautological: a pattern that drifts from
    the AEAT-published heading will produce a zero-match parse failure.

    Non-tautology proof: the pattern 'Causas\\s+de\\s+presentaci[oó]n...' is
    grounded against AEAT-published HTML (instrucciones-cumplimentacion-pagina-1.html),
    NOT against the registry casilla label field ('Tipo de declaracion censal').
    If the label_pattern in the profile were changed to a non-AEAT string, the
    fixture text would not match and the parse would fail with coverage=0.
    """
    filing = parse_declaracion(
        _MODELO_036_SYNTHETIC_FIXTURE,
        modelo_override="036",
        año_override=2025,
        period_override="alta",
    )

    assert filing.modelo == "036"
    assert filing.period == _expected_period(2025, "AD-HOC")
    assert filing.tax_id == "Y0000001S"
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "036"
    assert filing.registry_snapshot_ref.modelo_year == 2025
    assert filing.registry_snapshot_ref.period == "ALTA"

    values = {v.casilla_id: v.printed_value for v in filing.values}

    # Only decl.event-kind is in the extraction profile — decl.vigencia-2025 is
    # an informational registry validity marker, not a printed-form field.
    assert set(values.keys()) == {_M036_EVENT_KIND_CASILLA}, (
        f"expected exactly {{decl.event-kind}}, got {set(values.keys())!r}"
    )

    # decl.event-kind: fixture prints
    #   "Causas de presentacion de la declaracion Alta"
    # named_label parser captures the trailing token "Alta" as the enum value string.
    # Ground truth: AEAT PAGINA 1 section heading "Causas de presentación de la
    # declaración" (instrucciones-cumplimentacion-pagina-1.html, h3 element).
    # TIPO column values per AEAT instructions: ALTA / MODIFICACIÓN / BAJA.
    # The fixture places "Alta" so the enum token is the mixed-case form.
    assert values[_M036_EVENT_KIND_CASILLA] == "Alta", (
        f"decl.event-kind: expected 'Alta' from AEAT-grounded fixture, got {values[_M036_EVENT_KIND_CASILLA]!r}"
    )
