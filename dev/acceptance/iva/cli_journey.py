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
from decimal import Decimal, InvalidOperation
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Final, cast

from cadrumo.domain.calculations.registry.authority import IndexedRegistryAuthority
from cadrumo.domain.calculations.registry.export import resolve_export_layout
from cadrumo.domain.calculations.registry.export_parse import parse_export_payload
from dev.acceptance.installed_cli import (
    CommandEvidence,
    InstalledCli,
    InstalledCliError,
    authority_generation,
    profile_create_args,
)

_YEAR: Final = 2025
_PERIOD: Final = "1T"
_SALE_IVA: Final = Decimal("21.00")
_PURCHASE_IVA: Final = Decimal("10.50")
_EXPECTED_RESULT: Final = _SALE_IVA - _PURCHASE_IVA
_PRIVATE_ARTIFACT_PLACEHOLDER: Final = "<synthetic-purchase-artifact>"
_EXPORT_ARTIFACT_PLACEHOLDER: Final = "<local-m303-export-artifact>"
_PRODUCT_IDENTITY_EXPORT_REFUSAL_CODE: Final = "REFUSED_MODELO_EXPORT_PRODUCT_IDENTITY_UNAVAILABLE"
_PRODUCT_IDENTITY_EXPORT_REFUSAL_DIAGNOSTIC: Final = (
    'Official export is unavailable: the record design reserves the header fields "Versión del Programa" '
    'and "NIF del desarrollador" for the software developer, and no reviewed product identity exists for '
    "them. Cadrumo does not fill them with blanks or placeholders. The calculation and its verification "
    "remain valid; exporting needs a reviewed program identifier and developer NIF from the software developer."
)
# The 2025 DP30300 record design reserves positions 93-96 and 101-109 for these two fields.
_PRODUCT_IDENTITY_EXPORT_REFUSAL_POSITIONS: Final = ("DP30300", "93-96", "101-109")
_AUTHORITY_GENERATION: Final = authority_generation


class IvaCliJourneyError(RuntimeError):
    """A public IVA command refused before the acceptance path completed."""


