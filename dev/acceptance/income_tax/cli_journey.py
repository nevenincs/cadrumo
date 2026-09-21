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

from .scenario import (
    BRIEF_REVISION,
    SCENARIO_VERSION,
    AcceptanceOutcome,
    AnnualOracle,
    ExpenseInvoice,
    IssuedInvoice,
    QuarterlyOracle,
    build_boundary_control_scenario,
    build_retention_mutation_oracle,
    build_scenario,
)

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


@dataclass(frozen=True, slots=True)
class LinkedLedgerPair:
    """Persisted public identifiers for one invoice and its linked transaction."""

    fixture_invoice_id: str
    transaction_id: str
    invoice_id: str


@dataclass(frozen=True, slots=True)
class IngestedLedgerEvidence:
    """The stable identities produced by an isolated CLI ingestion."""

    transaction_ids: tuple[str, ...]
    invoice_ids: tuple[str, ...]
    issued_pairs: tuple[LinkedLedgerPair, ...]


@dataclass(frozen=True, slots=True)
class AcceptanceControlEvidence:
    """One A2/A4/A5 result with calculation and export status kept separate."""

    acceptance_id: str
    outcome: AcceptanceOutcome
    calculation: AcceptanceOutcome
    verification: AcceptanceOutcome
    export_readiness: AcceptanceOutcome
    diagnostic_code: str | None
    observations: dict[str, str]


@dataclass(frozen=True, slots=True)
class CliControlsEvidence:
    """Compact receipt for the isolated installed-CLI control cases."""

    brief_revision: str
    scenario: str
    year: int
    authority_generation: str
    executable: str
    controls_root: str
    cases: tuple[AcceptanceControlEvidence, ...]
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


def _ingest(
    cli: InstalledCli,
    *,
    year: int,
    income: tuple[IssuedInvoice, ...] | None = None,
    expenses: tuple[ExpenseInvoice, ...] | None = None,
) -> IngestedLedgerEvidence:
    """Persist matched ledger facts through public CLI commands only."""
    scenario = build_scenario(year)
    income_items = scenario.income if income is None else income
    expense_items = scenario.expenses if expenses is None else expenses
    transaction_ids: list[str] = []
    invoice_ids: list[str] = []
    issued_pairs: list[LinkedLedgerPair] = []
    for income in income_items:
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
        transaction_ids.append(income_tx_id)
        invoice_ids.append(income_invoice_id)
        issued_pairs.append(
            LinkedLedgerPair(
                fixture_invoice_id=income.invoice_id,
                transaction_id=income_tx_id,
                invoice_id=income_invoice_id,
            )
        )

    for expense in expense_items:
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
        transaction_ids.append(expense_tx_id)
        invoice_ids.append(expense_invoice_id)
    return IngestedLedgerEvidence(
        transaction_ids=tuple(transaction_ids),
        invoice_ids=tuple(invoice_ids),
        issued_pairs=tuple(issued_pairs),
    )


def _m130_expected(oracle: QuarterlyOracle) -> dict[str, str]:
    return {
        "01": _money(oracle.cumulative_income),
        "02": _money(oracle.cumulative_expenses),
        "03": _money(oracle.cumulative_net),
        "04": _money(oracle.twenty_percent),
        "05": _money(oracle.prior_positive_results),
        "06": _money(oracle.cumulative_withholding),
        "07": _money(oracle.partial_result),
        "13": _money(oracle.low_income_reduction),
        "19": _money(oracle.payment),
    }


def _create_m130_work(cli: InstalledCli, *, year: int, period: str) -> str:
    create = _result(
        cli.run(
            (
                "app",
                "modelo",
                "work",
                "create",
                "--modelo",
                "130",
                "--year",
                str(year),
                "--period",
                period,
                "--revision",
                "2019-y-siguientes",
                "--by",
                "income-acceptance",
            )
        )
    )
    return str(create["work_unit_id"])


