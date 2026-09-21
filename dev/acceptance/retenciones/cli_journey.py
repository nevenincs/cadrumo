"""Installed CLI acceptance for the grounded RETENCIONES-01 periodic slices.

The driver deliberately uses public CLI writes only.  It creates canonical
received invoices, submits each payment allocation through
``--received-invoice-retencion``, then starts fresh processes for readback,
calculation, verification, export, and independent canonical parsing.  It
does not seed an encrypted withholding repository or submit anything to AEAT.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal

from cadrumo.domain.calculations.registry.authority import IndexedRegistryAuthority
from cadrumo.domain.calculations.registry.export import resolve_export_layout
from cadrumo.domain.calculations.registry.export_parse import ParsedExportPayload, parse_export_payload
from cadrumo.domain.calculations.registry.schema_exports import ExportLayoutDefinition
from dev.acceptance.income_tax.cli_journey import ArtifactEvidence, CommandEvidence, InstalledCli

from .scenario import (
    BRIEF_ID,
    BRIEF_REVISION,
    INSTALLED_CLI_SCENARIO_VERSION,
    PATTERN_ID,
    PATTERN_REVISION,
    SUPPORTED_YEAR,
    InstalledPeriodicCliSlice,
    build_installed_periodic_cli_slices,
    money,
)

_SCHEMA_VERSION = "retenciones-01-installed-cli-journey-v1"
_ACTOR = "retenciones-acceptance"


class RetencionesInstalledCliError(RuntimeError):
    """A sanitized installed-journey failure suitable for a durable receipt."""

    def __init__(
        self,
        *,
        stage: str,
        diagnostic_code: str,
        commands: tuple[CommandEvidence, ...] = (),
    ) -> None:
        """Keep a stable stage/code and redacted command evidence only."""
        self.stage = stage
        self.diagnostic_code = diagnostic_code
        self.commands = commands
        super().__init__(f"installed retenciones CLI journey failed at {stage}: {diagnostic_code}")


@dataclass(frozen=True, slots=True)
class ExportValidationEvidence:
    """Independent canonical-parser evidence for one exported periodic return."""

    layout_id: str
    parsed_casillas: dict[str, str]
    expected_casillas: dict[str, str]


@dataclass(frozen=True, slots=True)
class PeriodicSliceEvidence:
    """One completed public evidence-to-export vertical slice."""

    slice_id: str
    modelo: str
    period: str
    revision: str
    invoice_id: str
    captured_allocation_count: int
    reopened_observation_count: int
    calculated_casillas: dict[str, str]
    verification_granted: bool
    artifact: ArtifactEvidence
    export_validation: ExportValidationEvidence
    annual_detail_status: Literal["not_exercised", "blocked_property_attribution_capture"]


@dataclass(frozen=True, slots=True)
class RetencionesCliJourneyEvidence:
    """Sanitized receipt for a full campaign or explicitly selected periodic slices."""

    schema_version: str
    status: Literal["proven", "partial"]
    campaign_scope: Literal["full_campaign", "selected_slices"]
    pattern_id: str
    pattern_revision: str
    brief_id: str
    brief_revision: str
    scenario: str
    year: int
    as_of: str
    authority_generation: str
    source_identity: str
    package_identity: str
    executable: str
    executable_sha256: str
    storage_root: str
    executed_slice_ids: tuple[str, ...]
    slices: tuple[PeriodicSliceEvidence, ...]
    commands: tuple[CommandEvidence, ...]
    retention: str

    def to_dict(self) -> dict[str, object]:
        """Return the stable JSON-safe acceptance receipt."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RetencionesCliFailureEvidence:
    """Sanitized failure receipt that preserves the exact acceptance stage."""

    schema_version: str
    status: Literal["failed"]
    pattern_id: str
    pattern_revision: str
    brief_id: str
    brief_revision: str
    scenario: str
    year: int
    source_identity: str
    package_identity: str
    executable: str
    executable_sha256: str | None
    storage_root: str | None
    output_dir: str | None
    stage: str
    diagnostic_code: str
    commands: tuple[CommandEvidence, ...]
    retention: str

    def to_dict(self) -> dict[str, object]:
        """Return a payload-free machine-readable failure receipt."""
        return asdict(self)