@dataclass(frozen=True, slots=True)
class SanitizedCommandReceipt:
    """One exact installed invocation with private local input paths removed."""

    argv: tuple[str, ...]
    returncode: int
    status: str
    notice_codes: tuple[str, ...]
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
    verification_report_id: str
    verification_status: str
    verification_granted: bool
    export_status: str
    export_failure_code: str | None
    export_failure_diagnostic: str | None
    export_artifact: str | None
    export_size: int | None
    export_sha256: str | None
    export_layout_id: str | None
    export_parser_verdict: str
    exported_iva_resultado: str | None
    local_export_only: bool | None
    commands: tuple[SanitizedCommandReceipt, ...]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe receipt without financial source bytes or secrets."""
        return cast(dict[str, object], asdict(self))


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
    except InstalledCliError as exc:
        raise IvaCliJourneyError("config profile create refused") from exc
    profile_commands = cli.commands[profile_start:]
    if len(profile_commands) != 2:
        raise IvaCliJourneyError("profile setup did not produce its two public command receipts")
    receipts.extend(
        (
            _command_receipt(
                args=profile_create_args(_YEAR),
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
    raw_resultado = casillas.get("iva.resultado")
    try:
        iva_resultado = Decimal(str(raw_resultado)).quantize(Decimal("0.01"))
    except Exception as exc:  # Decimal exposes several public parse exceptions.
        raise IvaCliJourneyError("Modelo 303 calculate returned no decimal iva.resultado") from exc
    if iva_resultado != _EXPECTED_RESULT:
        raise IvaCliJourneyError(
            f"independent IVA oracle mismatch: expected {_EXPECTED_RESULT:.2f}, got {iva_resultado:.2f}"
        )

    export_cli = InstalledCli(
        cli.executable,
        storage_root=storage_root,
        authority_root=authority_root,
        passphrase=cli.passphrase,
    )
    verification = _result(
        _run(
            export_cli,
            receipts,
            artifact,
            ("app", "modelo", "work", "verify", revision_id),
            result_keys=("verification_report_id", "calculation_revision_id"),
        )
    )
    verification_report_id = _required_id(verification, "verification_report_id")
    verification_status = _required_text(verification, "completeness_status")
    if verification.get("calculation_revision_id") != revision_id:
        raise IvaCliJourneyError("Modelo 303 verify returned a different calculation revision")
    if verification.get("granted_verificado_completo") is not True:
        raise IvaCliJourneyError(
            "Modelo 303 verify did not grant complete verification: "
            f"status={verification_status}; findings={verification.get('finding_count')}"
        )

    export_artifact = artifact_root / "m303-2025-1t.fichero-boe"
    export_document = _run(
        export_cli,
        receipts,
        artifact,
        ("app", "modelo", "export", work_unit_id, "--output", str(export_artifact)),
        result_keys=("work_unit_id", "calculation_revision_id", "file_sha256"),
        redacted_paths={export_artifact: _EXPORT_ARTIFACT_PLACEHOLDER},
        accepted_refusal=(_PRODUCT_IDENTITY_EXPORT_REFUSAL_CODE, _PRODUCT_IDENTITY_EXPORT_REFUSAL_DIAGNOSTIC),
    )
    export_error = _object_mapping(export_document.get("error"))
    if export_error:
        if export_artifact.exists():
            raise IvaCliJourneyError("refused Modelo 303 export wrote an artifact")
        refusal_context = _object_mapping(export_error.get("context"))
        observed_positions = tuple(
            refusal_context.get(key) for key in ("record", "program_positions", "developer_positions")
        )
        if observed_positions != _PRODUCT_IDENTITY_EXPORT_REFUSAL_POSITIONS:
            raise IvaCliJourneyError(
                f"export refusal located the developer header fields at {observed_positions}, "
                f"not the official {_PRODUCT_IDENTITY_EXPORT_REFUSAL_POSITIONS}"
            )
        export_status = "verified_export_blocked"
        export_failure_code = _PRODUCT_IDENTITY_EXPORT_REFUSAL_CODE
        export_failure_diagnostic = _PRODUCT_IDENTITY_EXPORT_REFUSAL_DIAGNOSTIC
        receipt_export_artifact: str | None = None
        export_size: int | None = None
        export_sha256: str | None = None
        export_layout_id: str | None = None
        export_parser_verdict = "not_run_product_software_identity_pending"
        exported_iva_resultado: str | None = None
        local_export_only: bool | None = None
    else:
        exported = _result(export_document)
        _require_export_receipt(
            exported=exported,
            work_unit_id=work_unit_id,
            calculation_revision_id=revision_id,
            artifact=export_artifact,
        )
        payload = export_artifact.read_bytes()
        if not payload:
            raise IvaCliJourneyError("Modelo 303 export wrote an empty artifact")
        export_layout_id, parsed_resultado = _parse_exported_iva_resultado(
            authority_root=authority_root,
            payload=payload,
        )
        if parsed_resultado != _EXPECTED_RESULT:
            raise IvaCliJourneyError(
                f"canonical export IVA result mismatch: expected {_EXPECTED_RESULT:.2f}, got {parsed_resultado:.2f}"
            )
        export_status = "verified_exported"
        export_failure_code = None
        export_failure_diagnostic = None
        receipt_export_artifact = _EXPORT_ARTIFACT_PLACEHOLDER
        export_size = len(payload)
        export_sha256 = _sha256_bytes(payload)
        export_parser_verdict = "canonical_export_parser_verified"
        exported_iva_resultado = f"{parsed_resultado:.2f}"
        local_export_only = True

    descriptor = authority_root.resolve(strict=True) / "authority.current.json"
    return IvaM303CliJourneyReceipt(
        schema_version="iva-01-installed-cli-journey-v1",
        executable=str(cli.executable),
        executable_sha256=_sha256_path(cli.executable),
        source_identity=_checkout_source_identity(),
        package_identity=_installed_package_identity(),
        authority_generation=_AUTHORITY_GENERATION(authority_root),
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
        verification_report_id=verification_report_id,
        verification_status=verification_status,
        verification_granted=True,
        export_status=export_status,
        export_failure_code=export_failure_code,
        export_failure_diagnostic=export_failure_diagnostic,
        export_artifact=receipt_export_artifact,
        export_size=export_size,
        export_sha256=export_sha256,
        export_layout_id=export_layout_id,
        export_parser_verdict=export_parser_verdict,
        exported_iva_resultado=exported_iva_resultado,
        local_export_only=local_export_only,
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
    redacted_paths: Mapping[Path, str] | None = None,
    accepted_refusal: tuple[str, str] | None = None,
) -> dict[str, object]:
    """Run one public command and retain a strict, sanitized receipt only."""
    document = cli.run(args, allow_error=True)
    evidence = cli.commands[-1]
    result = cast(object, document.get("result"))
    result_mapping = _object_mapping(result)
    result_ids = tuple(str(value) for key in result_keys if isinstance((value := result_mapping.get(key)), str))
    receipts.append(
        _command_receipt(
            args=args,
            evidence=evidence,
            artifact=artifact,
            result_ids=result_ids,
            redacted_paths=redacted_paths,
        )
    )
    if evidence.returncode != 0:
        error = cast(object, document.get("error"))
        error_mapping = _object_mapping(error)
        code = error_mapping.get("code")
        message = error_mapping.get("message")
        if accepted_refusal == (code, message):
            return cast(dict[str, object], document)
        raise IvaCliJourneyError(
            "public command refused: "
            f"{' '.join(_sanitize_argv(args, artifact, redacted_paths))}; code={code}; message={message}"
        )
    return cast(dict[str, object], document)


def _command_receipt(
    *,
    args: tuple[str, ...],
    evidence: CommandEvidence,
    artifact: Path,
    result_ids: tuple[str, ...],
    redacted_paths: Mapping[Path, str] | None = None,
) -> SanitizedCommandReceipt:
    return SanitizedCommandReceipt(
        argv=("--format", "json", *_sanitize_argv(args, artifact, redacted_paths)),
        returncode=int(evidence.returncode),
        status=str(evidence.status),
        notice_codes=tuple(evidence.notice_codes),
        result_ids=result_ids,
    )


def _sanitize_argv(
    args: tuple[str, ...],
    artifact: Path,
    redacted_paths: Mapping[Path, str] | None = None,
) -> tuple[str, ...]:
    replacements = {str(artifact.resolve()): _PRIVATE_ARTIFACT_PLACEHOLDER}
    if redacted_paths is not None:
        replacements.update({str(path.resolve()): placeholder for path, placeholder in redacted_paths.items()})
    return tuple(replacements.get(value, value) for value in args)


def _result(document: dict[str, object]) -> dict[str, object]:
    result = document.get("result")
    if not isinstance(result, dict):
        raise IvaCliJourneyError("public command returned no object result")
    return cast(dict[str, object], result)


def _require_export_receipt(
    *,
    exported: Mapping[str, object],
    work_unit_id: str,
    calculation_revision_id: str,
    artifact: Path,
) -> None:
    """Bind the command receipt to the local artifact before parsing its bytes."""
    if exported.get("work_unit_id") != work_unit_id:
        raise IvaCliJourneyError("Modelo 303 export returned a different work unit")
    if exported.get("calculation_revision_id") != calculation_revision_id:
        raise IvaCliJourneyError("Modelo 303 export returned a different calculation revision")
    if not artifact.is_file():
        raise IvaCliJourneyError("Modelo 303 export reported success without an artifact")
    size = exported.get("byte_size")
    if not isinstance(size, int) or size != artifact.stat().st_size:
        raise IvaCliJourneyError("Modelo 303 export byte-size receipt does not match its artifact")
    sha256 = exported.get("file_sha256")
    if not isinstance(sha256, str) or sha256 != _sha256_path(artifact):
        raise IvaCliJourneyError("Modelo 303 export digest receipt does not match its artifact")


def _parse_exported_iva_resultado(*, authority_root: Path, payload: bytes) -> tuple[str, Decimal]:
    """Read the selected official M303 layout and its semantic IVA result field."""
    descriptor = authority_root.resolve(strict=True) / "authority.current.json"
    try:
        authority = IndexedRegistryAuthority(descriptor)
        with authority.operation() as operation:
            snapshot = operation.snapshot("303", filing_year=_YEAR, period=_PERIOD)
            layout = resolve_export_layout(snapshot).layout
        parsed = parse_export_payload(layout, payload)
    except Exception as exc:
        raise IvaCliJourneyError(f"canonical Modelo 303 export parser refused: {type(exc).__name__}") from exc
    values: set[Decimal] = set()
    for field in parsed.casillas:
        if str(field.casilla_id) != "iva.resultado":
            continue
        try:
            values.add(Decimal(str(field.value)).quantize(Decimal("0.01")))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise IvaCliJourneyError("canonical export iva.resultado is not decimal") from exc
    if len(values) != 1:
        raise IvaCliJourneyError("canonical export has no unambiguous iva.resultado field")
    return str(parsed.layout_id), values.pop()


def _object_mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        return cast(Mapping[str, object], {})
    return cast(Mapping[str, object], value)


def _required_id(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise IvaCliJourneyError(f"public command returned no {key}")
    return value


def _required_text(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise IvaCliJourneyError(f"public command returned no {key}")
    return value


def _sha256_path(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


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
