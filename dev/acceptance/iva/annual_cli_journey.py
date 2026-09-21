"""Installed-CLI foundation for annual IVA continuity from one filed 2025/1T.

The slice deliberately stops after the first ordinary Modelo 303 is calculated,
verified, locally filed, and reopened through public read surfaces.  It does not
assert a Modelo 390 outcome, produce an export, or contact AEAT.
"""

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

_ACCEPTANCE_ID: Final = "IVA-01-ANNUAL-FOUNDATION-2025-1T"
_YEAR: Final = 2025
_PERIOD: Final = "1T"
_SALE_IVA: Final = Decimal("21.00")
_PURCHASE_IVA: Final = Decimal("10.50")
_EXPECTED_RESULT: Final = _SALE_IVA - _PURCHASE_IVA
_PRIVATE_ARTIFACT_PLACEHOLDER: Final = "<synthetic-purchase-artifact>"


@dataclass(frozen=True, slots=True)
class IvaAnnualFoundationCliJourneyReceipt:
    """Sanitized proof of one locally filed 303 ready for later annual work."""

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


def run_iva_annual_foundation_cli_journey(
    *,
    executable: Path,
    authority_root: Path,
    storage_root: Path,
    artifact_root: Path,
) -> IvaAnnualFoundationCliJourneyReceipt:
    """File the first ordinary 2025/1T 303 through the installed public CLI."""
    if storage_root.exists() and any(storage_root.iterdir()):
        raise IvaCliJourneyError(f"storage root must be fresh and empty: {storage_root}")
    storage_root.mkdir(parents=True, exist_ok=True)
    artifact_root.mkdir(parents=True, exist_ok=True)
    artifact = artifact_root / "synthetic-annual-foundation-purchase.pdf"
    artifact.write_bytes(b"%PDF-1.4\n% synthetic annual-foundation purchase evidence\n")

    cli = InstalledCli(
        executable,
        storage_root=storage_root,
        authority_root=authority_root,
        passphrase=secrets.token_urlsafe(32),
    )
    receipts: list[SanitizedCommandReceipt] = []
    try:
        _create_profile(cli=cli, receipts=receipts, artifact=artifact)
    except JourneyError as exc:
        raise IvaCliJourneyError("config profile create refused") from exc

    evidence_id = _add_purchase_evidence(cli=cli, receipts=receipts, artifact=artifact)
    sale_transaction_id = _add_transaction(
        cli=cli,
        receipts=receipts,
        artifact=artifact,
        amount="121.00",
        description="Synthetic annual-foundation IVA sale",
        taxable_base=Decimal("100.00"),
        iva_rate="0.21",
        iva_amount=_SALE_IVA,
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

    work_cli = InstalledCli(
        cli.executable,
        storage_root=storage_root,
        authority_root=authority_root,
        passphrase=cli.passphrase,
    )
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
            _PERIOD,
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
                _PERIOD,
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
            ("app", "modelo", "work", "create", "--modelo", "303", "--year", str(_YEAR), "--period", _PERIOD),
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
    if iva_resultado != _EXPECTED_RESULT:
        raise IvaCliJourneyError(
            f"independent IVA oracle mismatch: expected {_EXPECTED_RESULT:.2f}, got {iva_resultado:.2f}"
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

    readback_cli = InstalledCli(
        cli.executable,
        storage_root=storage_root,
        authority_root=authority_root,
        passphrase=cli.passphrase,
    )
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
        acceptance_ids=(_ACCEPTANCE_ID,),
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
                    description="Synthetic annual-foundation sale", subtotal="100.00", iva_amount="21.00"
                ),
            ),
            result_keys=("invoice_id",),
        )
    )
    return _required_id(invoice, "invoice_id")


def _decimal_casilla(calculated: Mapping[str, object], casilla_id: str) -> Decimal:
    casillas = calculated.get("casilla_values")
    if not isinstance(casillas, Mapping):
        raise IvaCliJourneyError("Modelo 303 calculate returned no public casilla projection")
    try:
        return Decimal(str(casillas.get(casilla_id))).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise IvaCliJourneyError(f"Modelo 303 calculate returned no decimal {casilla_id}") from exc


def _assert_fresh_process_filing_readback(
    *,
    work_listing: Mapping[str, object],
    filing_listing: Mapping[str, object],
    work_unit_id: str,
    calculation_revision_id: str,
    filing_record_id: str,
) -> None:
    work = _unique_row(work_listing, "work_units", "work_unit_id", work_unit_id, label="work")
    if work.get("filed_calculation_revision_id") != calculation_revision_id:
        raise IvaCliJourneyError("fresh-process work list lost the filed calculation revision")
    if work.get("current_filing_record_id") != filing_record_id:
        raise IvaCliJourneyError("fresh-process work list lost the current local filing record")

    filing = _unique_row(filing_listing, "records", "filing_record_id", filing_record_id, label="filing record")
    if filing.get("work_unit_id") != work_unit_id or filing.get("calculation_revision_id") != calculation_revision_id:
        raise IvaCliJourneyError("fresh-process filing-record list returned another work unit or revision")
    if filing.get("origin") != "local" or filing.get("confirmation") != "pendiente":
        raise IvaCliJourneyError("fresh-process filing-record list lost local pending state")
    if filing.get("aeat_accepted") is not False or filing.get("live_submission") is not False:
        raise IvaCliJourneyError("fresh-process filing-record list claimed AEAT acceptance or live submission")
    if filing.get("external_evidence") is not None:
        raise IvaCliJourneyError("fresh-process filing-record list unexpectedly carries external AEAT evidence")


def _unique_row(
    payload: Mapping[str, object], collection_key: str, id_key: str, expected_id: str, *, label: str
) -> Mapping[str, object]:
    rows = payload.get(collection_key)
    if not isinstance(rows, list):
        raise IvaCliJourneyError(f"fresh-process {label} list returned no public collection")
    matches = [row for row in rows if isinstance(row, Mapping) and row.get(id_key) == expected_id]
    if len(matches) != 1:
        raise IvaCliJourneyError(f"fresh-process {label} list did not return one expected identity")
    return cast(Mapping[str, object], matches[0])


__all__ = ["IvaAnnualFoundationCliJourneyReceipt", "run_iva_annual_foundation_cli_journey"]
