"""Drive INCOME-01 through an installed ``aeat`` executable.

The driver uses only public CLI commands for product writes.  It keeps the
independent fixture/oracle in :mod:`scenario`, starts every command as a fresh
process, and emits a compact receipt rather than retaining command stdout that
contains synthetic financial details.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import subprocess
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Final

from .scenario import BRIEF_REVISION, SCENARIO_VERSION, build_scenario

_CLIENT_NIF: Final[str] = "A58818501"


class JourneyError(RuntimeError):
    """A public CLI command or acceptance assertion failed."""


@dataclass(frozen=True, slots=True)
class CommandEvidence:
    """Sanitized result of one fresh installed CLI process."""

    command: str
    returncode: int
    status: str
    notice_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ArtifactEvidence:
    """Digest and coordinate of one locally validated export."""

    modelo: str
    period: str
    path: str
    size: int
    sha256: str


@dataclass(frozen=True, slots=True)
class CliJourneyEvidence:
    """Compact machine-readable result of the CLI-only journey."""

    brief_revision: str
    scenario: str
    year: int
    authority_generation: str
    executable: str
    storage_root: str
    transactions: int
    invoices: int
    links: int
    reopened_transaction_count: int
    quarterly_casillas: dict[str, dict[str, str]]
    artifacts: tuple[ArtifactEvidence, ...]
    modelo_100: dict[str, object]
    commands: tuple[CommandEvidence, ...]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe representation."""
        return asdict(self)


class InstalledCli:
    """Fresh-process adapter for the public installed CLI."""

    def __init__(self, executable: Path, *, storage_root: Path, authority_root: Path, passphrase: str) -> None:
        """Bind the executable to one isolated store and authority tree."""
        self.executable = executable.resolve(strict=True)
        self.storage_root = storage_root.resolve()
        self.authority_root = authority_root.resolve(strict=True)
        self.passphrase = passphrase
        self.commands: list[CommandEvidence] = []

    def run(self, args: Sequence[str], *, authenticated: bool = True, allow_error: bool = False) -> dict[str, Any]:
        """Run one JSON command, recording only sanitized status evidence."""
        argv = [str(self.executable), "--format", "json"]
        input_text: str | None = None
        if authenticated:
            argv.append("--profile-secrets-stdin")
            input_text = json.dumps({"profile_passphrase": self.passphrase}, separators=(",", ":"))
        argv.extend(args)
        environment = {key: value for key, value in os.environ.items() if not key.startswith("CADRUMO_")}
        environment.update(
            {
                "CADRUMO_LOCAL_STORAGE_ROOT": str(self.storage_root),
                "CADRUMO_AUTHORITY_ROOT": str(self.authority_root),
                "CADRUMO_OUTPUT_LANGUAGE": "en",
                "PYTHONIOENCODING": "utf-8",
            }
        )
        completed = subprocess.run(  # noqa: S603 - executable is an explicit acceptance input
            argv,
            check=False,
            capture_output=True,
            cwd=self.storage_root,
            env=environment,
            input=input_text,
            text=True,
            timeout=180,
            encoding="utf-8",
        )
        try:
            document = _decode_cli_document(completed.stdout, completed.stderr)
        except json.JSONDecodeError as exc:
            if allow_error:
                self.commands.append(
                    CommandEvidence(
                        command=" ".join(args[:4]),
                        returncode=completed.returncode,
                        status="non_json_failure",
                        notice_codes=(),
                    )
                )
                return {
                    "status": "error",
                    "error": {
                        "code": "acceptance.installed_cli.non_json_failure",
                        "context": {
                            "returncode": completed.returncode,
                            "stderr_length": len(completed.stderr),
                            "stderr_sha256": hashlib.sha256(completed.stderr.encode("utf-8")).hexdigest(),
                        },
                    },
                }
            raise JourneyError(f"{args!r} did not emit one JSON document on stdout or stderr") from exc
        if not isinstance(document, dict):
            raise JourneyError(f"{args!r} emitted a non-object JSON document")
        notices = document.get("notices", [])
        codes = tuple(
            sorted(
                str(notice.get("code"))
                for notice in notices
                if isinstance(notice, dict) and notice.get("code") is not None
            )
        )
        self.commands.append(
            CommandEvidence(
                command=" ".join(args[:4]),
                returncode=completed.returncode,
                status=str(document.get("status")),
                notice_codes=codes,
            )
        )
        if completed.returncode != 0 and not allow_error:
            error = document.get("error", {})
            raise JourneyError(f"{args!r} failed: {error}")
        return document

    def create_profile(self, *, year: int) -> None:
        """Create and complete the synthetic natural-person profile."""
        payload = json.dumps(
            {"passphrase": self.passphrase, "passphrase_confirmation": self.passphrase},
            separators=(",", ":"),
        )
        args = _profile_create_args(year)
        argv = [str(self.executable), "--format", "json", *args]
        environment = {key: value for key, value in os.environ.items() if not key.startswith("CADRUMO_")}
        environment.update(
            {
                "CADRUMO_LOCAL_STORAGE_ROOT": str(self.storage_root),
                "CADRUMO_AUTHORITY_ROOT": str(self.authority_root),
                "CADRUMO_OUTPUT_LANGUAGE": "en",
                "PYTHONIOENCODING": "utf-8",
            }
        )
        completed = subprocess.run(  # noqa: S603 - executable is an explicit acceptance input
            argv,
            check=False,
            capture_output=True,
            cwd=self.storage_root,
            env=environment,
            input=payload,
            text=True,
            timeout=180,
            encoding="utf-8",
        )
        try:
            document = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise JourneyError(f"profile creation emitted invalid JSON: {completed.stdout!r}") from exc
        notices = document.get("notices", [])
        self.commands.append(
            CommandEvidence(
                command="config profile create",
                returncode=completed.returncode,
                status=str(document.get("status")),
                notice_codes=tuple(
                    sorted(str(item.get("code")) for item in notices if isinstance(item, dict) and item.get("code"))
                ),
            )
        )
        if completed.returncode != 0:
            raise JourneyError(f"profile creation failed: {document.get('error')}")
        self.run(("config", "profile", "complete-setup"))


