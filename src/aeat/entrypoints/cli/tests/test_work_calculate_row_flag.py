"""Integration tests for the ``--row`` typed flag on ``work calculate``.

Tests the row-input flow:
  * ``_parse_row_spec`` parses valid TYPE FIELD=value specs
  * ``_parse_row_spec`` raises BadParameter on malformed input
  * domain row validators enforce aggregate legal constraints outside the CLI layer
  * Row type discrimination routes to correct pydantic model

The final test runs the real CLI to verify persisted rows remain visible in
operator output.
"""

from __future__ import annotations

import subprocess
from decimal import Decimal
from pathlib import Path

import pytest
import typer

from ....domain.modelos._row_models import (
    Modelo184MemberRow,
    Modelo184ShareSumError,
    Modelo232VinculadaRow,
    Modelo347ContraparteRow,
    Modelo347ThresholdError,
    Modelo349OperadorRow,
    validate_m184_member_share_sum,
    validate_m347_threshold,
)
from .._modelo_cli_support import parse_row_spec as _parse_row_spec

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


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
            "tipo_vinculacion=2 tipo_operacion=05 metodo=TNMM importe=75000",
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
            _parse_row_spec("socio nif=X12345678 importe=1000")

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
# validate_m184_member_share_sum
# ---------------------------------------------------------------------------


class TestValidateM184ShareSum:
    def test_three_members_summing_100_passes(self) -> None:
        """3 sòcies with 40/35/25 share pass validation without error."""
        rows = (
            Modelo184MemberRow(nif="11111111A", porcentaje=Decimal("40"), importe=Decimal("12000")),
            Modelo184MemberRow(nif="22222222B", porcentaje=Decimal("35"), importe=Decimal("10500")),
            Modelo184MemberRow(nif="33333333C", porcentaje=Decimal("25"), importe=Decimal("7500")),
        )
        validate_m184_member_share_sum(rows)  # Must not raise

    def test_single_member_100_passes(self) -> None:
        """Single member with 100% share passes."""
        rows = (Modelo184MemberRow(nif="11111111A", porcentaje=Decimal("100"), importe=Decimal("10000")),)
        validate_m184_member_share_sum(rows)  # Must not raise

    def test_members_not_summing_100_raises(self) -> None:
        """Shares summing to != 100 raise BadParameter."""
        rows = (
            Modelo184MemberRow(nif="11111111A", porcentaje=Decimal("40"), importe=Decimal("4000")),
            Modelo184MemberRow(nif="22222222B", porcentaje=Decimal("35"), importe=Decimal("3500")),
        )
        with pytest.raises(Modelo184ShareSumError):
            validate_m184_member_share_sum(rows)

    def test_empty_rows_skips_check(self) -> None:
        """Empty row tuple skips validation."""
        validate_m184_member_share_sum(())  # Must not raise

    def test_antitautology_changing_importe_does_not_affect_share_sum(self) -> None:
        """Anti-tautology: changing importe on a row does not affect share-sum validation.

        The share validation ONLY reads porcentaje, not importe. This test
        confirms the validator is checking the right field.
        """
        rows_pass = (
            Modelo184MemberRow(nif="11111111A", porcentaje=Decimal("60"), importe=Decimal("60000")),
            Modelo184MemberRow(nif="22222222B", porcentaje=Decimal("40"), importe=Decimal("40000")),
        )
        validate_m184_member_share_sum(rows_pass)  # Passes

        rows_still_pass = (
            Modelo184MemberRow(nif="11111111A", porcentaje=Decimal("60"), importe=Decimal("99999")),
            Modelo184MemberRow(nif="22222222B", porcentaje=Decimal("40"), importe=Decimal("1")),
        )
        validate_m184_member_share_sum(rows_still_pass)  # Still passes - different importe same share

        rows_fail = (
            Modelo184MemberRow(nif="11111111A", porcentaje=Decimal("50"), importe=Decimal("60000")),
            Modelo184MemberRow(nif="22222222B", porcentaje=Decimal("40"), importe=Decimal("40000")),
        )
        with pytest.raises(Modelo184ShareSumError):
            validate_m184_member_share_sum(rows_fail)


# ---------------------------------------------------------------------------
# _parse_row_spec — M349 operador + M347 contraparte valid inputs
# ---------------------------------------------------------------------------


