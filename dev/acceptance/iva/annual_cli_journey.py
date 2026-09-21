"""Installed-CLI IVA annual acceptance paths with local-only filing records."""

from __future__ import annotations

import secrets
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Final, cast

from dev.acceptance.income_tax.cli_journey import InstalledCli, JourneyError

from .cli_journey import (
    _AUTHORITY_GENERATION,
    IvaCliJourneyError,
    SanitizedCommandReceipt,
    _checkout_source_identity,
    _installed_package_identity,
    _invoice_add_args,
    _invoice_line,
    _required_id,
    _required_text,
    _result,
    _run,
    _sha256_path,
)
from .multirate_cli_journey import (
    _add_purchase_evidence,
    _add_purchase_invoice,
    _add_purchase_transaction,
    _add_transaction,
    _create_profile,
)

_FOUNDATION_ACCEPTANCE_ID: Final = "IVA-01-ANNUAL-FOUNDATION-2025-1T"
_YEAR: Final = 2025
_FOUNDATION_PERIOD: Final = "1T"
_FOUNDATION_SALE_IVA: Final = Decimal("21.00")
_FOUNDATION_PURCHASE_IVA: Final = Decimal("10.50")
_FOUNDATION_EXPECTED_RESULT: Final = _FOUNDATION_SALE_IVA - _FOUNDATION_PURCHASE_IVA
_QUARTERS: Final = ("1T", "2T", "3T", "4T")
_QUARTER_OBSERVED_AT: Final = {
    "1T": "2025-03-31T12:00:00+00:00",
    "2T": "2025-06-30T12:00:00+00:00",
    "3T": "2025-09-30T12:00:00+00:00",
    "4T": "2025-12-31T12:00:00+00:00",
}
_PRIVATE_ARTIFACT_PLACEHOLDER: Final = "<synthetic-purchase-artifact>"


@dataclass(frozen=True, slots=True)
class IvaAnnualFoundationCliJourneyReceipt:
    """Sanitized evidence for the preserved ordinary local 2025/1T path."""

    schema_version: str
    acceptance_ids: tuple[str, ...]
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
    """Sanitized evidence for four local 303 records and verified 2025 Modelo 390."""

    schema_version: str
    acceptance_ids: tuple[str, ...]
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


