"""Installed CLI acceptance for one canonical two-rate issued IVA invoice."""

from __future__ import annotations

import json
import secrets
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Final, cast

from dev.acceptance.income_tax.cli_journey import InstalledCli, JourneyError

from .cli_journey import (
    _AUTHORITY_GENERATION,
    _PROFILE_CREATE_ARGS,
    IvaCliJourneyError,
    SanitizedCommandReceipt,
    _checkout_source_identity,
    _command_receipt,
    _installed_package_identity,
    _required_id,
    _required_text,
    _result,
    _row_ids,
    _run,
    _sha256_path,
)

_YEAR: Final = 2025
_PERIOD: Final = "1T"
_GENERAL_BASE: Final = Decimal("100.00")
_GENERAL_IVA: Final = Decimal("21.00")
_REDUCED_BASE: Final = Decimal("50.00")
_REDUCED_IVA: Final = Decimal("5.00")
_PURCHASE_IVA: Final = Decimal("10.50")
_EXPECTED_RESULT: Final = _GENERAL_IVA + _REDUCED_IVA - _PURCHASE_IVA
_PRIVATE_ARTIFACT_PLACEHOLDER: Final = "<synthetic-purchase-artifact>"
_RATE_OBSERVATIONS: Final = (
    ("iva.repercutido.general", _GENERAL_IVA),
    ("iva.repercutido.reducido", _REDUCED_IVA),
    ("iva.soportado.interiores", _PURCHASE_IVA),
)


@dataclass(frozen=True, slots=True)
class RateObservation:
    """One public Modelo 303 casilla observation tied to its IVA-rate input."""

    casilla_id: str
    value: str
    legal_ref_count: int
    source_ref_count: int


@dataclass(frozen=True, slots=True)
class IvaMultirateCliJourneyReceipt:
    """Sanitized evidence for the persisted, calculated two-rate IVA case."""

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
    transaction_ids: tuple[str, str, str]
    issued_invoice_id: str
    purchase_invoice_id: str
    issued_invoice_line_rates: tuple[str, str]
    issued_invoice_linked_transaction_ids: tuple[str, str]
    evidence_id: str
    work_unit_id: str
    calculation_revision_id: str
    iva_resultado: str
    rate_observations: tuple[RateObservation, RateObservation, RateObservation]
    verification_report_id: str
    verification_status: str
    verification_granted: bool
    export_status: str
    commands: tuple[SanitizedCommandReceipt, ...]

    def to_dict(self) -> dict[str, object]:
        """Return identity and public-command evidence without private bytes."""
        return cast(dict[str, object], asdict(self))


