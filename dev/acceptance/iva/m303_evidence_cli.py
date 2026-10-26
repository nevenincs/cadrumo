"""Installed public CLI capture, attestation and revision evidence observations."""

from __future__ import annotations

import argparse
import json
import secrets
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, cast

from dev.acceptance.installed_cli import InstalledCli, InstalledCliError

from .filing_year import IvaJourneyYear
from .m303_evidence_contracts import (
    _DEVELOPMENT_MOCK_HEADER,
    _LAST_PERIOD_DAYS,
    _PERIOD,
    _PRIOR_PERIOD,
    CommandOutcome,
    IvaInstalledM303Error,
)
from .m303_evidence_projection import _mapping, _text, resultado_matches_oracle

if TYPE_CHECKING:
    pass


class _Cli:
    """Installed CLI calls that retain only public outcomes."""

    def __init__(self, cli: InstalledCli) -> None:
        self.cli = cli
        self.outcomes: list[CommandOutcome] = []

    def run(self, args: tuple[str, ...], *, expect_refusal: bool = False) -> Mapping[str, object]:
        document = self.cli.run(args, allow_error=True)
        evidence = self.cli.commands[-1]
        error = document.get("error")
        code = cast("Mapping[str, object]", error).get("code") if isinstance(error, Mapping) else None
        self.outcomes.append(
            CommandOutcome(
                command=evidence.command,
                returncode=evidence.returncode,
                status=evidence.status,
                error_code=code if isinstance(code, str) else None,
            )
        )
        if expect_refusal:
            if evidence.returncode == 0:
                raise IvaInstalledM303Error(f"installed CLI accepted a request it must refuse: {evidence.command}")
            return document
        if evidence.returncode != 0:
            raise IvaInstalledM303Error(f"installed CLI refused {evidence.command}: {code}")
        return _mapping(document.get("result"), label=evidence.command)


def _cli_capture_and_create_work(
    cli: _Cli, *, artifact: Path, year: int, period: str, wallet_period: str, dates: tuple[str, str]
) -> str:
    """Capture one ordinary ``year`` sale and purchase inside ``period`` and create its M303 work unit."""
    sale_date, purchase_date = dates
    evidence_id = _text(
        cli.run(("app", "ledger", "evidence", "add", str(artifact), "--supplier", "Synthetic supplier SL")).get(
            "evidence_id"
        ),
        label="evidence add",
    )
    sale = _text(
        cli.run(
            (
                *("app", "ledger", "add", "--date", sale_date, "--amount", "121.00", "--direction", "INCOMING"),
                *("--description", "Synthetic ordinary IVA sale", "--classification", "BUSINESS"),
                *("--taxable-base", "100.00", "--iva-rate", "0.21", "--iva-amount", "21.00"),
                *("--iva-category", "domestic_general", "--source-jurisdiction", "ES"),
                *("--idempotency-key", f"iva-m303-evidence-sale-{year}-{period.lower()}"),
            )
        ).get("transaction_id"),
        label="sale add",
    )
    sale_invoice = _text(
        cli.run(
            _invoice_args(kind="issued", number="IVA-M303-ISS", subtotal="100.00", iva_amount="21.00", date=sale_date)
        ).get("invoice_id"),
        label="sale invoice add",
    )
    cli.run(("app", "ledger", "link", sale, "--invoice-id", sale_invoice))
    purchase = _text(
        cli.run(
            (
                *("app", "ledger", "add", "--date", purchase_date, "--amount", "60.50", "--direction", "OUTGOING"),
                *("--description", "Synthetic ordinary IVA purchase", "--classification", "BUSINESS"),
                *("--category-id", "material_oficina", "--taxable-base", "50.00", "--iva-rate", "0.21"),
                *("--iva-amount", "10.50", "--iva-category", "domestic_general"),
                *("--purchase-invoice-evidence-id", evidence_id, "--source-jurisdiction", "ES"),
                *("--idempotency-key", f"iva-m303-evidence-purchase-{year}-{period.lower()}"),
            )
        ).get("transaction_id"),
        label="purchase add",
    )
    cli.run(
        (
            *("app", "ledger", "classify", purchase, "--classification", "BUSINESS"),
            *("--deduction-kind", "domestic_current", "--counterparty-country", "ES", "--reaffirm"),
        )
    )
    purchase_invoice = _text(
        cli.run(
            _invoice_args(kind="received", number="IVA-M303-REC", subtotal="50.00", iva_amount="10.50", date=sale_date)
        ).get("invoice_id"),
        label="purchase invoice add",
    )
    cli.run(("app", "ledger", "link", purchase, "--invoice-id", purchase_invoice))
    cli.run(
        (
            *("app", "modelo", "iva-wallet", "seed", "--filing-year", str(year), "--period", wallet_period),
            *("--amount", "0.00", "--confirm"),
        )
    )
    created = cli.run(("app", "modelo", "work", "create", "--modelo", "303", "--year", str(year), "--period", period))
    return _text(created.get("work_unit_id"), label="work create")