def _calculate_m130_work(
    cli: InstalledCli, *, work_id: str, oracle: QuarterlyOracle
) -> tuple[dict[str, str], str]:
    calculation = _result(cli.run(("app", "modelo", "work", "calculate", work_id, "--by", "income-acceptance")))
    values = calculation.get("casilla_values")
    if not isinstance(values, dict):
        raise JourneyError(f"Modelo 130 {oracle.period} returned no casilla map")
    expected = _m130_expected(oracle)
    actual = {casilla: _money(Decimal(str(values.get(casilla)))) for casilla in expected}
    if actual != expected:
        raise JourneyError(f"Modelo 130 {oracle.period} oracle mismatch")
    return actual, str(calculation["calculation_revision_id"])


def _verify_and_file_m130(cli: InstalledCli, *, revision_id: str, period: str) -> None:
    verification = _result(cli.run(("app", "modelo", "work", "verify", revision_id, "--by", "income-acceptance")))
    if verification.get("granted_verificado_completo") is not True:
        raise JourneyError(f"Modelo 130 {period} did not verify complete")
    cli.run(
        (
            "app",
            "modelo",
            "work",
            "file",
            revision_id,
            "--by",
            "income-acceptance",
            "--notes",
            "Synthetic local pending filing only; not sent to AEAT",
        )
    )


def _calculate_quarters(
    cli: InstalledCli, *, year: int, output_dir: Path
) -> tuple[dict[str, dict[str, str]], tuple[ArtifactEvidence, ...]]:
    scenario = build_scenario(year)
    observed: dict[str, dict[str, str]] = {}
    artifacts: list[ArtifactEvidence] = []
    for oracle in scenario.quarter_oracle:
        work_id = _create_m130_work(cli, year=year, period=oracle.period)
        actual, revision_id = _calculate_m130_work(cli, work_id=work_id, oracle=oracle)
        observed[oracle.period] = actual
        _verify_and_file_m130(cli, revision_id=revision_id, period=oracle.period)
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


def _calculate_m100(
    cli: InstalledCli,
    *,
    year: int,
    output_dir: Path,
    annual_oracle: AnnualOracle | None = None,
    attempt_export: bool = True,
) -> dict[str, object]:
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
            "--casilla", "0001=declarante",
            "--casilla", "0165=declarante",
            "--casilla", "0166=A05",
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
            "verification": "not_exercised",
            "export_execution": "not_exercised",
            "export_readiness": "not_exercised",
            "diagnostic_code": error.get("code") if isinstance(error, dict) else None,
        }
    calculation = _result(calculated)
    values = calculation.get("casilla_values")
    if not isinstance(values, dict):
        raise JourneyError("Modelo 100 returned no casilla map")
    annual = annual_oracle or build_scenario(year).annual_oracle
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
            "calculation": "proven",
            "casillas": actual,
            "verification": "blocked",
            "export_execution": "not_exercised",
            "export_readiness": "not_exercised",
            "diagnostic_code": error.get("code") if isinstance(error, dict) else None,
        }
    if not attempt_export:
        return {
            "calculation": "proven",
            "casillas": actual,
            "verification": "proven",
            "export_execution": "not_exercised",
            "export_readiness": "not_exercised",
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
            "calculation": "proven",
            "casillas": actual,
            "verification": "proven",
            "export_execution": "blocked",
            "export_readiness": "blocked",
            "diagnostic_code": error.get("code") if isinstance(error, dict) else None,
            "cause": context.get("cause") if isinstance(context, dict) else None,
            "artifact_exists": target.exists(),
        }
    return {
        "calculation": "proven",
        "casillas": actual,
        "verification": "proven",
        "export_execution": "proven",
        # A successful write is not an independent official-structure check.
        "export_readiness": "not_exercised",
        "artifact_exists": target.exists(),
    }


def _fresh_directory(path: Path, *, label: str) -> Path:
    """Create one owned empty run directory without touching any other state."""
    if path.exists() and any(path.iterdir()):
        raise JourneyError(f"{label} must be fresh and empty")
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def _authority_generation(authority_root: Path) -> str:
    descriptor = json.loads((authority_root / "authority.current.json").read_text(encoding="utf-8"))
    generation = descriptor.get("logical_generation")
    if not isinstance(generation, str):
        raise JourneyError("authority descriptor has no logical generation")
    return generation


