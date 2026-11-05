"""Installed IVA annual acceptance orchestration with local-only filing records."""

from __future__ import annotations

from contextlib import AbstractContextManager, ExitStack
from decimal import Decimal
from pathlib import Path

from cadrumo.domain.calculations.registry.authority_store import AUTHORITY_DESCRIPTOR_FILENAME
from dev.acceptance.installed_cli import InstalledCli, authority_generation

from .annual_capture import add_documented_ledger_facts, add_issued_invoice
from .annual_contracts import (
    ANNUAL_PERIOD,
    FOUNDATION_EXPECTED_RESULT,
    FOUNDATION_PERIOD,
    FOUNDATION_SALE_IVA,
    M390_COORDINATES,
    PRIVATE_ARTIFACT_PLACEHOLDER,
    QUARTERS,
    IvaAnnualFoundationCliJourneyReceipt,
    IvaAnnualM390CliJourneyReceipt,
)
from .annual_m390 import calculate_and_verify_m390
from .annual_projection import decimal_casilla
from .annual_quarter_work import (
    assert_fresh_process_filing_readback,
    assert_local_quarter_chain,
    file_quarter,
    require_foundation_filing_identity,
    seed_first_period,
)
from .annual_runtime import reopen, start
from .cli_journey import (
    IvaCliJourneyError,
    SanitizedCommandReceipt,
    checkout_source_identity,
    installed_package_identity,
    required_id,
    required_text,
    result,
    run,
    sha256_path,
)
from .filing_year import IvaJourneyYear, require_journey_year
from .multirate_cli_journey import (
    add_purchase_evidence,
    add_purchase_invoice,
    add_purchase_transaction,
    add_transaction,
)


def run_iva_annual_foundation_cli_journey(
    *,
    executable: Path,
    authority_root: Path,
    storage_root: Path,
    artifact_root: Path,
    year: int,
    runtime_scope: AbstractContextManager[object] | None = None,
) -> IvaAnnualFoundationCliJourneyReceipt:
    """File the preserved ordinary ``year``/1T 303 through the installed public CLI.

    Raises:
        IvaFilingYearUnsupportedError: Before any side effect, when the published
            authority has no Modelo 303 1T revision authored for ``year``.
    """
    journey_year = require_journey_year(
        authority_root=authority_root, year=year, coordinates=(("303", FOUNDATION_PERIOD),)
    )
    with ExitStack() as resources:
        cli, receipts, artifact = start(
            executable,
            authority_root,
            storage_root,
            artifact_root,
            journey_year,
            resources=resources,
            runtime_scope=runtime_scope,
        )
        evidence_id = add_purchase_evidence(cli=cli, receipts=receipts, artifact=artifact)
        sale_transaction_id = add_transaction(
            cli=cli,
            receipts=receipts,
            artifact=artifact,
            journey_year=journey_year,
            amount="121.00",
            description="Synthetic annual-foundation IVA sale",
            taxable_base=Decimal("100.00"),
            iva_rate="0.21",
            iva_amount=FOUNDATION_SALE_IVA,
            iva_category="domestic_general",
            idempotency_key=f"iva-01-annual-foundation-sale-{year}-1t",
        )
        sale_invoice_id = add_issued_invoice(cli=cli, receipts=receipts, artifact=artifact, journey_year=journey_year)
        run(
            cli,
            receipts,
            artifact,
            ("app", "ledger", "link", sale_transaction_id, "--invoice-id", sale_invoice_id),
            result_keys=(),
        )
        purchase_transaction_id = add_purchase_transaction(
            cli=cli, receipts=receipts, artifact=artifact, evidence_id=evidence_id, journey_year=journey_year
        )
        purchase_invoice_id = add_purchase_invoice(
            cli=cli, receipts=receipts, artifact=artifact, journey_year=journey_year
        )
        run(
            cli,
            receipts,
            artifact,
            ("app", "ledger", "link", purchase_transaction_id, "--invoice-id", purchase_invoice_id),
            result_keys=(),
        )

        work_cli = reopen(cli, authority_root, storage_root)
        work_unit_id, calculation_revision_id, iva_resultado = _calculate_foundation_quarter(
            work_cli, receipts, artifact, journey_year, year
        )

        verification_report_id, verification_status = _verify_foundation_quarter(
            work_cli, receipts, artifact, calculation_revision_id
        )
        filed = result(
            run(
                work_cli,
                receipts,
                artifact,
                (
                    "app",
                    "modelo",
                    "work",
                    "file",
                    calculation_revision_id,
                    "--notes",
                    "Synthetic local pending annual-foundation filing; not sent to AEAT",
                ),
                result_keys=("filing_record_id", "calculation_revision_id", "work_unit_id"),
            )
        )
        filing_record_id, filing_origin, filing_confirmation = require_foundation_filing_identity(
            filed, work_unit_id, calculation_revision_id
        )

        readback_cli = reopen(cli, authority_root, storage_root)
        work_listing = result(run(readback_cli, receipts, artifact, ("app", "modelo", "work", "list"), result_keys=()))
        filing_listing = result(
            run(
                readback_cli,
                receipts,
                artifact,
                ("app", "modelo", "filing-record", "list", "--modelo", "303"),
                result_keys=(),
            )
        )
        assert_fresh_process_filing_readback(
            work_listing=work_listing,
            filing_listing=filing_listing,
            work_unit_id=work_unit_id,
            calculation_revision_id=calculation_revision_id,
            filing_record_id=filing_record_id,
        )
        descriptor = authority_root.resolve(strict=True) / AUTHORITY_DESCRIPTOR_FILENAME
        return IvaAnnualFoundationCliJourneyReceipt(
            schema_version="iva-01-annual-foundation-1t-installed-cli-journey-v2",
            acceptance_ids=(f"IVA-01-ANNUAL-FOUNDATION-{year}-1T",),
            filing_year=year,
            executable=str(cli.executable),
            executable_sha256=sha256_path(cli.executable),
            source_identity=checkout_source_identity(),
            package_identity=installed_package_identity(),
            authority_generation=authority_generation(authority_root),
            authority_descriptor_sha256=sha256_path(descriptor),
            storage_root=str(storage_root.resolve()),
            purchase_artifact=PRIVATE_ARTIFACT_PLACEHOLDER,
            transaction_ids=(sale_transaction_id, purchase_transaction_id),
            invoice_ids=(sale_invoice_id, purchase_invoice_id),
            evidence_id=evidence_id,
            work_unit_id=work_unit_id,
            calculation_revision_id=calculation_revision_id,
            iva_resultado=f"{iva_resultado:.2f}",
            verification_report_id=verification_report_id,
            verification_status=verification_status,
            filing_record_id=filing_record_id,
            filing_origin=filing_origin,
            filing_confirmation=filing_confirmation,
            filing_aeat_accepted=False,
            filing_live_submission=False,
            commands=tuple(receipts),
        )


