"""Installed quarterly withholding scenario selection and public command stages."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from cadrumo.domain.calculations.registry.schema_exports import ExportLayoutDefinition
from dev.acceptance.income_tax.cli_journey import ArtifactEvidence
from dev.acceptance.installed_cli import InstalledCli

from .cli_contracts import _ACTOR, PeriodicSliceEvidence, RetencionesInstalledCliError
from .cli_export_validation import _expected_casillas_from_result, _validate_export
from .cli_invoice_capture import _capture_invoice_withholding
from .cli_observations import _require_result, _required_nonnegative_int, _required_text
from .scenario import (
    InstalledPeriodicCliSlice,
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


def _run_periodic_slice(
    *,
    cli: InstalledCli,
    slice_: InstalledPeriodicCliSlice,
    layouts: Mapping[str, ExportLayoutDefinition],
    year: int,
    output_dir: Path,
) -> PeriodicSliceEvidence:
    """Run one invoice-backed public capture through periodic export validation."""
    invoice_id = _capture_invoice_withholding(cli=cli, slice_=slice_, year=year)

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