def run_iva_multirate_cli_journey(
    *,
    executable: Path,
    authority_root: Path,
    storage_root: Path,
    artifact_root: Path,
) -> IvaMultirateCliJourneyReceipt:
    """Run a fresh 2025/1T M303 case with 21% and 10% issued lines."""
    if storage_root.exists() and any(storage_root.iterdir()):
        raise IvaCliJourneyError(f"storage root must be fresh and empty: {storage_root}")
    storage_root.mkdir(parents=True, exist_ok=True)
    artifact_root.mkdir(parents=True, exist_ok=True)
    artifact = artifact_root / "synthetic-multirate-purchase.pdf"
    artifact.write_bytes(b"%PDF-1.4\n% synthetic acceptance purchase evidence\n")

    cli = InstalledCli(
        executable,
        storage_root=storage_root,
        authority_root=authority_root,
        passphrase=secrets.token_urlsafe(32),
    )
    receipts: list[SanitizedCommandReceipt] = []
    _create_profile(cli=cli, receipts=receipts, artifact=artifact)

    evidence_id = _add_purchase_evidence(cli=cli, receipts=receipts, artifact=artifact)
    general_transaction_id = _add_transaction(
        cli=cli,
        receipts=receipts,
        artifact=artifact,
        amount="121.00",
        description="Synthetic multirate IVA sale at 21 percent",
        taxable_base=_GENERAL_BASE,
        iva_rate="0.21",
        iva_amount=_GENERAL_IVA,
        iva_category="domestic_general",
        idempotency_key="iva-acceptance-multirate-general-2025-1t",
    )
    reduced_transaction_id = _add_transaction(
        cli=cli,
        receipts=receipts,
        artifact=artifact,
        amount="55.00",
        description="Synthetic multirate IVA sale at 10 percent",
        taxable_base=_REDUCED_BASE,
        iva_rate="0.10",
        iva_amount=_REDUCED_IVA,
        iva_category="domestic_reduced",
        idempotency_key="iva-acceptance-multirate-reduced-2025-1t",
    )
    issued_invoice_id = _add_issued_invoice(
        cli=cli,
        receipts=receipts,
        artifact=artifact,
    )
    for transaction_id in (general_transaction_id, reduced_transaction_id):
        _run(
            cli,
            receipts,
            artifact,
            ("app", "ledger", "link", transaction_id, "--invoice-id", issued_invoice_id),
            result_keys=(),
        )

    purchase_transaction_id = _add_purchase_transaction(
        cli=cli,
        receipts=receipts,
        artifact=artifact,
        evidence_id=evidence_id,
    )
    purchase_invoice_id = _add_purchase_invoice(cli=cli, receipts=receipts, artifact=artifact)
    _run(
        cli,
        receipts,
        artifact,
        ("app", "ledger", "link", purchase_transaction_id, "--invoice-id", purchase_invoice_id),
        result_keys=(),
    )

    transaction_ids = (general_transaction_id, reduced_transaction_id, purchase_transaction_id)
    reopened = InstalledCli(
        cli.executable,
        storage_root=storage_root,
        authority_root=authority_root,
        passphrase=cli.passphrase,
    )
    issued_invoice_lines, issued_links = _assert_reopened_persistence(
        cli=reopened,
        receipts=receipts,
        artifact=artifact,
        transaction_ids=transaction_ids,
        invoice_ids=(issued_invoice_id, purchase_invoice_id),
        issued_invoice_id=issued_invoice_id,
        issued_transaction_ids=(general_transaction_id, reduced_transaction_id),
        evidence_id=evidence_id,
    )

    _run(
        reopened,
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
            reopened,
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
    attestation_sha256 = _required_id(attestation, "sha256")

    created = _result(
        _run(
            reopened,
            receipts,
            artifact,
            ("app", "modelo", "work", "create", "--modelo", "303", "--year", str(_YEAR), "--period", _PERIOD),
            result_keys=("work_unit_id",),
        )
    )
    work_unit_id = _required_id(created, "work_unit_id")
    calculated = _result(
        _run(
            reopened,
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
                attestation_sha256,
            ),
            result_keys=("calculation_revision_id",),
        )
    )
    if calculated.get("saved") is not True:
        raise IvaCliJourneyError("Modelo 303 calculate did not confirm a saved revision")
    calculation_revision_id = _required_id(calculated, "calculation_revision_id")
    iva_resultado = _decimal_field(calculated, "iva.resultado")
    if iva_resultado != _EXPECTED_RESULT:
        raise IvaCliJourneyError(
            f"independent multi-rate IVA oracle mismatch: expected {_EXPECTED_RESULT:.2f}, got {iva_resultado:.2f}"
        )
    rate_observations = _rate_observations(calculated=calculated)

    verification_cli = InstalledCli(
        cli.executable,
        storage_root=storage_root,
        authority_root=authority_root,
        passphrase=cli.passphrase,
    )
    verification = _result(
        _run(
            verification_cli,
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
        raise IvaCliJourneyError(
            "Modelo 303 verify did not grant complete verification: "
            f"status={verification_status}; findings={verification.get('finding_count')}"
        )

    descriptor = authority_root.resolve(strict=True) / "authority.current.json"
    return IvaMultirateCliJourneyReceipt(
        schema_version="iva-01-installed-cli-multirate-journey-v1",
        acceptance_ids=("IVA-CLI-MULTIRATE-2025-1T",),
        executable=str(cli.executable),
        executable_sha256=_sha256_path(cli.executable),
        source_identity=_checkout_source_identity(),
        package_identity=_installed_package_identity(),
        authority_generation=cast(str, _AUTHORITY_GENERATION(authority_root)),
        authority_descriptor_sha256=_sha256_path(descriptor),
        storage_root=str(storage_root.resolve()),
        purchase_artifact=_PRIVATE_ARTIFACT_PLACEHOLDER,
        transaction_ids=transaction_ids,
        issued_invoice_id=issued_invoice_id,
        purchase_invoice_id=purchase_invoice_id,
        issued_invoice_line_rates=issued_invoice_lines,
        issued_invoice_linked_transaction_ids=issued_links,
        evidence_id=evidence_id,
        work_unit_id=work_unit_id,
        calculation_revision_id=calculation_revision_id,
        iva_resultado=f"{iva_resultado:.2f}",
        rate_observations=rate_observations,
        verification_report_id=verification_report_id,
        verification_status=verification_status,
        verification_granted=True,
        export_status="not_attempted_product_software_identity_pending",
        commands=tuple(receipts),
    )


def _create_profile(*, cli: InstalledCli, receipts: list[SanitizedCommandReceipt], artifact: Path) -> None:
    profile_start = len(cli.commands)
    try:
        cli.create_profile(year=_YEAR)
    except JourneyError as exc:
        raise IvaCliJourneyError("config profile create refused") from exc
    commands = cli.commands[profile_start:]
    if len(commands) != 2:
        raise IvaCliJourneyError("profile setup did not produce its two public command receipts")
    receipts.extend(
        (
            _command_receipt(args=_PROFILE_CREATE_ARGS(_YEAR), evidence=commands[0], artifact=artifact, result_ids=()),
            _command_receipt(
                args=("config", "profile", "complete-setup"), evidence=commands[1], artifact=artifact, result_ids=()
            ),
        )
    )


def _add_purchase_evidence(*, cli: InstalledCli, receipts: list[SanitizedCommandReceipt], artifact: Path) -> str:
    evidence = _result(
        _run(
            cli,
            receipts,
            artifact,
            ("app", "ledger", "evidence", "add", str(artifact), "--supplier", "Synthetic supplier SL"),
            result_keys=("evidence_id",),
        )
    )
    return _required_id(evidence, "evidence_id")


def _add_transaction(
    *,
    cli: InstalledCli,
    receipts: list[SanitizedCommandReceipt],
    artifact: Path,
    amount: str,
    description: str,
    taxable_base: Decimal,
    iva_rate: str,
    iva_amount: Decimal,
    iva_category: str,
    idempotency_key: str,
) -> str:
    transaction = _result(
        _run(
            cli,
            receipts,
            artifact,
            (
                "app",
                "ledger",
                "add",
                "--date",
                "2025-02-15",
                "--amount",
                amount,
                "--direction",
                "INCOMING",
                "--description",
                description,
                "--classification",
                "BUSINESS",
                "--taxable-base",
                f"{taxable_base:.2f}",
                "--iva-rate",
                iva_rate,
                "--iva-amount",
                f"{iva_amount:.2f}",
                "--iva-category",
                iva_category,
                "--source-jurisdiction",
                "ES",
                "--idempotency-key",
                idempotency_key,
            ),
            result_keys=("transaction_id",),
        )
    )
    return _required_id(transaction, "transaction_id")


def _add_issued_invoice(*, cli: InstalledCli, receipts: list[SanitizedCommandReceipt], artifact: Path) -> str:
    first_line = _invoice_line(
        description="Synthetic issued service at 21 percent",
        subtotal=_GENERAL_BASE,
        iva_rate="RATE_21",
        iva_amount=_GENERAL_IVA,
    )
    second_line = _invoice_line(
        description="Synthetic issued service at 10 percent",
        subtotal=_REDUCED_BASE,
        iva_rate="RATE_10",
        iva_amount=_REDUCED_IVA,
    )
    invoice = _result(
        _run(
            cli,
            receipts,
            artifact,
            (
                "app",
                "ledger",
                "invoice",
                "add",
                "--kind",
                "issued",
                "--counterparty-name",
                "Synthetic multirate client SL",
                "--counterparty-nif",
                "A58818501",
                "--invoice-number",
                "IVA-ISS-MULTIRATE-2025-1T",
                "--invoice-date",
                "2025-02-15",
                "--country-code",
                "ES",
                "--iva-category",
                "domestic_general",
                "--line",
                first_line,
                "--line",
                second_line,
            ),
            result_keys=("invoice_id",),
        )
    )
    return _required_id(invoice, "invoice_id")


def _add_purchase_transaction(
    *, cli: InstalledCli, receipts: list[SanitizedCommandReceipt], artifact: Path, evidence_id: str
) -> str:
    transaction = _result(
        _run(
            cli,
            receipts,
            artifact,
            (
                "app",
                "ledger",
                "add",
                "--date",
                "2025-02-18",
                "--amount",
                "60.50",
                "--direction",
                "OUTGOING",
                "--description",
                "Synthetic ordinary IVA purchase",
                "--classification",
                "BUSINESS",
                "--category-id",
                "material_oficina",
                "--taxable-base",
                "50.00",
                "--iva-rate",
                "0.21",
                "--iva-amount",
                "10.50",
                "--iva-category",
                "domestic_general",
                "--purchase-invoice-evidence-id",
                evidence_id,
                "--source-jurisdiction",
                "ES",
                "--idempotency-key",
                "iva-acceptance-multirate-purchase-2025-1t",
            ),
            result_keys=("transaction_id",),
        )
    )
    transaction_id = _required_id(transaction, "transaction_id")
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
    return transaction_id


def _add_purchase_invoice(*, cli: InstalledCli, receipts: list[SanitizedCommandReceipt], artifact: Path) -> str:
    invoice = _result(
        _run(
            cli,
            receipts,
            artifact,
            (
                "app",
                "ledger",
                "invoice",
                "add",
                "--kind",
                "received",
                "--counterparty-name",
                "Synthetic supplier SL",
                "--counterparty-nif",
                "A58818501",
                "--invoice-number",
                "IVA-REC-MULTIRATE-2025-1T",
                "--invoice-date",
                "2025-02-18",
                "--country-code",
                "ES",
                "--iva-category",
                "domestic_general",
                "--line",
                _invoice_line(
                    description="Synthetic purchase",
                    subtotal=Decimal("50.00"),
                    iva_rate="RATE_21",
                    iva_amount=_PURCHASE_IVA,
                ),
            ),
            result_keys=("invoice_id",),
        )
    )
    return _required_id(invoice, "invoice_id")


def _invoice_line(*, description: str, subtotal: Decimal, iva_rate: str, iva_amount: Decimal) -> str:
    return json.dumps(
        {
            "description": description,
            "quantity": "1",
            "unit_price": f"{subtotal:.2f}",
            "subtotal": f"{subtotal:.2f}",
            "iva_rate": iva_rate,
            "iva_amount": f"{iva_amount:.2f}",
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def _assert_reopened_persistence(
    *,
    cli: InstalledCli,
    receipts: list[SanitizedCommandReceipt],
    artifact: Path,
    transaction_ids: tuple[str, str, str],
    invoice_ids: tuple[str, str],
    issued_invoice_id: str,
    issued_transaction_ids: tuple[str, str],
    evidence_id: str,
) -> tuple[tuple[str, str], tuple[str, str]]:
    ledger = _result(_run(cli, receipts, artifact, ("app", "ledger", "list"), result_keys=()))
    invoices = _result(_run(cli, receipts, artifact, ("app", "ledger", "invoice", "list"), result_keys=()))
    evidence = _result(_run(cli, receipts, artifact, ("app", "ledger", "evidence", "list"), result_keys=()))
    if _row_ids(ledger, "transaction_id") != set(transaction_ids):
        raise IvaCliJourneyError("fresh-process ledger readback lost a transaction identity")
    if _row_ids(invoices, "invoice_id") != set(invoice_ids):
        raise IvaCliJourneyError("fresh-process invoice readback lost an invoice identity")
    if _row_ids(evidence, "evidence_id") != {evidence_id}:
        raise IvaCliJourneyError("fresh-process evidence readback lost the purchase evidence identity")
    issued = _result(
        _run(
            cli,
            receipts,
            artifact,
            ("app", "ledger", "invoice", "view", issued_invoice_id),
            result_keys=("invoice_id",),
        )
    )
    raw_lines = issued.get("lines")
    if not isinstance(raw_lines, list) or len(raw_lines) != 2:
        raise IvaCliJourneyError("fresh-process issued invoice readback lost its two canonical lines")
    lines = cast(list[object], raw_lines)
    rates = tuple(
        str(line.get("iva_rate"))
        for line in lines
        if isinstance(line, Mapping) and isinstance(line.get("iva_rate"), str)
    )
    if rates != ("RATE_21", "RATE_10"):
        raise IvaCliJourneyError("fresh-process issued invoice readback lost its canonical rate order")
    links_raw = issued.get("linked_transaction_ids")
    if not isinstance(links_raw, list) or set(links_raw) != set(issued_transaction_ids):
        raise IvaCliJourneyError("fresh-process issued invoice readback lost its two public transaction links")
    return cast(tuple[str, str], rates), cast(tuple[str, str], tuple(links_raw))


def _decimal_field(calculated: Mapping[str, object], casilla_id: str) -> Decimal:
    raw_casillas = calculated.get("casilla_values")
    if not isinstance(raw_casillas, Mapping):
        raise IvaCliJourneyError("Modelo 303 calculate returned no public casilla projection")
    value = raw_casillas.get(casilla_id)
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise IvaCliJourneyError(f"Modelo 303 calculate returned no decimal {casilla_id}") from exc


def _rate_observations(*, calculated: Mapping[str, object]) -> tuple[RateObservation, RateObservation, RateObservation]:
    raw_observations = calculated.get("observations")
    if not isinstance(raw_observations, list):
        raise IvaCliJourneyError("Modelo 303 calculate returned no public observations")
    observations = {
        row.get("casilla_id"): row
        for item in raw_observations
        if isinstance(item, Mapping)
        if isinstance((row := cast(Mapping[str, object], item)).get("casilla_id"), str)
    }
    resolved: list[RateObservation] = []
    for casilla_id, expected in _RATE_OBSERVATIONS:
        raw = observations.get(casilla_id)
        if not isinstance(raw, Mapping):
            raise IvaCliJourneyError(f"Modelo 303 calculate omitted rate-specific observation {casilla_id}")
        try:
            observed = Decimal(str(raw.get("value"))).quantize(Decimal("0.01"))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise IvaCliJourneyError(f"rate-specific observation {casilla_id} is not decimal") from exc
        if observed != expected:
            raise IvaCliJourneyError(
                f"rate-specific observation mismatch for {casilla_id}: expected {expected:.2f}, got {observed:.2f}"
            )
        legal_refs = raw.get("legal_refs")
        source_refs = raw.get("source_refs")
        if not isinstance(legal_refs, list) or not legal_refs:
            raise IvaCliJourneyError(f"rate-specific observation {casilla_id} has no legal grounding")
        if not isinstance(source_refs, list) or not source_refs:
            raise IvaCliJourneyError(f"rate-specific observation {casilla_id} has no source grounding")
        resolved.append(
            RateObservation(
                casilla_id=casilla_id,
                value=f"{observed:.2f}",
                legal_ref_count=len(legal_refs),
                source_ref_count=len(source_refs),
            )
        )
    return cast(tuple[RateObservation, RateObservation, RateObservation], tuple(resolved))


__all__ = ["IvaMultirateCliJourneyReceipt", "RateObservation", "run_iva_multirate_cli_journey"]