def _control_cli(*, executable: Path, authority_root: Path, storage_root: Path, year: int) -> InstalledCli:
    _fresh_directory(storage_root, label="control storage root")
    cli = InstalledCli(
        executable,
        storage_root=storage_root,
        authority_root=authority_root,
        passphrase=secrets.token_urlsafe(32),
    )
    cli.create_profile(year=year)
    return cli


def _assert_reopened_ledger(cli: InstalledCli, ingested: IngestedLedgerEvidence) -> int:
    """Prove the next process can read every persisted transaction identity."""
    listed = _result(cli.run(("app", "ledger", "list")))
    rows = listed.get("rows")
    if not isinstance(rows, list):
        raise JourneyError("ledger list returned no transaction collection")
    actual_ids = {str(row.get("transaction_id")) for row in rows if isinstance(row, dict)}
    if actual_ids != set(ingested.transaction_ids):
        raise JourneyError("fresh-process ledger read did not reproduce ingested transaction identities")
    return len(rows)


def _m100_control_outcome(result: dict[str, object]) -> tuple[AcceptanceOutcome, AcceptanceOutcome, str | None]:
    calculation = AcceptanceOutcome(str(result.get("calculation", AcceptanceOutcome.FAILED.value)))
    verification = AcceptanceOutcome(str(result.get("verification", AcceptanceOutcome.NOT_EXERCISED.value)))
    diagnostic_code = result.get("diagnostic_code")
    return calculation, verification, diagnostic_code if isinstance(diagnostic_code, str) else None


def _a2_retention_mutation_case(
    *, executable: Path, authority_root: Path, storage_root: Path, output_dir: Path, year: int
) -> tuple[AcceptanceControlEvidence, tuple[CommandEvidence, ...]]:
    """Correct a persisted Q4 retention pair and prove the downstream deltas."""
    cli = _control_cli(executable=executable, authority_root=authority_root, storage_root=storage_root, year=year)
    scenario = build_scenario(year)
    mutation = build_retention_mutation_oracle(year)
    ingested = _ingest(cli, year=year)
    _assert_reopened_ledger(cli, ingested)

    for oracle in scenario.quarter_oracle[:3]:
        work_id = _create_m130_work(cli, year=year, period=oracle.period)
        _actual, revision_id = _calculate_m130_work(cli, work_id=work_id, oracle=oracle)
        _verify_and_file_m130(cli, revision_id=revision_id, period=oracle.period)

    q4_work_id = _create_m130_work(cli, year=year, period=mutation.baseline_quarter.period)
    before, _before_revision = _calculate_m130_work(
        cli, work_id=q4_work_id, oracle=mutation.baseline_quarter
    )
    pair = next(
        (item for item in ingested.issued_pairs if item.fixture_invoice_id == mutation.target_invoice.invoice_id),
        None,
    )
    if pair is None:
        raise JourneyError("A2 target issued invoice was not persisted")
    cli.run(
        (
            "app",
            "ledger",
            "invoice",
            "update",
            pair.invoice_id,
            "--retention-rate",
            str(mutation.corrected_invoice.withholding_rate),
            "--retention-amount",
            _money(mutation.corrected_invoice.withholding),
        )
    )
    cli.run(
        (
            "app",
            "ledger",
            "update",
            pair.transaction_id,
            "--amount",
            _money(mutation.corrected_invoice.net_receipt),
        )
    )
    after, corrected_revision = _calculate_m130_work(cli, work_id=q4_work_id, oracle=mutation.corrected_quarter)
    _verify_and_file_m130(cli, revision_id=corrected_revision, period=mutation.corrected_quarter.period)
    annual = _calculate_m100(
        cli,
        year=year,
        output_dir=output_dir,
        annual_oracle=mutation.corrected_annual,
        attempt_export=False,
    )
    calculation, verification, diagnostic_code = _m100_control_outcome(annual)
    outcome = AcceptanceOutcome.PROVEN
    if calculation is not AcceptanceOutcome.PROVEN or verification is not AcceptanceOutcome.PROVEN:
        outcome = AcceptanceOutcome.FAILED
    observations = {
        "baseline_q4_withholding": before["06"],
        "corrected_q4_withholding": after["06"],
        "baseline_q4_payment": before["19"],
        "corrected_q4_payment": after["19"],
        "corrected_annual_withholding_oracle": _money(mutation.corrected_annual.activity_withholding),
        "corrected_annual_m130_payments": str(annual.get("casillas", {}).get("0604", "")),
    }
    return (
        AcceptanceControlEvidence(
            acceptance_id="A2",
            outcome=outcome,
            calculation=calculation,
            verification=verification,
            export_readiness=AcceptanceOutcome.NOT_EXERCISED,
            diagnostic_code=diagnostic_code,
            observations=observations,
        ),
        tuple(cli.commands),
    )


