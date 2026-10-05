"""Integration tests for the ``--row`` typed flag on ``work calculate``.

Tests the row-input flow:
  * domain row validators enforce aggregate legal constraints outside the CLI layer
  * Row type discrimination routes to correct pydantic model

The final test runs the real CLI to verify persisted rows remain visible in
operator output.
"""

from __future__ import annotations

import json
import subprocess
from decimal import Decimal
from pathlib import Path

import pytest

from ....core.config import override_settings
from ....domain.modelos.row_models import (
    Modelo184MemberRow,
    Modelo184ShareSumError,
    validate_m184_member_share_sum,
)
from ....tests.os_keychain_hook import require_os_credential_store

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]


def _output_language(language: str):
    """Pin the rendered language for assertions that match message TEXT.

    These refusals ride ``tr()``, so their wording follows the configured output
    language, which defaults to Spanish. The subject of each test below is WHICH
    refusal fires, not the language it fires in, so the language is pinned
    rather than the assertion rewritten in Spanish.
    """
    return override_settings(cadrumo_output_language=language)


# ---------------------------------------------------------------------------
# validate_m184_member_share_sum
# ---------------------------------------------------------------------------


class TestValidateM184ShareSum:
    def test_three_members_summing_100_passes(self) -> None:
        """3 sòcies with 40/35/25 share pass validation without error."""
        rows = (
            Modelo184MemberRow(nif="11111111A", porcentaje=Decimal("40"), importe=Decimal("12000"), clave="D"),
            Modelo184MemberRow(nif="22222222B", porcentaje=Decimal("35"), importe=Decimal("10500"), clave="D"),
            Modelo184MemberRow(nif="33333333C", porcentaje=Decimal("25"), importe=Decimal("7500"), clave="D"),
        )
        validate_m184_member_share_sum(rows)  # Must not raise

    def test_single_member_100_passes(self) -> None:
        """Single member with 100% share passes."""
        rows = (Modelo184MemberRow(nif="11111111A", porcentaje=Decimal("100"), importe=Decimal("10000"), clave="D"),)
        validate_m184_member_share_sum(rows)  # Must not raise

    def test_members_not_summing_100_raises(self) -> None:
        """Shares summing to != 100 raise BadParameter."""
        rows = (
            Modelo184MemberRow(nif="11111111A", porcentaje=Decimal("40"), importe=Decimal("4000"), clave="D"),
            Modelo184MemberRow(nif="22222222B", porcentaje=Decimal("35"), importe=Decimal("3500"), clave="D"),
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
            Modelo184MemberRow(nif="11111111A", porcentaje=Decimal("60"), importe=Decimal("60000"), clave="D"),
            Modelo184MemberRow(nif="22222222B", porcentaje=Decimal("40"), importe=Decimal("40000"), clave="D"),
        )
        validate_m184_member_share_sum(rows_pass)  # Passes

        rows_still_pass = (
            Modelo184MemberRow(nif="11111111A", porcentaje=Decimal("60"), importe=Decimal("99999"), clave="D"),
            Modelo184MemberRow(nif="22222222B", porcentaje=Decimal("40"), importe=Decimal("1"), clave="D"),
        )
        validate_m184_member_share_sum(rows_still_pass)  # Still passes - different importe same share

        rows_fail = (
            Modelo184MemberRow(nif="11111111A", porcentaje=Decimal("50"), importe=Decimal("60000"), clave="D"),
            Modelo184MemberRow(nif="22222222B", porcentaje=Decimal("40"), importe=Decimal("40000"), clave="D"),
        )
        with pytest.raises(Modelo184ShareSumError):
            validate_m184_member_share_sum(rows_fail)