def _profile_create_args(year: int) -> tuple[str, ...]:
    return (
        "config", "profile", "create", f"income-{year}", "--quiet", "--accept-defaults",
        "--entity-type", "natural_person", "--tax-id", "12345678Z", "--name", "Ada",
        "--surnames", "Synthetic", "--fiscal-residency", "resident_irpf",
        "--tax-residence-jurisdiction-scope", "common_regime", "--tax-residence-ccaa", "madrid",
        "--address-postcode", "28001", "--irpf-income-categories", "actividad_economica",
        "--activity", "software services", "--activity-start-date", f"{year}-01-01",
        "--taxation-type", "1", "--taxpayer-sex", "M", "--taxpayer-marital-status", "1",
        "--situacion-familiar", "soltero", "--taxpayer-birth-date", f"{year - 35}-06-15",
        "--irpf-estimation-regime", "directa_normal", "--irpf-special-regime", "general",
        "--iva-regime", "GENERAL", "--iva-m303-regime-composition", "general",
        "--no-iva-redeme-enrolled", "--no-iva-cash-accounting-regime-enrolled",
        "--no-iva-voluntary-sii-enrolled", "--no-iva-hydrocarbon-deposit-advance-payment-deduction-entitled",
        "--no-has-employees", "--no-pays-professionals-with-retencion", "--no-pays-rent-with-retencion",
        "--no-pays-capital-income-with-retencion", "--no-does-intracomunitario",
        "--no-third-party-transactions-above-347-threshold", "--no-bienes-extranjero-above-threshold",
        "--no-monedas-virtuales-extranjero-above-threshold", "--secrets-stdin",
    )


