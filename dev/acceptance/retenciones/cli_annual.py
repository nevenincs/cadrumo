"""Installed annual withholding allocation capture and public campaign stages."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path

from cadrumo.domain.calculations.registry.schema_exports import ExportLayoutDefinition
from dev.acceptance.income_tax.cli_journey import ArtifactEvidence
from dev.acceptance.installed_cli import InstalledCli

from .cli_annual_export_validation import _validate_annual_export
from .cli_annual_source import (
    _annual_source_revision,
    _attest_annual_no_activity_periods,
    _materialize_annual_source_period,
)
from .cli_contracts import _ACTOR, AnnualSliceEvidence, RetencionesInstalledCliError
from .cli_invoice_capture import _capture_invoice_withholding
from .cli_observations import _require_result, _required_nonnegative_int, _required_text
from .scenario import (
    InstalledAnnualCliSlice,
    InstalledPeriodicCliSlice,
)


def _capture_annual_source_allocations(
    cli: InstalledCli, slice_: InstalledAnnualCliSlice, year: int
) -> tuple[int, dict[str, list[InstalledPeriodicCliSlice]]]:
    """Capture annual source allocations."""
    captured_count = 0
    captures_by_period: dict[str, list[InstalledPeriodicCliSlice]] = {}
    source_periods_by_token = {source_period.period: source_period for source_period in slice_.source_periods}
    if len(source_periods_by_token) != len(slice_.source_periods):
        raise RetencionesInstalledCliError(
            stage=f"{slice_.slice_id}:capture_preflight",
            diagnostic_code="annual_source_period_duplicate",
        )
    for capture in slice_.captures:
        if capture.modelo != slice_.source_modelo:
            raise RetencionesInstalledCliError(
                stage=f"{slice_.slice_id}:capture_preflight",
                diagnostic_code="annual_source_modelo_mismatch",
            )
        _capture_invoice_withholding(cli=cli, slice_=capture, year=year)
        captured_count += len(capture.allocations)
        if capture.period not in source_periods_by_token:
            raise RetencionesInstalledCliError(
                stage=f"{slice_.slice_id}:capture_preflight",
                diagnostic_code="annual_capture_period_unclassified",
            )
        captures_by_period.setdefault(capture.period, []).append(capture)

    if captured_count != slice_.expected_capture_allocation_count:
        raise RetencionesInstalledCliError(
            stage=f"{slice_.slice_id}:capture_preflight",
            diagnostic_code="annual_capture_allocation_count_mismatch",
        )
    return captured_count, captures_by_period


def _select_annual_slices(
    available: tuple[InstalledAnnualCliSlice, ...],
    *,
    requested_ids: tuple[str, ...] | None,
) -> tuple[InstalledAnnualCliSlice, ...]:
    """Select an explicit annual subset without silently broadening scope."""
    if requested_ids is None:
        return available
    if not requested_ids or len(set(requested_ids)) != len(requested_ids):
        raise RetencionesInstalledCliError(stage="annual_preflight", diagnostic_code="invalid_annual_slice_selection")
    by_id = {slice_.slice_id: slice_ for slice_ in available}
    try:
        return tuple(by_id[slice_id] for slice_id in requested_ids)
    except KeyError as exc:
        raise RetencionesInstalledCliError(
            stage="annual_preflight",
            diagnostic_code="unknown_annual_slice_selection",
        ) from exc


def _is_full_annual_campaign(
    selected: tuple[InstalledAnnualCliSlice, ...],
    *,
    available: tuple[InstalledAnnualCliSlice, ...],
) -> bool:
    """Return whether every supported annual slice ran exactly once."""
    return len(selected) == len(available) and {slice_.slice_id for slice_ in selected} == {
        slice_.slice_id for slice_ in available
    }


def _run_annual_slice(
    *,
    cli: InstalledCli,
    slice_: InstalledAnnualCliSlice,
    layouts: Mapping[str, ExportLayoutDefinition],
    year: int,
    output_dir: Path,
) -> AnnualSliceEvidence:
    """Capture quarterly source evidence, then prove one annual return/export.

    The capture identities remain deliberately quarterly: Modelo 180/190 are
    materializations of those observations, not annual data-entry surfaces.
    Every readback is a separate installed process through :class:`InstalledCli`.
    """
    captured_count, captures_by_period = _capture_annual_source_allocations(cli, slice_, year)
    reopened_counts: dict[str, int] = {}
    for source_period in slice_.source_periods:
        period = source_period.period
        reopened = _require_result(
            cli,
            (
                "app",
                "modelo",
                "aggregate",
                "--modelo",
                slice_.source_modelo,
                "--year",
                str(year),
                "--period",
                period,
            ),
            stage=f"{slice_.slice_id}:fresh_reopen:{period}",
        )
        observed_count = _required_nonnegative_int(
            reopened,
            key="observation_count",
            stage=f"{slice_.slice_id}:fresh_reopen:{period}",
        )
        if observed_count != source_period.expected_observation_count:
            raise RetencionesInstalledCliError(
                stage=f"{slice_.slice_id}:fresh_reopen:{period}",
                diagnostic_code="annual_observation_count_mismatch",
            )
        reopened_counts[period] = observed_count

    no_activity_attestations = _attest_annual_no_activity_periods(
        cli=cli,
        slice_=slice_,
        captures_by_period=captures_by_period,
        year=year,
    )
    source_periods = tuple(
        _materialize_annual_source_period(
            cli=cli,
            source_modelo=slice_.source_modelo,
            source_revision=_annual_source_revision(slice_, stage=f"{slice_.slice_id}:source_preflight"),
            source_period=source_period,
            captures=tuple(captures_by_period.get(source_period.period, ())),
            year=year,
            no_activity_attestations=no_activity_attestations,
        )
        for source_period in slice_.source_periods
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
            diagnostic_code="annual_verification_not_complete",
        )

    target = output_dir / f"modelo-{slice_.modelo}-{year}-{slice_.period}.boe"
    _require_result(
        cli,
        ("app", "modelo", "export", work_id, "--output", str(target), "--by", _ACTOR),
        stage=f"{slice_.slice_id}:export",
    )
    if not target.is_file():
        raise RetencionesInstalledCliError(
            stage=f"{slice_.slice_id}:export",
            diagnostic_code="annual_export_artifact_missing",
        )
    payload = target.read_bytes()
    validation = _validate_annual_export(
        layout=layouts[slice_.slice_id],
        payload=payload,
        expected_header=slice_.expected_header_fields,
        expected_type2_rows=slice_.expected_type2_rows,
        stage=f"{slice_.slice_id}:export_parse",
    )
    artifact = ArtifactEvidence(
        modelo=slice_.modelo,
        period=slice_.period,
        path=str(target),
        size=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
    )
    return AnnualSliceEvidence(
        slice_id=slice_.slice_id,
        modelo=slice_.modelo,
        period=slice_.period,
        revision=slice_.revision,
        source_modelo=slice_.source_modelo,
        captured_allocation_count=captured_count,
        reopened_observation_counts=reopened_counts,
        source_periods=source_periods,
        calculation_revision_id=revision_id,
        verification_granted=True,
        artifact=artifact,
        export_validation=validation,
    )