def run_retenciones_cli_journey(
    *,
    executable: Path,
    authority_root: Path,
    storage_root: Path,
    output_dir: Path,
    year: int,
    as_of: date,
    source_identity: str,
    package_identity: str,
    slice_ids: tuple[str, ...] | None = None,
) -> RetencionesCliJourneyEvidence:
    """Run professional and urban-rent periodic journeys through installed CLI.

    ``source_identity`` and ``package_identity`` are supplied by the wheel-build
    owner.  The driver records them beside the live executable digest; it does
    not infer a source commit from an installed package.
    """
    available_slices = build_installed_periodic_cli_slices(year)
    slices = _select_slices(available_slices, requested_ids=slice_ids)
    _require_nonempty_identity(source_identity, label="source_identity")
    _require_nonempty_identity(package_identity, label="package_identity")
    storage = _fresh_directory(storage_root, label="scenario storage root")
    outputs = _fresh_directory(output_dir, label="scenario output directory")
    authority_generation, layouts = _selected_layouts(authority_root=authority_root, slices=slices, year=year)
    cli = InstalledCli(
        executable,
        storage_root=storage,
        authority_root=authority_root,
        passphrase=secrets.token_urlsafe(32),
    )
    try:
        _create_withholding_profile(cli, year=year)
        evidence = tuple(
            _run_periodic_slice(cli=cli, slice_=slice_, layouts=layouts, year=year, output_dir=outputs)
            for slice_ in slices
        )
    except RetencionesInstalledCliError as exc:
        if not exc.commands:
            exc.commands = tuple(cli.commands)
        raise
    except Exception as exc:
        raise RetencionesInstalledCliError(
            stage="driver",
            diagnostic_code=f"unexpected_{type(exc).__name__}",
            commands=tuple(cli.commands),
        ) from exc
    return RetencionesCliJourneyEvidence(
        schema_version=_SCHEMA_VERSION,
        status="proven" if _is_full_campaign(slices, available=available_slices) else "partial",
        campaign_scope="full_campaign" if _is_full_campaign(slices, available=available_slices) else "selected_slices",
        pattern_id=PATTERN_ID,
        pattern_revision=PATTERN_REVISION,
        brief_id=BRIEF_ID,
        brief_revision=BRIEF_REVISION,
        scenario=INSTALLED_CLI_SCENARIO_VERSION,
        year=year,
        as_of=as_of.isoformat(),
        authority_generation=authority_generation,
        source_identity=source_identity,
        package_identity=package_identity,
        executable=str(cli.executable),
        executable_sha256=_sha256_file(cli.executable),
        storage_root=str(storage),
        executed_slice_ids=tuple(slice_.slice_id for slice_ in slices),
        slices=evidence,
        commands=tuple(cli.commands),
        # The caller allocated these roots.  Keeping their encrypted store and
        # selected public artifacts under its explicit retention policy avoids
        # deleting an externally supplied path from inside this driver.
        retention="caller_owned_encrypted_store_and_validated_synthetic_artifacts",
    )


def _select_slices(
    available: tuple[InstalledPeriodicCliSlice, ...],
    *,
    requested_ids: tuple[str, ...] | None,
) -> tuple[InstalledPeriodicCliSlice, ...]:
    """Select explicit independent slices without relabeling a partial run.

    The default is the full professional-plus-rent journey.  A named subset is
    useful when one model has a public-product prerequisite outside this
    acceptance lane: it proves the other model without claiming that the
    complete campaign passed.  The receipt names every executed slice.
    """
    if requested_ids is None:
        return available
    if not requested_ids or len(set(requested_ids)) != len(requested_ids):
        raise RetencionesInstalledCliError(stage="preflight", diagnostic_code="invalid_slice_selection")
    by_id = {slice_.slice_id: slice_ for slice_ in available}
    try:
        selected = tuple(by_id[slice_id] for slice_id in requested_ids)
    except KeyError as exc:
        raise RetencionesInstalledCliError(stage="preflight", diagnostic_code="unknown_slice_selection") from exc
    return selected


def _is_full_campaign(
    selected: tuple[InstalledPeriodicCliSlice, ...],
    *,
    available: tuple[InstalledPeriodicCliSlice, ...],
) -> bool:
    """Return whether the receipt covers every required periodic slice exactly once."""
    return len(selected) == len(available) and {slice_.slice_id for slice_ in selected} == {
        slice_.slice_id for slice_ in available
    }


