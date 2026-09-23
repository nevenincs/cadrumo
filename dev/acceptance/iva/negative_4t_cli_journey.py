"""Installed-CLI acceptance for one negative 2025/4T Modelo 303 filing.

The scenario records one synthetic deductible purchase and no sale, then proves
that a locally filed negative result remains local and pending.  ``compensar``
creates one available IVA compensation lot, while ``devolver`` creates none.
It never exports or submits anything to AEAT.
"""

from __future__ import annotations

import secrets
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Final, Literal, cast

from dev.acceptance.installed_cli import InstalledCli, InstalledCliError, authority_generation

from .cli_journey import (
    IvaCliJourneyError,
    SanitizedCommandReceipt,
    _checkout_source_identity,
    _installed_package_identity,
    _required_id,
    _result,
    _run,
    _sha256_path,
)
from .multirate_cli_journey import _create_profile

RefundElection = Literal["compensar", "devolver"]

_ACCEPTANCE_IDS: Final[Mapping[RefundElection, str]] = {
    "compensar": "IVA-01-NEGATIVE-2025-4T-COMPENSAR",
    "devolver": "IVA-01-NEGATIVE-2025-4T-DEVOLVER",
}
_YEAR: Final = 2025
_PERIOD: Final = "4T"
_PRIOR_PERIOD: Final = "3T"
_PURCHASE_IVA: Final = Decimal("10.50")
_EXPECTED_RESULT: Final = -_PURCHASE_IVA
_ZERO: Final = Decimal("0.00")
_PRIVATE_ARTIFACT_PLACEHOLDER: Final = "<synthetic-purchase-artifact>"


@dataclass(frozen=True, slots=True)
class IvaNegative4TCliJourneyReceipt:
    """Sanitized evidence of one local, pending negative Modelo 303 filing."""

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
    transaction_id: str
    invoice_id: str
    evidence_id: str
    work_unit_id: str
    calculation_revision_id: str
    iva_resultado: str
    local_refund_election: RefundElection
    filing_record_id: str
    filing_origin: str
    filing_confirmation: str
    filing_aeat_accepted: bool
    filing_live_submission: bool
    wallet_row_count: int
    wallet_generated_amount: str
    wallet_available_end_amount: str
    wallet_carry_forward_lot_count: int
    wallet_remaining_lot_amount: str | None
    commands: tuple[SanitizedCommandReceipt, ...]

    def to_dict(self) -> dict[str, object]:
        """Return the safe receipt without source bytes, paths, or secrets."""
        return cast(dict[str, object], asdict(self))


