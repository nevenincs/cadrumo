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
from typing import Any, Literal, cast

from cadrumo.domain.calculations.registry.authority import IndexedRegistryAuthority
from cadrumo.domain.calculations.registry.export import resolve_export_layout
from cadrumo.domain.calculations.registry.export_parse import (
    ParsedExportFieldValue,
    ParsedExportPayload,
    parse_export_payload,
)
from cadrumo.domain.calculations.registry.schema_exports import ExportLayoutDefinition, ExportRecordDefinition
from dev.acceptance.income_tax.cli_journey import ArtifactEvidence
from dev.acceptance.installed_cli import CommandEvidence, InstalledCli

from .scenario import (
    BRIEF_ID,
    BRIEF_REVISION,
    INSTALLED_ANNUAL_CLI_SCENARIO_VERSION,
    INSTALLED_CLI_SCENARIO_VERSION,
    PATTERN_ID,
    PATTERN_REVISION,
    SUPPORTED_YEAR,
    AnnualExportRecordExpectation,
    AnnualSourcePeriodInput,
    EvidenceState,
    InstalledAnnualCliSlice,
    InstalledPeriodicCliSlice,
    Modelo180PropertyInput,
    Modelo190AnnualDetailInput,
    PaymentAllocation,
    build_installed_annual_cli_slices,
    build_installed_periodic_cli_slices,
    money,
)

_SCHEMA_VERSION = "retenciones-01-installed-cli-journey-v1"
_ANNUAL_SCHEMA_VERSION = "retenciones-01-installed-annual-cli-journey-v1"
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
class AnnualExportValidationEvidence:
    """Independent parser evidence for actual annual header and type-2 rows."""

    layout_id: str
    parsed_header_fields: dict[str, str]
    expected_header_fields: dict[str, str]
    parsed_type2_rows: tuple[dict[str, str], ...]
    expected_type2_rows: tuple[dict[str, str], ...]


@dataclass(frozen=True, slots=True)
class AnnualSourcePeriodEvidence:
    """One labelled annual-source state used by the annual local chain.

    A filed local source record and an explicit no-activity attestation are
    intentionally different evidence forms.  Modelo 111 retains its profile
    fact alone; Modelo 115 uses its profile fact to authorise an otherwise
    valid local zero source record.  Neither is a synthetic payment.
    """

    modelo: str
    period: str
    evidence_state: str
    source_workflow: Literal[
        "local_filing_record",
        "m111_no_retenciones_attestation",
        "m115_no_relevant_payment_attested_local_filing_record",
    ]
    work_unit_id: str | None
    calculation_revision_id: str | None
    calculated_casillas: dict[str, str] | None
    verification_granted: bool
    filing_record_id: str | None
    live_submission: Literal[False]
    attestation_period: str | None


@dataclass(frozen=True, slots=True)
class AnnualSliceEvidence:
    """One public quarterly-evidence-to-annual-export journey."""

    slice_id: str
    modelo: str
    period: str
    revision: str
    source_modelo: str
    captured_allocation_count: int
    reopened_observation_counts: dict[str, int]
    source_periods: tuple[AnnualSourcePeriodEvidence, ...]
    calculation_revision_id: str
    verification_granted: bool
    artifact: ArtifactEvidence
    export_validation: AnnualExportValidationEvidence


@dataclass(frozen=True, slots=True)
class RetencionesAnnualCliJourneyEvidence:
    """Sanitized receipt for the annual 180/190 installed CLI campaign."""

    schema_version: str
    status: Literal["proven", "partial"]
    campaign_scope: Literal["full_annual_campaign", "selected_annual_slices"]
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
    slices: tuple[AnnualSliceEvidence, ...]
    commands: tuple[CommandEvidence, ...]
    retention: str

    def to_dict(self) -> dict[str, object]:
        """Return the stable JSON-safe annual acceptance receipt."""
        return asdict(self)


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


