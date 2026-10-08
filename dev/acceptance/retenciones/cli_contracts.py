"""Typed installed withholding evidence and stable failure contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

from dev.acceptance.income_tax.cli_journey import ArtifactEvidence
from dev.acceptance.installed_cli import CommandEvidence

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
        return dict[str, object](asdict(self))


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
        return dict[str, object](asdict(self))


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
        return dict[str, object](asdict(self))