def _decode_cli_document(stdout: str, stderr: str) -> dict[str, Any]:
    """Decode the CLI envelope even when diagnostics precede it on stderr."""
    decoder = json.JSONDecoder()
    for stream in (stdout, stderr):
        text = stream.strip()
        if not text:
            continue
        try:
            document = json.loads(text)
        except json.JSONDecodeError:
            candidates: list[dict[str, Any]] = []
            for offset, character in enumerate(text):
                if character != "{":
                    continue
                try:
                    candidate, _end = decoder.raw_decode(text, offset)
                except json.JSONDecodeError:
                    continue
                if isinstance(candidate, dict) and "schema_version" in candidate and "status" in candidate:
                    candidates.append(candidate)
            if candidates:
                return candidates[-1]
        else:
            if isinstance(document, dict):
                return document
    raise json.JSONDecodeError("no CLI JSON envelope", stdout or stderr, 0)


def _result(document: dict[str, Any]) -> dict[str, Any]:
    result = document.get("result")
    if not isinstance(result, dict):
        raise JourneyError(f"command result is not an object: {document!r}")
    return result


def _money(value: Decimal) -> str:
    return f"{value:.2f}"


def _ingest(cli: InstalledCli, *, year: int) -> tuple[list[str], list[str]]:
    scenario = build_scenario(year)
    transaction_ids: list[str] = []
    invoice_ids: list[str] = []
    for income, expense in zip(scenario.income, scenario.expenses, strict=True):
        income_tx = _result(
            cli.run(
                (
                    "app", "ledger", "add", "--date", income.transaction_date.isoformat(),
                    "--amount", _money(income.net_receipt), "--direction", "INCOMING",
                    "--description", f"Synthetic income {income.period}", "--classification", "BUSINESS",
                    "--taxable-base", _money(income.taxable_base), "--iva-rate", str(income.iva_rate),
                    "--iva-amount", _money(income.iva), "--iva-category", "domestic_general",
                    "--irpf-category", "actividad_economica", "--source-jurisdiction", "ES",
                    "--idempotency-key", income.transaction_id,
                )
            )
        )
        income_invoice = _result(
            cli.run(
                (
                    "app", "ledger", "invoice", "add", "--kind", "issued",
                    "--counterparty-name", "Synthetic Client SL", "--counterparty-nif", _CLIENT_NIF,
                    "--invoice-number", income.invoice_id.upper(), "--invoice-date", income.invoice_date.isoformat(),
                    "--taxable-base", _money(income.taxable_base), "--iva-rate", "21", "--country-code", "ES",
                    "--retention-rate", str(income.withholding_rate), "--retention-amount", _money(income.withholding),
                    "--iva-category", "domestic_general",
                )
            )
        )
        income_tx_id = str(income_tx["transaction_id"])
        income_invoice_id = str(income_invoice["invoice_id"])
        cli.run(("app", "ledger", "link", income_tx_id, "--invoice-id", income_invoice_id))

        expense_tx = _result(
            cli.run(
                (
                    "app", "ledger", "add", "--date", expense.transaction_date.isoformat(),
                    "--amount", _money(expense.bank_payment), "--direction", "OUTGOING",
                    "--description", f"Synthetic expense {expense.period}", "--classification", "BUSINESS",
                    "--category-id", expense.category, "--taxable-base", _money(expense.taxable_base),
                    "--iva-rate", str(expense.iva_rate), "--iva-amount", _money(expense.iva),
                    "--iva-category", "domestic_general", "--source-jurisdiction", "ES",
                    "--idempotency-key", expense.transaction_id,
                )
            )
        )
        expense_invoice = _result(
            cli.run(
                (
                    "app", "ledger", "invoice", "add", "--kind", "received",
                    "--counterparty-name", "Synthetic Supplier SL", "--counterparty-nif", _CLIENT_NIF,
                    "--invoice-number", expense.invoice_id.upper(), "--invoice-date", expense.invoice_date.isoformat(),
                    "--taxable-base", _money(expense.taxable_base), "--iva-rate", "21", "--country-code", "ES",
                    "--iva-category", "domestic_general",
                )
            )
        )
        expense_tx_id = str(expense_tx["transaction_id"])
        expense_invoice_id = str(expense_invoice["invoice_id"])
        cli.run(("app", "ledger", "link", expense_tx_id, "--invoice-id", expense_invoice_id))
        transaction_ids.extend((income_tx_id, expense_tx_id))
        invoice_ids.extend((income_invoice_id, expense_invoice_id))
    return transaction_ids, invoice_ids


