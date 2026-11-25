"""Installed IVA quarter filing and ordered fresh-process local-chain guards."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from dev.acceptance.installed_cli import InstalledCli

from .annual_contracts import FINAL_QUARTER, QUARTERS, IvaQuarterlyLocalFilingReceipt
from .annual_projection import decimal_casilla, period_code, unique_row
from .cli_journey import (
    IvaCliJourneyError,
    SanitizedCommandReceipt,
    required_id,
    required_text,
    result,
    run,
)
from .filing_year import IvaJourneyYear


def _require_quarter_filing_identity(
    filed: dict[str, object], work_id: str, revision_id: str, period: str
) -> tuple[str, str, str]:
    """Require quarter filing identity."""
    filing_id, origin, confirmation = (
        required_id(filed, "filing_record_id"),
        required_text(filed, "origin"),
        required_text(filed, "confirmation"),
    )
    if (
        filed.get("work_unit_id") != work_id
        or filed.get("calculation_revision_id") != revision_id
        or origin != "local"
        or confirmation != "pendiente"
    ):
        raise IvaCliJourneyError(f"Modelo 303 {period} local filing identity or state is invalid")
    if (
        filed.get("aeat_accepted") is not False
        or filed.get("live_submission") is not False
        or filed.get("external_evidence") is not None
    ):
        raise IvaCliJourneyError(f"Modelo 303 {period} local filing claimed external confirmation")
    return filing_id, origin, confirmation


def require_foundation_filing_identity(
    filed: dict[str, object], work_unit_id: str, calculation_revision_id: str
) -> tuple[str, str, str]:
    """Require foundation filing identity."""
    filing_record_id = required_id(filed, "filing_record_id")
    filing_origin = required_text(filed, "origin")
    filing_confirmation = required_text(filed, "confirmation")
    if filed.get("work_unit_id") != work_unit_id or filed.get("calculation_revision_id") != calculation_revision_id:
        raise IvaCliJourneyError("Modelo 303 file returned another work unit or calculation revision")
    if filing_origin != "local" or filing_confirmation != "pendiente":
        raise IvaCliJourneyError("Modelo 303 file did not label the filing local and pending")
    if filed.get("aeat_accepted") is not False or filed.get("live_submission") is not False:
        raise IvaCliJourneyError("Modelo 303 file claimed AEAT acceptance or a live submission")
    if filed.get("external_evidence") is not None:
        raise IvaCliJourneyError("Modelo 303 local filing unexpectedly carries external AEAT evidence")
    return filing_record_id, filing_origin, filing_confirmation


def assert_fresh_process_filing_readback(
    *,
    work_listing: Mapping[str, object],
    filing_listing: Mapping[str, object],
    work_unit_id: str,
    calculation_revision_id: str,
    filing_record_id: str,
) -> None:
    """Check that a fresh process reads back the filed revision and local filing record."""
    work = unique_row(work_listing, "work_units", "work_unit_id", work_unit_id)
    if work.get("filed_calculation_revision_id") != calculation_revision_id:
        raise IvaCliJourneyError("fresh-process work list lost the filed calculation revision")
    if work.get("current_filing_record_id") != filing_record_id:
        raise IvaCliJourneyError("fresh-process work list lost the current local filing record")
    filing = unique_row(filing_listing, "records", "filing_record_id", filing_record_id)
    if filing.get("work_unit_id") != work_unit_id or filing.get("calculation_revision_id") != calculation_revision_id:
        raise IvaCliJourneyError("fresh-process filing-record list returned another work unit or revision")
    if filing.get("origin") != "local" or filing.get("confirmation") != "pendiente":
        raise IvaCliJourneyError("fresh-process filing-record list lost local pending state")
    if filing.get("aeat_accepted") is not False or filing.get("live_submission") is not False:
        raise IvaCliJourneyError("fresh-process filing-record list claimed AEAT acceptance or live submission")
    if filing.get("external_evidence") is not None:
        raise IvaCliJourneyError("fresh-process filing-record list unexpectedly carries external AEAT evidence")


def seed_first_period(
    *, cli: InstalledCli, receipts: list[SanitizedCommandReceipt], artifact: Path, journey_year: IvaJourneyYear
) -> None:
    """Seed the first period's IVA wallet carry through the CLI."""
    run(
        cli,
        receipts,
        artifact,
        (
            "app",
            "modelo",
            "iva-wallet",
            "seed",
            "--filing-year",
            str(journey_year.year),
            "--period",
            "1T",
            "--amount",
            "0.00",
            "--confirm",
        ),
        result_keys=(),
    )