def _create_withholding_profile(cli: InstalledCli, *, year: int) -> None:
    """Create a secure synthetic profile and explicitly activate both duties."""
    try:
        cli.create_profile(year=year)
    except Exception as exc:
        raise RetencionesInstalledCliError(
            stage="profile_create",
            diagnostic_code=f"profile_create_{type(exc).__name__}",
        ) from exc
    _require_result(
        cli,
        (
            "config",
            "profile",
            "edit",
            f"income-{year}",
            "--quiet",
            "--accept-defaults",
            "--pays-professionals-with-retencion",
            "--pays-rent-with-retencion",
            "--no-pays-capital-income-with-retencion",
        ),
        stage="profile_enable_withholding_duties",
    )
    _require_result(
        cli,
        ("config", "profile", "complete-setup"),
        stage="profile_complete_setup",
    )


def _run_periodic_slice(
    *,
    cli: InstalledCli,
    slice_: InstalledPeriodicCliSlice,
    layouts: Mapping[str, ExportLayoutDefinition],
    year: int,
    output_dir: Path,
) -> PeriodicSliceEvidence:
    """Run one invoice-backed public capture through periodic export validation."""
    invoice_id = _create_received_invoice(cli, slice_=slice_)
    for allocation in slice_.allocations:
        request = {
            "invoice_id": invoice_id,
            "income_kind": slice_.income_kind,
            "scheme": slice_.scheme,
            "recipient_tax_status": "resident",
            "recipient_tax_regime": "irpf",
            "payment_event_id": allocation.payment_event_id,
            "payment_occurred_on": allocation.paid_on.isoformat(),
            "allocation_id": allocation.allocation_id,
            "allocated_base": _money_text(allocation.allocated_base),
            "allocated_withholding": _money_text(allocation.allocated_withholding),
            "allocated_settlement": _money_text(allocation.allocated_settlement),
            "idempotency_key": f"{slice_.slice_id}:{allocation.allocation_id}",
        }
        _require_result(
            cli,
            (
                "app",
                "modelo",
                "aggregate",
                "--modelo",
                slice_.modelo,
                "--year",
                str(year),
                "--period",
                slice_.period,
                "--received-invoice-retencion",
                json.dumps(request, separators=(",", ":"), sort_keys=True),
            ),
            stage=f"{slice_.slice_id}:capture",
        )

    # This command includes no write option.  InstalledCli starts a separate
    # process for it, so this is the required fresh-process readback boundary.
    reopened = _require_result(
        cli,
        ("app", "modelo", "aggregate", "--modelo", slice_.modelo, "--year", str(year), "--period", slice_.period),
        stage=f"{slice_.slice_id}:fresh_reopen",
    )
    observed_count = _required_nonnegative_int(
        reopened,
        key="observation_count",
        stage=f"{slice_.slice_id}:fresh_reopen",
    )
    if observed_count != slice_.expected_observation_count:
        raise RetencionesInstalledCliError(
            stage=f"{slice_.slice_id}:fresh_reopen",
            diagnostic_code="observation_count_mismatch",
        )

    work = _require_result(
        cli,
        (
            "app",
            "modelo",
            "work",
            "create",
            "--modelo",
            slice_.modelo,
            "--year",
            str(year),
            "--period",
            slice_.period,
            "--revision",
            slice_.revision,
            "--by",
            _ACTOR,
        ),
        stage=f"{slice_.slice_id}:work_create",
    )
    work_id = _required_text(work, key="work_unit_id", stage=f"{slice_.slice_id}:work_create")
    calculation = _require_result(
        cli,
        ("app", "modelo", "work", "calculate", work_id, "--by", _ACTOR),
        stage=f"{slice_.slice_id}:work_calculate",
    )
    calculated_casillas = _expected_casillas_from_result(
        calculation,
        expected=slice_.expected_casillas,
        stage=f"{slice_.slice_id}:work_calculate",
    )
    revision_id = _required_text(
        calculation,
        key="calculation_revision_id",
        stage=f"{slice_.slice_id}:work_calculate",
    )
    verification = _require_result(
        cli,
        ("app", "modelo", "work", "verify", revision_id, "--by", _ACTOR),
        stage=f"{slice_.slice_id}:work_verify",
    )
    if verification.get("granted_verificado_completo") is not True:
        raise RetencionesInstalledCliError(
            stage=f"{slice_.slice_id}:work_verify",
            diagnostic_code="verification_not_complete",
        )

    target = output_dir / f"modelo-{slice_.modelo}-{year}-{slice_.period}.boe"
    _require_result(
        cli,
        ("app", "modelo", "export", work_id, "--output", str(target), "--by", _ACTOR),
        stage=f"{slice_.slice_id}:export",
    )
    if not target.is_file():
        raise RetencionesInstalledCliError(stage=f"{slice_.slice_id}:export", diagnostic_code="export_artifact_missing")
    payload = target.read_bytes()
    validation = _validate_export(
        layout=layouts[slice_.slice_id],
        payload=payload,
        expected=slice_.expected_casillas,
        stage=f"{slice_.slice_id}:export_parse",
    )
    artifact = ArtifactEvidence(
        modelo=slice_.modelo,
        period=slice_.period,
        path=str(target),
        size=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
    )
    annual_status: Literal["not_exercised", "blocked_property_attribution_capture"]
    annual_status = (
        "not_exercised" if slice_.annual_detail_capture_supported else "blocked_property_attribution_capture"
    )
    return PeriodicSliceEvidence(
        slice_id=slice_.slice_id,
        modelo=slice_.modelo,
        period=slice_.period,
        revision=slice_.revision,
        invoice_id=invoice_id,
        captured_allocation_count=len(slice_.allocations),
        reopened_observation_count=observed_count,
        calculated_casillas=calculated_casillas,
        verification_granted=True,
        artifact=artifact,
        export_validation=validation,
        annual_detail_status=annual_status,
    )