class TestParseRowSpecM349:
    def test_parse_operador_minimal(self) -> None:
        """Minimal operador spec with required fields parses to Modelo349OperadorRow."""
        result = _parse_row_spec("operador codigo_pais=DE nif_comunitario=DE123456789 clave_operacion=E importe=50000")
        assert isinstance(result, Modelo349OperadorRow)
        assert result.codigo_pais == "DE"
        assert result.nif_comunitario == "DE123456789"
        assert result.clave_operacion == "E"
        assert result.importe == Decimal("50000")

    def test_parse_operador_with_razon_social(self) -> None:
        """operador spec with optional razon_social round-trips."""
        result = _parse_row_spec(
            "operador codigo_pais=FR nif_comunitario=FR12345678901 "
            "razon_social=EntidadFR clave_operacion=S importe=30000",
        )
        assert isinstance(result, Modelo349OperadorRow)
        assert result.razon_social == "EntidadFR"
        assert result.clave_operacion == "S"

    def test_parse_operador_type_case_insensitive(self) -> None:
        """TYPE token is lowercased before dispatch."""
        result = _parse_row_spec("OPERADOR codigo_pais=IT nif_comunitario=IT12345678901 clave_operacion=M importe=1000")
        assert isinstance(result, Modelo349OperadorRow)

    def test_parse_operador_invalid_nif_format_raises(self) -> None:
        """operador with NIF not matching the country pattern raises BadParameter."""
        with pytest.raises(typer.BadParameter, match="NIF-IVA"):
            # DE requires 9 digits; this has only 8
            _parse_row_spec("operador codigo_pais=DE nif_comunitario=DE12345678 clave_operacion=E importe=1000")

    def test_parse_operador_invalid_clave_raises(self) -> None:
        """Invalid clave_operacion raises BadParameter."""
        with pytest.raises(typer.BadParameter):
            _parse_row_spec("operador codigo_pais=DE nif_comunitario=DE123456789 clave_operacion=Z importe=1000")

    def test_parse_operador_negative_importe_raises(self) -> None:
        """Negative importe raises BadParameter."""
        with pytest.raises(typer.BadParameter):
            _parse_row_spec("operador codigo_pais=DE nif_comunitario=DE123456789 clave_operacion=E importe=-100")


class TestParseRowSpecM347:
    def test_parse_contraparte_minimal(self) -> None:
        """Minimal contraparte spec with required fields parses to Modelo347ContraparteRow."""
        result = _parse_row_spec("contraparte nif=12345678A importe_Q1=5000")
        assert isinstance(result, Modelo347ContraparteRow)
        assert result.nif == "12345678A"
        assert result.importe_Q1 == Decimal("5000")

    def test_parse_contraparte_full_quarters(self) -> None:
        """contraparte spec with all four quarters round-trips."""
        result = _parse_row_spec(
            "contraparte nif=12345678A nombre=ProveedorSL "
            "importe_Q1=3000 importe_Q2=2000 importe_Q3=1500 importe_Q4=1000 "
            "clave_operacion=B",
        )
        assert isinstance(result, Modelo347ContraparteRow)
        assert result.importe_total == Decimal("7500")
        assert result.clave_operacion == "B"

    def test_parse_contraparte_blank_nif_raises(self) -> None:
        """Blank NIF raises BadParameter."""
        with pytest.raises(typer.BadParameter):
            _parse_row_spec("contraparte nif=   importe_Q1=5000")


# ---------------------------------------------------------------------------
# validate_m347_threshold
# ---------------------------------------------------------------------------