def _verify_foundation_quarter(
    work_cli: InstalledCli,
    receipts: list[SanitizedCommandReceipt],
    artifact: Path,
    calculation_revision_id: str,
) -> tuple[str, str]:
    """Require complete verification of the same saved foundation revision."""
    verification = result(
        run(
            work_cli,
            receipts,
            artifact,
            ("app", "modelo", "work", "verify", calculation_revision_id),
            result_keys=("verification_report_id", "calculation_revision_id"),
        )
    )
    verification_report_id = required_id(verification, "verification_report_id")
    verification_status = required_text(verification, "completeness_status")
    if verification.get("calculation_revision_id") != calculation_revision_id:
        raise IvaCliJourneyError("Modelo 303 verify returned a different calculation revision")
    if verification.get("granted_verificado_completo") is not True:
        raise IvaCliJourneyError("Modelo 303 verify did not grant complete verification")
    return verification_report_id, verification_status


def _calculate_foundation_quarter(
    work_cli: InstalledCli,
    receipts: list[SanitizedCommandReceipt],
    artifact: Path,
    journey_year: IvaJourneyYear,
    year: int,
) -> tuple[str, str, Decimal]:
    """Execute this acceptance phase in order through its existing command boundary."""
    run(
        work_cli,
        receipts,
        artifact,
        (
            "app",
            "modelo",
            "iva-wallet",
            "seed",
            "--filing-year",
            str(year),
            "--period",
            FOUNDATION_PERIOD,
            "--amount",
            "0.00",
            "--confirm",
        ),
        result_keys=(),
    )
    created = result(
        run(
            work_cli,
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
                str(year),
                "--period",
                FOUNDATION_PERIOD,
            ),
            result_keys=("work_unit_id",),
        )
    )
    work_unit_id = required_id(created, "work_unit_id")
    calculated = result(
        run(
            work_cli,
            receipts,
            artifact,
            (
                "app",
                "modelo",
                "work",
                "calculate",
                work_unit_id,
                "--no-joint-return-elected",
            ),
            result_keys=("calculation_revision_id",),
        )
    )
    if calculated.get("saved") is not True:
        raise IvaCliJourneyError("Modelo 303 calculate did not confirm a saved revision")
    calculation_revision_id = required_id(calculated, "calculation_revision_id")
    iva_resultado = decimal_casilla(calculated, "iva.resultado")
    if iva_resultado != FOUNDATION_EXPECTED_RESULT:
        raise IvaCliJourneyError(
            f"independent IVA oracle mismatch: expected {FOUNDATION_EXPECTED_RESULT:.2f}, got {iva_resultado:.2f}"
        )
    return work_unit_id, calculation_revision_id, iva_resultado