def _invoice_args(*, kind: str, number: str, subtotal: str, iva_amount: str, date: str) -> tuple[str, ...]:
    line = json.dumps(
        {
            "description": f"Synthetic {kind} line",
            "quantity": "1",
            "unit_price": subtotal,
            "subtotal": subtotal,
            "iva_rate": "RATE_21",
            "iva_amount": iva_amount,
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    return (
        *("app", "ledger", "invoice", "add", "--kind", kind, "--counterparty-name", "Synthetic party SL"),
        *("--counterparty-nif", "A58818501", "--invoice-number", number, "--invoice-date", date),
        *("--country-code", "ES", "--iva-category", "domestic_general", "--line", line),
    )


def _attest(cli: _Cli, *, year: int, period: str, observed_at: str) -> tuple[str, str]:
    attested = cli.run(
        (
            *("app", "modelo", "work", "attest-m303-exonerado-390", "--year", str(year)),
            *("--period", period, "--observed-at", observed_at),
        )
    )
    return _text(attested.get("attachment_id"), label="attest"), _text(attested.get("sha256"), label="attest")


def _calculate_args(
    work_unit_id: str, *, attestation: tuple[str, str] | None, joint_return_elected: bool = False
) -> tuple[str, ...]:
    """Answer the joint-return question, and supply the attestation pair only when given."""
    return (
        *("app", "modelo", "work", "calculate", work_unit_id),
        "--joint-return-elected" if joint_return_elected else "--no-joint-return-elected",
        *(
            ()
            if attestation is None
            else ("--m303-exonerado-390-attachment-id", attestation[0], "--m303-exonerado-390-sha256", attestation[1])
        ),
    )


def _revision_ids(cli: _Cli, work_unit_id: str) -> tuple[str, ...]:
    listed = cli.run(("app", "modelo", "work", "revisions", work_unit_id))
    rows = listed.get("revisions")
    if not isinstance(rows, list):
        raise IvaInstalledM303Error("installed revisions listing returned no rows")
    return tuple(
        _text(_mapping(row, label="revision row").get("calculation_revision_id"), label="revision row")
        for row in cast(list[object], rows)
    )


def _read_revision(cli: _Cli, revision_id: str) -> tuple[bool, bool]:
    """Return (resultado matches oracle, revision verified) from the public revision readback."""
    revision = cli.run(("app", "modelo", "work", "revision", revision_id))
    casillas = _mapping(revision.get("casilla_values"), label="revision casillas")
    return resultado_matches_oracle(casillas.get("iva.resultado")), revision.get("verified_at") is not None


def _require_development_developer_header(payload: bytes, positions: tuple[str, str, str]) -> None:
    """Refuse unless the official developer-header bytes carry the all-zero development identity."""
    record, program_span, developer_span = positions
    envelope_start = payload.find(b"<T303")
    if envelope_start < 0:
        raise IvaInstalledM303Error(f"Modelo 303 export carries no {record} envelope prefix")
    for span, expected in (
        (program_span, _DEVELOPMENT_MOCK_HEADER["program"]),
        (developer_span, _DEVELOPMENT_MOCK_HEADER["developer"]),
    ):
        first, last = (int(bound) for bound in span.split("-"))
        if payload[envelope_start + first - 1 : envelope_start + last] != expected:
            raise IvaInstalledM303Error(f"{record} bytes {span} do not carry the development identity")


def _fresh_cli(args: argparse.Namespace, store: Path, passphrase: str) -> _Cli:
    return _Cli(InstalledCli(args.cli, storage_root=store, authority_root=args.authority_root, passphrase=passphrase))


def _setup_store(
    args: argparse.Namespace,
    journey_year: IvaJourneyYear,
    name: str,
    *,
    period: str = _PERIOD,
    wallet_period: str = _PRIOR_PERIOD,
    days: tuple[tuple[int, int], tuple[int, int]] = _LAST_PERIOD_DAYS,
    monthly_filer: bool = False,
) -> tuple[Path, str, _Cli, str]:
    store = cast(Path, args.output_root) / name
    store.mkdir(parents=True)
    artifact = args.output_root / f"{name}-synthetic-purchase.pdf"
    artifact.write_bytes(b"%PDF-1.4\n% synthetic acceptance purchase evidence\n")
    passphrase = secrets.token_urlsafe(32)
    cli = _fresh_cli(args, store, passphrase)
    try:
        cli.cli.create_profile(year=journey_year.year)
    except InstalledCliError as error:
        raise IvaInstalledM303Error("installed CLI profile creation refused") from error
    if monthly_filer:
        # RD 1624/1992 art. 71: a REDEME-registered taxpayer settles Modelo 303 monthly.
        cli.run(("config", "profile", "edit", f"income-{journey_year.year}", "--quiet", "--iva-redeme-enrolled"))
    (sale_month, sale_day), (purchase_month, purchase_day) = days
    work_unit_id = _cli_capture_and_create_work(
        cli,
        artifact=artifact,
        year=journey_year.year,
        period=period,
        wallet_period=wallet_period,
        dates=(journey_year.iso_date(sale_month, sale_day), journey_year.iso_date(purchase_month, purchase_day)),
    )
    artifact.unlink()
    return store, passphrase, cli, work_unit_id