class TestValidateM347Threshold:
    def test_above_threshold_passes(self) -> None:
        """A contraparte row with total > €3,005.06 passes validation."""
        rows = (Modelo347ContraparteRow(nif="12345678A", importe_Q1=Decimal("3005.07")),)
        validate_m347_threshold(rows)  # Must not raise

    def test_exactly_threshold_rejected(self) -> None:
        """A total equal to €3,005.06 is rejected (must exceed, not equal).

        Oracle: RD 1065/2007 art. 31.1 — 'supere' (exceed), not 'iguale'."""
        rows = (Modelo347ContraparteRow(nif="12345678A", importe_Q1=Decimal("3005.06")),)
        with pytest.raises(Modelo347ThresholdError):
            validate_m347_threshold(rows)

    def test_below_threshold_rejected(self) -> None:
        """A total below €3,005.06 is rejected."""
        rows = (Modelo347ContraparteRow(nif="12345678A", importe_Q1=Decimal("1000")),)
        with pytest.raises(Modelo347ThresholdError):
            validate_m347_threshold(rows)

    def test_empty_rows_skips_check(self) -> None:
        """Empty row tuple skips validation."""
        validate_m347_threshold(())  # Must not raise

    def test_antitautology_threshold_check_reads_total_not_individual_quarters(self) -> None:
        """Anti-tautology: the check sums Q1+Q2+Q3+Q4, not just Q1.

        Oracle: RD 1065/2007 art. 31.1 — annual total must exceed €3,005.06.
        A row with Q1=1000 + Q2=1000 + Q3=1000 + Q4=1005.07 = 4005.07 > 3005.06.
        If the check only looked at Q1 this would incorrectly fail.
        """
        rows = (
            Modelo347ContraparteRow(
                nif="12345678A",
                importe_Q1=Decimal("1000"),
                importe_Q2=Decimal("1000"),
                importe_Q3=Decimal("1000"),
                importe_Q4=Decimal("1005.07"),
            ),
        )
        validate_m347_threshold(rows)  # total=4005.07 > 3005.06, must not raise

    def test_same_nif_split_across_rows_aggregates_over_threshold(self) -> None:
        """Two rows for the SAME counterparty (e.g. entregas + adquisiciones), each
        at/below the threshold, whose annual aggregate exceeds it, must pass.

        Oracle: RD 1065/2007 art. 33.1 — the threshold is on the operations with
        the same person, summed across rows. 2000 + 2000 = 4000 > 3005.06.
        """
        rows = (
            Modelo347ContraparteRow(nif="12345678A", importe_Q1=Decimal("2000")),
            Modelo347ContraparteRow(nif="12345678A", importe_Q3=Decimal("2000")),
        )
        validate_m347_threshold(rows)  # per-NIF total 4000 > 3005.06, must not raise

    def test_same_nif_split_across_rows_aggregate_below_threshold_rejected(self) -> None:
        """Same-NIF rows whose AGGREGATE is at/below the threshold are rejected,
        and the error reports the aggregated per-NIF total (1000+1500=2500)."""
        rows = (
            Modelo347ContraparteRow(nif="12345678A", importe_Q1=Decimal("1000")),
            Modelo347ContraparteRow(nif="12345678A", importe_Q2=Decimal("1500")),
        )
        with pytest.raises(Modelo347ThresholdError) as exc:
            validate_m347_threshold(rows)
        # The error reports the AGGREGATED per-NIF total = the sum of the two rows' totals.
        assert exc.value.total == rows[0].importe_total + rows[1].importe_total
        assert exc.value.nif == "12345678A"

    def test_distinct_nifs_thresholded_independently(self) -> None:
        """Aggregation is per-NIF: a declarable counterparty does not rescue a
        different counterparty below the threshold."""
        rows = (
            Modelo347ContraparteRow(nif="11111111H", importe_Q1=Decimal("5000")),
            Modelo347ContraparteRow(nif="22222222J", importe_Q1=Decimal("1000")),
        )
        with pytest.raises(Modelo347ThresholdError) as exc:
            validate_m347_threshold(rows)
        assert exc.value.nif == "22222222J"


# ---------------------------------------------------------------------------
# Revision view surfaces persisted detail rows (regression for #200)
# ---------------------------------------------------------------------------


