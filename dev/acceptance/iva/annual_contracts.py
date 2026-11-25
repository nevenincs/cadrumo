"""Value-free IVA annual and quarterly local-filing receipt contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Final, cast

from .cli_journey import (
    SanitizedCommandReceipt,
)

FOUNDATION_PERIOD: Final = "1T"


FOUNDATION_SALE_IVA: Final = Decimal("21.00")


_FOUNDATION_PURCHASE_IVA: Final = Decimal("10.50")


FOUNDATION_EXPECTED_RESULT: Final = FOUNDATION_SALE_IVA - _FOUNDATION_PURCHASE_IVA


QUARTERS: Final = ("1T", "2T", "3T", "4T")


FINAL_QUARTER: Final = "4T"


ANNUAL_PERIOD: Final = "0A"


M390_COORDINATES: Final = (*(("303", quarter) for quarter in QUARTERS), ("390", ANNUAL_PERIOD))


PRIVATE_ARTIFACT_PLACEHOLDER: Final = "<synthetic-purchase-artifact>"


@dataclass(frozen=True, slots=True)
class IvaAnnualFoundationCliJourneyReceipt:
    """Sanitized evidence for the preserved ordinary local 1T path."""

    schema_version: str
    acceptance_ids: tuple[str, ...]
    filing_year: int
    executable: str
    executable_sha256: str
    source_identity: str
    package_identity: str
    authority_generation: str
    authority_descriptor_sha256: str
    storage_root: str
    purchase_artifact: str
    transaction_ids: tuple[str, str]
    invoice_ids: tuple[str, str]
    evidence_id: str
    work_unit_id: str
    calculation_revision_id: str
    iva_resultado: str
    verification_report_id: str
    verification_status: str
    filing_record_id: str
    filing_origin: str
    filing_confirmation: str
    filing_aeat_accepted: bool
    filing_live_submission: bool
    commands: tuple[SanitizedCommandReceipt, ...]

    def to_dict(self) -> dict[str, object]:
        """Return receipt metadata without source bytes, paths, or secrets."""
        return cast(dict[str, object], asdict(self))


@dataclass(frozen=True, slots=True)
class IvaQuarterlyLocalFilingReceipt:
    """One verified local 303 source for the annual reconciliation."""

    period: str
    work_unit_id: str
    calculation_revision_id: str
    iva_resultado: str
    verification_report_id: str
    verification_status: str
    filing_record_id: str
    filing_origin: str
    filing_confirmation: str
    filing_aeat_accepted: bool
    filing_live_submission: bool


@dataclass(frozen=True, slots=True)
class IvaAnnualM390CliJourneyReceipt:
    """Sanitized evidence for four local 303 records and one verified annual Modelo 390."""

    schema_version: str
    acceptance_ids: tuple[str, ...]
    filing_year: int
    executable: str
    executable_sha256: str
    source_identity: str
    package_identity: str
    authority_generation: str
    authority_descriptor_sha256: str
    storage_root: str
    purchase_artifact: str
    transaction_ids: tuple[str, ...]
    evidence_id: str
    quarterly_filings: tuple[IvaQuarterlyLocalFilingReceipt, ...]
    annual_work_unit_id: str
    annual_calculation_revision_id: str
    annual_verification_report_id: str
    annual_verification_status: str
    annual_devengada: str
    annual_deducible: str
    annual_resultado: str
    commands: tuple[SanitizedCommandReceipt, ...]

    def to_dict(self) -> dict[str, object]:
        """Return receipt metadata without source bytes, paths, or secrets."""
        return cast(dict[str, object], asdict(self))


class IvaProrrataSettlementScenario(StrEnum):
    """The register state a fourth quarter's export meets."""

    SETTLED = "settled"
    """No declaration for the year: the export reads the register as filing will leave it."""
    UNDECLARED_SECTOR = "undeclared-sector"
    """A declared differentiated sector with no entry for the year: the export refuses."""
    PRIOR_YEAR_ESPECIAL = "prior-year-especial"
    """An especial year before and no declaration for this one: the export refuses."""


@dataclass(frozen=True, slots=True)
class IvaAnnualProrrataSettlementCliJourneyReceipt:
    """Sanitized evidence for the year's last Modelo 303 meeting one register state at export."""

    schema_version: str
    acceptance_ids: tuple[str, ...]
    filing_year: int
    scenario: str
    executable: str
    executable_sha256: str
    source_identity: str
    package_identity: str
    authority_generation: str
    authority_descriptor_sha256: str
    storage_root: str
    work_unit_id: str
    calculation_revision_id: str
    definitive_percentage: str
    exported_opcion: str
    exported_revocacion: str
    refusal_code: str
    filing_record_id: str
    next_year_provisional_percentage: str
    commands: tuple[SanitizedCommandReceipt, ...]

    def to_dict(self) -> dict[str, object]:
        """Return receipt metadata without source bytes, paths, or secrets."""
        return cast(dict[str, object], asdict(self))
