"""Run the installed IVA TUI capture and reopen proof and its bounded child entrypoint."""

from __future__ import annotations

import argparse
import secrets
from collections.abc import Sequence
from pathlib import Path

from dev.acceptance.income_tax.installed_tui_child import (
    InstalledTuiChildError,
    read_passphrase_from_stdin,
    run_installed_tui_child_process,
    write_installed_tui_failure_receipt,
)

from .filing_year import require_journey_year
from .iva_tui_child_lifecycle import _capture_child, _reopen_child
from .iva_tui_cli_readback import _readback_canonical_fields
from .iva_tui_contracts import (
    _CLASSIFICATION_FIELDS,
    _PERIOD,
    _SCHEMA_VERSION,
    _UNEXERCISED,
    ChildHandle,
    InstalledIvaTuiReceipt,
    IvaInstalledTuiError,
    _CaptureChildReceipt,
    _ReopenChildReceipt,
)
from .iva_tui_identity import (
    _assert_child_identity,
    _authority_identity,
    _module_hash_arguments,
    _parse_module_hashes,
    _source_identity,
)
from .iva_tui_projection import _reported_reason
from .iva_tui_receipts import (
    _capture_transaction_ids,
    _child_document,
    _require_submitted_classification_fields,
    _write_success_receipt,
)
from .iva_tui_scenario import _synthetic_rows
from .iva_tui_storage import _require_empty_directory