def _create_received_invoice(cli: InstalledCli, *, slice_: InstalledPeriodicCliSlice) -> str:
    """Create the canonical invoice through the installed public CLI."""
    result = _require_result(
        cli,
        (
            "app",
            "ledger",
            "invoice",
            "add",
            "--kind",
            "received",
            "--counterparty-name",
            slice_.counterparty_name,
            "--counterparty-nif",
            slice_.counterparty_nif,
            "--invoice-number",
            slice_.invoice_number,
            "--invoice-date",
            slice_.invoice_date.isoformat(),
            "--taxable-base",
            _money_text(slice_.invoice_base),
            "--iva-rate",
            _percentage_text(slice_.invoice_iva_rate),
            "--country-code",
            "ES",
            "--retention-rate",
            str(slice_.invoice_withholding_rate),
            "--retention-amount",
            _money_text(slice_.invoice_withholding),
            "--iva-category",
            "domestic_general",
        ),
        stage=f"{slice_.slice_id}:invoice_create",
    )
    return _required_text(result, key="invoice_id", stage=f"{slice_.slice_id}:invoice_create")


def _selected_layouts(
    *, authority_root: Path, slices: tuple[InstalledPeriodicCliSlice, ...], year: int
) -> tuple[str, dict[str, ExportLayoutDefinition]]:
    """Load the same descriptor-selected layouts used by the installed CLI."""
    descriptor = authority_root.resolve(strict=True) / "authority.current.json"
    if not descriptor.is_file():
        raise RetencionesInstalledCliError(stage="authority_preflight", diagnostic_code="authority_descriptor_missing")
    try:
        authority = IndexedRegistryAuthority(descriptor)
        with authority.operation() as operation:
            generation = operation.generation.logical_generation
            layouts = {
                slice_.slice_id: resolve_export_layout(
                    operation.snapshot(
                        slice_.modelo,
                        filing_year=year,
                        period=slice_.period,
                        revision_id=slice_.revision,
                    ),
                    slice_.layout_id,
                ).layout
                for slice_ in slices
            }
    except Exception as exc:
        raise RetencionesInstalledCliError(
            stage="authority_preflight",
            diagnostic_code=f"authority_layout_{type(exc).__name__}",
        ) from exc
    return generation, layouts


def _validate_export(
    *,
    layout: ExportLayoutDefinition,
    payload: bytes,
    expected: tuple[tuple[str, Decimal], ...],
    stage: str,
) -> ExportValidationEvidence:
    """Parse actual export bytes through the canonical selected-layout parser."""
    try:
        parsed = parse_export_payload(layout, payload)
    except Exception as exc:
        raise RetencionesInstalledCliError(
            stage=stage,
            diagnostic_code=f"canonical_export_parse_{type(exc).__name__}",
        ) from exc
    return _validate_parsed_casillas(parsed=parsed, expected=expected, stage=stage)


