"""Real selected-language CLI coverage for the selected-language continuity repairs."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import textwrap
from collections.abc import Generator
from contextlib import ExitStack
from contextvars import ContextVar
from pathlib import Path

import pytest

from cadrumo.core.type_adapters import STR_KEYED_MAPPING_ADAPTER
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.authority_location import bundled_authority_descriptor_path
from cadrumo.tests.installed_process_ports import InstalledProcessWorld
from cadrumo.tests.os_keychain_hook import require_os_credential_store
from cadrumo.tests.subprocess_cli import run_subprocess_cli_harness

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

with bundled_indexed_authority().operation() as _operation:
    _FILING_YEAR = _operation.supported_filing_years().horizon
_PRIOR_YEAR = _FILING_YEAR - 1

_CLI_HARNESS = """
from __future__ import annotations

import os
import sys

os.environ["CADRUMO_STORAGE_ROOT"] = sys.argv[1]
sys.argv = ["aeat", *sys.argv[2:]]

from cadrumo_runtime.host.frontend.cli.bootstrap import main

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

os.environ["CADRUMO_STORAGE_ROOT"] = sys.argv[1]

from cadrumo.adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from cadrumo.adapters.persistence.storage.master_key.active_session import current_active_bucket_session, session_serves_bucket
from cadrumo.application.user_profile.login_session import authenticate_profile_for_invocation
from cadrumo.adapters.persistence.storage.profile_persistence_composition import composed_profile_persistence_ports
from cadrumo.core.bucket_pointer import resolve_active_bucket_id
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority

bucket_id = resolve_active_bucket_id()
assert bucket_id is not None
with composed_profile_persistence_ports(), bundled_indexed_authority().operation() as operation:
    authenticate_profile_for_invocation(
        name="operator",
        passphrase_callback=lambda: "s423-selected-language-secret",
        profile_decode_context=operation.profile_decode_context(),
    )
    assert session_serves_bucket(current_active_bucket_session(), bucket_id)
    catalogue = VerificationReportCatalogueRepository(bucket_id=bucket_id).load()
report = catalogue.get(sys.argv[2])
assert report is not None
print(json.dumps({"report": report.model_dump(mode="json"), "report_count": len(catalogue)}, sort_keys=True))
"""


# The activity of the profile began before the quarter, so Modelo 130 box 13 reads the
# prior year's net activity income (art. 110.3.c RIRPF). The prior Modelo 100 is recorded
# above the highest ceiling the box 13 formula tests, so the minoracion is a proven zero.
_PRIOR_YEAR_RENTA_HARNESS = """
from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from decimal import Decimal

os.environ["CADRUMO_STORAGE_ROOT"] = sys.argv[1]

from cadrumo.adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from cadrumo.adapters.persistence.storage.profile_persistence_composition import composed_profile_persistence_ports
from cadrumo.application.user_profile.login_session import authenticate_profile_for_invocation
from cadrumo.core.bucket_pointer import resolve_active_bucket_id
from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.bindings import RegistryModeloObservation
from cadrumo.domain.calculations.registry.tests.registry_observations import (
    registry_grounded_observations,
    revision_id_for_observation,
)

modelo, filing_year, period = sys.argv[2], int(sys.argv[3]), sys.argv[4]
binding_id = "irpf.previous_year_economic_activity_net_income"
bucket_id = resolve_active_bucket_id()
assert bucket_id is not None
with composed_profile_persistence_ports(), bundled_indexed_authority().operation() as operation:
    authenticate_profile_for_invocation(
        name="operator",
        passphrase_callback=lambda: "s423-selected-language-secret",
        profile_decode_context=operation.profile_decode_context(),
    )
    snapshot = operation.snapshot(modelo, filing_year=filing_year, period=period)
    (formula,) = (item for item in snapshot.revision.formulas if item.target_casilla_id == "13")
    ceilings = []

    def collect(expression):
        if expression.op == "less_equal" and any(arg.binding == binding_id for arg in expression.args):
            ceilings.extend(arg.literal for arg in expression.args if arg.literal is not None)
        for arg in expression.args:
            collect(arg)

    collect(formula.expression)
    (binding,) = (item for item in snapshot.revision.bindings if item.id == binding_id)
    source_casillas = binding.provider.source_casilla_ids
    values = dict.fromkeys((validated_casilla_id(box) for box in source_casillas[1:]), Decimal("0.00"))
    values[validated_casilla_id(source_casillas[0])] = max(ceilings) + Decimal("1000.00")
    observation = RegistryModeloObservation(
        modelo="100",
        filing_year=filing_year - 1,
        period="0A",
        observations=registry_grounded_observations(
            modelo="100", filing_year=filing_year - 1, period="0A", casilla_values=values
        ),
    )
    repository = CalculationObservationRepository(bucket_id=bucket_id)
    repository.save(
        repository.prepare_observation_envelope(
            observation,
            source_kind="app_filing",
            captured_at=datetime(filing_year, 1, 15, 12, 0, tzinfo=UTC),
            result_disposition=None,
            filing_kind=None,
            stamped_revision_id=revision_id_for_observation(observation),
        )
    )