class TestRevisionViewSurfacesDetailRows:
    """Persisted ``detail_rows`` must render in the ``work revision`` view.

    Regression: informativa repeating rows (M184 comuneros, M347/M349
    contrapartes) are persisted on the revision but live outside the flat
    ``casilla_values`` map. Before the fix the revision view rendered only the
    empty ``tipo2.*`` template casillas, so an operator who entered N members
    saw zeros and believed the rows were silently dropped.
    """

    @staticmethod
    def _run_cli(storage_root: Path, argv: list[str]) -> subprocess.CompletedProcess[str]:
        import subprocess
        import sys
        import textwrap

        code = f"""
            import os, sys
            os.environ["AEAT_LOCAL_STORAGE_ROOT"] = {str(storage_root)!r}
            os.environ["AEAT_SECRET_STORE_BACKEND"] = "file"
            os.environ["AEAT_SECRET_STORE_DIR"] = {str(storage_root / "secrets")!r}
            os.environ["AEAT_SECRET_PASSPHRASE"] = "row-flag-revision-view-passphrase"
            from click.testing import CliRunner
            from typer.main import get_command
            from aeat.entrypoints.cli import app

            result = CliRunner().invoke(get_command(app), {argv!r})
            sys.stdout.write(result.output)
            sys.exit(result.exit_code)
            """
        return subprocess.run(
            [sys.executable, "-c", textwrap.dedent(code)],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )

    def test_m184_member_rows_surface_in_revision_view(self, tmp_path: Path) -> None:
        """A cold M184 ``--row`` flow renders the members as ``detail_row`` lines.

        End-to-end so the work unit resolves (the result-summary block runs on a
        real revision): create a comunidad profile, an M184 work unit, then
        calculate with two ``--row miembro`` specs. ``work calculate`` renders the
        revision via the same path as ``work revision``, so both members must
        appear as ``detail_row`` lines with their share and amount — previously
        they were persisted but invisible (only the empty ``tipo2.*`` template
        casillas showed).
        """
        import re

        setup = self._run_cli(
            tmp_path,
            [
                "config",
                "profile",
                "create",
                "cb",
                "--tax-id",
                "E12345674",
                "--legal-entity-form",
                "sociedad_civil_mercantil",
                "--quiet",
            ],
        )
        assert setup.returncode == 0, f"profile create failed: {setup.stdout}\n{setup.stderr}"
        created = self._run_cli(
            tmp_path,
            [
                "app",
                "modelo",
                "work",
                "create",
                "--modelo",
                "184",
                "--year",
                "2024",
                "--period",
                "0A",
                "--revision",
                "2015-y-siguientes",
            ],
        )
        assert created.returncode == 0, f"work create failed: {created.stdout}\n{created.stderr}"
        listing = self._run_cli(tmp_path, ["app", "modelo", "work", "list"])
        wid_match = re.search(r"[0-9a-f]{64}", listing.stdout)
        assert wid_match, f"no work unit id in: {listing.stdout}"
        work_unit_id = wid_match.group(0)
        calc = self._run_cli(
            tmp_path,
            [
                "app",
                "modelo",
                "work",
                "calculate",
                work_unit_id,
                "--row",
                "miembro nif=45678912S porcentaje=60 importe=10000",
                "--row",
                "miembro nif=00000001R porcentaje=40 importe=5000",
            ],
        )
        assert calc.returncode == 0, f"calculate failed: {calc.stdout}\n{calc.stderr}"

        detail_lines = [line for line in calc.stdout.splitlines() if line.startswith("detail_row\t")]
        assert len(detail_lines) == 2, f"expected 2 detail rows, got: {calc.stdout}"
        assert "porcentaje=60" in calc.stdout and "importe=10000" in calc.stdout, calc.stdout
        assert "porcentaje=40" in calc.stdout and "importe=5000" in calc.stdout, calc.stdout

    def test_m349_operador_rows_feed_summary_and_verify(self, tmp_path: Path) -> None:
        """Cold M349 operador rows produce Tipo-1 summary casillas and verify.

        The two Tipo-2 operador rows are the operator-facing source of truth in
        this manual-entry path. The persisted draft must hash those rows, expose
        them in the revision output, and populate the declarant summary totals
        that the M349 fixed-width record defines over the operator records.
        """
        setup = self._run_cli(
            tmp_path,
            [
                "config",
                "profile",
                "create",
                "m349",
                "--tax-id",
                "E12345674",
                "--legal-entity-form",
                "sociedad_civil_mercantil",
                "--quiet",
            ],
        )
        assert setup.returncode == 0, f"profile create failed: {setup.stdout}\n{setup.stderr}"
        created = self._run_cli(
            tmp_path,
            [
                "app",
                "modelo",
                "work",
                "create",
                "--modelo",
                "349",
                "--year",
                "2026",
                "--period",
                "1T",
                "--revision",
                "2020-y-siguientes",
            ],
        )
        assert created.returncode == 0, f"work create failed: {created.stdout}\n{created.stderr}"

        calc = self._run_cli(
            tmp_path,
            [
                "app",
                "modelo",
                "work",
                "calculate",
                "--modelo",
                "349",
                "--year",
                "2026",
                "--period",
                "1T",
                "--row",
                (
                    "operador codigo_pais=DE nif_comunitario=DE123456789 razon_social=EntidadDE "
                    "clave_operacion=E importe=1500.00"
                ),
                "--row",
                (
                    "operador codigo_pais=FR nif_comunitario=FR12345678901 razon_social=EntidadFR "
                    "clave_operacion=E importe=900.00"
                ),
            ],
        )
        assert calc.returncode == 0, f"calculate failed: {calc.stdout}\n{calc.stderr}"
        assert "casilla\tdecl.numero-operadores\t2" in calc.stdout, calc.stdout
        assert "casilla\tdecl.importe-operaciones\t2400.00" in calc.stdout, calc.stdout
        assert len([line for line in calc.stdout.splitlines() if line.startswith("detail_row\t")]) == 2, calc.stdout

        verified = self._run_cli(
            tmp_path,
            [
                "app",
                "modelo",
                "work",
                "verify",
                "--modelo",
                "349",
                "--year",
                "2026",
                "--period",
                "1T",
            ],
        )
        assert verified.returncode == 0, f"verify failed: {verified.stdout}\n{verified.stderr}"
        assert "content-address mismatch" not in verified.stdout + verified.stderr
