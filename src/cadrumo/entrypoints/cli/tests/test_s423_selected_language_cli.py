"""Real selected-language CLI coverage for the selected-language continuity repairs."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_CLI_HARNESS = """
from __future__ import annotations

import os
import sys

os.environ["CADRUMO_LOCAL_STORAGE_ROOT"] = sys.argv[1]
os.environ["CADRUMO_SECRET_STORE_DIR"] = sys.argv[2]
os.environ["CADRUMO_SECRET_STORE_BACKEND"] = "file"
os.environ["CADRUMO_SECRET_PASSPHRASE"] = "s423-selected-language-passphrase"
sys.argv = ["cadrumo", *sys.argv[3:]]

from cadrumo.entrypoints.cli import main

try:
    main()
except SystemExit as exit_:
    raise SystemExit(exit_.code)
"""

_PERSISTED_REPORT_HARNESS = """
from __future__ import annotations

import json
import os
import sys

os.environ["CADRUMO_LOCAL_STORAGE_ROOT"] = sys.argv[1]
os.environ["CADRUMO_SECRET_STORE_DIR"] = sys.argv[2]
os.environ["CADRUMO_SECRET_STORE_BACKEND"] = "file"
os.environ["CADRUMO_SECRET_PASSPHRASE"] = "s423-selected-language-passphrase"

from cadrumo.adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from cadrumo.application.user_profile import profile_storage_session
from cadrumo.core import resolve_active_bucket_id

bucket_id = resolve_active_bucket_id()
assert bucket_id is not None
with profile_storage_session(bucket_id):
    catalogue = VerificationReportCatalogueRepository(bucket_id=bucket_id).load()