"""


_OPERATOR_CREDENTIAL_INPUT = "s423-selected-language-secret"
_RUNTIME_SCOPE: ContextVar[tuple[ExitStack, set[Path]] | None] = ContextVar("selected-language-runtime", default=None)


@pytest.fixture(autouse=True)
def _owned_runtime_lifetime(*, installed_process_world: InstalledProcessWorld) -> Generator[None]:
    """Own only the native runtimes required by this test's private commands."""
    with ExitStack() as stack:
        roots: set[Path] = set()
        token = _RUNTIME_SCOPE.set((stack, roots))
        try:
            yield
        finally:
            try:
                for root in roots:
                    logout = _run_cli(
                        root, ["--format", "json", "config", "logout"], installed_process_world=installed_process_world
                    )
                    assert logout.returncode == 0, _combined_output(logout)
            finally:
                _RUNTIME_SCOPE.reset(token)


def _serve_profile_root(storage_root: Path, *, installed_process_world: InstalledProcessWorld) -> None:
    scope = _RUNTIME_SCOPE.get()
    assert scope is not None
    stack, roots = scope
    if storage_root in roots:
        return
    scripts = Path(sys.prefix) / ("Scripts" if sys.platform == "win32" else "bin")
    executable = scripts / ("aeat.exe" if sys.platform == "win32" else "aeat")
    storage_root.mkdir(parents=True, exist_ok=True)
    stack.enter_context(
        installed_process_world.runtime(
            executable,
            installed_process_world.environment(
                storage_root=storage_root, authority_root=bundled_authority_descriptor_path().parent
            ),
            storage_root.parent / "caller-owned-runtime.log",
        )
    )
    roots.add(storage_root)


def _run_cli(
    storage_root: Path,
    args: list[str],
    *,
    stdin_payload: str | None = None,
    installed_process_world: InstalledProcessWorld,
) -> subprocess.CompletedProcess[str]:
    # `config profile create` mints a custody envelope, so it needs the operator
    # passphrase, and a subprocess is not a terminal -- the bounded strict-JSON
    # channel on stdin is the only one it accepts. Supplied here rather than at
    # each call site so a new create invocation cannot forget it.
    creates_profile = "profile" in args and "create" in args
    if creates_profile:
        _serve_profile_root(storage_root, installed_process_world=installed_process_world)
    if creates_profile and "--secrets-stdin" not in args:
        args = [*args, "--secrets-stdin"]
        stdin_payload = stdin_payload or _CREATE_SECRETS
    completed = run_subprocess_cli_harness(
        textwrap.dedent(_CLI_HARNESS),
        [str(storage_root), *args],
        env_strip_prefixes=("AEAT_",),
        cwd=Path.cwd(),
        stdin_payload=stdin_payload,
        timeout=None,
    )
    if creates_profile and completed.returncode == 0:
        login = _run_cli(
            storage_root,
            ["--format", "json", "config", "login", "operator", "--secrets-stdin"],
            stdin_payload=json.dumps({"passphrase": _OPERATOR_CREDENTIAL_INPUT}),
            installed_process_world=installed_process_world,
        )
        assert login.returncode == 0, _combined_output(login)
        document = json.loads(login.stdout)
        assert document["result"]["session_persisted"] is True
        setup = _run_cli(
            storage_root,
            ["--format", "json", "config", "profile", "complete-setup"],
            installed_process_world=installed_process_world,
        )
        assert setup.returncode == 0, _combined_output(setup)
    return completed