def _a4_boundary_case(
    *, executable: Path, authority_root: Path, storage_root: Path, output_dir: Path, year: int
) -> tuple[AcceptanceControlEvidence, tuple[CommandEvidence, ...]]:
    """Exercise the year and quarter controls against their own persisted store."""
    cli = _control_cli(executable=executable, authority_root=authority_root, storage_root=storage_root, year=year)
    controls = build_boundary_control_scenario(year)
    ingested = _ingest(
        cli,
        year=year,
        income=controls.ingested_income,
        expenses=controls.ingested_expenses,
    )
    _assert_reopened_ledger(cli, ingested)
    observed: dict[str, dict[str, str]] = {}
    for oracle in controls.quarter_oracle:
        work_id = _create_m130_work(cli, year=year, period=oracle.period)
        values, revision_id = _calculate_m130_work(cli, work_id=work_id, oracle=oracle)
        _verify_and_file_m130(cli, revision_id=revision_id, period=oracle.period)
        observed[oracle.period] = values
    annual = _calculate_m100(
        cli,
        year=year,
        output_dir=output_dir,
        annual_oracle=controls.annual_oracle,
        attempt_export=False,
    )
    calculation, verification, diagnostic_code = _m100_control_outcome(annual)
    outcome = AcceptanceOutcome.PROVEN
    if calculation is not AcceptanceOutcome.PROVEN or verification is not AcceptanceOutcome.PROVEN:
        outcome = AcceptanceOutcome.FAILED
    return (
        AcceptanceControlEvidence(
            acceptance_id="A4",
            outcome=outcome,
            calculation=calculation,
            verification=verification,
            export_readiness=AcceptanceOutcome.NOT_EXERCISED,
            diagnostic_code=diagnostic_code,
            observations={
                "q1_income": observed["1T"]["01"],
                "q2_income": observed["2T"]["01"],
                "q2_expenses": observed["2T"]["02"],
                "annual_income": str(annual.get("casillas", {}).get("0171", "")),
                "annual_expenses": str(annual.get("casillas", {}).get("0218", "")),
                "prior_year_excluded_invoice_count": str(len(controls.excluded_income_ids)),
            },
        ),
        tuple(cli.commands),
    )


def _error_code(document: dict[str, Any]) -> str | None:
    error = document.get("error")
    if not isinstance(error, dict):
        return None
    code = error.get("code")
    return code if isinstance(code, str) else None