def run_retenciones_annual_cli_journey(
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
) -> RetencionesAnnualCliJourneyEvidence:
    """Run public capture through annual Modelo 180/190 export validation.

    The caller receives a distinct receipt from the periodic journey.  This
    prevents a successful annual subset from being relabelled as full
    withholding-campaign completion while preserving a durable vertical-slice
    result for each supported annual return.
    """
    available_slices = build_installed_annual_cli_slices(year)
    slices = _select_annual_slices(available_slices, requested_ids=slice_ids)
    _require_nonempty_identity(source_identity, label="source_identity")
    _require_nonempty_identity(package_identity, label="package_identity")
    storage = _fresh_directory(storage_root, label="annual scenario storage root")
    outputs = _fresh_directory(output_dir, label="annual scenario output directory")
    authority_generation, layouts = _selected_annual_layouts(authority_root=authority_root, slices=slices, year=year)
    cli = InstalledCli(
        executable,
        storage_root=storage,
        authority_root=authority_root,
        passphrase=secrets.token_urlsafe(32),
    )
    try:
        _create_withholding_profile(cli, year=year)
        evidence = tuple(
            _run_annual_slice(cli=cli, slice_=slice_, layouts=layouts, year=year, output_dir=outputs)
            for slice_ in slices
        )
    except RetencionesInstalledCliError as exc:
        if not exc.commands:
            exc.commands = tuple(cli.commands)
        raise
    except Exception as exc:
        raise RetencionesInstalledCliError(
            stage="annual_driver",
            diagnostic_code=f"unexpected_{type(exc).__name__}",
            commands=tuple(cli.commands),
        ) from exc
    full_campaign = _is_full_annual_campaign(slices, available=available_slices)
    return RetencionesAnnualCliJourneyEvidence(
        schema_version=_ANNUAL_SCHEMA_VERSION,
        status="proven" if full_campaign else "partial",
        campaign_scope="full_annual_campaign" if full_campaign else "selected_annual_slices",
        pattern_id=PATTERN_ID,
        pattern_revision=PATTERN_REVISION,
        brief_id=BRIEF_ID,
        brief_revision=BRIEF_REVISION,
        scenario=INSTALLED_ANNUAL_CLI_SCENARIO_VERSION,
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
        retention="caller_owned_encrypted_store_and_validated_synthetic_annual_artifacts",
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


def _is_full_campaign(
    selected: tuple[InstalledPeriodicCliSlice, ...],
    *,
    available: tuple[InstalledPeriodicCliSlice, ...],
) -> bool:
    """Return whether the receipt covers every required periodic slice exactly once."""
    return len(selected) == len(available) and {slice_.slice_id for slice_ in selected} == {
        slice_.slice_id for slice_ in available
    }


def _is_full_annual_campaign(
    selected: tuple[InstalledAnnualCliSlice, ...],
    *,
    available: tuple[InstalledAnnualCliSlice, ...],
) -> bool:
    """Return whether every supported annual slice ran exactly once."""
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
            # Modelo 111 requires this filing-header attestation.  The value
            # is a synthetic operator fact, deliberately supplied through
            # the now-public profile edit surface rather than seeded.
            "--no-colegio-concertado",
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


def _attest_annual_no_activity_periods(
    *,
    cli: InstalledCli,
    slice_: InstalledAnnualCliSlice,
    captures_by_period: Mapping[str, Sequence[InstalledPeriodicCliSlice]],
    year: int,
) -> frozenset[str]:
    """Record the source modelo's explicit public no-activity facts.

    Modelo 111 retains its no-retenciones profile fact rather than creating a
    zero local filing.  Modelo 115's distinct no-relevant-payment fact instead
    authorises its local zero calculation and source filing.  Both are public
    operator evidence and neither invents a payment allocation.
    """
    option_by_modelo = {
        "111": "--modelo-111-no-retenciones-periods",
        "115": "--modelo-115-no-relevant-payment-periods",
    }
    option = option_by_modelo.get(slice_.source_modelo)
    if option is None:
        return frozenset()
    tokens: list[str] = []
    for source_period in slice_.source_periods:
        captures = tuple(captures_by_period.get(source_period.period, ()))
        _assert_source_period_evidence(
            source_period=source_period,
            captures=captures,
            stage=f"{slice_.slice_id}:{slice_.source_modelo}_no_activity_preflight:{source_period.period}",
        )
        if not captures:
            tokens.append(f"{year}:{source_period.period}")
    if not tokens:
        return frozenset()
    _require_result(
        cli,
        (
            "config",
            "profile",
            "edit",
            f"income-{year}",
            "--quiet",
            option,
            ",".join(tokens),
        ),
        stage=f"{slice_.slice_id}:{slice_.source_modelo}_no_activity_attestation",
    )
    return frozenset(tokens)


def _materialize_annual_source_period(
    *,
    cli: InstalledCli,
    source_modelo: str,
    source_revision: str,
    source_period: AnnualSourcePeriodInput,
    captures: tuple[InstalledPeriodicCliSlice, ...],
    year: int,
    no_activity_attestations: frozenset[str],
) -> AnnualSourcePeriodEvidence:
    """Materialize a local source record or retain a supported no-duty state.

    ``work file`` is deliberately checked as an internal local record only. It
    is the canonical producer of the ``app_filing`` carry observation; it does
    not contact AEAT or establish external filing evidence.  A no-activity
    Modelo 111 period is represented instead by its profile attestation, with
    no work unit, calculation revision, or local filing record.  Modelo 115's
    public no-relevant-payment attestation authorises a local zero source
    record, which supplies the annual cross-period relation without claiming
    AEAT submission.
    """
    stage = f"{source_modelo}:{source_period.period}:annual_source"
    if any(
        capture.modelo != source_modelo or capture.revision != source_revision or capture.period != source_period.period
        for capture in captures
    ):
        raise RetencionesInstalledCliError(
            stage=f"{stage}:preflight",
            diagnostic_code="annual_source_period_coordinate_mismatch",
        )
    _assert_source_period_evidence(
        source_period=source_period,
        captures=captures,
        stage=f"{stage}:preflight",
    )
    if not captures:
        attestation_period = f"{year}:{source_period.period}"
        if source_modelo == "111":
            if attestation_period not in no_activity_attestations:
                raise RetencionesInstalledCliError(
                    stage=f"{stage}:preflight",
                    diagnostic_code="annual_source_m111_no_retenciones_attestation_missing",
                )
            return AnnualSourcePeriodEvidence(
                modelo=source_modelo,
                period=source_period.period,
                evidence_state=source_period.evidence_state.value,
                source_workflow="m111_no_retenciones_attestation",
                work_unit_id=None,
                calculation_revision_id=None,
                calculated_casillas=None,
                verification_granted=False,
                filing_record_id=None,
                live_submission=False,
                attestation_period=attestation_period,
            )
        if source_modelo != "115":
            raise RetencionesInstalledCliError(
                stage=f"{stage}:preflight",
                diagnostic_code="annual_source_no_activity_workflow_unsupported",
            )
        if attestation_period not in no_activity_attestations:
            raise RetencionesInstalledCliError(
                stage=f"{stage}:preflight",
                diagnostic_code="annual_source_m115_no_relevant_payment_attestation_missing",
            )
    work = _require_result(
        cli,
        (
            "app",
            "modelo",
            "work",
            "create",
            "--modelo",
            source_modelo,
            "--year",
            str(year),
            "--period",
            source_period.period,
            "--revision",
            source_revision,
            "--by",
            _ACTOR,
        ),
        stage=f"{stage}:work_create",
    )
    work_id = _required_text(work, key="work_unit_id", stage=f"{stage}:work_create")
    calculation = _require_result(
        cli,
        ("app", "modelo", "work", "calculate", work_id, "--by", _ACTOR),
        stage=f"{stage}:work_calculate",
    )
    calculated_casillas = _expected_casillas_from_result(
        calculation,
        expected=source_period.expected_casillas,
        stage=f"{stage}:work_calculate",
    )
    revision_id = _required_text(
        calculation,
        key="calculation_revision_id",
        stage=f"{stage}:work_calculate",
    )
    verification = _require_result(
        cli,
        ("app", "modelo", "work", "verify", revision_id, "--by", _ACTOR),
        stage=f"{stage}:work_verify",
    )
    if verification.get("granted_verificado_completo") is not True:
        raise RetencionesInstalledCliError(
            stage=f"{stage}:work_verify",
            diagnostic_code="annual_source_verification_not_complete",
        )
    filing = _require_result(
        cli,
        ("app", "modelo", "work", "file", revision_id, "--by", _ACTOR),
        stage=f"{stage}:work_file",
    )
    if filing.get("live_submission") is not False or filing.get("aeat_accepted") is not False:
        raise RetencionesInstalledCliError(
            stage=f"{stage}:work_file",
            diagnostic_code="annual_source_filing_not_local",
        )
    filing_id = _required_text(filing, key="filing_record_id", stage=f"{stage}:work_file")
    m115_no_relevant_payment_attestation = not captures and source_modelo == "115"
    return AnnualSourcePeriodEvidence(
        modelo=source_modelo,
        period=source_period.period,
        evidence_state=source_period.evidence_state.value,
        source_workflow=(
            "m115_no_relevant_payment_attested_local_filing_record"
            if m115_no_relevant_payment_attestation
            else "local_filing_record"
        ),
        work_unit_id=work_id,
        calculation_revision_id=revision_id,
        calculated_casillas=calculated_casillas,
        verification_granted=True,
        filing_record_id=filing_id,
        live_submission=False,
        attestation_period=(f"{year}:{source_period.period}" if m115_no_relevant_payment_attestation else None),
    )


def _annual_source_revision(slice_: InstalledAnnualCliSlice, *, stage: str) -> str:
    """Require the annual slice's public captures to share one source revision."""
    revisions = {capture.revision for capture in slice_.captures}
    if len(revisions) != 1:
        raise RetencionesInstalledCliError(stage=stage, diagnostic_code="annual_source_revision_ambiguous")
    return next(iter(revisions))


def _assert_source_period_evidence(
    *,
    source_period: AnnualSourcePeriodInput,
    captures: tuple[InstalledPeriodicCliSlice, ...],
    stage: str,
) -> None:
    """Keep no-activity zeros distinct from public payment-allocation evidence."""
    observed_count = sum(capture.expected_observation_count for capture in captures)
    if observed_count != source_period.expected_observation_count:
        raise RetencionesInstalledCliError(stage=stage, diagnostic_code="annual_source_observation_count_mismatch")
    if captures:
        expected_from_captures = _aggregate_source_casillas(captures=captures, stage=stage)
        if expected_from_captures != source_period.expected_casillas:
            raise RetencionesInstalledCliError(stage=stage, diagnostic_code="annual_source_casilla_oracle_mismatch")
        if source_period.evidence_state is not EvidenceState.AVAILABLE:
            raise RetencionesInstalledCliError(stage=stage, diagnostic_code="annual_source_payment_state_mismatch")
        return
    if source_period.evidence_state is not EvidenceState.NO_RELEVANT_PAYMENT:
        raise RetencionesInstalledCliError(stage=stage, diagnostic_code="annual_source_empty_state_mismatch")
    if any(value != Decimal("0") for _casilla_id, value in source_period.expected_casillas):
        raise RetencionesInstalledCliError(stage=stage, diagnostic_code="annual_source_empty_casilla_not_zero")


def _aggregate_source_casillas(
    *, captures: tuple[InstalledPeriodicCliSlice, ...], stage: str
) -> tuple[tuple[str, Decimal], ...]:
    """Combine independent quarterly scenario facts without a second resolver."""
    source_modelo = captures[0].modelo
    count_casilla_by_modelo = {"111": "07", "115": "01"}
    count_casilla = count_casilla_by_modelo.get(source_modelo)
    if count_casilla is None:
        raise RetencionesInstalledCliError(stage=stage, diagnostic_code="annual_source_modelo_oracle_unsupported")
    expected_ids = tuple(casilla_id for casilla_id, _value in captures[0].expected_casillas)
    if any(
        tuple(casilla_id for casilla_id, _value in capture.expected_casillas) != expected_ids for capture in captures
    ):
        raise RetencionesInstalledCliError(stage=stage, diagnostic_code="annual_source_casilla_shape_mismatch")
    totals = {casilla_id: Decimal("0") for casilla_id in expected_ids}
    for capture in captures:
        for casilla_id, value in capture.expected_casillas:
            totals[casilla_id] += value
    if count_casilla not in totals:
        raise RetencionesInstalledCliError(stage=stage, diagnostic_code="annual_source_count_casilla_missing")
    totals[count_casilla] = Decimal(len({capture.counterparty_nif for capture in captures}))
    return tuple((casilla_id, totals[casilla_id]) for casilla_id in expected_ids)


def _capture_invoice_withholding(*, cli: InstalledCli, slice_: InstalledPeriodicCliSlice, year: int) -> str:
    """Capture one invoice's allocations only through the public typed CLI flag."""
    invoice_id = _create_received_invoice(cli, slice_=slice_)
    for allocation in slice_.allocations:
        request = _invoice_withholding_request(slice_=slice_, invoice_id=invoice_id, allocation=allocation)
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
    return invoice_id


def _invoice_withholding_request(
    *,
    slice_: InstalledPeriodicCliSlice,
    invoice_id: str,
    allocation: PaymentAllocation,
) -> dict[str, object]:
    """Render evidence facts without admitting a caller-derived recognition date."""
    request: dict[str, object] = {
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
    if slice_.modelo_180_property is not None:
        request["modelo_180_property"] = _modelo_180_property_payload(slice_.modelo_180_property)
    if slice_.modelo_190_detail is not None:
        request["modelo_190_detail"] = _modelo_190_detail_payload(
            detail=slice_.modelo_190_detail,
            slice_=slice_,
            invoice_id=invoice_id,
            allocation=allocation,
        )
    return request


def _modelo_180_property_payload(detail: Modelo180PropertyInput) -> dict[str, object]:
    """Render only the accepted explicit property-attribution evidence."""
    return {
        "property_key": detail.property_key,
        "situation": detail.situation,
        "cadastral_reference": detail.cadastral_reference,
        "recipient_province_code": detail.recipient_province_code,
        "modality": detail.modality,
        "accrual_year": detail.accrual_year,
        "withholding_percentage": _money_text(detail.withholding_percentage),
        "address": {
            "province_code": detail.province_code,
            "municipality_code": "079",
            "municipality": "Madrid",
            "locality": "Madrid",
            "postal_code": detail.postal_code,
            "street_type": "CL",
            "street_name": "Ejemplo",
            "number_type": "NUM",
            "house_number": "1",
        },
    }


def _modelo_190_detail_payload(
    *,
    detail: Modelo190AnnualDetailInput,
    slice_: InstalledPeriodicCliSlice,
    invoice_id: str,
    allocation: PaymentAllocation,
) -> dict[str, object]:
    """Render the typed annual detail that the producer checks against evidence."""
    zero = "0.00"
    return {
        "source_id": invoice_id,
        "source_allocation_id": allocation.allocation_id,
        "perceptor_tax_id": slice_.counterparty_nif,
        "perceptor_legal_name": slice_.counterparty_name,
        "transaction_date": allocation.paid_on.isoformat(),
        "clave": detail.clave,
        "subclave": detail.subclave,
        "province_code": detail.province_code,
        "territorial_deduction_clave": detail.territorial_deduction_clave,
        "percibido_dinerario": _money_text(allocation.allocated_base),
        "retencion_practicada": _money_text(allocation.allocated_withholding),
        "incapacity_cash_perception": zero,
        "incapacity_cash_withholding": zero,
        "incapacity_kind_value": zero,
        "incapacity_kind_ingreso_a_cuenta": zero,
        "incapacity_kind_repercutido": zero,
        "foral_retention_estatal": zero,
        "foral_retention_navarra": zero,
        "foral_retention_araba": zero,
        "foral_retention_gipuzkoa": zero,
        "foral_retention_bizkaia": zero,
        "base_retenciones": _money_text(allocation.allocated_base),
        "porcentaje_retencion": _percentage_text(slice_.invoice_withholding_rate),
    }


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


def _selected_annual_layouts(
    *, authority_root: Path, slices: tuple[InstalledAnnualCliSlice, ...], year: int
) -> tuple[str, dict[str, ExportLayoutDefinition]]:
    """Load the selected annual layouts through the same local authority descriptor."""
    descriptor = authority_root.resolve(strict=True) / "authority.current.json"
    if not descriptor.is_file():
        raise RetencionesInstalledCliError(
            stage="annual_authority_preflight",
            diagnostic_code="authority_descriptor_missing",
        )
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
            stage="annual_authority_preflight",
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


def _validate_annual_export(
    *,
    layout: ExportLayoutDefinition,
    payload: bytes,
    expected_header: tuple[tuple[str, str], ...],
    expected_type2_rows: tuple[AnnualExportRecordExpectation, ...],
    stage: str,
) -> AnnualExportValidationEvidence:
    """Independently parse annual header/count/control and emitted type-2 rows."""
    try:
        parsed = parse_export_payload(layout, payload)
    except Exception as exc:
        raise RetencionesInstalledCliError(
            stage=stage,
            diagnostic_code=f"canonical_annual_export_parse_{type(exc).__name__}",
        ) from exc
    if str(parsed.layout_id) != str(layout.id):
        raise RetencionesInstalledCliError(stage=stage, diagnostic_code="annual_export_layout_mismatch")
    header_record = _record_for_type(layout=layout, record_type="declarante", stage=stage)
    type2_record = _record_for_type(layout=layout, record_type="perceptor", stage=stage)
    header_rows = _parsed_record_rows(parsed=parsed, record=header_record, stage=stage)
    type2_rows = _parsed_record_rows(parsed=parsed, record=type2_record, stage=stage)
    if len(header_rows) != 1:
        raise RetencionesInstalledCliError(stage=stage, diagnostic_code="annual_export_header_count_mismatch")

    expected_header_values = dict(expected_header)
    actual_header = header_rows[0]
    parsed_header = _selected_expected_fields(
        actual=actual_header,
        expected=expected_header_values,
        stage=stage,
        mismatch_code="annual_export_header_field_mismatch",
    )
    if len(type2_rows) != len(expected_type2_rows):
        raise RetencionesInstalledCliError(stage=stage, diagnostic_code="annual_export_type2_count_mismatch")
    _assert_header_count_matches_type2_rows(
        parsed_header=parsed_header,
        expected_header=expected_header_values,
        actual_type2_count=len(type2_rows),
        stage=stage,
    )
    expected_rows = tuple(dict(row.values) for row in expected_type2_rows)
    expected_row_fields = {field_id: "" for expected in expected_rows for field_id in expected}
    parsed_rows = tuple(
        _selected_annual_row_fields(
            actual=row,
            expected=expected_row_fields,
            stage=stage,
        )
        for row in type2_rows
    )
    if sorted(_row_identity(row) for row in parsed_rows) != sorted(_row_identity(row) for row in expected_rows):
        raise RetencionesInstalledCliError(stage=stage, diagnostic_code="annual_export_type2_rows_mismatch")
    return AnnualExportValidationEvidence(
        layout_id=str(parsed.layout_id),
        parsed_header_fields=dict(sorted(parsed_header.items())),
        expected_header_fields=dict(sorted(expected_header_values.items())),
        parsed_type2_rows=tuple(dict(sorted(row.items())) for row in parsed_rows),
        expected_type2_rows=tuple(dict(sorted(row.items())) for row in expected_rows),
    )


def _record_for_type(*, layout: ExportLayoutDefinition, record_type: str, stage: str) -> ExportRecordDefinition:
    """Return one unambiguous official record family by its registry type."""
    matches = tuple(record for record in layout.records if record.record_type == record_type)
    if len(matches) != 1:
        raise RetencionesInstalledCliError(stage=stage, diagnostic_code=f"annual_export_{record_type}_record_mismatch")
    return matches[0]


def _parsed_record_rows(
    *, parsed: ParsedExportPayload, record: ExportRecordDefinition, stage: str
) -> tuple[dict[str, str], ...]:
    """Reconstruct fixed-width record instances in canonical layout field order."""
    expected_field_ids = tuple(str(field.id) for field in sorted(record.fields, key=lambda item: item.offset or 0))
    if not expected_field_ids:
        raise RetencionesInstalledCliError(stage=stage, diagnostic_code="annual_export_empty_record_layout")
    record_fields = tuple(field for field in parsed.fields if str(field.record_id) == str(record.id))
    if len(record_fields) % len(expected_field_ids) != 0:
        raise RetencionesInstalledCliError(stage=stage, diagnostic_code="annual_export_record_extent_mismatch")
    rows: list[dict[str, str]] = []
    for offset in range(0, len(record_fields), len(expected_field_ids)):
        row = record_fields[offset : offset + len(expected_field_ids)]
        if tuple(str(field.field_id) for field in row) != expected_field_ids:
            raise RetencionesInstalledCliError(stage=stage, diagnostic_code="annual_export_record_field_order_mismatch")
        rows.append({str(field.field_id): _parsed_field_text(field) for field in row})
    return tuple(rows)


def _selected_expected_fields(
    *, actual: Mapping[str, str], expected: Mapping[str, str], stage: str, mismatch_code: str
) -> dict[str, str]:
    """Require every independently authored annual expectation from a parsed row."""
    selected: dict[str, str] = {}
    for field_id, expected_value in expected.items():
        actual_value = actual.get(field_id)
        if actual_value != expected_value:
            raise RetencionesInstalledCliError(stage=stage, diagnostic_code=mismatch_code)
        if actual_value is None:  # Keeps the receipt type honest after the equality check.
            raise RetencionesInstalledCliError(stage=stage, diagnostic_code=mismatch_code)
        selected[field_id] = actual_value
    return selected


def _selected_annual_row_fields(
    *, actual: Mapping[str, str], expected: Mapping[str, str], stage: str
) -> dict[str, str]:
    """Select required row fields before comparing unordered emitted record identities."""
    selected: dict[str, str] = {}
    for field_id in expected:
        actual_value = actual.get(field_id)
        if actual_value is None:
            raise RetencionesInstalledCliError(stage=stage, diagnostic_code="annual_export_type2_field_missing")
        selected[field_id] = actual_value
    return selected


def _assert_header_count_matches_type2_rows(
    *,
    parsed_header: Mapping[str, str],
    expected_header: Mapping[str, str],
    actual_type2_count: int,
    stage: str,
) -> None:
    """Prove the emitted-record count agrees with the exported control field."""
    count_ids = tuple(
        field_id
        for field_id in expected_header
        if field_id.endswith("total-perceptores") or field_id.endswith("total-percepciones")
    )
    if len(count_ids) != 1:
        raise RetencionesInstalledCliError(stage=stage, diagnostic_code="annual_export_count_field_ambiguous")
    try:
        parsed_count = int(parsed_header[count_ids[0]])
    except (TypeError, ValueError) as exc:
        raise RetencionesInstalledCliError(stage=stage, diagnostic_code="annual_export_count_field_invalid") from exc
    if parsed_count != actual_type2_count:
        raise RetencionesInstalledCliError(stage=stage, diagnostic_code="annual_export_count_control_mismatch")


def _parsed_field_text(field: ParsedExportFieldValue) -> str:
    """Normalize parser values into the synthetic fixture's stable value form."""
    value = field.value
    if isinstance(value, Decimal):
        return _money_or_integer_text(value)
    return str(value)


def _row_identity(row: Mapping[str, str]) -> tuple[tuple[str, str], ...]:
    """Compare independently ordered type-2 expectations without hiding duplicates."""
    return tuple(sorted(row.items()))


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
    casilla_values = cast(Mapping[str, object], values)
    observed: dict[str, str] = {}
    for casilla_id, expected_value in expected:
        try:
            value = _as_decimal(casilla_values.get(casilla_id))
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
        error_document: Mapping[str, object] = cast(Mapping[str, object], error) if isinstance(error, Mapping) else {}
        code: object | None = error_document.get("code")
        raise RetencionesInstalledCliError(
            stage=stage,
            diagnostic_code=str(code) if isinstance(code, str) and code else "installed_cli_error",
        )
    result = document.get("result")
    if not isinstance(result, dict):
        raise RetencionesInstalledCliError(stage=stage, diagnostic_code="installed_cli_result_missing")
    return cast(dict[str, Any], result)


def _required_text(result: Mapping[str, Any], *, key: str, stage: str) -> str:
    """Read a stable CLI result identity without retaining the result object."""
    value = result.get(key)
    if not isinstance(value, str) or not value:
        raise RetencionesInstalledCliError(stage=stage, diagnostic_code=f"missing_{key}")
    return value


def _required_nonnegative_int(result: Mapping[str, Any], *, key: str, stage: str) -> int:
    """Read an aggregate readback count from a public result envelope."""
    value: object = result.get(key)
    if isinstance(value, bool):
        raise RetencionesInstalledCliError(stage=stage, diagnostic_code=f"invalid_{key}")
    if not isinstance(value, (str, int, float, Decimal)):
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
    schema_version: str = _SCHEMA_VERSION,
    scenario: str = INSTALLED_CLI_SCENARIO_VERSION,
) -> RetencionesCliFailureEvidence:
    """Render a complete failure receipt without exception or stream contents."""
    return RetencionesCliFailureEvidence(
        schema_version=schema_version,
        status="failed",
        pattern_id=PATTERN_ID,
        pattern_revision=PATTERN_REVISION,
        brief_id=BRIEF_ID,
        brief_revision=BRIEF_REVISION,
        scenario=scenario,
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
    parser.add_argument(
        "--annual",
        action="store_true",
        help="Run the public capture-to-annual Modelo 180/190 journey.",
    )
    parser.add_argument(
        "--annual-slice",
        action="append",
        dest="annual_slice_ids",
        help="Run one named annual slice; repeat only for an explicit subset.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the installed acceptance journey and persist a sanitized receipt."""
    parser = _parser()
    args = parser.parse_args(argv)
    if args.annual and args.slice_ids:
        parser.error("--slice is periodic-only; use --annual-slice with --annual")
    if not args.annual and args.annual_slice_ids:
        parser.error("--annual-slice requires --annual")
    is_annual = bool(args.annual)
    failure_schema_version = _ANNUAL_SCHEMA_VERSION if is_annual else _SCHEMA_VERSION
    failure_scenario = INSTALLED_ANNUAL_CLI_SCENARIO_VERSION if is_annual else INSTALLED_CLI_SCENARIO_VERSION
    try:
        if is_annual:
            evidence = run_retenciones_annual_cli_journey(
                executable=args.cli,
                authority_root=args.authority_root,
                storage_root=args.storage_root,
                output_dir=args.output_dir,
                year=args.year,
                as_of=args.as_of,
                source_identity=args.source_identity,
                package_identity=args.package_identity,
                slice_ids=None if args.annual_slice_ids is None else tuple(args.annual_slice_ids),
            )
        else:
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
            schema_version=failure_schema_version,
            scenario=failure_scenario,
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
            schema_version=failure_schema_version,
            scenario=failure_scenario,
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
    "AnnualExportValidationEvidence",
    "AnnualSliceEvidence",
    "AnnualSourcePeriodEvidence",
    "ExportValidationEvidence",
    "PeriodicSliceEvidence",
    "RetencionesAnnualCliJourneyEvidence",
    "RetencionesCliFailureEvidence",
    "RetencionesCliJourneyEvidence",
    "RetencionesInstalledCliError",
    "main",
    "run_retenciones_annual_cli_journey",
    "run_retenciones_cli_journey",
]
