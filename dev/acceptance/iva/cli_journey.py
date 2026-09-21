"""Exercise one ordinary 2025/1T Modelo 303 path through installed CLI commands.

The journey deliberately owns no repository or product fixture.  It makes each
write through the installed ``aeat`` command, retains only a sanitized command
receipt, and independently checks the one expected IVA result.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from decimal import Decimal
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Final, cast

from dev.acceptance.income_tax import cli_journey as income_tax_cli_journey
from dev.acceptance.income_tax.cli_journey import CommandEvidence, InstalledCli, JourneyError

_YEAR: Final = 2025
_PERIOD: Final = "1T"
_SALE_IVA: Final = Decimal("21.00")
_PURCHASE_IVA: Final = Decimal("10.50")
_EXPECTED_RESULT: Final = _SALE_IVA - _PURCHASE_IVA
_PRIVATE_ARTIFACT_PLACEHOLDER: Final = "<synthetic-purchase-artifact>"
_PROFILE_CREATE_ARGS: Final = getattr(income_tax_cli_journey, "_profile_create_args")  # noqa: B009
_AUTHORITY_GENERATION: Final = getattr(income_tax_cli_journey, "_authority_generation")  # noqa: B009


class IvaCliJourneyError(RuntimeError):
    """A public IVA command refused before the acceptance path completed."""


@dataclass(frozen=True, slots=True)
class SanitizedCommandReceipt:
    """One exact installed invocation with private local input paths removed."""

    argv: tuple[str, ...]
    returncode: int
    status: str
    result_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class IvaM303CliJourneyReceipt:
    """Minimal durable evidence of the public ordinary-M303 calculation path."""

    schema_version: str
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
    attestation_attachment_id: str
    attestation_sha256: str
    work_unit_id: str
    calculation_revision_id: str
    iva_resultado: str
    commands: tuple[SanitizedCommandReceipt, ...]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe receipt without financial source bytes or secrets."""
        return asdict(self)