def run_iva_negative_4t_cli_journey(
    *,
    executable: Path,
    authority_root: Path,
    storage_root: Path,
    artifact_root: Path,
    refund_election: RefundElection = "compensar",
) -> IvaNegative4TCliJourneyReceipt:
    """File one 2025/4T local negative election, then reopen its wallet history."""
    if storage_root.exists() and any(storage_root.iterdir()):
        raise IvaCliJourneyError(f"storage root must be fresh and empty: {storage_root}")
    storage_root.mkdir(parents=True, exist_ok=True)
    artifact_root.mkdir(parents=True, exist_ok=True)
    artifact = artifact_root / "synthetic-negative-4t-purchase.pdf"
    artifact.write_bytes(b"%PDF-1.4\n% synthetic negative IVA purchase evidence\n")

    cli = InstalledCli(
        executable,
        storage_root=storage_root,
        authority_root=authority_root,
        passphrase=secrets.token_urlsafe(32),
    )
    receipts: list[SanitizedCommandReceipt] = []
    try:
        _create_profile(cli=cli, receipts=receipts, artifact=artifact)
    except InstalledCliError as exc:
        raise IvaCliJourneyError("config profile create refused") from exc

    evidence = _result(
        _run(
            cli,
            receipts,
            artifact,
            ("app", "ledger", "evidence", "add", str(artifact), "--supplier", "Synthetic supplier SL"),
            result_keys=("evidence_id",),
        )
    )
    evidence_id = _required_id(evidence, "evidence_id")

    purchase = _result(
        _run(
            cli,
            receipts,
            artifact,
            (
                "app",
                "ledger",
                "add",
                "--date",
                "2025-12-15",
                "--amount",
                "60.50",
                "--direction",
                "OUTGOING",
                "--description",
                "Synthetic deductible IVA purchase",
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
                "iva-01-negative-2025-4t-purchase",
            ),
            result_keys=("transaction_id",),
        )
    )
    transaction_id = _required_id(purchase, "transaction_id")
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
                "IVA-REC-NEGATIVE-2025-4T",
                "--invoice-date",
                "2025-12-15",
                "--country-code",
                "ES",
                "--iva-category",
                "domestic_general",
                "--line",
                (
                    '{"description":"Synthetic deductible purchase","iva_amount":"10.50",'
                    '"iva_rate":"RATE_21","quantity":"1","subtotal":"50.00","unit_price":"50.00"}'
                ),
            ),
            result_keys=("invoice_id",),
        )
    )
    invoice_id = _required_id(invoice, "invoice_id")
    _run(
        cli,
        receipts,
        artifact,
        ("app", "ledger", "link", transaction_id, "--invoice-id", invoice_id),
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
            _PRIOR_PERIOD,
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
                "2025-12-31T12:00:00+00:00",
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
            f"independent negative IVA oracle mismatch: expected {_EXPECTED_RESULT:.2f}, got {iva_resultado:.2f}"
        )

    verify_cli = InstalledCli(
        cli.executable,
        storage_root=storage_root,
        authority_root=authority_root,
        passphrase=cli.passphrase,
    )
    verified = _result(
        _run(
            verify_cli,
            receipts,
            artifact,
            ("app", "modelo", "work", "verify", calculation_revision_id),
            result_keys=("verification_report_id", "calculation_revision_id"),
        )
    )
    if verified.get("calculation_revision_id") != calculation_revision_id:
        raise IvaCliJourneyError("Modelo 303 verify returned a different calculation revision")
    if verified.get("granted_verificado_completo") is not True:
        raise IvaCliJourneyError("Modelo 303 verify did not grant complete verification")

    filed = _result(
        _run(
            verify_cli,
            receipts,
            artifact,
            (
                "app",
                "modelo",
                "work",
                "file",
                calculation_revision_id,
                "--refund-election",
                refund_election,
                "--notes",
                f"Synthetic local pending {refund_election} filing; not sent to AEAT",
            ),
            result_keys=("filing_record_id",),
        )
    )
    filing_record_id = _required_id(filed, "filing_record_id")
    filing_origin = _required_text(filed, "origin")
    filing_confirmation = _required_text(filed, "confirmation")
    if filing_origin != "local" or filing_confirmation != "pendiente":
        raise IvaCliJourneyError("Modelo 303 file did not label the filing local and pending")
    if filed.get("aeat_accepted") is not False or filed.get("live_submission") is not False:
        raise IvaCliJourneyError("Modelo 303 file claimed AEAT acceptance or a live submission")
    if filed.get("external_evidence") is not None:
        raise IvaCliJourneyError("Modelo 303 local filing unexpectedly carries external AEAT evidence")

    history_cli = InstalledCli(
        cli.executable,
        storage_root=storage_root,
        authority_root=authority_root,
        passphrase=cli.passphrase,
    )
    history = _result(
        _run(
            history_cli,
            receipts,
            artifact,
            ("app", "live", "iva-wallet", "history", "--as-of-year", str(_YEAR)),
            result_keys=(),
        )
    )
    wallet_row_count, wallet_generated, wallet_available, wallet_lot_count, wallet_remaining = _assert_wallet_history(
        history, refund_election=refund_election
    )

    descriptor = authority_root.resolve(strict=True) / "authority.current.json"
    return IvaNegative4TCliJourneyReceipt(
        schema_version="iva-01-negative-2025-4t-installed-cli-journey-v2",
        acceptance_ids=(_acceptance_id(refund_election),),
        executable=str(cli.executable),
        executable_sha256=_sha256_path(cli.executable),
        source_identity=_checkout_source_identity(),
        package_identity=_installed_package_identity(),
        authority_generation=authority_generation(authority_root),
        authority_descriptor_sha256=_sha256_path(descriptor),
        storage_root=str(storage_root.resolve()),
        purchase_artifact=_PRIVATE_ARTIFACT_PLACEHOLDER,
        transaction_id=transaction_id,
        invoice_id=invoice_id,
        evidence_id=evidence_id,
        work_unit_id=work_unit_id,
        calculation_revision_id=calculation_revision_id,
        iva_resultado=f"{iva_resultado:.2f}",
        local_refund_election=refund_election,
        filing_record_id=filing_record_id,
        filing_origin=filing_origin,
        filing_confirmation=filing_confirmation,
        filing_aeat_accepted=False,
        filing_live_submission=False,
        wallet_row_count=wallet_row_count,
        wallet_generated_amount=f"{wallet_generated:.2f}",
        wallet_available_end_amount=f"{wallet_available:.2f}",
        wallet_carry_forward_lot_count=wallet_lot_count,
        wallet_remaining_lot_amount=None if wallet_remaining is None else f"{wallet_remaining:.2f}",
        commands=tuple(receipts),
    )