def _a5_history_case(
    *, executable: Path, authority_root: Path, storage_root: Path, year: int
) -> tuple[AcceptanceControlEvidence, tuple[CommandEvidence, ...]]:
    """Keep first-period, missing-history, and recorded-zero states distinct."""
    first_root = storage_root / "first-period-and-recorded-zero"
    missing_root = storage_root / "missing-required-history"
    first_cli = _control_cli(executable=executable, authority_root=authority_root, storage_root=first_root, year=year)
    q1_work_id = _create_m130_work(first_cli, year=year, period="1T")
    q1_zero = QuarterlyOracle(
        period="1T",
        cumulative_income=Decimal(),
        cumulative_expenses=Decimal(),
        cumulative_net=Decimal(),
        twenty_percent=Decimal(),
        cumulative_withholding=Decimal(),
        prior_positive_results=Decimal(),
        partial_result=Decimal(),
        low_income_reduction=Decimal("100.00"),
        payment=Decimal("-100.00"),
    )
    q1_values, q1_revision_id = _calculate_m130_work(first_cli, work_id=q1_work_id, oracle=q1_zero)
    _verify_and_file_m130(first_cli, revision_id=q1_revision_id, period="1T")
    q2_work_id = _create_m130_work(first_cli, year=year, period="2T")
    recorded_zero = first_cli.run(
        ("app", "modelo", "work", "calculate", q2_work_id, "--by", "income-acceptance"), allow_error=True
    )

    missing_cli = _control_cli(
        executable=executable,
        authority_root=authority_root,
        storage_root=missing_root,
        year=year,
    )
    missing_q2_work_id = _create_m130_work(missing_cli, year=year, period="2T")
    missing = missing_cli.run(
        ("app", "modelo", "work", "calculate", missing_q2_work_id, "--by", "income-acceptance"), allow_error=True
    )
    commands = (*first_cli.commands, *missing_cli.commands)
    missing_code = _error_code(missing)
    if missing.get("status") != "error":
        return (
            AcceptanceControlEvidence(
                acceptance_id="A5",
                outcome=AcceptanceOutcome.FAILED,
                calculation=AcceptanceOutcome.FAILED,
                verification=AcceptanceOutcome.NOT_EXERCISED,
                export_readiness=AcceptanceOutcome.NOT_EXERCISED,
                diagnostic_code="acceptance.a5.missing_history_not_refused",
                observations={"first_period_history": "not_applicable", "missing_history": "silently_accepted"},
            ),
            commands,
        )
    if recorded_zero.get("status") == "error":
        return (
            AcceptanceControlEvidence(
                acceptance_id="A5",
                outcome=AcceptanceOutcome.BLOCKED,
                calculation=AcceptanceOutcome.PROVEN,
                verification=AcceptanceOutcome.PROVEN,
                export_readiness=AcceptanceOutcome.NOT_EXERCISED,
                diagnostic_code=_error_code(recorded_zero),
                observations={
                    "first_period_history": "not_applicable",
                    "first_period_payment": q1_values["19"],
                    "missing_history": "refused",
                    "missing_history_diagnostic": missing_code or "",
                    "recorded_zero_capability": "public_cli_local_zero_history_unavailable",
                },
            ),
            commands,
        )
    recorded_result = _result(recorded_zero)
    values = recorded_result.get("casilla_values")
    if not isinstance(values, dict) or _money(Decimal(str(values.get("05")))) != "0.00":
        return (
            AcceptanceControlEvidence(
                acceptance_id="A5",
                outcome=AcceptanceOutcome.FAILED,
                calculation=AcceptanceOutcome.FAILED,
                verification=AcceptanceOutcome.NOT_EXERCISED,
                export_readiness=AcceptanceOutcome.NOT_EXERCISED,
                diagnostic_code="acceptance.a5.recorded_zero_not_preserved",
                observations={"first_period_history": "not_applicable", "missing_history": "refused"},
            ),
            commands,
        )
    return (
        AcceptanceControlEvidence(
            acceptance_id="A5",
            outcome=AcceptanceOutcome.PROVEN,
            calculation=AcceptanceOutcome.PROVEN,
            verification=AcceptanceOutcome.PROVEN,
            export_readiness=AcceptanceOutcome.NOT_EXERCISED,
            diagnostic_code=missing_code,
            observations={
                "first_period_history": "not_applicable",
                "first_period_payment": q1_values["19"],
                "missing_history": "refused",
                "recorded_zero_history": "recorded_zero",
                "recorded_zero_prior_result": _money(Decimal(str(values.get("05")))),
            },
        ),
        commands,
    )


def _failed_control_case(acceptance_id: str, error: Exception) -> AcceptanceControlEvidence:
    """Persist a sanitized failure rather than presenting a partial control as green."""
    return AcceptanceControlEvidence(
        acceptance_id=acceptance_id,
        outcome=AcceptanceOutcome.FAILED,
        calculation=AcceptanceOutcome.FAILED,
        verification=AcceptanceOutcome.NOT_EXERCISED,
        export_readiness=AcceptanceOutcome.NOT_EXERCISED,
        diagnostic_code=f"acceptance.{acceptance_id.lower()}.journey_error",
        observations={"failure_type": type(error).__name__},
    )