@dataclass(frozen=True, slots=True)
class VerifiedQuarter:
    """One calculated quarter whose saved revision verified complete and is not yet filed."""

    period: str
    work_unit_id: str
    calculation_revision_id: str
    verification_report_id: str
    verification_status: str
    resultado: Decimal
    calculated: dict[str, object]
    """The public result of the calculation, with its casilla values."""


def calculate_and_verify_quarter(
    *,
    cli: InstalledCli,
    receipts: list[SanitizedCommandReceipt],
    artifact: Path,
    journey_year: IvaJourneyYear,
    period: str,
    expected: Decimal,
) -> VerifiedQuarter:
    """Create, calculate and verify one quarter through the CLI against its independent oracle."""
    created = result(
        run(
            cli,
            receipts,
            artifact,
            (
                "app",
                "modelo",
                "work",
                "create",
                "--modelo",
                "303",
                "--year",
                str(journey_year.year),
                "--period",
                period,
            ),
            result_keys=("work_unit_id",),
        )
    )
    work_id = required_id(created, "work_unit_id")
    evidence_args: tuple[str, ...] = ("--no-joint-return-elected",)
    if period == FINAL_QUARTER:
        attestation = result(
            run(
                cli,
                receipts,
                artifact,
                (
                    "app",
                    "modelo",
                    "work",
                    "attest-m303-exonerado-390",
                    "--year",
                    str(journey_year.year),
                    "--period",
                    period,
                    "--observed-at",
                    journey_year.noon_utc(12, 31),
                ),
                result_keys=("attachment_id", "sha256"),
            )
        )
        evidence_args = (
            *evidence_args,
            "--m303-exonerado-390-attachment-id",
            required_id(attestation, "attachment_id"),
            "--m303-exonerado-390-sha256",
            required_id(attestation, "sha256"),
        )
    calculated = result(
        run(
            cli,
            receipts,
            artifact,
            ("app", "modelo", "work", "calculate", work_id, *evidence_args),
            result_keys=("calculation_revision_id",),
        )
    )
    if calculated.get("saved") is not True:
        raise IvaCliJourneyError(f"Modelo 303 {period} calculate did not confirm a saved revision")
    revision_id = required_id(calculated, "calculation_revision_id")
    resultado = decimal_casilla(calculated, "iva.resultado")
    if resultado != expected:
        raise IvaCliJourneyError(f"independent Modelo 303 {period} oracle mismatch")
    verified = result(
        run(
            cli,
            receipts,
            artifact,
            ("app", "modelo", "work", "verify", revision_id),
            result_keys=("verification_report_id", "calculation_revision_id"),
        )
    )
    report_id, status = (
        required_id(verified, "verification_report_id"),
        required_text(verified, "completeness_status"),
    )
    if (
        verified.get("calculation_revision_id") != revision_id
        or verified.get("granted_verificado_completo") is not True
    ):
        raise IvaCliJourneyError(f"Modelo 303 {period} verify did not prove its saved revision complete")
    return VerifiedQuarter(period, work_id, revision_id, report_id, status, resultado, calculated)