def _validate_parsed_casillas(
    *, parsed: ParsedExportPayload, expected: tuple[tuple[str, Decimal], ...], stage: str
) -> ExportValidationEvidence:
    """Compare only independently authored expected casillas to parsed bytes."""
    expected_by_id = dict(expected)
    actual: dict[str, Decimal] = {}
    for field in parsed.casillas:
        if field.casilla_id is None:
            continue
        try:
            value = _as_decimal(field.value)
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise RetencionesInstalledCliError(
                stage=stage,
                diagnostic_code="non_decimal_expected_export_casilla",
            ) from exc
        casilla_id = str(field.casilla_id)
        prior = actual.get(casilla_id)
        if prior is not None and prior != value:
            raise RetencionesInstalledCliError(stage=stage, diagnostic_code="conflicting_export_casilla")
        actual[casilla_id] = value
    for casilla_id, expected_value in expected_by_id.items():
        if actual.get(casilla_id) != expected_value:
            raise RetencionesInstalledCliError(stage=stage, diagnostic_code="export_casilla_mismatch")
    return ExportValidationEvidence(
        layout_id=str(parsed.layout_id),
        parsed_casillas={key: _money_or_integer_text(actual[key]) for key in expected_by_id},
        expected_casillas={key: _money_or_integer_text(value) for key, value in expected_by_id.items()},
    )


def _expected_casillas_from_result(
    result: Mapping[str, Any],
    *,
    expected: tuple[tuple[str, Decimal], ...],
    stage: str,
) -> dict[str, str]:
    """Require canonical work calculation values to match the independent oracle."""
    values = result.get("casilla_values")
    if not isinstance(values, Mapping):
        raise RetencionesInstalledCliError(stage=stage, diagnostic_code="calculation_casillas_missing")
    observed: dict[str, str] = {}
    for casilla_id, expected_value in expected:
        try:
            value = _as_decimal(values.get(casilla_id))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise RetencionesInstalledCliError(stage=stage, diagnostic_code="calculation_casilla_invalid") from exc
        if value != expected_value:
            raise RetencionesInstalledCliError(stage=stage, diagnostic_code="calculation_casilla_mismatch")
        observed[casilla_id] = _money_or_integer_text(value)
    return observed


def _require_result(cli: InstalledCli, args: Sequence[str], *, stage: str) -> dict[str, Any]:
    """Run one fresh installed command without leaking raw diagnostics."""
    try:
        document = cli.run(args, allow_error=True)
    except Exception as exc:
        raise RetencionesInstalledCliError(
            stage=stage,
            diagnostic_code=f"installed_cli_{type(exc).__name__}",
        ) from exc
    if document.get("status") == "error":
        error = document.get("error")
        code = error.get("code") if isinstance(error, Mapping) else None
        raise RetencionesInstalledCliError(
            stage=stage,
            diagnostic_code=str(code) if isinstance(code, str) and code else "installed_cli_error",
        )
    result = document.get("result")
    if not isinstance(result, dict):
        raise RetencionesInstalledCliError(stage=stage, diagnostic_code="installed_cli_result_missing")
    return result


def _required_text(result: Mapping[str, Any], *, key: str, stage: str) -> str:
    """Read a stable CLI result identity without retaining the result object."""
    value = result.get(key)
    if not isinstance(value, str) or not value:
        raise RetencionesInstalledCliError(stage=stage, diagnostic_code=f"missing_{key}")
    return value


def _required_nonnegative_int(result: Mapping[str, Any], *, key: str, stage: str) -> int:
    """Read an aggregate readback count from a public result envelope."""
    value = result.get(key)
    if isinstance(value, bool):
        raise RetencionesInstalledCliError(stage=stage, diagnostic_code=f"invalid_{key}")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise RetencionesInstalledCliError(stage=stage, diagnostic_code=f"invalid_{key}") from exc
    if number < 0:
        raise RetencionesInstalledCliError(stage=stage, diagnostic_code=f"invalid_{key}")
    return number


def _as_decimal(value: object) -> Decimal:
    """Read numeric public/parser values without accepting booleans."""
    if isinstance(value, bool) or value is None:
        raise ValueError("expected a decimal value")
    return Decimal(str(value))


def _money_text(value: Decimal) -> str:
    """Render an independently authored money fact for a public request."""
    return f"{money(value):.2f}"


def _money_or_integer_text(value: Decimal) -> str:
    """Keep count casillas compact and monetary values to their cent precision."""
    if value == value.to_integral_value():
        return str(value.quantize(Decimal("1")))
    return _money_text(value)


def _percentage_text(rate: Decimal) -> str:
    """Render the invoice's supplied IVA rate in the CLI's percent unit."""
    percentage = rate * Decimal("100")
    return str(percentage.quantize(Decimal("1")))


