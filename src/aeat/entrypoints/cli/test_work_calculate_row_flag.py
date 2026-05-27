"""Integration tests for the ``--row`` typed flag on ``work calculate``.

Tests the CLI boundary layer:
  * ``_parse_row_spec`` parses valid TYPE FIELD=value specs
  * ``_parse_row_spec`` raises BadParameter on malformed input
  * ``_validate_m184_share_sum`` enforces the 100% constraint
  * Row type discrimination routes to correct pydantic model

Tests are unit-level (no storage, no registry snapshot) — the parsing
helpers are pure functions that do not touch any external state.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
import typer

from ...domain.modelos._row_models import Modelo184MemberRow, Modelo232VinculadaRow
from ._modelo import _parse_row_spec, _validate_m184_share_sum

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


# ---------------------------------------------------------------------------
# _parse_row_spec — valid inputs
# ---------------------------------------------------------------------------


class TestParseRowSpecValid:
    def test_parse_miembro_minimal(self) -> None:
        """Minimal miembro spec with required fields parses correctly."""
        result = _parse_row_spec("miembro nif=12345678A porcentaje=40 importe=10000")
        assert isinstance(result, Modelo184MemberRow)
        assert result.nif == "12345678A"
        assert result.porcentaje == Decimal("40")
        assert result.importe == Decimal("10000")

    def test_parse_miembro_with_optional_fields(self) -> None:
        """miembro spec with nombre and pais round-trips."""
        result = _parse_row_spec("miembro nif=11111111A nombre=Sòcia1 pais=ES porcentaje=60 importe=18000")
        assert isinstance(result, Modelo184MemberRow)
        assert result.nombre == "Sòcia1"
        assert result.pais == "ES"

    def test_parse_vinculada_minimal(self) -> None:
        """Minimal vinculada spec parses correctly."""
        result = _parse_row_spec("vinculada nif=A12345678 importe=50000")
        assert isinstance(result, Modelo232VinculadaRow)
        assert result.nif == "A12345678"
        assert result.importe == Decimal("50000")

    def test_parse_vinculada_full_spec(self) -> None:
        """Full vinculada spec with all optional fields."""
        result = _parse_row_spec(
            "vinculada nif=B87654321 nombre=EntidadSL pais=DE "
            "tipo_vinculacion=2 tipo_operacion=05 metodo=TNMM importe=75000"
        )
        assert isinstance(result, Modelo232VinculadaRow)
        assert result.nif == "B87654321"
        assert result.pais == "DE"
        assert result.metodo == "TNMM"
        assert result.importe == Decimal("75000")

    def test_row_type_is_case_insensitive(self) -> None:
        """TYPE token is lowercased before dispatch."""
        result = _parse_row_spec("MIEMBRO nif=12345678A porcentaje=50 importe=5000")
        assert isinstance(result, Modelo184MemberRow)


# ---------------------------------------------------------------------------
# _parse_row_spec — invalid inputs
# ---------------------------------------------------------------------------


class TestParseRowSpecInvalid:
    def test_empty_spec_raises(self) -> None:
        """Empty spec raises BadParameter."""
        with pytest.raises(typer.BadParameter, match="empty"):
            _parse_row_spec("   ")

    def test_unknown_type_raises(self) -> None:
        """Unknown row type raises BadParameter."""
        with pytest.raises(typer.BadParameter, match="not recognised"):
            _parse_row_spec("operador nif=X12345678 importe=1000")

    def test_missing_equals_in_field_raises(self) -> None:
        """Token without '=' raises BadParameter."""
        with pytest.raises(typer.BadParameter, match="KEY=VALUE"):
            _parse_row_spec("miembro nif 12345678A porcentaje=50 importe=0")

    def test_empty_key_raises(self) -> None:
        """Token with empty key raises BadParameter."""
        with pytest.raises(typer.BadParameter):
            _parse_row_spec("miembro =value porcentaje=50 importe=0")

    def test_porcentaje_above_100_raises(self) -> None:
        """porcentaje > 100 raises BadParameter via model validation."""
        with pytest.raises(typer.BadParameter):
            _parse_row_spec("miembro nif=12345678A porcentaje=101 importe=0")

    def test_invalid_pais_raises(self) -> None:
        """Lowercase pais raises BadParameter."""
        with pytest.raises(typer.BadParameter):
            _parse_row_spec("miembro nif=12345678A pais=es porcentaje=50 importe=0")

    def test_missing_required_field_raises(self) -> None:
        """Missing required field (porcentaje for miembro) raises BadParameter."""
        with pytest.raises(typer.BadParameter):
            _parse_row_spec("miembro nif=12345678A importe=0")

    def test_non_numeric_decimal_field_raises(self) -> None:
        """Non-numeric value for a Decimal field raises BadParameter, not a crash."""
        with pytest.raises(typer.BadParameter):
            _parse_row_spec("miembro nif=12345678A porcentaje=abc importe=0")


# ---------------------------------------------------------------------------
# _validate_m184_share_sum
# ---------------------------------------------------------------------------


class TestValidateM184ShareSum:
    def test_three_members_summing_100_passes(self) -> None:
        """3 sòcies with 40/35/25 share pass validation without error."""
        rows = (
            Modelo184MemberRow(nif="11111111A", porcentaje=Decimal("40"), importe=Decimal("12000")),
            Modelo184MemberRow(nif="22222222B", porcentaje=Decimal("35"), importe=Decimal("10500")),
            Modelo184MemberRow(nif="33333333C", porcentaje=Decimal("25"), importe=Decimal("7500")),
        )
        _validate_m184_share_sum(rows)  # Must not raise

    def test_single_member_100_passes(self) -> None:
        """Single member with 100% share passes."""
        rows = (Modelo184MemberRow(nif="11111111A", porcentaje=Decimal("100"), importe=Decimal("10000")),)
        _validate_m184_share_sum(rows)  # Must not raise

    def test_members_not_summing_100_raises(self) -> None:
        """Shares summing to != 100 raise BadParameter."""
        rows = (
            Modelo184MemberRow(nif="11111111A", porcentaje=Decimal("40"), importe=Decimal("4000")),
            Modelo184MemberRow(nif="22222222B", porcentaje=Decimal("35"), importe=Decimal("3500")),
        )
        with pytest.raises(typer.BadParameter, match="100"):
            _validate_m184_share_sum(rows)

    def test_no_miembro_rows_skips_check(self) -> None:
        """When no miembro rows are present the check is skipped silently."""
        rows = (Modelo232VinculadaRow(nif="A12345678", importe=Decimal("1000")),)
        _validate_m184_share_sum(rows)  # Must not raise

    def test_empty_rows_skips_check(self) -> None:
        """Empty row tuple skips validation."""
        _validate_m184_share_sum(())  # Must not raise

    def test_antitautology_changing_importe_does_not_affect_share_sum(self) -> None:
        """Anti-tautology: changing importe on a row does not affect share-sum validation.

        The share validation ONLY reads porcentaje, not importe. This test
        confirms the validator is checking the right field.
        """
        rows_pass = (
            Modelo184MemberRow(nif="11111111A", porcentaje=Decimal("60"), importe=Decimal("60000")),
            Modelo184MemberRow(nif="22222222B", porcentaje=Decimal("40"), importe=Decimal("40000")),
        )
        _validate_m184_share_sum(rows_pass)  # Passes

        rows_still_pass = (
            Modelo184MemberRow(nif="11111111A", porcentaje=Decimal("60"), importe=Decimal("99999")),
            Modelo184MemberRow(nif="22222222B", porcentaje=Decimal("40"), importe=Decimal("1")),
        )
        _validate_m184_share_sum(rows_still_pass)  # Still passes — different importe same share

        rows_fail = (
            Modelo184MemberRow(nif="11111111A", porcentaje=Decimal("50"), importe=Decimal("60000")),
            Modelo184MemberRow(nif="22222222B", porcentaje=Decimal("40"), importe=Decimal("40000")),
        )
        with pytest.raises(typer.BadParameter, match="100"):
            _validate_m184_share_sum(rows_fail)