def run_cli_controls(
    *, executable: Path, authority_root: Path, controls_root: Path, output_dir: Path, year: int
) -> CliControlsEvidence:
    """Run the A2/A4/A5 controls in separately owned installed-CLI stores."""
    controls_root = _fresh_directory(controls_root, label="controls root")
    output_dir = _fresh_directory(output_dir, label="controls output directory")
    generation = _authority_generation(authority_root)
    cases: list[AcceptanceControlEvidence] = []
    commands: list[CommandEvidence] = []
    control_calls = (
        ("A2", _a2_retention_mutation_case, controls_root / "a2", output_dir / "a2"),
        ("A4", _a4_boundary_case, controls_root / "a4", output_dir / "a4"),
    )
    for acceptance_id, runner, storage_root, case_output_dir in control_calls:
        try:
            evidence, case_commands = runner(
                executable=executable,
                authority_root=authority_root,
                storage_root=storage_root,
                output_dir=_fresh_directory(case_output_dir, label=f"{acceptance_id} output directory"),
                year=year,
            )
        except JourneyError as exc:
            cases.append(_failed_control_case(acceptance_id, exc))
        else:
            cases.append(evidence)
            commands.extend(case_commands)
    try:
        history, history_commands = _a5_history_case(
            executable=executable,
            authority_root=authority_root,
            storage_root=_fresh_directory(controls_root / "a5", label="A5 controls root"),
            year=year,
        )
    except JourneyError as exc:
        cases.append(_failed_control_case("A5", exc))
    else:
        cases.append(history)
        commands.extend(history_commands)
    return CliControlsEvidence(
        brief_revision=BRIEF_REVISION,
        scenario=f"{SCENARIO_VERSION}:{year}:cli-controls",
        year=year,
        authority_generation=generation,
        executable=str(executable.resolve(strict=True)),
        controls_root=str(controls_root),
        cases=tuple(cases),
        commands=tuple(commands),
    )


def run_cli_journey(
    *, executable: Path, authority_root: Path, storage_root: Path, output_dir: Path, year: int
) -> CliJourneyEvidence:
    """Execute the installed CLI-only path in a fresh secure store."""
    if storage_root.exists() and any(storage_root.iterdir()):
        raise JourneyError(f"storage root must be fresh and empty: {storage_root}")
    storage_root.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    generation = _authority_generation(authority_root)
    cli = InstalledCli(
        executable, storage_root=storage_root, authority_root=authority_root, passphrase=secrets.token_urlsafe(32)
    )
    cli.create_profile(year=year)
    ingested = _ingest(cli, year=year)
    # A new child process reads the store after all ingestion; no in-memory
    # object crosses this boundary.
    listed = _result(cli.run(("app", "ledger", "list")))
    rows = listed.get("rows")
    if not isinstance(rows, list):
        raise JourneyError("ledger list returned no transaction collection")
    if {str(row.get("transaction_id")) for row in rows if isinstance(row, dict)} != set(ingested.transaction_ids):
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
        transactions=len(ingested.transaction_ids),
        invoices=len(ingested.invoice_ids),
        links=len(ingested.invoice_ids),
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
    parser.add_argument(
        "--mode",
        choices=("journey", "controls"),
        default="journey",
        help="Run the baseline journey or the isolated A2/A4/A5 controls.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Write one CLI evidence receipt and mirror it to stdout."""
    args = _parser().parse_args(argv)
    if args.mode == "controls":
        evidence = run_cli_controls(
            executable=args.cli,
            authority_root=args.authority_root,
            controls_root=args.storage_root,
            output_dir=args.output_dir,
            year=args.year,
        )
    else:
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
    if isinstance(evidence, CliControlsEvidence) and any(
        case.outcome is not AcceptanceOutcome.PROVEN for case in evidence.cases
    ):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