def _fresh_directory(path: Path, *, label: str) -> Path:
    """Claim one explicit empty caller-provided acceptance root."""
    if path.exists() and any(path.iterdir()):
        raise RetencionesInstalledCliError(stage="preflight", diagnostic_code=f"nonempty_{label.replace(' ', '_')}")
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def _require_nonempty_identity(value: str, *, label: str) -> None:
    """Reject a receipt coordinate that cannot identify its evaluated build."""
    if not value.strip():
        raise RetencionesInstalledCliError(stage="preflight", diagnostic_code=f"missing_{label}")


def _sha256_file(path: Path) -> str:
    """Return the identity digest of the executable actually invoked."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _failure_evidence(
    *,
    error: RetencionesInstalledCliError,
    executable: Path,
    year: int,
    source_identity: str,
    package_identity: str,
    storage_root: Path | None = None,
    output_dir: Path | None = None,
    commands: tuple[CommandEvidence, ...] = (),
) -> RetencionesCliFailureEvidence:
    """Render a complete failure receipt without exception or stream contents."""
    return RetencionesCliFailureEvidence(
        schema_version=_SCHEMA_VERSION,
        status="failed",
        pattern_id=PATTERN_ID,
        pattern_revision=PATTERN_REVISION,
        brief_id=BRIEF_ID,
        brief_revision=BRIEF_REVISION,
        scenario=INSTALLED_CLI_SCENARIO_VERSION,
        year=year,
        source_identity=source_identity,
        package_identity=package_identity,
        executable=str(executable),
        executable_sha256=_sha256_file(executable) if executable.is_file() else None,
        storage_root=None if storage_root is None else str(storage_root),
        output_dir=None if output_dir is None else str(output_dir),
        stage=error.stage,
        diagnostic_code=error.diagnostic_code,
        commands=commands,
        retention="caller_owned_failure_artifacts_only; no stdout_or_stderr_retained",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", required=True, type=Path, help="Absolute installed aeat executable.")
    parser.add_argument("--authority-root", required=True, type=Path)
    parser.add_argument("--storage-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--year", type=int, default=SUPPORTED_YEAR)
    parser.add_argument("--as-of", type=date.fromisoformat, default=date(2026, 9, 21))
    parser.add_argument("--source-identity", required=True)
    parser.add_argument("--package-identity", required=True)
    parser.add_argument(
        "--slice",
        action="append",
        dest="slice_ids",
        help="Run one named periodic slice; repeat only for an explicit subset.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the installed acceptance journey and persist a sanitized receipt."""
    args = _parser().parse_args(argv)
    try:
        evidence = run_retenciones_cli_journey(
            executable=args.cli,
            authority_root=args.authority_root,
            storage_root=args.storage_root,
            output_dir=args.output_dir,
            year=args.year,
            as_of=args.as_of,
            source_identity=args.source_identity,
            package_identity=args.package_identity,
            slice_ids=None if args.slice_ids is None else tuple(args.slice_ids),
        )
    except RetencionesInstalledCliError as exc:
        rendered = _failure_evidence(
            error=exc,
            executable=args.cli,
            year=args.year,
            source_identity=args.source_identity,
            package_identity=args.package_identity,
            storage_root=args.storage_root,
            output_dir=args.output_dir,
            commands=exc.commands,
        ).to_dict()
        status = 2
    except Exception as exc:
        rendered = _failure_evidence(
            error=RetencionesInstalledCliError(
                stage="driver",
                diagnostic_code=f"unexpected_{type(exc).__name__}",
            ),
            executable=args.cli,
            year=args.year,
            source_identity=args.source_identity,
            package_identity=args.package_identity,
            storage_root=args.storage_root,
            output_dir=args.output_dir,
        ).to_dict()
        status = 2
    else:
        rendered = evidence.to_dict()
        status = 0
    serialized = json.dumps(rendered, indent=2, sort_keys=True)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(f"{serialized}\n", encoding="utf-8", newline="\n")
    print(serialized)
    return status


if __name__ == "__main__":  # pragma: no cover - module executable boundary
    raise SystemExit(main())


__all__ = [
    "ExportValidationEvidence",
    "PeriodicSliceEvidence",
    "RetencionesCliFailureEvidence",
    "RetencionesCliJourneyEvidence",
    "RetencionesInstalledCliError",
    "main",
    "run_retenciones_cli_journey",
]