def file_verified_quarter(
    *,
    cli: InstalledCli,
    receipts: list[SanitizedCommandReceipt],
    artifact: Path,
    quarter: VerifiedQuarter,
) -> IvaQuarterlyLocalFilingReceipt:
    """File one verified quarter locally through the CLI."""
    period, work_id, revision_id = quarter.period, quarter.work_unit_id, quarter.calculation_revision_id
    filed = result(
        run(
            cli,
            receipts,
            artifact,
            (
                "app",
                "modelo",
                "work",
                "file",
                revision_id,
                "--notes",
                f"Synthetic local pending annual Modelo 390 source filing {period}; not sent to AEAT",
            ),
            result_keys=("filing_record_id", "calculation_revision_id", "work_unit_id"),
        )
    )
    filing_id, origin, confirmation = _require_quarter_filing_identity(filed, work_id, revision_id, period)
    return IvaQuarterlyLocalFilingReceipt(
        period,
        work_id,
        revision_id,
        f"{quarter.resultado:.2f}",
        quarter.verification_report_id,
        quarter.verification_status,
        filing_id,
        origin,
        confirmation,
        False,
        False,
    )


def file_quarter(
    *,
    cli: InstalledCli,
    receipts: list[SanitizedCommandReceipt],
    artifact: Path,
    journey_year: IvaJourneyYear,
    period: str,
    expected: Decimal,
) -> IvaQuarterlyLocalFilingReceipt:
    """File one quarter locally through the CLI and return its receipt for the expected result."""
    quarter = calculate_and_verify_quarter(
        cli=cli, receipts=receipts, artifact=artifact, journey_year=journey_year, period=period, expected=expected
    )
    return file_verified_quarter(cli=cli, receipts=receipts, artifact=artifact, quarter=quarter)


def _require_local_work_chain(
    work: Mapping[str, object], filing: IvaQuarterlyLocalFilingReceipt, journey_year: IvaJourneyYear
) -> None:
    """Require the public work row to retain the quarter local filing chain."""
    if (
        work.get("modelo") != "303"
        or period_code(work.get("period"), filing_year=journey_year.year) != filing.period
        or work.get("filed_calculation_revision_id") != filing.calculation_revision_id
        or work.get("current_filing_record_id") != filing.filing_record_id
    ):
        raise IvaCliJourneyError(f"fresh-process work list lost the {filing.period} local filing chain")


def _require_local_record_chain(
    record: Mapping[str, object], filing: IvaQuarterlyLocalFilingReceipt, journey_year: IvaJourneyYear
) -> None:
    """Require the public record row to retain the quarter local filing chain."""
    if (
        record.get("work_unit_id") != filing.work_unit_id
        or record.get("calculation_revision_id") != filing.calculation_revision_id
        or record.get("origin") != "local"
        or record.get("confirmation") != "pendiente"
        or record.get("aeat_accepted") is not False
        or record.get("live_submission") is not False
        or record.get("external_evidence") is not None
    ):
        raise IvaCliJourneyError(f"fresh-process filing-record list lost local-only {filing.period} evidence")


def assert_local_quarter_chain(
    *,
    cli: InstalledCli,
    receipts: list[SanitizedCommandReceipt],
    artifact: Path,
    filings: tuple[IvaQuarterlyLocalFilingReceipt, ...],
    journey_year: IvaJourneyYear,
) -> None:
    """Check that the work units and filing records form the complete local quarter chain."""
    if tuple(item.period for item in filings) not in (("1T",), QUARTERS):
        raise IvaCliJourneyError("quarterly source chain is incomplete or out of order")
    work_listing = result(run(cli, receipts, artifact, ("app", "modelo", "work", "list"), result_keys=()))
    record_listing = result(
        run(cli, receipts, artifact, ("app", "modelo", "filing-record", "list", "--modelo", "303"), result_keys=())
    )
    for filing in filings:
        work = unique_row(work_listing, "work_units", "work_unit_id", filing.work_unit_id)
        record = unique_row(record_listing, "records", "filing_record_id", filing.filing_record_id)
        _require_local_work_chain(work, filing, journey_year)
        _require_local_record_chain(record, filing, journey_year)
