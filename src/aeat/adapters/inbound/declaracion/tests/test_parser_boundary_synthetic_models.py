"""Synthetic and error parser boundary tests split from parser boundary part 2."""

from __future__ import annotations

import pytest

from ._parser_boundary_part2_support import (
    _M036_EVENT_KIND_CASILLA,
)
from ._parser_boundary_support import (
    _MODELO_036_SYNTHETIC_FIXTURE,
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
