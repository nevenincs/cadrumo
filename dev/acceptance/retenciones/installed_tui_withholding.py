"""Run CLI-seeded withholding lifecycle and reopen through the installed runtime TUI.

This continuation covers professional 111/190 and rent 115/180 declarations.
The retired withholding capture screen is explicitly unavailable in the
current runtime. Public CLI capture supplies the inputs; neither the child
nor the parent injects a workbench composition or writes product repositories.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import secrets
import sys
from collections.abc import Sequence
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
from typing import Any

from dev.acceptance.income_tax.installed_tui_child import (
    InstalledTuiChildError,
    installed_product_evidence,
    public_surface_diagnostic,
    reportable_child_failure_reason,
    run_admitted_installed_launcher,
    run_installed_tui_child_process,
    write_installed_tui_failure_receipt,
)
from dev.acceptance.income_tax.tui_contracts import TuiJourneyError
from dev.acceptance.installed_cli import InstalledCli

from .cli_annual_export_validation import _validate_annual_export
from .cli_contracts import RetencionesInstalledCliError
from .cli_export_validation import _validate_export
from .cli_layout_selection import _selected_annual_layouts
from .cli_preflight import _fresh_directory
from .installed_tui_controls import assert_capture_unavailable, assert_recorded_reopen, run_work_lifecycle
from .installed_tui_runtime import installed_foreground_runtime
from .installed_tui_seed import WithholdingWork, seed_withholding_work
from .scenario import SUPPORTED_YEAR, build_installed_annual_cli_slices

_SCHEMA = "retenciones-installed-runtime-tui-continuation-v1"
_MODULE = "dev.acceptance.retenciones.installed_tui_withholding"
_REQUIRED_OPERATIONS = ("modelo.work.calculate", "modelo.work.verify", "modelo.export", "modelo.work.file")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_SAFE_TUI_REASONS = (
    "the declaration's workbench could not read its form",
    "the declaration's workbench did not read its form within",
    "the workbench did not open its export dialog",
    "the export statement did not close",
    "the finished export did not show its statement",
    "the review's acknowledgement did not take",
    "the review never allowed applying the changes",
    "the workbench offered to confirm assumed values but its dialog lists none it can confirm",
    "the confirmation of assumed values did not take the tick",
    "the confirmation of assumed values kept Confirm unavailable once ticked",
    "the workbench did not keep the confirmed values",
    "the workbench did not offer to apply the confirmed values",
    "the workbench did not open its confirmation of assumed values",
)
_SAFE_OPERATION_FAILURES = (
    "did not reach a succeeded terminal",
    "has no installed refresh target",
    "did not reach its refreshed TUI destination",
    "has no visible refusal control",
    "did not open an operation modal or visible refusal",
    "has no terminal result control",
    "did not expose a terminal operation status",
    "would start under an earlier workbench notice; open the declaration afresh first",
)
_SAFE_WITHHOLDING_CONTROL_REASONS = frozenset(
    {
        "installed withholding journey could not return to Home",
        "installed withholding public Back control did not change its screen",
        "installed TUI did not complete its public Home refresh",
        "installed palette offered the unavailable withholding capture route",
        "installed withholding refusal check never observed a populated palette",
        "installed palette search offered unavailable withholding capture",
        "installed withholding assumed-value confirmation did not succeed",
        "installed withholding fresh reopen did not show the recorded filing state",
    }
)
_SAFE_WITHHOLDING_CONTROL_FUNCTIONS = frozenset(
    {"_home", "open_withholding_work", "assert_capture_unavailable", "run_work_lifecycle", "assert_recorded_reopen"}
)


class WithholdingTuiError(InstalledTuiChildError):
    """Retain a public continuation stage and sanitized mounted surface."""

    def __init__(self, message: str, *, stage: str, diagnostic: dict[str, object] | None = None) -> None:
        """Bind one static reason to its driver stage and public surface."""
        super().__init__(message, diagnostic=diagnostic)
        self.stage = stage


def _safe_tui_failure_reason(error: Exception) -> str:
    """Project known driver messages without copying notices or findings."""
    message = str(error)
    if isinstance(error, InstalledTuiChildError) and message in _SAFE_WITHHOLDING_CONTROL_REASONS:
        return message
    reasons = (
        *_SAFE_TUI_REASONS,
        *(
            f"{operation} {failure}"
            for operation in (*_REQUIRED_OPERATIONS, "modelo.edit.apply", "confirming the assumed values")
            for failure in _SAFE_OPERATION_FAILURES
        ),
    )
    for reason in reasons:
        if message == reason or message.startswith((f"{reason} (", f"{reason}:", f"{reason} ")):
            return reason
    return "installed withholding public control failed"


def _pilot_failure(error: Exception, *, pilot: Any, stage: str) -> WithholdingTuiError:
    """Capture only driver function identity while the public screen is mounted."""
    traceback = error.__traceback__
    while traceback is not None:
        module = traceback.tb_frame.f_globals.get("__name__", "")
        function = traceback.tb_frame.f_code.co_name
        if (isinstance(module, str) and module.startswith("dev.acceptance.income_tax.tui_")) or (
            module == "dev.acceptance.retenciones.installed_tui_controls"
            and function in _SAFE_WITHHOLDING_CONTROL_FUNCTIONS
        ):
            stage = f"{stage.split('.')[0]}.{function}"
        traceback = traceback.tb_next
    reason = _safe_tui_failure_reason(error)
    return WithholdingTuiError(
        f"installed withholding {stage} failed: {reason}",
        stage=stage,
        diagnostic=public_surface_diagnostic(pilot),
    )


def _child_process_failure(*, phase: str, receipt: Path) -> WithholdingTuiError:
    """Carry the sanitized child reason into the parent continuation receipt."""
    reason = reportable_child_failure_reason(receipt) or "installed child recorded no reportable failure reason"
    return WithholdingTuiError(f"installed withholding {phase} child failed: {reason}", stage=f"{phase}.child")


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_receipt(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate_child_receipt(
    document: dict[str, Any],
    *,
    phase: str,
    targets: tuple[WithholdingWork, ...],
    manifest_sha256: str,
    authority_generation: str,
) -> None:
    """Refuse success when a child skipped admission, a target, or a lifecycle stage."""
    if (
        document.get("schema_version") != _SCHEMA
        or document.get("status") != "proven"
        or document.get("phase") != phase
        or document.get("manifest_sha256") != manifest_sha256
        or document.get("authority_generation") != authority_generation
        or document.get("product_origin") != "site-packages"
        or not isinstance(document.get("product_init_sha256"), str)
        or _SHA256.fullmatch(document["product_init_sha256"]) is None
        or document.get("withholding_capture") != "unavailable_and_withheld_from_populated_palette"
        or document.get("live_submission") is not False
        or document.get("aeat_acceptance_claimed") is not False
    ):
        raise InstalledTuiChildError("installed withholding child did not prove its requested admitted continuation")
    observed = document.get("works")
    if not isinstance(observed, list) or len(observed) != len(targets):
        raise InstalledTuiChildError("installed withholding child skipped a required work unit")
    for target, evidence in zip(targets, observed, strict=True):
        if not isinstance(evidence, dict) or evidence.get("target") != asdict(target):
            raise InstalledTuiChildError("installed withholding child reported another work coordinate")
        if evidence.get("independent_export_matches") is not True:
            raise InstalledTuiChildError("installed withholding child did not validate its real export bytes")
        artifact = evidence.get("artifact")
        if (
            not isinstance(artifact, dict)
            or not isinstance(artifact.get("size"), int)
            or artifact["size"] <= 0
            or not isinstance(artifact.get("sha256"), str)
            or _SHA256.fullmatch(artifact["sha256"]) is None
        ):
            raise InstalledTuiChildError("installed withholding child has no durable artifact identity")
        if phase == "lifecycle":
            operations = evidence.get("operations")
            if (
                not isinstance(operations, list)
                or tuple(operation for operation in operations if operation != "modelo.edit.apply")
                != _REQUIRED_OPERATIONS
            ):
                raise InstalledTuiChildError("installed withholding child skipped a required lifecycle terminal")
        elif phase == "reopen":
            if evidence.get("recorded_reopen") is not True:
                raise InstalledTuiChildError("installed withholding child did not reopen a recorded declaration")
        else:
            raise InstalledTuiChildError("installed withholding child phase is unknown")


def _export_evidence(target: WithholdingWork, *, path: Path, operation: Any) -> dict[str, Any]:
    """Check exported bytes against independent existing withholding scenario oracles."""
    from cadrumo.domain.calculations.registry.export import resolve_export_layout

    annual = next(
        slice_ for slice_ in build_installed_annual_cli_slices(target.year) if slice_.slice_id == target.annual_slice_id
    )
    if target.modelo == annual.modelo:
        if target.period != annual.period or target.revision != annual.revision:
            raise InstalledTuiChildError("installed annual withholding work has unexpected natural coordinates")
        layout_id = annual.layout_id
        expected_source = None
    else:
        if target.modelo != annual.source_modelo:
            raise InstalledTuiChildError("installed quarterly withholding work belongs to another annual source")
        expected_source = next(source for source in annual.source_periods if source.period == target.period)
        layout_id = annual.captures[0].layout_id
    snapshot = operation.snapshot(
        target.modelo, filing_year=target.year, period=target.period, revision_id=target.revision
    )
    layout = resolve_export_layout(snapshot, layout_id).layout
    payload = path.read_bytes()
    if expected_source is None:
        _validate_annual_export(
            layout=layout,
            payload=payload,
            expected_header=annual.expected_header_fields,
            expected_type2_rows=annual.expected_type2_rows,
            stage="tui_annual_export_oracle",
        )
    else:
        _validate_export(
            layout=layout,
            payload=payload,
            expected=tuple((key, Decimal(value)) for key, value in expected_source.expected_casillas),
            stage="tui_periodic_export_oracle",
        )
    return {"name": path.name, "size": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}


def _run_child(args: argparse.Namespace) -> dict[str, Any]:
    """Admit through the production launcher and drive only rendered public controls."""
    from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority

    product = installed_product_evidence(workspace_root=args.workspace_root)
    credential = json.loads(sys.stdin.read()).get("profile_passphrase")
    if not isinstance(credential, str) or not credential:
        raise InstalledTuiChildError("installed withholding child has no stdin credential")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    targets = tuple(WithholdingWork(**target) for target in manifest["works"])
    if not targets or any(target.year != SUPPORTED_YEAR for target in targets):
        raise InstalledTuiChildError("installed withholding child has no supported work coordinates")
    works: list[dict[str, Any]] = []
    capture_checked = False
    with bundled_indexed_authority().operation() as operation:
        generation = operation.generation.logical_generation
        if generation != manifest["authority_generation"]:
            raise InstalledTuiChildError("installed withholding authority changed after public seeding")

        async def drive(pilot: Any) -> None:
            nonlocal capture_checked
            stage = "capture_unavailable"
            try:
                await assert_capture_unavailable(pilot)
                capture_checked = True
                for target in targets:
                    artifact = args.output_dir / f"modelo-{target.modelo}-{target.year}-{target.period}.boe"
                    evidence: dict[str, Any] = {"target": asdict(target)}
                    stage = args.child_phase
                    if args.child_phase == "lifecycle":
                        if artifact.exists():
                            raise InstalledTuiChildError("installed withholding export destination was not fresh")
                        evidence["operations"] = list(await run_work_lifecycle(pilot, target, export_path=artifact))
                    else:
                        await assert_recorded_reopen(pilot, target)
                        evidence["recorded_reopen"] = True
                    stage = "export_oracle"
                    evidence["artifact"] = _export_evidence(target, path=artifact, operation=operation)
                    evidence["independent_export_matches"] = True
                    works.append(evidence)
                pilot.app.exit()
            except (TuiJourneyError, InstalledTuiChildError) as error:
                raise _pilot_failure(error, pilot=pilot, stage=stage) from error

        run_admitted_installed_launcher(passphrase=credential, drive_after_home=drive, admission_polls=900)
    if not capture_checked or len(works) != len(targets):
        raise InstalledTuiChildError("installed withholding launcher exited before the requested continuation")
    receipt = {
        "schema_version": _SCHEMA,
        "status": "proven",
        "phase": args.child_phase,
        **product.to_dict(),
        "authority_generation": generation,
        "manifest_sha256": _digest(args.manifest),
        "withholding_capture": "unavailable_and_withheld_from_populated_palette",
        "works": works,
        "live_submission": False,
        "aeat_acceptance_claimed": False,
    }
    validate_child_receipt(
        receipt,
        phase=args.child_phase,
        targets=targets,
        manifest_sha256=_digest(args.manifest),
        authority_generation=generation,
    )
    return receipt


def _run_parent(args: argparse.Namespace) -> dict[str, Any]:
    """Seed in public child CLI processes, then launch separate lifecycle and reopen TUIs."""
    if args.cli is None or args.python is None or args.storage_root is None or args.authority_root is None:
        raise ValueError("parent continuation requires installed CLI/Python, fresh storage and published authority")
    installed_product_evidence(workspace_root=args.workspace_root)
    storage = _fresh_directory(args.storage_root, label="withholding TUI continuation storage")
    outputs = _fresh_directory(args.output_dir, label="withholding TUI continuation outputs")
    slices = build_installed_annual_cli_slices(args.year)
    generation, _ = _selected_annual_layouts(authority_root=args.authority_root, slices=slices, year=args.year)
    cli = InstalledCli(
        args.cli,
        storage_root=storage,
        authority_root=args.authority_root,
        passphrase=secrets.token_urlsafe(32),
        runtime_socket_dir=storage / "r",
    )
    with installed_foreground_runtime(
        cli_executable=args.cli,
        storage_root=storage,
        authority_root=args.authority_root,
        runtime_socket_dir=storage / "r",
    ) as runtime_evidence:
        try:
            targets = seed_withholding_work(cli, year=args.year)
        except RetencionesInstalledCliError as error:
            raise RetencionesInstalledCliError(
                stage=error.stage, diagnostic_code=error.diagnostic_code, commands=tuple(cli.commands)
            ) from error
        manifest_path = outputs / "withholding-work.json"
        _write_receipt(
            manifest_path, {"authority_generation": generation, "works": [asdict(target) for target in targets]}
        )
        children = []
        artifact_identities = None
        for phase in ("lifecycle", "reopen"):
            child_receipt = outputs / f"{phase}-receipt.json"
            process = run_installed_tui_child_process(
                python_executable=args.python,
                workspace_root=args.workspace_root,
                child_module=_MODULE,
                child_args=(
                    "--workspace-root",
                    str(args.workspace_root),
                    "--child-phase",
                    phase,
                    "--manifest",
                    str(manifest_path),
                    "--output-dir",
                    str(outputs),
                    "--receipt",
                    str(child_receipt),
                ),
                storage_root=storage,
                authority_root=args.authority_root,
                runtime_socket_dir=cli.runtime_socket_dir,
                receipt_path=child_receipt,
                passphrase=cli.passphrase,
                timeout_seconds=args.timeout_seconds,
            )
            if process.returncode != 0 or process.receipt_status != "proven":
                raise _child_process_failure(phase=phase, receipt=child_receipt)
            document = json.loads(child_receipt.read_text(encoding="utf-8"))
            validate_child_receipt(
                document,
                phase=phase,
                targets=targets,
                manifest_sha256=_digest(manifest_path),
                authority_generation=generation,
            )
            observed_artifacts = [work["artifact"] for work in document["works"]]
            if artifact_identities is not None and observed_artifacts != artifact_identities:
                raise InstalledTuiChildError(
                    "installed withholding fresh reopen changed the validated export artifacts"
                )
            artifact_identities = observed_artifacts
            children.append(process.to_dict())
        return {
            "schema_version": _SCHEMA,
            "status": "proven",
            "scope": "public_cli_seeded_runtime_tui_continuation",
            "runtime_fixture": runtime_evidence,
            "year": args.year,
            "authority_generation": generation,
            "works": [asdict(target) for target in targets],
            "cli_commands": [asdict(command) for command in cli.commands],
            "children": children,
            "artifacts": artifact_identities,
            "withholding_capture": "unavailable_in_current_runtime",
            "live_submission": False,
            "aeat_acceptance_claimed": False,
        }


def main(argv: Sequence[str] | None = None) -> int:
    """Write a sanitized complete or failed receipt, never an unexecuted success."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", type=Path)
    parser.add_argument("--python", type=Path)
    parser.add_argument("--authority-root", type=Path)
    parser.add_argument("--storage-root", type=Path)
    parser.add_argument("--workspace-root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--year", type=int, choices=(SUPPORTED_YEAR,), default=SUPPORTED_YEAR)
    parser.add_argument("--child-phase", choices=("lifecycle", "reopen"))
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    args = parser.parse_args(argv)
    if args.receipt.exists():
        parser.error("withholding continuation receipt must be fresh")
    try:
        if args.child_phase and args.manifest is None:
            raise ValueError("withholding child requires its public work manifest")
        receipt = _run_child(args) if args.child_phase else _run_parent(args)
    except Exception as error:
        failure: dict[str, Any] = {}
        if isinstance(error, InstalledTuiChildError):
            write_installed_tui_failure_receipt(path=args.receipt, schema_version=_SCHEMA, error=error)
            failure = json.loads(args.receipt.read_text(encoding="utf-8"))
        if isinstance(error, WithholdingTuiError):
            failure["stage"] = error.stage
        _write_receipt(
            args.receipt,
            {
                "schema_version": _SCHEMA,
                "status": "failed",
                "phase": args.child_phase or "parent",
                "diagnostic_code": type(error).__name__,
                **failure,
                **(
                    {
                        "stage": error.stage,
                        "diagnostic_code": error.diagnostic_code,
                        "cli_commands": [asdict(command) for command in error.commands],
                    }
                    if isinstance(error, RetencionesInstalledCliError)
                    else {}
                ),
                "live_submission": False,
                "aeat_acceptance_claimed": False,
            },
        )
        return 2
    _write_receipt(args.receipt, receipt)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