def _calculate_quarters(
    cli: InstalledCli, *, year: int, output_dir: Path
) -> tuple[dict[str, dict[str, str]], tuple[ArtifactEvidence, ...]]:
    scenario = build_scenario(year)
    observed: dict[str, dict[str, str]] = {}
    artifacts: list[ArtifactEvidence] = []
    for oracle in scenario.quarter_oracle:
        create = _result(
            cli.run(
                (
                    "app", "modelo", "work", "create", "--modelo", "130", "--year", str(year),
                    "--period", oracle.period, "--revision", "2019-y-siguientes", "--by", "income-acceptance",
                )
            )
        )
        work_id = str(create["work_unit_id"])
        calculation = _result(
            cli.run(("app", "modelo", "work", "calculate", work_id, "--by", "income-acceptance"))
        )
        values = calculation.get("casilla_values")
        if not isinstance(values, dict):
            raise JourneyError(f"Modelo 130 {oracle.period} returned no casilla map")
        expected = {
            "01": _money(oracle.cumulative_income), "02": _money(oracle.cumulative_expenses),
            "03": _money(oracle.cumulative_net), "04": _money(oracle.twenty_percent),
            "05": _money(oracle.prior_positive_results), "06": _money(oracle.cumulative_withholding),
            "07": _money(oracle.partial_result), "13": _money(oracle.low_income_reduction),
            "19": _money(oracle.payment),
        }
        actual = {casilla: _money(Decimal(str(values.get(casilla)))) for casilla in expected}
        if actual != expected:
            raise JourneyError(f"Modelo 130 {oracle.period} oracle mismatch: expected {expected}, got {actual}")
        observed[oracle.period] = actual
        revision_id = str(calculation["calculation_revision_id"])
        verification = _result(
            cli.run(("app", "modelo", "work", "verify", revision_id, "--by", "income-acceptance"))
        )
        if verification.get("granted_verificado_completo") is not True:
            raise JourneyError(f"Modelo 130 {oracle.period} did not verify complete")
        cli.run(
            (
                "app", "modelo", "work", "file", revision_id, "--by", "income-acceptance",
                "--notes", "Synthetic local filing only; not sent to AEAT",
            )
        )
        target = output_dir / f"modelo-130-{year}-{oracle.period}.boe"
        cli.run(("app", "modelo", "export", work_id, "--output", str(target), "--by", "income-acceptance"))
        payload = target.read_bytes()
        artifacts.append(
            ArtifactEvidence(
                modelo="130", period=oracle.period, path=str(target), size=len(payload),
                sha256=hashlib.sha256(payload).hexdigest(),
            )
        )
    return observed, tuple(artifacts)