#: `config profile create` mints a custody envelope, so it needs the operator
#: passphrase AND its confirmation. A subprocess is not a terminal, so the only
#: channel it accepts is the bounded strict-JSON one on stdin.
_CREATE_SECRETS = json.dumps(
    {"passphrase": _OPERATOR_CREDENTIAL_INPUT, "passphrase_confirmation": _OPERATOR_CREDENTIAL_INPUT}
)


def _combined_output(result: subprocess.CompletedProcess[str]) -> str:
    return f"{result.stdout}\n{result.stderr}"


def _persisted_report(storage_root: Path, verification_report_id: str) -> dict[str, object]:
    result = run_subprocess_cli_harness(
        textwrap.dedent(_PERSISTED_REPORT_HARNESS),
        [str(storage_root), verification_report_id],
        env_strip_prefixes=("AEAT_",),
        cwd=Path.cwd(),
        timeout=None,
    )
    assert result.returncode == 0, _combined_output(result)
    return STR_KEYED_MAPPING_ADAPTER.validate_json(result.stdout)


def _create_modelo_revision(
    storage_root: Path,
    language: str,
    *,
    modelo: str,
    year: str,
    period: str,
    activity_start_date: str,
    record_prior_year_renta: bool = False,
    installed_process_world: InstalledProcessWorld,
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
            "--tax-residence-jurisdiction-scope",
            "common_regime",
            "--iva-regime",
            "GENERAL",
            "--iva-m303-regime-composition",
            "general",
            "--no-iva-redeme-enrolled",
            "--no-iva-cash-accounting-regime-enrolled",
            "--no-iva-voluntary-sii-enrolled",
            "--no-iva-hydrocarbon-deposit-advance-payment-deduction-entitled",
            "--irpf-income-categories",
            "actividad_economica",
            "--irpf-estimation-regime",
            "directa_simplificada",
            "--activity-start-date",
            activity_start_date,
        ],
        installed_process_world=installed_process_world,
    )
    assert profile.returncode == 0, _combined_output(profile)
    if record_prior_year_renta:
        recorded = run_subprocess_cli_harness(
            textwrap.dedent(_PRIOR_YEAR_RENTA_HARNESS),
            [str(storage_root), modelo, year, period],
            env_strip_prefixes=("AEAT_",),
            cwd=Path.cwd(),
            timeout=None,
        )
        assert recorded.returncode == 0, _combined_output(recorded)
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
        installed_process_world=installed_process_world,
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
        installed_process_world=installed_process_world,
    )
    calculation_output = _combined_output(calculated)
    assert calculated.returncode == 0, calculation_output
    revision_match = re.search(r"calculation_revision_id\t([0-9a-f]{64})", calculation_output)
    assert revision_match is not None, calculation_output
    revision_id = revision_match.group(1)
    assert isinstance(revision_id, str)
    return revision_id


@pytest.mark.parametrize(
    "language,missing_option,invalid_value",
    [
        ("ca", "Falta l'opci", "Valor no v"),
        ("hu", "kapcsol", "ehhez: '--year'"),
    ],
)
def test_selected_languages_render_parser_refusals_without_keychain(
    tmp_path: Path,
    language: str,
    missing_option: str,
    invalid_value: str,
    *,
    installed_process_world: InstalledProcessWorld,
) -> None:
    storage_root = tmp_path / language
    root = ["--language", language]
    missing = _run_cli(
        storage_root,
        [*root, "app", "modelo", "work", "create", "--year", str(_FILING_YEAR), "--period", "1T"],
        installed_process_world=installed_process_world,
    )
    invalid = _run_cli(
        storage_root,
        [*root, "app", "modelo", "work", "create", "--modelo", "130", "--year", "abc", "--period", "1T"],
        installed_process_world=installed_process_world,
    )
    assert missing.returncode != 0 and missing_option in _combined_output(missing)
    assert invalid.returncode != 0 and invalid_value in _combined_output(invalid)