report = catalogue.get(sys.argv[3])
assert report is not None
print(json.dumps({"report": report.model_dump(mode="json"), "report_count": len(catalogue)}, sort_keys=True))
"""


def _run_cli(storage_root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    env = {key: value for key, value in os.environ.items() if not key.startswith("AEAT_")}
    env.update({"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"})
    return subprocess.run(  # noqa: S603 - fixed interpreter argv with controlled test inputs.
        [
            sys.executable,
            "-c",
            textwrap.dedent(_CLI_HARNESS),
            str(storage_root),
            str(storage_root / "secrets"),
            *args,
        ],
        cwd=Path.cwd(),
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        timeout=120,
    )


def _combined_output(result: subprocess.CompletedProcess[str]) -> str:
    return f"{result.stdout}\n{result.stderr}"


def _persisted_report(storage_root: Path, verification_report_id: str) -> dict[str, object]:
    env = {key: value for key, value in os.environ.items() if not key.startswith("AEAT_")}
    env.update({"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"})
    result = subprocess.run(  # noqa: S603 - fixed interpreter argv with controlled test inputs.
        [
            sys.executable,
            "-c",
            textwrap.dedent(_PERSISTED_REPORT_HARNESS),
            str(storage_root),
            str(storage_root / "secrets"),
            verification_report_id,
        ],
        cwd=Path.cwd(),
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        timeout=120,
    )
    assert result.returncode == 0, _combined_output(result)
    return json.loads(result.stdout)


def _create_modelo_revision(
    storage_root: Path,
    language: str,
    *,
    modelo: str,
    year: str,
    period: str,
    activity_start_date: str,
) -> str:
    profile = _run_cli(
        storage_root,
        [
            "--language",
            language,
            "config",
            "profile",
            "create",
            "operator",
            "--quiet",
            "--accept-defaults",
            "--entity-type",
            "natural_person",
            "--tax-id",
            "12345678Z",
            "--name",
            "Operator",
            "--surnames",
            "Locale",
            "--activity",
            "design",
            "--irpf-income-categories",
            "actividad_economica",
            "--activity-start-date",
            activity_start_date,
        ],
    )
    assert profile.returncode == 0, _combined_output(profile)
    created = _run_cli(
        storage_root,
        [
            "--language",
            language,
            "app",
            "modelo",
            "work",
            "create",
            "--modelo",
            modelo,
            "--year",
            year,
            "--period",
            period,
        ],
    )
    assert created.returncode == 0, _combined_output(created)
    calculated = _run_cli(
        storage_root,
        [
            "--language",
            language,
            "app",
            "modelo",
            "work",
            "calculate",
            "--modelo",
            modelo,
            "--year",
            year,
            "--period",
            period,
        ],
    )
    calculation_output = _combined_output(calculated)
    assert calculated.returncode == 0, calculation_output
    revision_match = re.search(r"calculation_revision_id\t([0-9a-f]{64})", calculation_output)
    assert revision_match is not None, calculation_output
    return revision_match.group(1)


@pytest.mark.parametrize(
    (
        "language",
        "missing_option",
        "invalid_value",
        "draft_state",
        "formula_labels",
        "advisory_prefix",
        "next_action",
        "verified_state",
        "already_verified_phrase",
    ),
    [
        (
            "ca",
            "Falta l'opció '--modelo'.",
            "Valor no vàlid per a '--year': 'abc' no és un enter vàlid.",
            "Esborrany",
            ("resta(", "màxim(", "percentatge(", "condicional(", "mínim("),
            "la dependència entre períodes s'ha exclòs com a sense obligació prèvia",
            "Confirmeu que la data d'inici d'activitat registrada és correcta.",
            "Verificat complet",
            "no es pot verificar de nou",
        ),
        (
            "hu",
            "Hiányzó kapcsoló '--modelo'.",
            "Érvénytelen érték ehhez: '--year': 'abc' nem érvényes egész szám.",
            "Piszkozat",
            ("kivonás(", "maximum(", "százalék(", "feltételes(", "minimum("),
            "Az időszakok közötti függőséget előzetes kötelezettség hiánya miatt kizártuk",
            "Erősítse meg, hogy a rögzített tevékenységkezdési dátum helyes.",
            "Teljesen ellenorizve",
            "nem ellenőrizhető újra",
        ),
    ],
)
def test_selected_languages_cover_parser_calculation_and_verification_without_s147_leaks(
    tmp_path: Path,
    language: str,
    missing_option: str,
    invalid_value: str,
    draft_state: str,
    formula_labels: tuple[str, ...],
    advisory_prefix: str,
    next_action: str,
    verified_state: str,
    already_verified_phrase: str,
) -> None:
    """Exercise the real entrypoint and persisted M130 work for each selected locale."""
    storage_root = tmp_path / language
    root = ["--language", language]

    profile = _run_cli(
        storage_root,
        [
            *root,
            "config",
            "profile",
            "create",
            "operator",
            "--quiet",
            "--accept-defaults",
            "--entity-type",
            "natural_person",
            "--tax-id",
            "12345678Z",
            "--name",
            "Operator",
            "--surnames",
            "Locale",
            "--activity",
            "design",
            "--irpf-income-categories",
            "actividad_economica",
            "--activity-start-date",
            "2026-01-01",
        ],
    )
    assert profile.returncode == 0, _combined_output(profile)

    missing = _run_cli(
        storage_root,
        [*root, "app", "modelo", "work", "create", "--year", "2026", "--period", "1T"],
    )
    missing_output = _combined_output(missing)
    assert missing.returncode != 0, missing_output
    assert missing_option in missing_output
    assert "Usage:" not in missing_output
    assert "Missing option" not in missing_output

    invalid = _run_cli(
        storage_root,
        [
            *root,
            "app",
            "modelo",
            "work",
            "create",
            "--modelo",
            "130",
            "--year",
            "abc",
            "--period",
            "1T",
        ],
    )
    invalid_output = _combined_output(invalid)
    assert invalid.returncode != 0, invalid_output
    assert invalid_value in invalid_output
    assert "Invalid value" not in invalid_output
    assert "is not a valid integer" not in invalid_output

    created = _run_cli(
        storage_root,
        [
            *root,
            "app",
            "modelo",
            "work",
            "create",
            "--modelo",
            "130",
            "--year",
            "2026",
            "--period",
            "1T",
        ],
    )
    assert created.returncode == 0, _combined_output(created)

    calculated = _run_cli(
        storage_root,
        [
            *root,
            "app",
            "modelo",
            "work",
            "calculate",
            "--modelo",
            "130",
            "--year",
            "2026",
            "--period",
            "1T",
        ],
    )
    calculation_output = _combined_output(calculated)
    assert calculated.returncode == 0, calculation_output
    assert f"state\t{draft_state}" in calculation_output
    assert all(label in calculation_output for label in formula_labels)
    assert all(
        raw_operation not in calculation_output
        for raw_operation in ("subtract(", "max(", "percent(", "if_then_else(", "min(")
    )
    assert "borrador" not in calculation_output

    revision_match = re.search(r"calculation_revision_id\t([0-9a-f]{64})", calculation_output)
    assert revision_match is not None, calculation_output
    verification = _run_cli(
        storage_root,
        [*root, "app", "modelo", "work", "verify", revision_match.group(1)],
    )
    verification_output = _combined_output(verification)
    assert verification.returncode == 0, verification_output
    assert advisory_prefix in verification_output
    assert next_action in verification_output
    assert "cross-period dependency scoped out" not in verification_output
    assert "Confirm the recorded activity-start date" not in verification_output

    already_verified = _run_cli(
        storage_root,
        [*root, "app", "modelo", "work", "verify", revision_match.group(1)],
    )
    already_verified_output = _combined_output(already_verified)
    assert already_verified.returncode != 0, already_verified_output
    assert verified_state in already_verified_output
    assert already_verified_phrase in already_verified_output
    assert "verificado_completo" not in already_verified_output
    assert "verification requires borrador" not in already_verified_output


def test_cross_locale_verify_reuses_one_persisted_report_and_localizes_its_projection(tmp_path: Path) -> None:
    """One revision and actor retain their report identity across selected languages."""
    storage_root = tmp_path / "cross-locale-identity"
    revision_id = _create_modelo_revision(
        storage_root,
        "ca",
        modelo="130",
        year="2026",
        period="1T",
        activity_start_date="2026-01-01",
    )

    catalan = _run_cli(
        storage_root,
        ["--language", "ca", "app", "modelo", "work", "verify", revision_id],
    )
    catalan_output = _combined_output(catalan)
    assert catalan.returncode == 0, catalan_output
    catalan_id = re.search(r"verification_report_id\t([0-9a-f]{64})", catalan_output)
    assert catalan_id is not None, catalan_output

    hungarian = _run_cli(
        storage_root,
        [
            "--language",
            "hu",
            "app",
            "modelo",
            "verification-report",
            "view",
            catalan_id.group(1),
        ],
    )
    hungarian_output = _combined_output(hungarian)
    assert hungarian.returncode == 0, hungarian_output
    assert "la dependència entre períodes s'ha exclòs" in catalan_output
    assert "Az időszakok közötti függőséget" in hungarian_output
    assert "cross-period dependency scoped out" not in catalan_output
    assert "cross-period dependency scoped out" not in hungarian_output

    hungarian_id = re.search(r"verification_report_id\t([0-9a-f]{64})", hungarian_output)
    assert hungarian_id is not None, hungarian_output
    assert catalan_id.group(1) == hungarian_id.group(1)

    persisted = _persisted_report(storage_root, catalan_id.group(1))
    assert persisted["report_count"] == 1
    report = persisted["report"]
    assert isinstance(report, dict)
    finding = next(
        finding
        for finding in report["findings"]
        if finding["message"].startswith("cross-period dependency scoped out as no-prior-obligation")
    )
    assert "modelo=100 year=2025 period=0A origin=previous_filing_binding" in finding["message"]
    assert finding["next_action"].startswith("Confirm the recorded activity-start date is correct.")


def test_cross_locale_non_granted_m390_verify_reuses_one_report_for_one_draft(tmp_path: Path) -> None:
    """A non-granted draft can be verified in both languages without history drift."""
    storage_root = tmp_path / "cross-locale-non-granted"
    revision_id = _create_modelo_revision(
        storage_root,
        "ca",
        modelo="390",
        year="2025",
        period="0A",
        activity_start_date="2025-01-01",
    )

    catalan = _run_cli(
        storage_root,
        ["--language", "ca", "app", "modelo", "work", "verify", revision_id],
    )
    hungarian = _run_cli(
        storage_root,
        ["--language", "hu", "app", "modelo", "work", "verify", revision_id],
    )
    catalan_output = _combined_output(catalan)
    hungarian_output = _combined_output(hungarian)
    assert catalan.returncode == 1, catalan_output
    assert hungarian.returncode == 1, hungarian_output
    assert "granted_verificado_completo\tfalse" in catalan_output
    assert "granted_verificado_completo\tfalse" in hungarian_output
    assert "La dependència entre períodes no està neta" in catalan_output
    assert "Captureu o importeu evidència de l'AEAT" in catalan_output
    assert "Az időszakok közötti függőség nem tiszta" in hungarian_output
    assert "Rögzítse vagy importálja az AEAT bizonyítékot" in hungarian_output
    assert "cross-period dependency is not clean" not in catalan_output
    assert "cross-period dependency is not clean" not in hungarian_output
    assert "Capture/import AEAT evidence" not in catalan_output
    assert "Capture/import AEAT evidence" not in hungarian_output

    catalan_id = re.search(r"verification_report_id\t([0-9a-f]{64})", catalan_output)
    hungarian_id = re.search(r"verification_report_id\t([0-9a-f]{64})", hungarian_output)
    assert catalan_id is not None, catalan_output
    assert hungarian_id is not None, hungarian_output
    assert catalan_id.group(1) == hungarian_id.group(1)

    persisted = _persisted_report(storage_root, catalan_id.group(1))
    assert persisted["report_count"] == 1
