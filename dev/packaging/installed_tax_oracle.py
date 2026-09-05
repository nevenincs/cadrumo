"""Run a grounded tax calculation through an installed Cadrumo CLI.

This probe is intentionally stdlib-only and imports no Cadrumo modules. It drives
the public ``aeat`` executable, uses fresh encrypted storage, and validates both
the calculation response and the persisted public observation surface.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import sys
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Final

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if not __package__:
    __package__ = "dev.packaging"

from ._command import CommandResult, run_command  # noqa: E402
from ._installed_wheel_binding import installed_wheel_payload_sha256  # noqa: E402
from ._recovery_enrollment import enrolled_profile_creation  # noqa: E402

_UTF_8: Final[str] = "utf-8"
_JSON_FORMAT: Final[tuple[str, ...]] = ("--format", "json")

PROFILE_LABEL = "installed-oracle"
PROFILE_TAX_ID = "B66012345"
MODEL = "200"
YEAR = "2024"
PERIOD = "0A"
REGISTRY_REVISION = "2024"
TARGET_CASILLA = "DP200014:00562"
EXPECTED_VALUE = Decimal("23000.00")
EXPECTED_FORMULA = "modelo-200-cuota-integra"
EXPECTED_LEGAL_REF = "ley-27-2014:art-29"
EXPECTED_SOURCE_REF = "aeat-modelo-200-manual-2024"
EXPECTED_NOTICE_CODES = {"modelo.work.calculate.plazo_vencido_unassessed_preview"}
_REVISION_ID = re.compile(r"^[0-9a-f]{64}$")

CASILLAS = (
    "00501=100000.00",
    "DP200013:00417=0.00",
    "DP200013:00418=0.00",
    "01032=0.00",
    "DP200014:00547=0.00",
    "DP200014:01033=0.00",
    "DP200014:01034=0.00",
)
BINDINGS = (
    "modelo-200-2024-profile-legal-entity-form=sl",
    "modelo-200-2024-profile-new-entity-flag=0",
    "modelo-200-2024-profile-incn-prior-12-months=500000",
    "modelo-200-2024-profile-tributacion-estado-porcentaje=100",
    "modelo-200-2024-bin-pendiente-ejercicios-anteriores=0",
    "modelo-200-2024-dotaciones-deterioro-creditos-saldo-no-cumplido-anteriores=0",
    "modelo-200-2024-dotaciones-deterioro-creditos-saldo-cumplido-anteriores=0",
)
RELATIONS = (
    "modelo-200-2024-rel-202-pagos-fraccionados=0",
    "modelo-200-2024-rel-202-pagos-fraccionados-40-2=0",
)


class InstalledTaxOracleError(RuntimeError):
    """Raised when installed CLI behavior does not satisfy the release oracle."""


@dataclass(frozen=True)
class InstalledTaxEvidence:
    """Evidence proving installed CLI calculation and persistence behavior."""

    requested_executable: str
    resolved_executable: str
    version_output: str
    cohort_source_commit: str
    cohort_manifest_sha256: str
    cohort_root_wheel_sha256: str
    executable_sha256: str
    installed_wheel_payload_sha256: str
    storage_root: str
    work_unit_id: str
    calculation_revision_id: str
    target_casilla: str
    target_value: str
    formula_id: str
    legal_refs: tuple[str, ...]
    source_refs: tuple[str, ...]
    notice_codes: tuple[str, ...]
    checkout_imports_removed: bool
    ambient_product_executables_removed: bool
    commands: tuple[CommandResult, ...]

    def to_jsonable(self) -> dict[str, Any]:
        """Return a JSON-compatible evidence mapping."""
        document = asdict(self)
        document["commands"] = [
            {
                "argv": list(command.argv),
                "cwd": command.cwd,
                "started_at": command.started_at.isoformat(),
                "completed_at": command.completed_at.isoformat(),
                "duration_seconds": command.duration_seconds,
                "returncode": command.returncode,
                "stdout": command.stdout,
                "stderr": command.stderr,
            }
            for command in self.commands
        ]
        return document


def checkout_imports_removed(environment: Mapping[str, str]) -> bool:
    """True when the isolated environment carries no checkout import path.

    The oracle drives an installed executable and must not let the source
    checkout leak onto the child's import path; :func:`isolated_product_environment`
    strips ``PYTHONPATH``/``PYTHONHOME`` for exactly that reason. This reads the
    fact back off the real environment so the emitted evidence records what
    isolation actually held rather than asserting it unconditionally.
    """
    return "PYTHONPATH" not in environment and "PYTHONHOME" not in environment


def ambient_product_executables_removed(environment: Mapping[str, str]) -> bool:
    """True when no ambient product CLI can shadow the absolute tested CLI."""
    return shutil.which("aeat", path=environment.get("PATH", "")) is None


def isolated_product_environment(storage_root: Path) -> dict[str, str]:
    """Build an isolated product environment without inherited Cadrumo state."""
    resolved_root = storage_root.resolve()
    resolved_root.mkdir(parents=True, exist_ok=True)
    environment = {key: value for key, value in os.environ.items() if not key.startswith("CADRUMO_")}
    environment.pop("PYTHONHOME", None)
    environment.pop("PYTHONPATH", None)
    environment.update(
        {
            "CADRUMO_CLI_REVEAL_IDENTIFIERS": "1",
            "CADRUMO_LOCAL_STORAGE_ROOT": str(resolved_root),
            "CADRUMO_OUTPUT_LANGUAGE": "en",
            # Packaging oracles use an isolated disposable root and explicitly
            # select the non-keychain test posture. This avoids host keyring
            # prompts without reviving the retired file-backend contract.
            "CADRUMO_SECRET_STORE_BACKEND": "unsecured",
            "PYTHONIOENCODING": _UTF_8,
        },
    )
    return environment


def profile_create_arguments() -> tuple[str, ...]:
    """Return the public profile-creation argument sequence."""
    return (
        "config",
        "profile",
        "create",
        PROFILE_LABEL,
        "--quiet",
        "--accept-defaults",
        "--entity-type",
        "legal_entity",
        "--legal-entity-form",
        "sl",
        "--tax-id",
        PROFILE_TAX_ID,
        "--legal-name",
        "Installed Oracle SL",
        "--activity",
        "software services",
        "--incn-prior-12-months",
        "500000",
        "--no-new-entity-first-two-profit-periods",
        "--iva-regime",
        "GENERAL",
        "--tax-residence-ccaa",
        "madrid",
    )


def work_create_arguments() -> tuple[str, ...]:
    """Return the public work-unit creation argument sequence."""
    return (
        "app",
        "modelo",
        "work",
        "create",
        "--modelo",
        MODEL,
        "--year",
        YEAR,
        "--period",
        PERIOD,
        "--revision",
        REGISTRY_REVISION,
        "--name",
        "Installed Modelo 200 oracle",
        "--by",
        "installed-tax-oracle",
    )


def work_calculate_arguments(work_unit_id: str) -> tuple[str, ...]:
    """Return the public calculation arguments for the created work unit."""
    arguments = [
        "app",
        "modelo",
        "work",
        "calculate",
        work_unit_id,
    ]
    for value in CASILLAS:
        arguments.extend(("--casilla", value))
    for value in BINDINGS:
        arguments.extend(("--binding", value))
    for value in RELATIONS:
        arguments.extend(("--relation", value))
    arguments.extend(("--by", "installed-tax-oracle"))
    return tuple(arguments)


def _run(
    argv: tuple[str, ...],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout_seconds: float,
    input_text: str | None = None,
    inherited_descriptors: tuple[int, ...] = (),
) -> CommandResult:
    result = run_command(
        argv,
        cwd=cwd,
        environment=env,
        timeout_seconds=timeout_seconds,
        input_text=input_text,
        inherited_descriptors=inherited_descriptors,
    )
    if result.returncode != 0:
        raise InstalledTaxOracleError(
            f"installed command failed ({result.returncode}): {argv!r}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
    return result


def assert_envelope_contract(
    envelope: Mapping[str, Any],
    *,
    command: str,
    error: Callable[[str], Exception],
) -> dict[str, Any]:
    """Assert the canonical envelope spine of one delivered command, returning its result.

    Every delivery oracle acquires its envelope over a different transport but
    then checks the same contract: the envelope names the command it was asked
    for, reports a non-failing status, ran under the expected active profile,
    and carries an object result beside a notices list. Acquisition stays with
    the caller; ``error`` builds the caller's own refusal so each oracle keeps
    reporting failures in its own type.
    """
    if envelope.get("command") != command:
        raise error(f"expected command {command!r}, got {envelope.get('command')!r}")
    if envelope.get("status") not in {"success", "warning"}:
        raise error(f"{command} did not succeed: {envelope!r}")
    if envelope.get("active_profile") != PROFILE_LABEL:
        raise error(f"{command} used active profile {envelope.get('active_profile')!r}")
    result = envelope.get("result")
    if not isinstance(result, dict):
        raise error(f"{command} result is not an object")
    if not isinstance(envelope.get("notices"), list):
        raise error(f"{command} notices are not a list")
    return result


def assert_no_diagnostic_notices(
    envelope: Mapping[str, Any],
    *,
    command: str,
    error: Callable[[str], Exception],
) -> None:
    """Assert a delivered command reported plain success and raised no diagnostic notice."""
    if envelope.get("status") != "success":
        raise error(f"{command} expected success status: {envelope!r}")
    diagnostics = [
        notice
        for notice in envelope["notices"]
        if isinstance(notice, dict) and notice.get("severity") in {"warning", "error"}
    ]
    if diagnostics:
        raise error(f"{command} emitted unexpected diagnostic notices: {diagnostics!r}")


def _json_envelope(evidence: CommandResult, *, expected_command: str) -> dict[str, Any]:
    try:
        document = json.loads(evidence.stdout)
    except json.JSONDecodeError as exc:
        raise InstalledTaxOracleError(
            f"{expected_command} did not emit one JSON document: {evidence.stdout!r}",
        ) from exc
    if not isinstance(document, dict):
        raise InstalledTaxOracleError(f"{expected_command} emitted a non-object JSON document")
    assert_envelope_contract(document, command=expected_command, error=InstalledTaxOracleError)
    return document


def _assert_no_diagnostic_notices(document: dict[str, Any], *, command: str) -> None:
    assert_no_diagnostic_notices(document, command=command, error=InstalledTaxOracleError)


def create_installed_profile(
    cli: Path,
    *,
    cwd: Path,
    environment: dict[str, str],
    passphrase: str,
    timeout_seconds: float,
) -> CommandResult:
    """Create the oracle's profile, completing the mandatory recovery enrollment.

    Creation refuses outright without a channel to hand the recovery phrase
    over and read the exact phrase back, so the oracle plays the operator's
    part rather than asking the product to skip a possession proof. Everything
    the oracle asserts afterwards depends on this profile existing, so a
    refusal here is raised, never carried forward.
    """
    with enrolled_profile_creation(
        cli=cli,
        arguments=(*_JSON_FORMAT, *profile_create_arguments(), "--secrets-stdin"),
    ) as invocation:
        return _run(
            invocation.argv,
            cwd=cwd,
            env=environment,
            timeout_seconds=timeout_seconds,
            input_text=json.dumps(
                {"passphrase": passphrase, "passphrase_confirmation": passphrase},
                separators=(",", ":"),
            ),
            inherited_descriptors=invocation.inherited_descriptors,
        )


def assert_grounded_observations(
    observations_result: dict[str, Any],
    *,
    calculation_revision_id: str,
    work_unit_id: str,
) -> dict[str, Any]:
    """Validate the persisted public observations against the legal oracle."""
    if observations_result.get("calculation_revision_id") != calculation_revision_id:
        raise InstalledTaxOracleError("persisted observations resolve a different calculation revision")
    if observations_result.get("work_unit_id") != work_unit_id:
        raise InstalledTaxOracleError("persisted observations resolve a different work unit")
    observations = observations_result.get("observations")
    if not isinstance(observations, list) or not observations:
        raise InstalledTaxOracleError("persisted calculation has no observations")
    ungrounded = [
        observation
        for observation in observations
        if not observation.get("legal_refs") or not observation.get("source_refs")
    ]
    if ungrounded:
        raise InstalledTaxOracleError(
            f"{len(ungrounded)} persisted observations lack legal or source grounding",
        )
    targets = [observation for observation in observations if observation.get("casilla_id") == TARGET_CASILLA]
    if len(targets) != 1:
        raise InstalledTaxOracleError(
            f"expected one {TARGET_CASILLA} observation, got {len(targets)}",
        )
    target = targets[0]
    if Decimal(str(target.get("value"))) != EXPECTED_VALUE:
        raise InstalledTaxOracleError(
            f"{TARGET_CASILLA} expected {EXPECTED_VALUE}, got {target.get('value')!r}",
        )
    if target.get("formula_id") != EXPECTED_FORMULA:
        raise InstalledTaxOracleError(
            f"{TARGET_CASILLA} expected formula {EXPECTED_FORMULA!r}, got {target.get('formula_id')!r}",
        )
    if EXPECTED_LEGAL_REF not in target["legal_refs"]:
        raise InstalledTaxOracleError(
            f"{TARGET_CASILLA} does not cite {EXPECTED_LEGAL_REF!r}",
        )
    if EXPECTED_SOURCE_REF not in target["source_refs"]:
        raise InstalledTaxOracleError(
            f"{TARGET_CASILLA} does not cite {EXPECTED_SOURCE_REF!r}",
        )
    return target


def run_installed_tax_oracle(
    cli: Path,
    *,
    storage_root: Path,
    work_dir: Path,
    cohort_source_commit: str,
    cohort_manifest_sha256: str,
    cohort_root_wheel_sha256: str,
    timeout_seconds: float = 180.0,
) -> InstalledTaxEvidence:
    """Execute the complete installed CLI oracle and return retained evidence."""
    requested_cli = cli.expanduser()
    resolved_cli = requested_cli.resolve(strict=True)
    if not resolved_cli.is_file():
        raise InstalledTaxOracleError(f"installed CLI is not a file: {resolved_cli}")
    executable_sha256 = hashlib.sha256(resolved_cli.read_bytes()).hexdigest()
    installed_payload_sha256 = installed_wheel_payload_sha256(resolved_cli)
    resolved_work_dir = work_dir.resolve()
    resolved_work_dir.mkdir(parents=True, exist_ok=True)
    environment = isolated_product_environment(storage_root)
    base = (str(resolved_cli), *_JSON_FORMAT)
    authenticated_base = (*base, "--profile-secrets-stdin")
    passphrase = secrets.token_urlsafe(32)
    profile_authentication = json.dumps({"profile_passphrase": passphrase}, separators=(",", ":"))
    commands: list[CommandResult] = []

    version = _run(
        (str(resolved_cli), "--version"),
        cwd=resolved_work_dir,
        env=environment,
        timeout_seconds=timeout_seconds,
    )
    commands.append(version)

    profile = create_installed_profile(
        resolved_cli,
        cwd=resolved_work_dir,
        environment=environment,
        passphrase=passphrase,
        timeout_seconds=timeout_seconds,
    )
    commands.append(profile)
    profile_document = _json_envelope(profile, expected_command="config.profile.create")
    _assert_no_diagnostic_notices(profile_document, command="config.profile.create")

    create = _run(
        (*authenticated_base, *work_create_arguments()),
        cwd=resolved_work_dir,
        env=environment,
        timeout_seconds=timeout_seconds,
        input_text=profile_authentication,
    )
    commands.append(create)
    create_document = _json_envelope(create, expected_command="modelo.work.create")
    _assert_no_diagnostic_notices(create_document, command="modelo.work.create")
    work_unit_id = str(create_document["result"].get("work_unit_id", ""))
    if not _REVISION_ID.fullmatch(work_unit_id):
        raise InstalledTaxOracleError(f"work creation returned an invalid work unit id: {work_unit_id!r}")

    calculate = _run(
        (*authenticated_base, *work_calculate_arguments(work_unit_id)),
        cwd=resolved_work_dir,
        env=environment,
        timeout_seconds=timeout_seconds,
        input_text=profile_authentication,
    )
    commands.append(calculate)
    calculate_document = _json_envelope(calculate, expected_command="modelo.work.calculate")
    result = calculate_document["result"]
    if result.get("saved") is not True:
        raise InstalledTaxOracleError("calculation did not report saved=true")
    calculation_revision_id = str(result.get("calculation_revision_id", ""))
    if not _REVISION_ID.fullmatch(calculation_revision_id):
        raise InstalledTaxOracleError(
            f"calculation returned an invalid persisted revision id: {calculation_revision_id!r}",
        )
    casilla_values = result.get("casilla_values")
    if not isinstance(casilla_values, dict) or Decimal(str(casilla_values.get(TARGET_CASILLA))) != EXPECTED_VALUE:
        raise InstalledTaxOracleError(
            f"calculation expected {TARGET_CASILLA}={EXPECTED_VALUE}, got {casilla_values!r}",
        )
    notices = calculate_document["notices"]
    notice_codes = {str(notice.get("code")) for notice in notices}
    if notice_codes != EXPECTED_NOTICE_CODES:
        raise InstalledTaxOracleError(
            f"calculation notices expected {sorted(EXPECTED_NOTICE_CODES)!r}, got {sorted(notice_codes)!r}",
        )
    if any(notice.get("severity") != "warning" for notice in notices):
        raise InstalledTaxOracleError(f"calculation notice severity drifted: {notices!r}")

    observations = _run(
        (
            *authenticated_base,
            "app",
            "modelo",
            "work",
            "observations",
            calculation_revision_id,
        ),
        cwd=resolved_work_dir,
        env=environment,
        timeout_seconds=timeout_seconds,
        input_text=profile_authentication,
    )
    commands.append(observations)
    observations_document = _json_envelope(observations, expected_command="modelo.work.observations")
    _assert_no_diagnostic_notices(observations_document, command="modelo.work.observations")
    target = assert_grounded_observations(
        observations_document["result"],
        calculation_revision_id=calculation_revision_id,
        work_unit_id=work_unit_id,
    )

    return InstalledTaxEvidence(
        requested_executable=str(requested_cli),
        resolved_executable=str(resolved_cli),
        version_output=version.stdout.strip(),
        cohort_source_commit=cohort_source_commit,
        cohort_manifest_sha256=cohort_manifest_sha256,
        cohort_root_wheel_sha256=cohort_root_wheel_sha256,
        executable_sha256=executable_sha256,
        installed_wheel_payload_sha256=installed_payload_sha256,
        storage_root=str(storage_root.resolve()),
        work_unit_id=work_unit_id,
        calculation_revision_id=calculation_revision_id,
        target_casilla=TARGET_CASILLA,
        target_value=str(EXPECTED_VALUE),
        formula_id=str(target["formula_id"]),
        legal_refs=tuple(str(value) for value in target["legal_refs"]),
        source_refs=tuple(str(value) for value in target["source_refs"]),
        notice_codes=tuple(sorted(notice_codes)),
        checkout_imports_removed=checkout_imports_removed(environment),
        ambient_product_executables_removed=ambient_product_executables_removed(environment),
        commands=tuple(commands),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", required=True, type=Path, help="Absolute installed aeat executable.")
    parser.add_argument("--storage-root", required=True, type=Path, help="Fresh isolated product storage root.")
    parser.add_argument("--work-dir", required=True, type=Path, help="Execution cwd outside the source checkout.")
    parser.add_argument("--cohort-source-commit", required=True)
    parser.add_argument("--cohort-manifest-sha256", required=True)
    parser.add_argument("--cohort-root-wheel-sha256", required=True)
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument("--output", type=Path, help="Optional JSON evidence destination.")
    return parser


def main() -> int:
    """Run the installed CLI oracle from the command line."""
    args = _parser().parse_args()
    evidence = run_installed_tax_oracle(
        args.cli,
        storage_root=args.storage_root,
        work_dir=args.work_dir,
        cohort_source_commit=args.cohort_source_commit,
        cohort_manifest_sha256=args.cohort_manifest_sha256,
        cohort_root_wheel_sha256=args.cohort_root_wheel_sha256,
        timeout_seconds=args.timeout_seconds,
    )
    rendered = json.dumps(evidence.to_jsonable(), ensure_ascii=False, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{rendered}\n", encoding=_UTF_8, newline="\n")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