@pytest.mark.os_keychain
@pytest.mark.parametrize(
    (
        "language",
        "missing_option",
        "invalid_value",
        "draft_state",
        "formula_labels",
        "advisory_prefix",
        "already_verified_phrase",
    ),
    [
        (
            "ca",
            "Falta l'opció '--modelo'.",
            "Valor no vàlid per a '--year': 'abc' no és un enter vàlid.",
            "Esborrany",
            ("resta(", "màxim(", "percentatge(", "condicional(", "mínim("),
            f"El model 100 de {_PRIOR_YEAR}, període 0A, no es fa servir aquí",
            "ja està comprovat",
        ),
        (
            "hu",
            "Hiányzó kapcsoló '--modelo'.",
            "Érvénytelen érték ehhez: '--year': 'abc' nem érvényes egész szám.",
            "Piszkozat",
            ("kivonás(", "maximum(", "százalék(", "feltételes(", "minimum("),
            f"A Modelo 100 ({_PRIOR_YEAR}, 0A időszak) itt nincs felhasználva",
            "már ellenőrzött",
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
    already_verified_phrase: str,
    *,
    installed_process_world: InstalledProcessWorld,
) -> None:
    """Exercise the real entrypoint and persisted M130 work for each selected locale."""
    storage_root = tmp_path / language
    root = ["--language", language]

    # Parser refusals need no profile, so they are proven before the expensive setup.
    missing = _run_cli(
        storage_root,
        [*root, "app", "modelo", "work", "create", "--year", str(_FILING_YEAR), "--period", "1T"],
        installed_process_world=installed_process_world,
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
        installed_process_world=installed_process_world,
    )
    invalid_output = _combined_output(invalid)
    assert invalid.returncode != 0, invalid_output
    assert invalid_value in invalid_output
    assert "Invalid value" not in invalid_output
    assert "is not a valid integer" not in invalid_output

    # Every later invocation resumes the profile session from the OS credential
    # store; refuse before paying for profile creation on a host that has none.
    require_os_credential_store()
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
            "--tax-residence-jurisdiction-scope",
            "common_regime",
            "--iva-regime",
            "GENERAL",
            "--iva-m303-regime-composition",
            "general",
            "--no-iva-redeme-enrolled",
            "--no-iva-cash-accounting-regime-enrolled",
            "--no-iva-voluntary-sii-enrolled",
            "--no-iva-hydrocarbon-deposit-advance-payment-deduction-entitled",
            "--irpf-income-categories",
            "actividad_economica",
            "--irpf-estimation-regime",
            "directa_simplificada",
            "--activity-start-date",
            f"{_FILING_YEAR}-01-01",
        ],
        installed_process_world=installed_process_world,
    )
    assert profile.returncode == 0, _combined_output(profile)

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
            str(_FILING_YEAR),
            "--period",
            "1T",
        ],
        installed_process_world=installed_process_world,
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
            str(_FILING_YEAR),
            "--period",
            "1T",
        ],
        installed_process_world=installed_process_world,
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
        installed_process_world=installed_process_world,
    )
    verification_output = _combined_output(verification)
    assert verification.returncode == 0, verification_output
    assert advisory_prefix in verification_output, verification_output
    assert "cross-period dependency scoped out" not in verification_output
    assert "Confirm the recorded activity-start date" not in verification_output

    # Re-verifying an already-verified revision is a guarded idempotent no-op
    # (aeat-cli-contract): the verb returns exit 0
    # with the existing report and a localized idempotent-no-op notice, never the
    # old refusal. The raw enum token and the retired refusal phrase must not leak.
    already_verified = _run_cli(
        storage_root,
        [*root, "app", "modelo", "work", "verify", revision_match.group(1)],
        installed_process_world=installed_process_world,
    )
    already_verified_output = _combined_output(already_verified)
    assert already_verified.returncode == 0, already_verified_output
    assert already_verified_phrase in already_verified_output, already_verified_output
    assert "state\tverificado_completo" not in already_verified_output
    assert "verification requires borrador" not in already_verified_output