def run_iva_annual_foundation_cli_journey(
    *,
    executable: Path,
    authority_root: Path,
    storage_root: Path,
    artifact_root: Path,
) -> IvaAnnualFoundationCliJourneyReceipt:
    """File the preserved ordinary 2025/1T 303 through the installed public CLI."""
    cli, receipts, artifact = _start(executable, authority_root, storage_root, artifact_root)
    evidence_id = _add_purchase_evidence(cli=cli, receipts=receipts, artifact=artifact)
    sale_transaction_id = _add_transaction(
        cli=cli,
        receipts=receipts,
        artifact=artifact,
        amount="121.00",
        description="Synthetic annual-foundation IVA sale",
        taxable_base=Decimal("100.00"),
        iva_rate="0.21",
        iva_amount=_FOUNDATION_SALE_IVA,
        iva_category="domestic_general",
        idempotency_key="iva-01-annual-foundation-sale-2025-1t",
    )
    sale_invoice_id = _add_issued_invoice(cli=cli, receipts=receipts, artifact=artifact)
    _run(
        cli,
        receipts,
        artifact,
        ("app", "ledger", "link", sale_transaction_id, "--invoice-id", sale_invoice_id),
        result_keys=(),
    )
    purchase_transaction_id = _add_purchase_transaction(
        cli=cli, receipts=receipts, artifact=artifact, evidence_id=evidence_id
    )
    purchase_invoice_id = _add_purchase_invoice(cli=cli, receipts=receipts, artifact=artifact)
    _run(
        cli,
        receipts,
        artifact,
        ("app", "ledger", "link", purchase_transaction_id, "--invoice-id", purchase_invoice_id),
        result_keys=(),
    )

    work_cli = _reopen(cli, authority_root, storage_root)
    _run(
        work_cli,
        receipts,
        artifact,
        (
            "app",
            "modelo",
            "iva-wallet",
            "seed",
            "--filing-year",
            str(_YEAR),
            "--period",
            _FOUNDATION_PERIOD,
            "--amount",
            "0.00",
            "--confirm",
        ),
        result_keys=(),
    )
    attestation = _result(
        _run(
            work_cli,
            receipts,
            artifact,
            (
                "app",
                "modelo",
                "work",
                "attest-m303-exonerado-390",
                "--year",
                str(_YEAR),
                "--period",
                _FOUNDATION_PERIOD,
                "--observed-at",
                "2025-03-31T12:00:00+00:00",
            ),
            result_keys=("attachment_id", "sha256"),
        )
    )
    attachment_id = _required_id(attestation, "attachment_id")
    attachment_sha256 = _required_id(attestation, "sha256")
    created = _result(
        _run(
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
                str(_YEAR),
                "--period",
                _FOUNDATION_PERIOD,
            ),
            result_keys=("work_unit_id",),
        )
    )
    work_unit_id = _required_id(created, "work_unit_id")
    calculated = _result(
        _run(
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
                "--no-annual-volume-nonzero",
                "--m303-exonerado-390-attachment-id",
                attachment_id,
                "--m303-exonerado-390-sha256",
                attachment_sha256,
            ),
            result_keys=("calculation_revision_id",),
        )
    )
    if calculated.get("saved") is not True:
        raise IvaCliJourneyError("Modelo 303 calculate did not confirm a saved revision")
    calculation_revision_id = _required_id(calculated, "calculation_revision_id")
    iva_resultado = _decimal_casilla(calculated, "iva.resultado")
    if iva_resultado != _FOUNDATION_EXPECTED_RESULT:
        raise IvaCliJourneyError(
            f"independent IVA oracle mismatch: expected {_FOUNDATION_EXPECTED_RESULT:.2f}, got {iva_resultado:.2f}"
        )
    verification = _result(
        _run(
            work_cli,
            receipts,
            artifact,
            ("app", "modelo", "work", "verify", calculation_revision_id),
            result_keys=("verification_report_id", "calculation_revision_id"),
        )
    )
    verification_report_id = _required_id(verification, "verification_report_id")
    verification_status = _required_text(verification, "completeness_status")
    if verification.get("calculation_revision_id") != calculation_revision_id:
        raise IvaCliJourneyError("Modelo 303 verify returned a different calculation revision")
    if verification.get("granted_verificado_completo") is not True:
        raise IvaCliJourneyError("Modelo 303 verify did not grant complete verification")
    filed = _result(
        _run(
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
    filing_record_id = _required_id(filed, "filing_record_id")
    filing_origin = _required_text(filed, "origin")
    filing_confirmation = _required_text(filed, "confirmation")
    if filed.get("work_unit_id") != work_unit_id or filed.get("calculation_revision_id") != calculation_revision_id:
        raise IvaCliJourneyError("Modelo 303 file returned another work unit or calculation revision")
    if filing_origin != "local" or filing_confirmation != "pendiente":
        raise IvaCliJourneyError("Modelo 303 file did not label the filing local and pending")
    if filed.get("aeat_accepted") is not False or filed.get("live_submission") is not False:
        raise IvaCliJourneyError("Modelo 303 file claimed AEAT acceptance or a live submission")
    if filed.get("external_evidence") is not None:
        raise IvaCliJourneyError("Modelo 303 local filing unexpectedly carries external AEAT evidence")

    readback_cli = _reopen(cli, authority_root, storage_root)
    work_listing = _result(_run(readback_cli, receipts, artifact, ("app", "modelo", "work", "list"), result_keys=()))
    filing_listing = _result(
        _run(
            readback_cli,
            receipts,
            artifact,
            ("app", "modelo", "filing-record", "list", "--modelo", "303"),
            result_keys=(),
        )
    )
    _assert_fresh_process_filing_readback(
        work_listing=work_listing,
        filing_listing=filing_listing,
        work_unit_id=work_unit_id,
        calculation_revision_id=calculation_revision_id,
        filing_record_id=filing_record_id,
    )
    descriptor = authority_root.resolve(strict=True) / "authority.current.json"
    return IvaAnnualFoundationCliJourneyReceipt(
        schema_version="iva-01-annual-foundation-2025-1t-installed-cli-journey-v1",
        acceptance_ids=(_FOUNDATION_ACCEPTANCE_ID,),
        executable=str(cli.executable),
        executable_sha256=_sha256_path(cli.executable),
        source_identity=_checkout_source_identity(),
        package_identity=_installed_package_identity(),
        authority_generation=cast(str, _AUTHORITY_GENERATION(authority_root)),
        authority_descriptor_sha256=_sha256_path(descriptor),
        storage_root=str(storage_root.resolve()),
        purchase_artifact=_PRIVATE_ARTIFACT_PLACEHOLDER,
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


def _add_issued_invoice(*, cli: InstalledCli, receipts: list[SanitizedCommandReceipt], artifact: Path) -> str:
    invoice = _result(
        _run(
            cli,
            receipts,
            artifact,
            _invoice_add_args(
                kind="issued",
                counterparty_name="Synthetic annual-foundation client SL",
                counterparty_nif="A58818501",
                invoice_number="IVA-ISS-ANNUAL-FOUNDATION-2025-1T",
                iva_category="domestic_general",
                line=_invoice_line(
                    description="Synthetic annual-foundation sale",
                    subtotal="100.00",
                    iva_amount="21.00",
                ),
            ),
            result_keys=("invoice_id",),
        )
    )
    return _required_id(invoice, "invoice_id")


def _assert_fresh_process_filing_readback(
    *,
    work_listing: Mapping[str, object],
    filing_listing: Mapping[str, object],
    work_unit_id: str,
    calculation_revision_id: str,
    filing_record_id: str,
) -> None:
    work = _unique_row(work_listing, "work_units", "work_unit_id", work_unit_id)
    if work.get("filed_calculation_revision_id") != calculation_revision_id:
        raise IvaCliJourneyError("fresh-process work list lost the filed calculation revision")
    if work.get("current_filing_record_id") != filing_record_id:
        raise IvaCliJourneyError("fresh-process work list lost the current local filing record")
    filing = _unique_row(filing_listing, "records", "filing_record_id", filing_record_id)
    if filing.get("work_unit_id") != work_unit_id or filing.get("calculation_revision_id") != calculation_revision_id:
        raise IvaCliJourneyError("fresh-process filing-record list returned another work unit or revision")
    if filing.get("origin") != "local" or filing.get("confirmation") != "pendiente":
        raise IvaCliJourneyError("fresh-process filing-record list lost local pending state")
    if filing.get("aeat_accepted") is not False or filing.get("live_submission") is not False:
        raise IvaCliJourneyError("fresh-process filing-record list claimed AEAT acceptance or live submission")
    if filing.get("external_evidence") is not None:
        raise IvaCliJourneyError("fresh-process filing-record list unexpectedly carries external AEAT evidence")


def run_iva_annual_m390_cli_journey(
    *, executable: Path, authority_root: Path, storage_root: Path, artifact_root: Path
) -> IvaAnnualM390CliJourneyReceipt:
    """Use the documented four-quarter 2025 source facts to verify Modelo 390."""
    cli, receipts, artifact = _start(executable, authority_root, storage_root, artifact_root)
    evidence_id = _add_purchase_evidence(cli=cli, receipts=receipts, artifact=artifact)
    transaction_ids = _add_documented_ledger_facts(
        cli=cli, receipts=receipts, artifact=artifact, purchase_evidence_id=evidence_id
    )
    work_cli = _reopen(cli, authority_root, storage_root)
    _seed_first_period(cli=work_cli, receipts=receipts, artifact=artifact)
    expected = {"1T": Decimal("315.00"), "2T": Decimal("315.00"), "3T": Decimal("210.00"), "4T": Decimal("525.00")}
    filings = tuple(
        _file_quarter(
            cli=work_cli,
            receipts=receipts,
            artifact=artifact,
            period=period,
            expected=expected[period],
        )
        for period in _QUARTERS
    )
    annual_work_id, annual_revision_id, annual_report_id, annual_status, annual_values = _calculate_and_verify_m390(
        cli=work_cli, receipts=receipts, artifact=artifact
    )
    readback = _reopen(cli, authority_root, storage_root)
    _assert_local_quarter_chain(cli=readback, receipts=receipts, artifact=artifact, filings=filings)
    descriptor = authority_root.resolve(strict=True) / "authority.current.json"
    return IvaAnnualM390CliJourneyReceipt(
        schema_version="iva-01-annual-m390-2025-installed-cli-journey-v1",
        acceptance_ids=("IVA-01-ANNUAL-M390-2025-0A",),
        executable=str(cli.executable),
        executable_sha256=_sha256_path(cli.executable),
        source_identity=_checkout_source_identity(),
        package_identity=_installed_package_identity(),
        authority_generation=cast(str, _AUTHORITY_GENERATION(authority_root)),
        authority_descriptor_sha256=_sha256_path(descriptor),
        storage_root=str(storage_root.resolve()),
        purchase_artifact=_PRIVATE_ARTIFACT_PLACEHOLDER,
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


def _start(
    executable: Path, authority_root: Path, storage_root: Path, artifact_root: Path
) -> tuple[InstalledCli, list[SanitizedCommandReceipt], Path]:
    if storage_root.exists() and any(storage_root.iterdir()):
        raise IvaCliJourneyError(f"storage root must be fresh and empty: {storage_root}")
    storage_root.mkdir(parents=True, exist_ok=True)
    artifact_root.mkdir(parents=True, exist_ok=True)
    artifact = artifact_root / "synthetic-annual-foundation-purchase.pdf"
    artifact.write_bytes(b"%PDF-1.4\n% synthetic annual IVA purchase evidence\n")
    cli = InstalledCli(
        executable, storage_root=storage_root, authority_root=authority_root, passphrase=secrets.token_urlsafe(32)
    )
    receipts: list[SanitizedCommandReceipt] = []
    try:
        _create_profile(cli=cli, receipts=receipts, artifact=artifact)
    except JourneyError as exc:
        raise IvaCliJourneyError("config profile create refused") from exc
    return cli, receipts, artifact


def _reopen(cli: InstalledCli, authority_root: Path, storage_root: Path) -> InstalledCli:
    return InstalledCli(
        cli.executable, storage_root=storage_root, authority_root=authority_root, passphrase=cli.passphrase
    )


def _add_documented_ledger_facts(
    *, cli: InstalledCli, receipts: list[SanitizedCommandReceipt], artifact: Path, purchase_evidence_id: str
) -> tuple[str, ...]:
    sales = (
        ("1T", "2025-02-10", "2420.00", "2000.00", "420.00"),
        ("2T", "2025-05-12", "1815.00", "1500.00", "315.00"),
        ("3T", "2025-08-15", "1210.00", "1000.00", "210.00"),
        ("4T", "2025-11-20", "3025.00", "2500.00", "525.00"),
    )
    rows = tuple(
        _add_documented_transaction(
            cli=cli,
            receipts=receipts,
            artifact=artifact,
            date=date,
            amount=amount,
            direction="INCOMING",
            description=f"Synthetic documented annual IVA sale {period}",
            taxable_base=base,
            iva_amount=iva,
            idempotency_key=f"iva-01-annual-m390-sale-{_YEAR}-{period.lower()}",
        )
        for period, date, amount, base, iva in sales
    )
    purchase = _add_documented_transaction(
        cli=cli,
        receipts=receipts,
        artifact=artifact,
        date="2025-03-05",
        amount="605.00",
        direction="OUTGOING",
        description="Synthetic documented annual IVA purchase 1T",
        taxable_base="500.00",
        iva_amount="105.00",
        idempotency_key="iva-01-annual-m390-purchase-2025-1t",
        purchase_evidence_id=purchase_evidence_id,
    )
    _classify_purchase(cli=cli, receipts=receipts, artifact=artifact, transaction_id=purchase)
    return (*rows, purchase)


def _add_documented_transaction(
    *,
    cli: InstalledCli,
    receipts: list[SanitizedCommandReceipt],
    artifact: Path,
    date: str,
    amount: str,
    direction: str,
    description: str,
    taxable_base: str,
    iva_amount: str,
    idempotency_key: str,
    purchase_evidence_id: str | None = None,
) -> str:
    args = [
        "app",
        "ledger",
        "add",
        "--date",
        date,
        "--amount",
        amount,
        "--direction",
        direction,
        "--description",
        description,
        "--classification",
        "BUSINESS",
    ]
    if purchase_evidence_id is not None:
        args.extend(("--category-id", "material_oficina"))
    args.extend(
        (
            "--taxable-base",
            taxable_base,
            "--iva-rate",
            "0.21",
            "--iva-amount",
            iva_amount,
            "--iva-category",
            "domestic_general",
        )
    )
    if purchase_evidence_id is not None:
        args.extend(("--purchase-invoice-evidence-id", purchase_evidence_id))
    args.extend(("--source-jurisdiction", "ES", "--idempotency-key", idempotency_key))
    return _required_id(
        _result(_run(cli, receipts, artifact, tuple(args), result_keys=("transaction_id",))), "transaction_id"
    )


def _classify_purchase(
    *, cli: InstalledCli, receipts: list[SanitizedCommandReceipt], artifact: Path, transaction_id: str
) -> None:
    _run(
        cli,
        receipts,
        artifact,
        (
            "app",
            "ledger",
            "classify",
            transaction_id,
            "--classification",
            "BUSINESS",
            "--deduction-kind",
            "domestic_current",
            "--counterparty-country",
            "ES",
            "--reaffirm",
        ),
        result_keys=(),
    )


def _seed_first_period(*, cli: InstalledCli, receipts: list[SanitizedCommandReceipt], artifact: Path) -> None:
    _run(
        cli,
        receipts,
        artifact,
        (
            "app",
            "modelo",
            "iva-wallet",
            "seed",
            "--filing-year",
            str(_YEAR),
            "--period",
            "1T",
            "--amount",
            "0.00",
            "--confirm",
        ),
        result_keys=(),
    )


def _file_quarter(
    *,
    cli: InstalledCli,
    receipts: list[SanitizedCommandReceipt],
    artifact: Path,
    period: str,
    expected: Decimal,
) -> IvaQuarterlyLocalFilingReceipt:
    created = _result(
        _run(
            cli,
            receipts,
            artifact,
            ("app", "modelo", "work", "create", "--modelo", "303", "--year", str(_YEAR), "--period", period),
            result_keys=("work_unit_id",),
        )
    )
    work_id = _required_id(created, "work_unit_id")
    attestation = _result(
        _run(
            cli,
            receipts,
            artifact,
            (
                "app",
                "modelo",
                "work",
                "attest-m303-exonerado-390",
                "--year",
                str(_YEAR),
                "--period",
                period,
                "--observed-at",
                _QUARTER_OBSERVED_AT[period],
            ),
            result_keys=("attachment_id", "sha256"),
        )
    )
    attachment_id = _required_id(attestation, "attachment_id")
    attachment_sha256 = _required_id(attestation, "sha256")
    calculated = _result(
        _run(
            cli,
            receipts,
            artifact,
            (
                "app",
                "modelo",
                "work",
                "calculate",
                work_id,
                "--no-joint-return-elected",
                "--no-annual-volume-nonzero",
                "--m303-exonerado-390-attachment-id",
                attachment_id,
                "--m303-exonerado-390-sha256",
                attachment_sha256,
            ),
            result_keys=("calculation_revision_id",),
        )
    )
    if calculated.get("saved") is not True:
        raise IvaCliJourneyError(f"Modelo 303 {period} calculate did not confirm a saved revision")
    revision_id = _required_id(calculated, "calculation_revision_id")
    resultado = _decimal_casilla(calculated, "iva.resultado")
    if resultado != expected:
        raise IvaCliJourneyError(f"independent Modelo 303 {period} oracle mismatch")
    verified = _result(
        _run(
            cli,
            receipts,
            artifact,
            ("app", "modelo", "work", "verify", revision_id),
            result_keys=("verification_report_id", "calculation_revision_id"),
        )
    )
    report_id, status = (
        _required_id(verified, "verification_report_id"),
        _required_text(verified, "completeness_status"),
    )
    if (
        verified.get("calculation_revision_id") != revision_id
        or verified.get("granted_verificado_completo") is not True
    ):
        raise IvaCliJourneyError(f"Modelo 303 {period} verify did not prove its saved revision complete")
    filed = _result(
        _run(
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
    filing_id, origin, confirmation = (
        _required_id(filed, "filing_record_id"),
        _required_text(filed, "origin"),
        _required_text(filed, "confirmation"),
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
    return IvaQuarterlyLocalFilingReceipt(
        period,
        work_id,
        revision_id,
        f"{resultado:.2f}",
        report_id,
        status,
        filing_id,
        origin,
        confirmation,
        False,
        False,
    )


def _calculate_and_verify_m390(
    *, cli: InstalledCli, receipts: list[SanitizedCommandReceipt], artifact: Path
) -> tuple[str, str, str, str, dict[str, Decimal]]:
    created = _result(
        _run(
            cli,
            receipts,
            artifact,
            ("app", "modelo", "work", "create", "--modelo", "390", "--year", str(_YEAR), "--period", "0A"),
            result_keys=("work_unit_id",),
        )
    )
    work_id = _required_id(created, "work_unit_id")
    calculated = _result(
        _run(
            cli,
            receipts,
            artifact,
            ("app", "modelo", "work", "calculate", work_id),
            result_keys=("calculation_revision_id",),
        )
    )
    if calculated.get("saved") is not True:
        raise IvaCliJourneyError("Modelo 390 calculate did not confirm a saved revision")
    revision_id = _required_id(calculated, "calculation_revision_id")
    values = {
        "devengada": _decimal_casilla(calculated, "iva.anual.cuota-devengada-total"),
        "deducible": _decimal_casilla(calculated, "iva.anual.cuota-deducible-total"),
        "resultado": _decimal_casilla(calculated, "iva.anual.resultado-regimen-general"),
        "reconciled_devengada": _decimal_casilla(calculated, "iva.anual.reconciliacion.devengada-303"),
        "reconciled_deducible": _decimal_casilla(calculated, "iva.anual.reconciliacion.deducible-303"),
        "reconciled_resultado": _decimal_casilla(calculated, "iva.anual.reconciliacion.resultado-303"),
    }
    expected = {
        "devengada": Decimal("1470.00"),
        "deducible": Decimal("105.00"),
        "resultado": Decimal("1365.00"),
        "reconciled_devengada": Decimal("1470.00"),
        "reconciled_deducible": Decimal("105.00"),
        "reconciled_resultado": Decimal("1365.00"),
    }
    if values != expected:
        raise IvaCliJourneyError(f"independent Modelo 390 oracle mismatch: expected {expected}, got {values}")
    verified = _result(
        _run(
            cli,
            receipts,
            artifact,
            ("app", "modelo", "work", "verify", revision_id),
            result_keys=("verification_report_id", "calculation_revision_id"),
        )
    )
    report_id, status = (
        _required_id(verified, "verification_report_id"),
        _required_text(verified, "completeness_status"),
    )
    if (
        verified.get("calculation_revision_id") != revision_id
        or verified.get("granted_verificado_completo") is not True
    ):
        raise IvaCliJourneyError("Modelo 390 verify did not prove the annual reconciliation complete")
    return work_id, revision_id, report_id, status, values


def _assert_local_quarter_chain(
    *,
    cli: InstalledCli,
    receipts: list[SanitizedCommandReceipt],
    artifact: Path,
    filings: tuple[IvaQuarterlyLocalFilingReceipt, ...],
) -> None:
    if tuple(item.period for item in filings) not in (("1T",), _QUARTERS):
        raise IvaCliJourneyError("quarterly source chain is incomplete or out of order")
    work_listing = _result(_run(cli, receipts, artifact, ("app", "modelo", "work", "list"), result_keys=()))
    record_listing = _result(
        _run(cli, receipts, artifact, ("app", "modelo", "filing-record", "list", "--modelo", "303"), result_keys=())
    )
    for filing in filings:
        work = _unique_row(work_listing, "work_units", "work_unit_id", filing.work_unit_id)
        record = _unique_row(record_listing, "records", "filing_record_id", filing.filing_record_id)
        if (
            work.get("modelo") != "303"
            or _period_code(work.get("period")) != filing.period
            or work.get("filed_calculation_revision_id") != filing.calculation_revision_id
            or work.get("current_filing_record_id") != filing.filing_record_id
        ):
            raise IvaCliJourneyError(f"fresh-process work list lost the {filing.period} local filing chain")
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


def _decimal_casilla(payload: Mapping[str, object], casilla_id: str) -> Decimal:
    values = payload.get("casilla_values")
    if not isinstance(values, Mapping):
        raise IvaCliJourneyError("Modelo calculation returned no public casilla projection")
    try:
        return Decimal(str(values.get(casilla_id))).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise IvaCliJourneyError(f"Modelo calculation returned no decimal {casilla_id}") from exc


def _period_code(value: object) -> str | None:
    if not isinstance(value, Mapping) or value.get("filing_year") != _YEAR:
        return None
    code = value.get("code")
    return code if isinstance(code, str) else None


def _unique_row(
    payload: Mapping[str, object], collection_key: str, id_key: str, expected_id: str
) -> Mapping[str, object]:
    rows = payload.get(collection_key)
    if not isinstance(rows, list):
        raise IvaCliJourneyError("fresh-process public list returned no collection")
    matches = [row for row in rows if isinstance(row, Mapping) and row.get(id_key) == expected_id]
    if len(matches) != 1:
        raise IvaCliJourneyError("fresh-process public list did not return one expected identity")
    return cast(Mapping[str, object], matches[0])


__all__ = [
    "IvaAnnualFoundationCliJourneyReceipt",
    "IvaAnnualM390CliJourneyReceipt",
    "run_iva_annual_foundation_cli_journey",
    "run_iva_annual_m390_cli_journey",
]