def _calculate_m100(cli: InstalledCli, *, year: int, output_dir: Path) -> dict[str, object]:
    create = _result(
        cli.run(
            (
                "app", "modelo", "work", "create", "--modelo", "100", "--year", str(year),
                "--period", "0A", "--revision", str(year), "--by", "income-acceptance",
            )
        )
    )
    work_id = str(create["work_unit_id"])
    calculated = cli.run(
        (
            "app", "modelo", "work", "calculate", work_id,
            "--binding", "renta-modelo-100-estimacion-directa-es-normal=1",
            "--binding", "renta-certificado-trabajo-retenciones=0",
            "--by", "income-acceptance",
        ),
        allow_error=True,
    )
    if calculated.get("status") == "error":
        error = calculated.get("error", {})
        return {
            "calculation": "blocked",
            "diagnostic_code": error.get("code") if isinstance(error, dict) else None,
            "message": error.get("message") if isinstance(error, dict) else None,
        }
    calculation = _result(calculated)
    values = calculation.get("casilla_values")
    if not isinstance(values, dict):
        raise JourneyError("Modelo 100 returned no casilla map")
    annual = build_scenario(year).annual_oracle
    expected = {
        "0171": _money(annual.activity_income),
        "0218": _money(annual.deductible_expenses),
        "0220": _money(annual.deductible_expenses),
        "0224": _money(annual.activity_net_income),
        "0604": _money(annual.m130_payments),
    }
    actual = {casilla: _money(Decimal(str(values.get(casilla)))) for casilla in expected}
    if actual != expected:
        raise JourneyError(f"Modelo 100 annual oracle mismatch: expected {expected}, got {actual}")
    revision_id = str(calculation["calculation_revision_id"])
    verification = cli.run(
        ("app", "modelo", "work", "verify", revision_id, "--by", "income-acceptance"),
        allow_error=True,
    )
    if verification.get("status") == "error":
        error = verification.get("error", {})
        return {
            "calculation": "proven", "casillas": actual, "verification": "blocked",
            "diagnostic_code": error.get("code") if isinstance(error, dict) else None,
        }
    target = output_dir / f"modelo-100-{year}-0A.xml"
    exported = cli.run(
        ("app", "modelo", "export", work_id, "--output", str(target), "--by", "income-acceptance"),
        allow_error=True,
    )
    if exported.get("status") == "error":
        error = exported.get("error", {})
        context = error.get("context", {}) if isinstance(error, dict) else {}
        return {
            "calculation": "proven", "casillas": actual, "verification": "proven", "export": "blocked",
            "diagnostic_code": error.get("code") if isinstance(error, dict) else None,
            "cause": context.get("cause") if isinstance(context, dict) else None,
            "artifact_exists": target.exists(),
        }
    return {
        "calculation": "proven", "casillas": actual, "verification": "proven",
        "export": "proven", "artifact_exists": target.exists(),
    }


def run_cli_journey(
    *, executable: Path, authority_root: Path, storage_root: Path, output_dir: Path, year: int
) -> CliJourneyEvidence:
    """Execute the installed CLI-only path in a fresh secure store."""
    if storage_root.exists() and any(storage_root.iterdir()):
        raise JourneyError(f"storage root must be fresh and empty: {storage_root}")
    storage_root.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    descriptor = json.loads((authority_root / "authority.current.json").read_text(encoding="utf-8"))
    generation = str(descriptor["logical_generation"])
    cli = InstalledCli(
        executable, storage_root=storage_root, authority_root=authority_root, passphrase=secrets.token_urlsafe(32)
    )
    cli.create_profile(year=year)
    transaction_ids, invoice_ids = _ingest(cli, year=year)
    # A new child process reads the store after all ingestion; no in-memory
    # object crosses this boundary.
    listed = _result(cli.run(("app", "ledger", "list")))
    rows = listed.get("rows")
    if not isinstance(rows, list):
        raise JourneyError("ledger list returned no transaction collection")
    if {str(row.get("transaction_id")) for row in rows if isinstance(row, dict)} != set(transaction_ids):
        raise JourneyError("fresh-process ledger read did not reproduce the ingested transaction identities")
    quarterly, artifacts = _calculate_quarters(cli, year=year, output_dir=output_dir)
    modelo_100 = _calculate_m100(cli, year=year, output_dir=output_dir)
    return CliJourneyEvidence(
        brief_revision=BRIEF_REVISION,
        scenario=f"{SCENARIO_VERSION}:{year}:cli",
        year=year,
        authority_generation=generation,
        executable=str(cli.executable),
        storage_root=str(cli.storage_root),
        transactions=len(transaction_ids),
        invoices=len(invoice_ids),
        links=len(invoice_ids),
        reopened_transaction_count=len(rows),
        quarterly_casillas=quarterly,
        artifacts=artifacts,
        modelo_100=modelo_100,
        commands=tuple(cli.commands),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", required=True, type=Path)
    parser.add_argument("--authority-root", required=True, type=Path)
    parser.add_argument("--storage-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--year", required=True, type=int)
    parser.add_argument("--receipt", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Write one CLI evidence receipt and mirror it to stdout."""
    args = _parser().parse_args(argv)
    evidence = run_cli_journey(
        executable=args.cli,
        authority_root=args.authority_root,
        storage_root=args.storage_root,
        output_dir=args.output_dir,
        year=args.year,
    )
    rendered = json.dumps(evidence.to_dict(), indent=2, sort_keys=True)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(f"{rendered}\n", encoding="utf-8", newline="\n")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