def run_iva_m303_cli_journey(
    *,
    executable: Path,
    authority_root: Path,
    storage_root: Path,
    artifact_root: Path,
) -> IvaM303CliJourneyReceipt:
    """Capture and calculate the smallest truthful ordinary 2025/1T IVA case."""
    if storage_root.exists() and any(storage_root.iterdir()):
        raise IvaCliJourneyError(f"storage root must be fresh and empty: {storage_root}")
    storage_root.mkdir(parents=True, exist_ok=True)
    artifact_root.mkdir(parents=True, exist_ok=True)
    artifact = artifact_root / "synthetic-purchase.pdf"
    artifact.write_bytes(b"%PDF-1.4\n% synthetic acceptance purchase evidence\n")

    cli = InstalledCli(
        executable,
        storage_root=storage_root,
        authority_root=authority_root,
        passphrase=secrets.token_urlsafe(32),
    )
    receipts: list[SanitizedCommandReceipt] = []
    profile_start = len(cli.commands)
    try:
        cli.create_profile(year=_YEAR)
    except JourneyError as exc:
        raise IvaCliJourneyError("config profile create refused") from exc
    profile_commands = cli.commands[profile_start:]
    if len(profile_commands) != 2:
        raise IvaCliJourneyError("profile setup did not produce its two public command receipts")
    receipts.extend(
        (
            _command_receipt(
                args=_PROFILE_CREATE_ARGS(_YEAR),
                evidence=profile_commands[0],
                artifact=artifact,
                result_ids=(),
            ),
            _command_receipt(
                args=("config", "profile", "complete-setup"),
                evidence=profile_commands[1],
                artifact=artifact,
                result_ids=(),
            ),
        )
    )

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

    sale_transaction = _result(
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
                "121.00",
                "--direction",
                "INCOMING",
                "--description",
                "Synthetic ordinary IVA sale",
                "--classification",
                "BUSINESS",
                "--taxable-base",
                "100.00",
                "--iva-rate",
                "0.21",
                "--iva-amount",
                "21.00",
                "--iva-category",
                "domestic_general",
                "--source-jurisdiction",
                "ES",
                "--idempotency-key",
                "iva-acceptance-sale-2025-1t",
            ),
            result_keys=("transaction_id",),
        )
    )
    sale_transaction_id = _required_id(sale_transaction, "transaction_id")
    sale_invoice = _result(
        _run(
            cli,
            receipts,
            artifact,
            _invoice_add_args(
                kind="issued",
                counterparty_name="Synthetic client SL",
                counterparty_nif="A58818501",
                invoice_number="IVA-ISS-2025-1T",
                iva_category="domestic_general",
                line=_invoice_line(description="Synthetic sale", subtotal="100.00", iva_amount="21.00"),
            ),
            result_keys=("invoice_id",),
        )
    )
    sale_invoice_id = _required_id(sale_invoice, "invoice_id")
    _run(
        cli,
        receipts,
        artifact,
        ("app", "ledger", "link", sale_transaction_id, "--invoice-id", sale_invoice_id),
        result_keys=(),
    )

    purchase_transaction = _result(
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
                "iva-acceptance-purchase-2025-1t",
            ),
            result_keys=("transaction_id",),
        )
    )
    purchase_transaction_id = _required_id(purchase_transaction, "transaction_id")
    _run(
        cli,
        receipts,
        artifact,
        (
            "app",
            "ledger",
            "classify",
            purchase_transaction_id,
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
    purchase_invoice = _result(
        _run(
            cli,
            receipts,
            artifact,
            _invoice_add_args(
                kind="received",
                counterparty_name="Synthetic supplier SL",
                counterparty_nif="A58818501",
                invoice_number="IVA-REC-2025-1T",
                iva_category="domestic_general",
                line=_invoice_line(description="Synthetic purchase", subtotal="50.00", iva_amount="10.50"),
            ),
            result_keys=("invoice_id",),
        )
    )
    purchase_invoice_id = _required_id(purchase_invoice, "invoice_id")
    _run(
        cli,
        receipts,
        artifact,
        ("app", "ledger", "link", purchase_transaction_id, "--invoice-id", purchase_invoice_id),
        result_keys=(),
    )

    reopened = InstalledCli(
        cli.executable,
        storage_root=storage_root,
        authority_root=authority_root,
        passphrase=cli.passphrase,
    )
    _assert_reopened_identities(
        cli=reopened,
        receipts=receipts,
        artifact=artifact,
        transaction_ids=(sale_transaction_id, purchase_transaction_id),
        invoice_ids=(sale_invoice_id, purchase_invoice_id),
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
    if len(attachment_id) != 64 or len(attestation_sha256) != 64:
        raise IvaCliJourneyError("attestation did not return 64-character secure identifiers")

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
    revision_id = _required_id(calculated, "calculation_revision_id")
    casillas_raw = calculated.get("casilla_values")
    if not isinstance(casillas_raw, dict):
        raise IvaCliJourneyError("Modelo 303 calculate returned no public casilla projection")
    casillas = cast(dict[str, object], casillas_raw)
    raw_resultado = cast(object, casillas.get("iva.resultado"))
    try:
        iva_resultado = Decimal(str(raw_resultado)).quantize(Decimal("0.01"))
    except Exception as exc:  # Decimal exposes several public parse exceptions.
        raise IvaCliJourneyError("Modelo 303 calculate returned no decimal iva.resultado") from exc
    if iva_resultado != _EXPECTED_RESULT:
        raise IvaCliJourneyError(
            f"independent IVA oracle mismatch: expected {_EXPECTED_RESULT:.2f}, got {iva_resultado:.2f}"
        )

    descriptor = authority_root.resolve(strict=True) / "authority.current.json"
    return IvaM303CliJourneyReceipt(
        schema_version="iva-01-installed-cli-journey-v1",
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
        attestation_attachment_id=attachment_id,
        attestation_sha256=attestation_sha256,
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        iva_resultado=f"{iva_resultado:.2f}",
        commands=tuple(receipts),
    )


def _invoice_add_args(
    *,
    kind: str,
    counterparty_name: str,
    counterparty_nif: str,
    invoice_number: str,
    iva_category: str,
    line: str,
) -> tuple[str, ...]:
    return (
        "app",
        "ledger",
        "invoice",
        "add",
        "--kind",
        kind,
        "--counterparty-name",
        counterparty_name,
        "--counterparty-nif",
        counterparty_nif,
        "--invoice-number",
        invoice_number,
        "--invoice-date",
        "2025-02-15",
        "--country-code",
        "ES",
        "--iva-category",
        iva_category,
        "--line",
        line,
    )


def _invoice_line(*, description: str, subtotal: str, iva_amount: str) -> str:
    return json.dumps(
        {
            "description": description,
            "quantity": "1",
            "unit_price": subtotal,
            "subtotal": subtotal,
            "iva_rate": "RATE_21",
            "iva_amount": iva_amount,
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def _assert_reopened_identities(
    *,
    cli: InstalledCli,
    receipts: list[SanitizedCommandReceipt],
    artifact: Path,
    transaction_ids: tuple[str, str],
    invoice_ids: tuple[str, str],
    evidence_id: str,
) -> None:
    ledger = _result(_run(cli, receipts, artifact, ("app", "ledger", "list"), result_keys=()))
    invoices = _result(_run(cli, receipts, artifact, ("app", "ledger", "invoice", "list"), result_keys=()))
    evidence = _result(_run(cli, receipts, artifact, ("app", "ledger", "evidence", "list"), result_keys=()))
    if _row_ids(ledger, "transaction_id") != set(transaction_ids):
        raise IvaCliJourneyError("fresh-process ledger readback lost a transaction identity")
    if _row_ids(invoices, "invoice_id") != set(invoice_ids):
        raise IvaCliJourneyError("fresh-process invoice readback lost an invoice identity")
    if _row_ids(evidence, "evidence_id") != {evidence_id}:
        raise IvaCliJourneyError("fresh-process evidence readback lost the purchase evidence identity")


def _row_ids(payload: dict[str, object], key: str) -> set[str]:
    rows_raw = payload.get("rows")
    if not isinstance(rows_raw, list):
        raise IvaCliJourneyError(f"public list returned no rows for {key}")
    rows = cast(list[object], rows_raw)
    resolved: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        value = cast(Mapping[str, object], row).get(key)
        if isinstance(value, str):
            resolved.add(value)
    return resolved


def _run(
    cli: InstalledCli,
    receipts: list[SanitizedCommandReceipt],
    artifact: Path,
    args: tuple[str, ...],
    *,
    result_keys: tuple[str, ...],
) -> dict[str, object]:
    """Run one public command and retain a strict, sanitized receipt only."""
    document = cli.run(args, allow_error=True)
    evidence = cli.commands[-1]
    result = cast(object, document.get("result"))
    result_mapping = _object_mapping(result)
    result_ids = tuple(str(value) for key in result_keys if isinstance((value := result_mapping.get(key)), str))
    receipts.append(_command_receipt(args=args, evidence=evidence, artifact=artifact, result_ids=result_ids))
    if evidence.returncode != 0:
        error = cast(object, document.get("error"))
        error_mapping = _object_mapping(error)
        code = error_mapping.get("code")
        message = error_mapping.get("message")
        raise IvaCliJourneyError(
            f"public command refused: {' '.join(_sanitize_argv(args, artifact))}; code={code}; message={message}"
        )
    return cast(dict[str, object], document)


def _command_receipt(
    *, args: tuple[str, ...], evidence: CommandEvidence, artifact: Path, result_ids: tuple[str, ...]
) -> SanitizedCommandReceipt:
    return SanitizedCommandReceipt(
        argv=("--format", "json", *_sanitize_argv(args, artifact)),
        returncode=int(evidence.returncode),
        status=str(evidence.status),
        result_ids=result_ids,
    )


def _sanitize_argv(args: tuple[str, ...], artifact: Path) -> tuple[str, ...]:
    artifact_text = str(artifact.resolve())
    return tuple(_PRIVATE_ARTIFACT_PLACEHOLDER if value == artifact_text else value for value in args)


def _result(document: dict[str, object]) -> dict[str, object]:
    result = cast(object, document.get("result"))
    if not isinstance(result, dict):
        raise IvaCliJourneyError("public command returned no object result")
    return cast(dict[str, object], result)


def _object_mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        return cast(Mapping[str, object], {})
    return cast(Mapping[str, object], value)


def _required_id(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise IvaCliJourneyError(f"public command returned no {key}")
    return value


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _checkout_source_identity() -> str:
    root = Path(__file__).resolve().parents[3]
    dot_git = root / ".git"
    if dot_git.is_file():
        raw = dot_git.read_text(encoding="utf-8").strip()
        if raw.startswith("gitdir: "):
            dot_git = (root / raw.removeprefix("gitdir: ").strip()).resolve()
    head = (dot_git / "HEAD").read_text(encoding="utf-8").strip()
    if head.startswith("ref: "):
        ref = head.removeprefix("ref: ")
        resolved = dot_git / ref
        if resolved.is_file():
            head = resolved.read_text(encoding="utf-8").strip()
    return head


def _installed_package_identity() -> str:
    try:
        return f"cadrumo=={version('cadrumo')}"
    except PackageNotFoundError as exc:
        raise IvaCliJourneyError("installed executable has no cadrumo distribution metadata") from exc


__all__ = ["IvaCliJourneyError", "IvaM303CliJourneyReceipt", "run_iva_m303_cli_journey"]