def run_iva_annual_m390_cli_journey(
    *,
    executable: Path,
    authority_root: Path,
    storage_root: Path,
    artifact_root: Path,
    year: int,
    runtime_scope: AbstractContextManager[object] | None = None,
) -> IvaAnnualM390CliJourneyReceipt:
    """Use the documented four-quarter source facts of ``year`` to verify its annual Modelo 390.

    Raises:
        IvaFilingYearUnsupportedError: Before any side effect, when the published
            authority lacks a revision authored for ``year`` for any Modelo 303
            quarter or for the Modelo 390 annual period.
    """
    journey_year = require_journey_year(authority_root=authority_root, year=year, coordinates=M390_COORDINATES)
    with ExitStack() as resources:
        cli, receipts, artifact = start(
            executable,
            authority_root,
            storage_root,
            artifact_root,
            journey_year,
            resources=resources,
            runtime_scope=runtime_scope,
        )
        evidence_id = add_purchase_evidence(cli=cli, receipts=receipts, artifact=artifact)
        transaction_ids = add_documented_ledger_facts(
            cli=cli, receipts=receipts, artifact=artifact, purchase_evidence_id=evidence_id, journey_year=journey_year
        )
        work_cli = reopen(cli, authority_root, storage_root)
        seed_first_period(cli=work_cli, receipts=receipts, artifact=artifact, journey_year=journey_year)
        expected = {"1T": Decimal("315.00"), "2T": Decimal("315.00"), "3T": Decimal("210.00"), "4T": Decimal("525.00")}
        filings = tuple(
            file_quarter(
                cli=work_cli,
                receipts=receipts,
                artifact=artifact,
                journey_year=journey_year,
                period=period,
                expected=expected[period],
            )
            for period in QUARTERS
        )
        annual_work_id, annual_revision_id, annual_report_id, annual_status, annual_values = calculate_and_verify_m390(
            cli=work_cli, receipts=receipts, artifact=artifact, journey_year=journey_year
        )
        readback = reopen(cli, authority_root, storage_root)
        assert_local_quarter_chain(
            cli=readback, receipts=receipts, artifact=artifact, filings=filings, journey_year=journey_year
        )
        descriptor = authority_root.resolve(strict=True) / AUTHORITY_DESCRIPTOR_FILENAME
        return IvaAnnualM390CliJourneyReceipt(
            schema_version="iva-01-annual-m390-installed-cli-journey-v2",
            acceptance_ids=(f"IVA-01-ANNUAL-M390-{year}-{ANNUAL_PERIOD}",),
            filing_year=year,
            executable=str(cli.executable),
            executable_sha256=sha256_path(cli.executable),
            source_identity=checkout_source_identity(),
            package_identity=installed_package_identity(),
            authority_generation=authority_generation(authority_root),
            authority_descriptor_sha256=sha256_path(descriptor),
            storage_root=str(storage_root.resolve()),
            purchase_artifact=PRIVATE_ARTIFACT_PLACEHOLDER,
            transaction_ids=transaction_ids,
            evidence_id=evidence_id,
            quarterly_filings=filings,
            annual_work_unit_id=annual_work_id,
            annual_calculation_revision_id=annual_revision_id,
            annual_verification_report_id=annual_report_id,
            annual_verification_status=annual_status,
            annual_devengada=f"{annual_values['devengada']:.2f}",
            annual_deducible=f"{annual_values['deducible']:.2f}",
            annual_resultado=f"{annual_values['resultado']:.2f}",
            commands=tuple(receipts),
        )