@pytest.mark.os_keychain
def test_cross_locale_verify_reuses_one_persisted_report_and_localizes_its_projection(
    tmp_path: Path, *, installed_process_world: InstalledProcessWorld
) -> None:
    """One revision and actor retain their report identity across selected languages."""
    # Every later invocation resumes the profile session from the OS credential
    # store; refuse before paying for profile creation on a host that has none.
    require_os_credential_store()
    storage_root = tmp_path / "cross-locale-identity"
    revision_id = _create_modelo_revision(
        storage_root,
        "ca",
        modelo="130",
        year=str(_FILING_YEAR),
        period="1T",
        activity_start_date=f"{_FILING_YEAR}-01-01",
        installed_process_world=installed_process_world,
    )

    catalan = _run_cli(
        storage_root,
        ["--language", "ca", "app", "modelo", "work", "verify", revision_id],
        installed_process_world=installed_process_world,
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
        installed_process_world=installed_process_world,
    )
    hungarian_output = _combined_output(hungarian)
    assert hungarian.returncode == 0, hungarian_output
    assert f"El model 100 de {_PRIOR_YEAR}, període 0A, no es fa servir aquí" in catalan_output, catalan_output
    assert f"A Modelo 100 ({_PRIOR_YEAR}, 0A időszak) itt nincs felhasználva" in hungarian_output, hungarian_output
    assert "cross-period dependency scoped out" not in catalan_output
    assert "cross-period dependency scoped out" not in hungarian_output

    hungarian_id = re.search(r"verification_report_id\t([0-9a-f]{64})", hungarian_output)
    assert hungarian_id is not None, hungarian_output
    assert catalan_id.group(1) == hungarian_id.group(1)

    persisted = _persisted_report(storage_root, catalan_id.group(1))
    assert persisted["report_count"] == 1
    raw_report = persisted["report"]
    assert isinstance(raw_report, dict)
    report: dict[str, object] = {key: value for key, value in raw_report.items() if isinstance(key, str)}
    assert len(report) == len(raw_report)
    raw_findings = report["findings"]
    assert isinstance(raw_findings, list)
    typed_findings: list[dict[str, object]] = []
    for raw_finding in raw_findings:
        assert isinstance(raw_finding, dict)
        finding_values = {key: value for key, value in raw_finding.items() if isinstance(key, str)}
        assert len(finding_values) == len(raw_finding)
        typed_findings.append(finding_values)

    # The stored report carries language-neutral message identity and typed facts;
    # selected-language prose is rendered only when the report is viewed.
    findings = [
        candidate
        for candidate in typed_findings
        if candidate.get("message_locale_key")
        == "application.modelo.findings.cross_period_operator_declared_suppression"
    ]
    assert len(findings) == 1, typed_findings
    finding = findings[0]
    assert finding["message_facts"] == {
        "source_modelo": "100",
        "source_filing_year": _PRIOR_YEAR,
        "source_period": "0A",
        "origin_code": "previous_filing_binding",
        "activity_start_date": f"{_FILING_YEAR}-01-01",
    }
    assert "message" not in finding
    assert "next_action" not in finding


@pytest.mark.os_keychain
def test_cross_locale_non_granted_verify_reuses_one_report_for_one_draft(
    tmp_path: Path, *, installed_process_world: InstalledProcessWorld
) -> None:
    """A non-granted draft can be verified in both languages without history drift."""
    # Every later invocation resumes the profile session from the OS credential
    # store; refuse before paying for profile creation on a host that has none.
    require_os_credential_store()
    storage_root = tmp_path / "cross-locale-non-granted"
    revision_id = _create_modelo_revision(
        storage_root,
        "ca",
        modelo="130",
        year=str(_FILING_YEAR),
        period="1T",
        activity_start_date="2020-01-01",
        record_prior_year_renta=True,
        installed_process_world=installed_process_world,
    )

    catalan = _run_cli(
        storage_root,
        ["--language", "ca", "app", "modelo", "work", "verify", revision_id],
        installed_process_world=installed_process_world,
    )
    hungarian = _run_cli(
        storage_root,
        ["--language", "hu", "app", "modelo", "work", "verify", revision_id],
        installed_process_world=installed_process_world,
    )
    catalan_output = _combined_output(catalan)
    hungarian_output = _combined_output(hungarian)
    assert catalan.returncode == 1, catalan_output
    assert hungarian.returncode == 1, hungarian_output
    assert "granted_verificado_completo\tfalse" in catalan_output
    assert "granted_verificado_completo\tfalse" in hungarian_output
    assert f"Aquesta declaració fa servir dades del model 100 de {_PRIOR_YEAR}, període 0A" in catalan_output, (
        catalan_output
    )
    assert "Resol-les allà primer." in catalan_output, catalan_output
    assert f"Ez a bevallás a Modelo 100 ({_PRIOR_YEAR}, 0A időszak) adatait használja" in hungarian_output, (
        hungarian_output
    )
    assert "Előbb ott oldd meg őket." in hungarian_output, hungarian_output
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