# ---------------------------------------------------------------------------
# _parse_row_spec — M349 operador and rectificacion inputs
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Revision view surfaces persisted detail rows (regression for #200)
# ---------------------------------------------------------------------------


_ROW_FLAG_CREDENTIAL_INPUT = "row-flag-revision-view-passphrase"


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
        import json
        import subprocess
        import sys
        import textwrap

        # `config profile create` mints custody, so it needs the operator passphrase
        # and its confirmation. CADRUMO_SECRET_CREDENTIAL_INPUT below no longer unlocks
        # anything -- the machine-secret rule refuses an environment fallback for a
        # caller-supplied secret -- so it arrives on the bounded strict-JSON channel.
        stdin_payload: str | None = None
        creating_profile = "profile" in argv and "create" in argv
        if creating_profile and "--secrets-stdin" not in argv:
            argv = [*argv, "--secrets-stdin"]
            stdin_payload = json.dumps(
                {
                    "passphrase": _ROW_FLAG_CREDENTIAL_INPUT,
                    "passphrase_confirmation": _ROW_FLAG_CREDENTIAL_INPUT,
                }
            )
        elif "login" in argv and "--secrets-stdin" not in argv:
            argv = [*argv, "--secrets-stdin"]
            stdin_payload = json.dumps({"passphrase": _ROW_FLAG_CREDENTIAL_INPUT})

        code = f"""
            import os, sys
            os.environ["CADRUMO_LOCAL_STORAGE_ROOT"] = {str(storage_root)!r}
            os.environ["CADRUMO_SECRET_STORE_DIR"] = {str(storage_root / "fallback-store")!r}
            os.environ["CADRUMO_SECRET_CREDENTIAL_INPUT"] = {_ROW_FLAG_CREDENTIAL_INPUT!r}
            sys.argv = ["cadrumo", *{argv!r}]
            from cadrumo.entrypoints.cli.main import main

            try:
                main()
            except SystemExit as exit_:
                raise SystemExit(exit_.code)
            """
        completed = subprocess.run(
            [sys.executable, "-c", textwrap.dedent(code)],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            text=True,
            input=stdin_payload,
            timeout=300,
            check=False,
        )
        if creating_profile and completed.returncode == 0:
            # Creation closes its own session, so every verb after it would refuse
            # with "you are not logged in". The storage root is shared across these
            # subprocesses, so unlocking here persists into the next invocation.
            label = argv[argv.index("create") + 1]
            TestRevisionViewSurfacesDetailRows._run_cli(storage_root, ["config", "login", label])
        return completed

    def test_work_calculate_help_documents_quoted_m349_legal_name(self, tmp_path: Path) -> None:
        """The real CLI help shows the shell-safe M349 spaced-name row contract."""
        result = self._run_cli(tmp_path, ["app", "modelo", "work", "calculate", "--help"])

        assert result.returncode == 0, result.stderr
        # Whitespace-normalized: Click's plain help formatter wraps prose to the
        # real terminal width, so the quoted spaced legal name legitimately
        # spans a line break between ``razon_social="DE`` and ``Auto GmbH"``.
        flat = " ".join(result.stdout.split())
        assert 'razon_social="DE Auto GmbH"' in flat
        assert "operador codigo_pais=DE" in flat

    @pytest.mark.os_keychain
    def test_m349_json_calculate_materialises_operador_detail_rows(self, tmp_path: Path) -> None:
        """M349 ``--row operador`` data reaches JSON calculate and revision payloads."""
        # Every later invocation resumes the profile session from the OS credential
        # store; refuse before paying for profile creation on a host that has none.
        require_os_credential_store()
        setup = self._run_cli(
            tmp_path,
            [
                "config",
                "profile",
                "create",
                "m349",
                "--tax-id",
                "12345678Z",
                "--entity-type",
                "natural_person",
                "--name",
                "Ana",
                "--surnames",
                "M349",
                "--irpf-income-categories",
                "actividad_economica",
                "--activity",
                "consultoria intracomunitaria",
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

        de_row = (
            'operador codigo_pais=DE nif_comunitario=DE123456789 razon_social="DE Auto GmbH" '
            "clave_operacion=E importe=1500.00"
        )
        fr_row = (
            'operador codigo_pais=FR nif_comunitario=FR12345678901 razon_social="Equipement Garage SARL" '
            "clave_operacion=E importe=900.00"
        )
        calc = self._run_cli(
            tmp_path,
            [
                "--format",
                "json",
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
                de_row,
                "--row",
                fr_row,
            ],
        )
        assert calc.returncode == 0, f"calculate failed: {calc.stdout}\n{calc.stderr}"
        calc_payload = json.loads(calc.stdout)["result"]

        assert calc_payload["casilla_values"]["decl.numero-operadores"] == "2"
        assert calc_payload["casilla_values"]["decl.importe-operaciones"] == "2400.00"
        detail_rows = calc_payload["detail_rows"]
        assert len(detail_rows) == 2
        calc_rows_by_nif = {row["fields"]["nif_comunitario"]: row for row in detail_rows}
        assert set(calc_rows_by_nif) == {"DE123456789", "FR12345678901"}
        assert calc_rows_by_nif["DE123456789"]["row_type"] == "operador"
        assert calc_rows_by_nif["DE123456789"]["fields"]["codigo_pais"] == "DE"
        assert calc_rows_by_nif["DE123456789"]["fields"]["razon_social"] == "DE Auto GmbH"
        assert calc_rows_by_nif["DE123456789"]["fields"]["clave_operacion"] == "E"
        assert calc_rows_by_nif["DE123456789"]["fields"]["importe"] == "1500.00"
        assert calc_rows_by_nif["FR12345678901"]["fields"]["codigo_pais"] == "FR"
        assert calc_rows_by_nif["FR12345678901"]["fields"]["razon_social"] == "Equipement Garage SARL"
        assert calc_rows_by_nif["FR12345678901"]["fields"]["importe"] == "900.00"

        revision = self._run_cli(
            tmp_path,
            [
                "--format",
                "json",
                "app",
                "modelo",
                "work",
                "revision",
                "--modelo",
                "349",
                "--year",
                "2026",
                "--period",
                "1T",
            ],
        )
        assert revision.returncode == 0, f"revision failed: {revision.stdout}\n{revision.stderr}"
        revision_payload = json.loads(revision.stdout)["result"]
        revision_rows_by_nif = {row["fields"]["nif_comunitario"]: row for row in revision_payload["detail_rows"]}

        assert revision_rows_by_nif == calc_rows_by_nif

    @pytest.mark.os_keychain
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
        # Every later invocation resumes the profile session from the OS credential
        # store; refuse before paying for profile creation on a host that has none.
        require_os_credential_store()
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
                "--entity-type",
                "attribution_entity",
                "--name",
                "M184 Row Test CB",
                "--activity",
                "arrendamiento conjunto",
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
                "2025-y-siguientes",
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

    @pytest.mark.os_keychain
    def test_m349_operador_rows_feed_summary_and_verify(self, tmp_path: Path) -> None:
        """Cold M349 operador rows produce Tipo-1 summary casillas and verify.

        The two Tipo-2 operador rows are the operator-facing source of truth in
        this manual-entry path. The persisted draft must hash those rows, expose
        them in the revision output, and populate the declarant summary totals
        that the M349 fixed-width record defines over the operator records.
        """
        # Every later invocation resumes the profile session from the OS credential
        # store; refuse before paying for profile creation on a host that has none.
        require_os_credential_store()
        setup = self._run_cli(
            tmp_path,
            [
                "config",
                "profile",
                "create",
                "m349",
                "--tax-id",
                "12345678Z",
                "--entity-type",
                "natural_person",
                "--name",
                "Ana",
                "--surnames",
                "M349",
                "--irpf-income-categories",
                "actividad_economica",
                "--activity",
                "consultoria intracomunitaria",
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
                    'operador codigo_pais=DE nif_comunitario=DE123456789 razon_social="DE Auto GmbH" '
                    "clave_operacion=E importe=1500.00"
                ),
                "--row",
                (
                    'operador codigo_pais=FR nif_comunitario=FR12345678901 razon_social="Equipement Garage SARL" '
                    "clave_operacion=E importe=900.00"
                ),
            ],
        )
        assert calc.returncode == 0, f"calculate failed: {calc.stdout}\n{calc.stderr}"
        assert "casilla\tdecl.numero-operadores\t2" in calc.stdout, calc.stdout
        assert "casilla\tdecl.importe-operaciones\t2400.00" in calc.stdout, calc.stdout
        assert "razon_social=DE Auto GmbH" in calc.stdout, calc.stdout
        assert "razon_social=Equipement Garage SARL" in calc.stdout, calc.stdout
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

        output_path = tmp_path / "modelo-349.txt"
        exported = self._run_cli(
            tmp_path,
            [
                "app",
                "modelo",
                "export",
                "--modelo",
                "349",
                "--year",
                "2026",
                "--period",
                "1T",
                "--output",
                str(output_path),
            ],
        )
        assert exported.returncode == 0, f"export failed: {exported.stdout}\n{exported.stderr}"

        text = output_path.read_bytes().decode("latin-1")
        assert len(text) % 500 == 0, f"unexpected M349 fixed-width length: {len(text)}"
        records = [text[index : index + 500] for index in range(0, len(text), 500)]
        operator_records = {
            record[75:77]: record for record in records if record.startswith("2349") and not record[146:178].strip()
        }

        assert operator_records["DE"][77:92].rstrip() == "123456789"
        assert operator_records["DE"][92:132].rstrip() == "DE Auto GmbH"
        assert operator_records["FR"][77:92].rstrip() == "12345678901"
        assert operator_records["FR"][92:132].rstrip() == "Equipement Garage SARL"
        assert "DEDE123456789" not in text
        assert "FRFR12345678901" not in text

    @pytest.mark.os_keychain
    def test_m349_post_transition_gb_operador_row_fails_before_calculation(self, tmp_path: Path) -> None:
        """Ordinary post-transition GB rows are refused at the CLI calculation boundary."""
        # Every later invocation resumes the profile session from the OS credential
        # store; refuse before paying for profile creation on a host that has none.
        require_os_credential_store()
        setup = self._run_cli(
            tmp_path,
            [
                "config",
                "profile",
                "create",
                "m349-gb",
                "--tax-id",
                "12345678Z",
                "--entity-type",
                "natural_person",
                "--name",
                "Ana",
                "--surnames",
                "M349",
                "--irpf-income-categories",
                "actividad_economica",
                "--activity",
                "consultoria intracomunitaria",
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
                    "operador codigo_pais=GB nif_comunitario=GB123456789 razon_social=EntidadGB "
                    "clave_operacion=E importe=1500.00"
                ),
            ],
        )

        output = calc.stdout + calc.stderr
        assert calc.returncode != 0, output
        assert "post-transition" in output
        assert "GB" in output
        assert "casilla\tdecl.numero-operadores" not in output