def _decimal_casilla(calculated: Mapping[str, object], casilla_id: str) -> Decimal:
    casillas = calculated.get("casilla_values")
    if not isinstance(casillas, Mapping):
        raise IvaCliJourneyError("Modelo 303 calculate returned no public casilla projection")
    try:
        return Decimal(str(casillas.get(casilla_id))).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise IvaCliJourneyError(f"Modelo 303 calculate returned no decimal {casilla_id}") from exc


def _assert_wallet_history(
    history: Mapping[str, object], *, refund_election: RefundElection
) -> tuple[int, Decimal, Decimal, int, Decimal | None]:
    """Validate the required 3T seed and the election-specific 4T wallet result."""
    if history.get("as_of_year") != _YEAR:
        raise IvaCliJourneyError("fresh-process IVA wallet history returned another as-of year")
    rows = history.get("rows")
    row_count = history.get("row_count")
    if not isinstance(rows, list) or not isinstance(row_count, int) or row_count != len(rows):
        raise IvaCliJourneyError("fresh-process IVA wallet history returned an invalid row projection")
    prior_seed = _unique_history_row(rows, period=_PRIOR_PERIOD, provenance="operator_seed")
    if _decimal_history_amount(prior_seed, "generated_amount") != _ZERO:
        raise IvaCliJourneyError("fresh-process IVA wallet history did not retain the 3T zero seed")
    if _decimal_history_amount(prior_seed, "available_end_amount") != _ZERO:
        raise IvaCliJourneyError("fresh-process IVA wallet history did not retain the 3T zero availability")
    filed_row = _unique_history_row(rows, period=_PERIOD, provenance="app_filing")
    generated = _decimal_history_amount(filed_row, "generated_amount")
    available = _decimal_history_amount(filed_row, "available_end_amount")
    lot_count = history.get("carry_forward_lot_count")
    lots = history.get("carry_forward_lots")
    if refund_election == "devolver":
        if generated != _ZERO or available != _ZERO:
            raise IvaCliJourneyError("fresh-process IVA wallet history retained carry after the devolver election")
        if not isinstance(lot_count, int) or lot_count != 0:
            raise IvaCliJourneyError("fresh-process IVA wallet history returned a carry-forward lot after devolver")
        if not isinstance(lots, list) or lots:
            raise IvaCliJourneyError("fresh-process IVA wallet history returned non-empty lots after devolver")
        return row_count, generated, available, lot_count, None

    if generated != _PURCHASE_IVA or available != _PURCHASE_IVA:
        raise IvaCliJourneyError("fresh-process IVA wallet history did not retain the generated available credit")
    if not isinstance(lot_count, int) or lot_count != 1:
        raise IvaCliJourneyError("fresh-process IVA wallet history did not return one carry-forward lot")
    if not isinstance(lots, list) or len(lots) != 1 or not isinstance(lots[0], Mapping):
        raise IvaCliJourneyError("fresh-process IVA wallet history returned no one-lot projection")
    lot = lots[0]
    if lot.get("source_filing_year") != _YEAR or _period_code(lot.get("source_period")) != _PERIOD:
        raise IvaCliJourneyError("fresh-process IVA wallet lot did not identify the 4T filing")
    if _decimal_history_amount(lot, "generated_amount") != _PURCHASE_IVA:
        raise IvaCliJourneyError("fresh-process IVA wallet lot did not retain the generated credit")
    remaining = _decimal_history_amount(lot, "remaining_amount")
    if remaining != _PURCHASE_IVA:
        raise IvaCliJourneyError("fresh-process IVA wallet lot did not retain the remaining credit")
    return row_count, generated, available, lot_count, remaining


def _acceptance_id(refund_election: RefundElection) -> str:
    """Return the acceptance identifier for the explicit local election."""
    return _ACCEPTANCE_IDS[refund_election]


def _unique_history_row(rows: list[object], *, period: str, provenance: str) -> Mapping[str, object]:
    matches = [
        row
        for row in rows
        if isinstance(row, Mapping)
        and row.get("year") == _YEAR
        and row.get("provenance") == provenance
        and _period_code(row.get("period")) == period
    ]
    if len(matches) != 1:
        raise IvaCliJourneyError(f"fresh-process IVA wallet history did not return one {period} {provenance} row")
    return cast(Mapping[str, object], matches[0])


def _period_code(value: object) -> str | None:
    if not isinstance(value, Mapping) or value.get("filing_year") != _YEAR:
        return None
    code = value.get("code")
    return code if isinstance(code, str) else None


def _decimal_history_amount(row: Mapping[str, object], key: str) -> Decimal:
    try:
        return Decimal(str(row.get(key))).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise IvaCliJourneyError(f"IVA wallet history returned no decimal {key}") from exc


def _required_text(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise IvaCliJourneyError(f"public command returned no {key}")
    return value


__all__ = ["IvaNegative4TCliJourneyReceipt", "run_iva_negative_4t_cli_journey"]