def _child_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--child-mode", required=True, choices=("capture", "reopen"))
    parser.add_argument("--workspace-root", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--year", required=True, type=int)
    parser.add_argument("--scratch", type=Path)
    parser.add_argument("--profile-label", default="iva-installed-tui")
    parser.add_argument("--source-manifest-sha256", required=True)
    parser.add_argument("--source-module", action="append", default=[])
    parser.add_argument("--expected-transaction-id", action="append", default=[])
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run one credentialed installed-TUI child and persist its sanitized receipt."""
    args = _child_parser().parse_args(argv)
    try:
        modules = _parse_module_hashes(args.source_module)
        if args.child_mode == "capture":
            if args.scratch is None:
                raise InstalledTuiChildError("capture child requires a transient scratch directory")
            receipt: _CaptureChildReceipt | _ReopenChildReceipt = _capture_child(
                workspace_root=args.workspace_root,
                profile_label=args.profile_label,
                passphrase=read_passphrase_from_stdin(),
                scratch=args.scratch,
                year=args.year,
                expected_manifest_sha256=args.source_manifest_sha256,
                expected_modules=modules,
            )
        else:
            ids = tuple(args.expected_transaction_id)
            if len(ids) != 2 or len(set(ids)) != 2:
                raise InstalledTuiChildError("reopen child requires exactly two distinct captured Ledger identities")
            receipt = _reopen_child(
                workspace_root=args.workspace_root,
                passphrase=read_passphrase_from_stdin(),
                expected_transaction_ids=(ids[0], ids[1]),
                expected_manifest_sha256=args.source_manifest_sha256,
                expected_modules=modules,
            )
    except (IvaInstalledTuiError, InstalledTuiChildError) as exc:
        write_installed_tui_failure_receipt(
            path=args.receipt,
            schema_version=_SCHEMA_VERSION,
            error=exc if isinstance(exc, InstalledTuiChildError) else InstalledTuiChildError(str(exc)),
        )
        return 2
    _write_success_receipt(args.receipt, receipt)
    return 0


def run_installed_tui_capture_reopen(
    *,
    workspace_root: Path,
    authority_root: Path,
    output_root: Path,
    year: int,
) -> InstalledIvaTuiReceipt:
    """Build/install the current source, then run capture, fresh TUI reopen, and read-only continuation.

    Raises:
        IvaFilingYearUnsupportedError: Before the output root is created, when the
            published authority has no Modelo 303 1T revision authored for ``year``.
    """
    journey_year = require_journey_year(authority_root=authority_root, year=year, coordinates=(("303", _PERIOD),))
    root = _require_empty_directory(output_root, label="IVA installed-TUI output root")
    workspace = workspace_root.resolve(strict=True)
    authority = _authority_identity(authority_root)
    source = _source_identity(workspace)

    # This is the shared supported build/install path.  The source-member
    # attestation below fails closed if its cached wheel predates this source.
    from dev.packaging.acquire_common import venv_executable
    from dev.packaging.installed_wheel_binding import (
        assert_installed_console_entry_point,
        installed_python_for_cli,
        installed_wheel_payload_sha256,
    )
    from dev.packaging.release_cohort_support import client_venv_template

    template = client_venv_template()
    executable = venv_executable(template, "aeat").resolve(strict=True)
    python_executable = installed_python_for_cli(executable)
    assert_installed_console_entry_point(
        executable,
        distribution="cadrumo",
        entry_point="aeat",
        expected_value="cadrumo.entrypoints.cli.bootstrap:main",
    )
    package_payload_sha256 = installed_wheel_payload_sha256(executable)
    storage_root = _require_empty_directory(root / "secure-store", label="IVA installed-TUI secure store")
    scratch = _require_empty_directory(root / "transient", label="IVA installed-TUI transient directory")
    passphrase = secrets.token_urlsafe(32)
    source_arguments = _module_hash_arguments(source)

    capture_path = root / "capture.json"
    capture_process = run_installed_tui_child_process(
        python_executable=python_executable,
        workspace_root=workspace,
        child_module="dev.acceptance.iva.installed_tui_capture_reopen",
        child_args=(
            "--child-mode",
            "capture",
            "--workspace-root",
            str(workspace),
            "--year",
            str(journey_year.year),
            "--scratch",
            str(scratch),
            "--receipt",
            str(capture_path),
            "--source-manifest-sha256",
            source.manifest_sha256,
            *source_arguments,
        ),
        storage_root=storage_root,
        authority_root=authority_root,
        receipt_path=capture_path,
        passphrase=passphrase,
        timeout_seconds=900,
    )
    if capture_process.returncode != 0 or capture_process.receipt_status != "proven":
        raise IvaInstalledTuiError(
            "installed IVA TUI capture child did not prove its bounded journey"
            + _reported_reason(capture_path, returncode=capture_process.returncode)
        )
    capture = _child_document(capture_path, mode="capture")
    product_origin, product_init_sha256, package_version = _assert_child_identity(
        capture,
        source=source,
        authority=authority,
    )
    transaction_ids = _capture_transaction_ids(capture)
    _require_submitted_classification_fields(capture)

    reopen_path = root / "reopen.json"
    reopen_process = run_installed_tui_child_process(
        python_executable=python_executable,
        workspace_root=workspace,
        child_module="dev.acceptance.iva.installed_tui_capture_reopen",
        child_args=(
            "--child-mode",
            "reopen",
            "--workspace-root",
            str(workspace),
            "--year",
            str(journey_year.year),
            "--receipt",
            str(reopen_path),
            "--source-manifest-sha256",
            source.manifest_sha256,
            *source_arguments,
            "--expected-transaction-id",
            transaction_ids[0],
            "--expected-transaction-id",
            transaction_ids[1],
        ),
        storage_root=storage_root,
        authority_root=authority_root,
        receipt_path=reopen_path,
        passphrase=passphrase,
        timeout_seconds=900,
    )
    if reopen_process.returncode != 0 or reopen_process.receipt_status != "proven":
        raise IvaInstalledTuiError(
            "fresh installed IVA TUI reopen child did not prove its bounded journey"
            + _reported_reason(reopen_path, returncode=reopen_process.returncode)
        )
    reopen = _child_document(reopen_path, mode="reopen")
    _assert_child_identity(
        reopen,
        source=source,
        authority=authority,
        product_origin=product_origin,
        product_init_sha256=product_init_sha256,
        package_version=package_version,
    )
    observed_ids = _capture_transaction_ids({"transaction_ids": reopen.get("observed_transaction_ids")})
    if observed_ids != transaction_ids:
        raise IvaInstalledTuiError("fresh installed TUI reopen returned a different captured identity order")

    fingerprint, command_handles = _readback_canonical_fields(
        executable=executable,
        storage_root=storage_root,
        authority_root=authority_root,
        passphrase=passphrase,
        transaction_ids=transaction_ids,
        synthetic_rows=_synthetic_rows(journey_year.year),
    )
    return InstalledIvaTuiReceipt(
        schema_version=_SCHEMA_VERSION,
        status="proven",
        filing_year=journey_year.year,
        partial_acceptance_ids=("V1", "V2", "V10"),
        acceptance_scope="partial_ledger_capture_classification_reopen",
        tui_only_path="installed_tui_capture_classify_then_fresh_tui_entries_reopen",
        continuation_path="read_only_installed_cli_ledger_view_after_tui_capture",
        product_origin=product_origin,
        product_init_sha256=product_init_sha256,
        package_version=package_version,
        package_payload_sha256=package_payload_sha256,
        source_manifest_sha256=source.manifest_sha256,
        source_module_count=len(source.module_sha256s),
        authority_generation=authority.logical_generation,
        authority_descriptor_sha256=authority.descriptor_sha256,
        authority_database_sha256=authority.database_sha256,
        child_handles=(
            ChildHandle(
                mode="capture",
                returncode=capture_process.returncode,
                receipt_status=capture_process.receipt_status,
                receipt_sha256=capture_process.receipt_sha256,
                stdout_sha256=capture_process.stdout_sha256,
                stderr_sha256=capture_process.stderr_sha256,
            ),
            ChildHandle(
                mode="reopen",
                returncode=reopen_process.returncode,
                receipt_status=reopen_process.receipt_status,
                receipt_sha256=reopen_process.receipt_sha256,
                stdout_sha256=reopen_process.stdout_sha256,
                stderr_sha256=reopen_process.stderr_sha256,
            ),
        ),
        transaction_count=2,
        classification_fields_submitted=_CLASSIFICATION_FIELDS,
        canonical_fields_read_back=(
            "business_classification",
            "taxable_base",
            "iva_rate",
            "iva_amount",
            "iva_category",
        ),
        canonical_classification_fingerprint=fingerprint,
        continuation_command_handles=command_handles,
        deduction_kind_readback="not_proven_public_ledger_view_does_not_expose_deduction_fact_kind",
        unexercised=_UNEXERCISED,
    )


if __name__ == "__main__":  # pragma: no cover - child execution is integration-owned
    raise SystemExit(main())
