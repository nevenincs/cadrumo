"""Seed one multi-year synthetic secure store through the public ``aeat`` CLI.

Every write crosses a fresh installed-CLI process (:class:`InstalledCli`); the
driver never opens encrypted storage. Stages are resumable: each completed
stage is recorded in ``seed-receipt.json`` beside the store and skipped on the
next run. A refused ledger or profile command stops the run. A refused
withholding item or modelo lifecycle is recorded under ``blocked`` with its
typed error code and reason and the independent items continue, so a product
gap is reported, never papered over with a zero; the blocked stage stays open
and a later run retries it.

Usage:
    python -m dev.acceptance.export_parity.seed --cli .venv/bin/aeat \
        --authority-root .authority --run-dir <dir> [--years 2022 2023] \
        [--carry-evidence synthetic_csv_register|none]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
from collections.abc import Callable, Iterator, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Final

from dev.acceptance.installed_cli import InstalledCli, InstalledCliError, authority_generation, profile_create_args

from .scenario import (
    ASSETS,
    CLIENT,
    QUARTERS,
    SCENARIO_VERSION,
    YEARS,
    ActivityAsset,
    IssuedInvoice,
    ReceivedInvoice,
    WithholdingDuty,
    activity_year,
    build_year,
)

RECEIPT_SCHEMA: Final = "export-parity.seed-receipt/v1"
_ACTOR: Final = "export-parity-seed"
_UNCHANGED_UPDATE: Final = "must change at least one ledger field"
_PROFILE: Final = f"income-{YEARS[0]}"
_PERIODIC: Final = ("303", "130", "111", "115")
_ANNUAL: Final = ("390", "190", "180", "100")
_M100_CASILLAS: Final = ("0001=declarante", "0165=declarante", "0166=A05")
#: Renta bindings the scenario answers, applied only where the selected revision declares them.
_M100_BINDINGS: Final = {
    "renta-modelo-100-estimacion-directa-es-normal": "1",
    "renta-certificado-trabajo-retenciones": "0",
}


class SeedError(RuntimeError):
    """A seed stage could not complete through the public CLI."""


class SeedRefusalError(SeedError):
    """The product refused one seed command; the refusal is already on the receipt."""


def _money(value: Decimal) -> str:
    return f"{value:.2f}"


def _rate(value: Decimal) -> str:
    return f"{value.normalize():f}"


@dataclass(slots=True)
class SeedReceipt:
    """Sanitized, resumable record of a seed run: identifiers and codes, never amounts or secrets."""

    scenario: str
    authority_generation: str
    executable_sha256: str
    carry_evidence: str
    completed_stages: list[str] = field(default_factory=list)
    identifiers: dict[str, str] = field(default_factory=dict)
    blocked: dict[str, str] = field(default_factory=dict)
    updated: str = ""

    def save(self, path: Path) -> None:
        """Write the receipt beside the store."""
        self.updated = datetime.now(UTC).isoformat()
        path.write_text(json.dumps(asdict(self) | {"schema": RECEIPT_SCHEMA}, indent=2, sort_keys=True) + "\n")

    @classmethod
    def load(cls, path: Path) -> SeedReceipt | None:
        """Read an earlier receipt so completed stages are skipped."""
        if not path.is_file():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload.pop("schema", None)
        return cls(**payload)


class _Seeder:
    def __init__(
        self, cli: InstalledCli, *, receipt: SeedReceipt, receipt_path: Path, artifact_dir: Path, first_year: int
    ) -> None:
        self.cli = cli
        self.receipt = receipt
        self.receipt_path = receipt_path
        self.artifact_dir = artifact_dir
        #: The earliest seeded year; assets in service before it enter with their known opening history.
        self.first_year = first_year

    # -- plumbing ---------------------------------------------------------------

    def _result(self, args: Sequence[str], *, stage: str) -> dict[str, Any]:
        document = self.cli.run(tuple(args), allow_error=True)
        if document.get("status") == "error":
            error = document.get("error") or {}
            code = str(error.get("code")) if isinstance(error, dict) else "unknown"
            message = str(error.get("message", ""))[:300] if isinstance(error, dict) else ""
            self.receipt.blocked[stage] = f"{code}: {message}"
            self.receipt.save(self.receipt_path)
            raise SeedRefusalError(f"{stage}: {' '.join(args[:5])} refused {code}: {message}")
        result = document.get("result")
        if not isinstance(result, dict):
            raise SeedError(f"{stage}: {' '.join(args[:5])} returned no result object")
        if self.receipt.blocked.pop(stage, None) is not None:
            self.receipt.save(self.receipt_path)
        return result

    def _attempt(self, run: Callable[[], None]) -> bool:
        """Run one independent seed item, leaving a refusal on the receipt instead of stopping."""
        try:
            run()
        except SeedRefusalError:
            return False
        return True

    def _stored_transaction(self, description: str) -> str | None:
        """Find a transaction an interrupted run already added, so a resume never replays the add."""
        listed = self._result(("app", "ledger", "list"), stage="lookup.transactions")
        rows = listed.get("rows")
        matches = [
            str(row["transaction_id"])
            for row in (rows if isinstance(rows, list) else ())
            if isinstance(row, dict) and row.get("description") == description
        ]
        if len(matches) > 1:
            raise SeedError(f"{len(matches)} stored transactions carry the description {description!r}")
        return matches[0] if matches else None

    def _stored_invoice(self, kind: str, number: str) -> str | None:
        """Find an invoice an interrupted run already recorded under its deterministic number."""
        listed = self._result(("app", "ledger", "invoice", "list", "--kind", kind), stage="lookup.invoices")
        rows = listed.get("rows")
        matches = [
            str(row["invoice_id"])
            for row in (rows if isinstance(rows, list) else ())
            if isinstance(row, dict) and row.get("invoice_number") == number
        ]
        if len(matches) > 1:
            raise SeedError(f"{len(matches)} stored {kind} invoices carry the number {number!r}")
        return matches[0] if matches else None

    def _remember(self, key: str, value: object) -> str:
        text = str(value)
        self.receipt.identifiers[key] = text
        return text

    def _pending(self, key: str) -> bool:
        """Whether ``key`` still needs seeding; a resumed run skips every completed item and sub-step."""
        return f"done:{key}" not in self.receipt.identifiers

    def _complete(self, key: str) -> None:
        self.receipt.identifiers[f"done:{key}"] = "1"
        # A refusal an interrupted run left for this item is resolved once the item completes.
        for stage in [stage for stage in self.receipt.blocked if stage.rsplit(".", 1)[-1] == key]:
            self.receipt.blocked.pop(stage)
        self.receipt.save(self.receipt_path)

    def _stage(self, name: str) -> bool:
        return name not in self.receipt.completed_stages

    def _done(self, name: str) -> None:
        self.receipt.completed_stages.append(name)
        self.receipt.save(self.receipt_path)

    # -- profile ----------------------------------------------------------------

    def profile(self) -> None:
        if not self._stage("profile"):
            return
        payload = json.dumps({"passphrase": self.cli.passphrase, "passphrase_confirmation": self.cli.passphrase})
        self.cli.run(
            profile_create_args(YEARS[0]), authenticated=False, stdin_payload=payload, command="config profile create"
        )
        self._result(
            (
                "config",
                "profile",
                "edit",
                _PROFILE,
                "--quiet",
                "--accept-defaults",
                "--pays-professionals-with-retencion",
                "--pays-rent-with-retencion",
                "--no-pays-capital-income-with-retencion",
                "--no-colegio-concertado",
                "--third-party-transactions-above-347-threshold",
            ),
            stage="profile.edit",
        )
        self._result(("config", "profile", "complete-setup"), stage="profile.complete_setup")
        self._done("profile")

    # -- ledger -----------------------------------------------------------------

    def ledger(self, year: int) -> None:
        stage = f"ledger:{year}"
        if not self._stage(stage):
            return
        scenario = build_year(year)
        for issued in scenario.issued:
            if self._pending(issued.key):
                self._issued(issued)
                self._complete(issued.key)
        for received in scenario.received:
            if self._pending(received.key):
                self._received(received)
                self._complete(received.key)
        for month in scenario.reta_months:
            if not self._pending(f"reta-{month:%Y-%m}"):
                continue
            self._result(
                (
                    "app",
                    "ledger",
                    "add",
                    "--date",
                    month.isoformat(),
                    "--amount",
                    "300.00",
                    "--direction",
                    "OUTGOING",
                    "--description",
                    f"Synthetic RETA {month:%Y-%m}",
                    "--classification",
                    "BUSINESS",
                    "--category-id",
                    "cuotas_autonomos_ss",
                    # A Social Security quota is outside the IVA taxable event (LIVA art. 7):
                    # its base is declared with a zero tipo and cuota, never inferred.
                    "--taxable-base",
                    "300.00",
                    "--iva-rate",
                    "0",
                    "--iva-amount",
                    "0.00",
                    "--iva-category",
                    "operacion_no_sujeta",
                    "--source-jurisdiction",
                    "ES",
                    "--idempotency-key",
                    f"reta-{month:%Y-%m}",
                ),
                stage=f"{stage}.reta",
            )
            self._complete(f"reta-{month:%Y-%m}")
        for asset in ASSETS:
            carried_in = year == self.first_year and asset.in_service.year < year
            if (asset.in_service.year == year or carried_in) and self._pending(f"register-{asset.asset_id}"):
                self._asset(asset, carried_in=carried_in)
                self._complete(f"register-{asset.asset_id}")
        self._done(stage)

    def _issued(self, item: IssuedInvoice) -> None:
        stage = f"ledger.issued.{item.key}"
        description = f"Synthetic fees {item.key}"
        transaction_id = self.receipt.identifiers.get(f"tx:{item.key}") or self._stored_transaction(description)
        if transaction_id is None:
            added = self._result(
                (
                    "app",
                    "ledger",
                    "add",
                    "--date",
                    item.payment_date.isoformat(),
                    "--amount",
                    _money(item.receipt),
                    "--direction",
                    "INCOMING",
                    "--description",
                    description,
                    "--classification",
                    "BUSINESS",
                    "--taxable-base",
                    _money(item.base),
                    "--iva-rate",
                    "0.21",
                    "--iva-amount",
                    _money(item.iva),
                    "--iva-category",
                    "domestic_general",
                    "--irpf-category",
                    "actividad_economica",
                    "--source-jurisdiction",
                    "ES",
                    "--idempotency-key",
                    item.key,
                ),
                stage=stage,
            )
            transaction_id = str(added["transaction_id"])
        self._remember(f"tx:{item.key}", transaction_id)
        self.receipt.save(self.receipt_path)
        invoice_id = self.receipt.identifiers.get(f"invoice:{item.key}") or self._stored_invoice(
            "issued", item.key.upper()
        )
        if invoice_id is None:
            added = self._result(
                (
                    "app",
                    "ledger",
                    "invoice",
                    "add",
                    "--kind",
                    "issued",
                    "--counterparty-name",
                    CLIENT.name,
                    "--counterparty-nif",
                    CLIENT.tax_id,
                    "--invoice-number",
                    item.key.upper(),
                    "--invoice-date",
                    item.invoice_date.isoformat(),
                    "--taxable-base",
                    _money(item.base),
                    "--iva-rate",
                    "21",
                    "--country-code",
                    "ES",
                    "--retention-rate",
                    _rate(item.withholding_rate),
                    "--retention-amount",
                    _money(item.withholding),
                    "--iva-category",
                    "domestic_general",
                ),
                stage=f"{stage}.invoice",
            )
            invoice_id = str(added["invoice_id"])
        self._remember(f"invoice:{item.key}", invoice_id)
        self.receipt.save(self.receipt_path)
        if self._pending(f"link:{item.key}"):
            self._result(("app", "ledger", "link", transaction_id, "--invoice-id", invoice_id), stage=f"{stage}.link")
            self._complete(f"link:{item.key}")

    def _evidence_pdf(self, item: ReceivedInvoice) -> Path:
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        path = self.artifact_dir / f"{item.key}.pdf"
        path.write_bytes(f"%PDF-1.4\n% synthetic export-parity purchase evidence {item.key}\n".encode("ascii"))
        return path

    def _received(self, item: ReceivedInvoice) -> None:
        stage = f"ledger.received.{item.key}"
        evidence_id = self.receipt.identifiers.get(f"evidence:{item.key}")
        if evidence_id is None:
            evidence = self._result(
                (
                    "app",
                    "ledger",
                    "evidence",
                    "add",
                    str(self._evidence_pdf(item)),
                    "--supplier",
                    item.counterparty.name,
                ),
                stage=f"{stage}.evidence",
            )
            evidence_id = self._remember(f"evidence:{item.key}", evidence["evidence_id"])
            self.receipt.save(self.receipt_path)
        iva_args: tuple[str, ...] = (
            (
                "--taxable-base",
                _money(item.base),
                "--iva-rate",
                _rate(item.iva_rate),
                "--iva-amount",
                _money(item.iva),
                "--iva-category",
                "domestic_general",
            )
            if item.iva_rate
            else (
                "--taxable-base",
                _money(item.base),
                "--iva-rate",
                "0",
                "--iva-amount",
                "0.00",
                "--iva-category",
                "domestic_exempt",
            )
        )
        # A payment settled net of the declarant's withholding names the IRPF
        # category that makes the cash gap a withholding rather than a mismatch.
        irpf_args: tuple[str, ...] = {
            WithholdingDuty.NONE: (),
            WithholdingDuty.PROFESSIONAL: ("--irpf-category", "actividad_economica"),
            WithholdingDuty.URBAN_RENT: ("--irpf-category", "arrendamiento_local"),
        }[item.duty]
        description = f"Synthetic purchase {item.key}"
        transaction_id = self.receipt.identifiers.get(f"tx:{item.key}") or self._stored_transaction(description)
        if transaction_id is None:
            transaction_id = self._remember(
                f"tx:{item.key}",
                self._result(
                    (
                        "app",
                        "ledger",
                        "add",
                        "--date",
                        item.payment_date.isoformat(),
                        "--amount",
                        _money(item.payment),
                        "--direction",
                        "OUTGOING",
                        "--description",
                        description,
                        "--classification",
                        "BUSINESS",
                        "--category-id",
                        item.category,
                        *iva_args,
                        *irpf_args,
                        "--purchase-invoice-evidence-id",
                        evidence_id,
                        "--source-jurisdiction",
                        "ES",
                        "--idempotency-key",
                        item.key,
                    ),
                    stage=stage,
                )["transaction_id"],
            )
            self.receipt.save(self.receipt_path)
        self._remember(f"tx:{item.key}", transaction_id)
        withholding_args: tuple[str, ...] = (
            ("--retention-rate", _rate(item.withholding / item.base), "--retention-amount", _money(item.withholding))
            if item.withholding
            else ()
        )
        invoice_id = self.receipt.identifiers.get(f"invoice:{item.key}") or self._stored_invoice(
            "received", item.key.upper()
        )
        if invoice_id is None:
            invoice_id = self._result(
                (
                    "app",
                    "ledger",
                    "invoice",
                    "add",
                    "--kind",
                    "received",
                    "--counterparty-name",
                    item.counterparty.name,
                    "--counterparty-nif",
                    item.counterparty.tax_id,
                    "--invoice-number",
                    item.key.upper(),
                    "--invoice-date",
                    item.invoice_date.isoformat(),
                    "--taxable-base",
                    _money(item.base),
                    "--iva-rate",
                    _rate(item.iva_rate * 100),
                    "--country-code",
                    "ES",
                    *withholding_args,
                    "--iva-category",
                    "domestic_general" if item.iva_rate else "domestic_exempt",
                ),
                stage=f"{stage}.invoice",
            )["invoice_id"]
        self._remember(f"invoice:{item.key}", invoice_id)
        self.receipt.save(self.receipt_path)
        if self._pending(f"link:{item.key}"):
            self._result(("app", "ledger", "link", transaction_id, "--invoice-id", invoice_id), stage=f"{stage}.link")
            self._complete(f"link:{item.key}")
        if item.iva_rate and self._pending(f"classify:{item.key}"):
            try:
                self._result(
                    (
                        "app",
                        "ledger",
                        "classify",
                        transaction_id,
                        "--classification",
                        "BUSINESS",
                        "--deduction-kind",
                        "domestic_investment" if _is_investment_good(item) else "domestic_current",
                        *_investment_asset_args(item),
                        "--counterparty-country",
                        "ES",
                        "--reaffirm",
                    ),
                    stage=f"{stage}.classify",
                )
            except SeedRefusalError:
                # An interrupted run already applied this classification; the product
                # refuses a no-op update, which on resume is the expected answer.
                if _UNCHANGED_UPDATE not in self.receipt.blocked.get(f"{stage}.classify", ""):
                    raise
                self.receipt.blocked.pop(f"{stage}.classify")
            self._complete(f"classify:{item.key}")

    def _asset(self, asset: ActivityAsset, *, carried_in: bool = False) -> None:
        """Register one asset; a carried-in asset predates the store and brings its accumulated history."""
        stage = f"asset.{asset.asset_id}"
        if carried_in:
            # Acquired in a year this store does not hold: its purchase is outside the
            # ledger, so the register names a stable synthetic acquisition reference.
            transaction_id = hashlib.sha256(f"prior-acquisition:{asset.asset_id}".encode("ascii")).hexdigest()
            evidence_id = f"synthetic-prior-{asset.asset_id}"
        else:
            transaction_id = self.receipt.identifiers[f"tx:asset-{asset.asset_id}"]
            evidence_id = self.receipt.identifiers[f"evidence:asset-{asset.asset_id}"]
        accumulated = sum(
            (asset.charge_for(year) for year in range(asset.in_service.year, self.first_year)), Decimal("0")
        )
        revision = {
            "asset_id": asset.asset_id,
            "revision_number": 1,
            "acquisition": {
                "observed_transaction_id": transaction_id,
                "invoice_evidence_id": evidence_id,
                "evidence_fingerprint": hashlib.sha256(evidence_id.encode("ascii")).hexdigest(),
            },
            "acquisition_shape": "primary_purchase",
            "asset_kind": asset.kind,
            "basis": {
                "stage": "business_allocated",
                "basis_amount": _money(asset.basis),
                "prior_allocation_provenance": "synthetic export-parity allocation",
            },
            "in_service_date": asset.in_service.isoformat(),
            "opening_history": {"status": "known", "accumulated_amount": _money(accumulated)},
            "acquired_condition": "new",
            "amortization": {"regime": "normal", "method": asset.method, "authority_class_key": asset.class_key},
        }
        self._result(
            ("app", "ledger", "actividad-asset", "create", json.dumps(revision, separators=(",", ":"))), stage=stage
        )
        if asset.is_iva_investment_good and not carried_in:
            self._result(
                (
                    "app",
                    "ledger",
                    "bienes-inversion",
                    "declare",
                    asset.asset_id,
                    "--description",
                    f"Synthetic {asset.asset_id}",
                    "--acquisition-year",
                    str(asset.in_service.year),
                    "--acquisition-ledger-id",
                    transaction_id,
                    "--cuota-soportada",
                    _money(asset.basis * Decimal("0.21")),
                    "--prorrata-inicial",
                    "100",
                    "--kind",
                    "mueble",
                ),
                stage=f"{stage}.bienes_inversion",
            )

    # -- amortization claims -------------------------------------------------------

    def amortization(self, year: int) -> None:
        """Forecast and claim each registered asset's charge for ``year``, as the operator would."""
        stage = f"amortization:{year}"
        if not self._stage(stage):
            return
        settled = True
        for asset in ASSETS:
            if asset.in_service.year > year or not self._pending(f"claim-{asset.asset_id}-{year}"):
                continue
            settled &= self._attempt(lambda asset=asset: self._claim(asset, year))
        if settled:
            self._done(stage)

    def _claim(self, asset: ActivityAsset, year: int) -> None:
        stage = f"amortization:{year}.{asset.asset_id}"
        covered_from = max(asset.in_service, date(year, 1, 1))
        forecast = self._result(
            (
                "app",
                "ledger",
                "actividad-asset",
                "forecast",
                asset.asset_id,
                "--covered-from",
                covered_from.isoformat(),
                "--covered-until",
                date(year + 1, 1, 1).isoformat(),
            ),
            stage=f"{stage}.forecast",
        )
        claimed = self._result(
            (
                "app",
                "ledger",
                "actividad-asset",
                "claim",
                json.dumps(forecast, separators=(",", ":")),
                "--creating-operation",
                _ACTOR,
            ),
            stage=f"{stage}.claim",
        )
        claim = claimed.get("claim")
        self._remember(f"claim:{asset.asset_id}:{year}", claim.get("claim_id", "") if isinstance(claim, dict) else "")
        self._complete(f"claim-{asset.asset_id}-{year}")

    # -- withholding the declarant practises ------------------------------------

    def withholding(self, year: int) -> None:
        stage = f"withholding:{year}"
        if not self._stage(stage):
            return
        settled = True
        for item in build_year(year).received:
            if item.duty is WithholdingDuty.NONE or not self._pending(f"withholding-{item.key}"):
                continue
            settled &= self._attempt(lambda item=item: self._withhold(year, item))
        if settled:
            self._done(stage)

    def _withhold(self, year: int, item: ReceivedInvoice) -> None:
        stage = f"withholding:{year}"
        modelo = "111" if item.duty is WithholdingDuty.PROFESSIONAL else "115"
        request: dict[str, object] = {
            "invoice_id": self.receipt.identifiers[f"invoice:{item.key}"],
            "income_kind": "professional" if modelo == "111" else "urban_rent",
            "scheme": "actividades_profesionales" if modelo == "111" else "arrendamiento_urbano",
            "recipient_tax_status": "resident",
            "recipient_tax_regime": "irpf",
            "payment_event_id": f"payment-{item.key}",
            "payment_occurred_on": item.payment_date.isoformat(),
            "allocation_id": f"allocation-{item.key}",
            "allocated_base": _money(item.base),
            "allocated_withholding": _money(item.withholding),
            "allocated_settlement": _money(item.payment),
            "idempotency_key": f"withholding-{item.key}",
        }
        if modelo == "111":
            request["modelo_190_detail"] = _modelo_190_detail(item, request)
        else:
            request["modelo_180_property"] = _modelo_180_property(year)
        self._result(
            (
                "app",
                "modelo",
                "aggregate",
                "--modelo",
                modelo,
                "--year",
                str(year),
                "--period",
                item.period,
                "--received-invoice-retencion",
                json.dumps(request, separators=(",", ":"), sort_keys=True),
            ),
            stage=f"{stage}.{item.key}",
        )
        self._complete(f"withholding-{item.key}")

    # -- prior-year carries ingested as AEAT register evidence --------------------

    def carry_in(self, year: int) -> None:
        """Import the prior year's Renta as a synthetic AEAT CSV register filing record.

        The lane that does not seed ``year - 1`` still needs the prior-year facts
        the cross-period gate reads (Modelo 130's prior-year activity yield, the
        Renta carry-forward balance). They enter through the product's own
        external-filing ingestion, a ``casilla_code;value`` manifest, under an
        evidence id that is visibly synthetic.
        """
        stage = f"carry:{year}"
        if not self._stage(stage):
            return
        prior = year - 1
        work_key = f"work:100:{prior}:0A"
        if self._pending(f"{stage}.create"):
            created = self._result(
                (
                    "app",
                    "modelo",
                    "work",
                    "create",
                    "--modelo",
                    "100",
                    "--year",
                    str(prior),
                    "--period",
                    "0A",
                    "--by",
                    _ACTOR,
                ),
                stage=f"{stage}.create",
            )
            self._remember(work_key, created["work_unit_id"])
            self._complete(f"{stage}.create")
        if self._pending(f"{stage}.import"):
            self.artifact_dir.mkdir(parents=True, exist_ok=True)
            manifest = self.artifact_dir / f"modelo-100-{prior}-synthetic-aeat-register.csv"
            manifest.write_text(
                f"casilla_code;value\n0224;{_money(activity_year(prior).net)}\n1391;0.00\n",
                encoding="utf-8",
            )
            imported = self._result(
                (
                    "app",
                    "modelo",
                    "filing-record",
                    "import",
                    self.receipt.identifiers[work_key],
                    "--evidence-kind",
                    "aeat_csv_register",
                    "--evidence-id",
                    f"CADRUMOSYNTHETIC{prior}M100",
                    "--file",
                    str(manifest),
                    "--by",
                    _ACTOR,
                ),
                stage=f"{stage}.import",
            )
            self._remember(f"filing-record:100:{prior}:0A", imported.get("filing_record_id", ""))
            self._complete(f"{stage}.import")
        self._done(stage)

    # -- modelo lifecycle ---------------------------------------------------------

    def _lifecycle(self, modelo: str, year: int, period: str, extra: Callable[[], Sequence[str]] = tuple) -> None:
        stage = f"modelo:{modelo}:{year}:{period}"
        if not self._stage(stage):
            return
        work_key, revision_key = f"work:{modelo}:{year}:{period}", f"revision:{modelo}:{year}:{period}"
        if self._pending(f"{stage}.create"):
            created = self._result(
                (
                    "app",
                    "modelo",
                    "work",
                    "create",
                    "--modelo",
                    modelo,
                    "--year",
                    str(year),
                    "--period",
                    period,
                    "--by",
                    _ACTOR,
                ),
                stage=f"{stage}.create",
            )
            self._remember(work_key, created["work_unit_id"])
            self._complete(f"{stage}.create")
        work_id = self.receipt.identifiers[work_key]
        if self._pending(f"{stage}.calculate"):
            calculated = self._result(
                ("app", "modelo", "work", "calculate", work_id, *extra(), "--by", _ACTOR), stage=f"{stage}.calculate"
            )
            self._remember(revision_key, calculated["calculation_revision_id"])
            self._complete(f"{stage}.calculate")
        revision_id = self.receipt.identifiers[revision_key]
        if self._pending(f"{stage}.verify"):
            verified = self._result(
                ("app", "modelo", "work", "verify", revision_id, "--by", _ACTOR), stage=f"{stage}.verify"
            )
            if verified.get("granted_verificado_completo") is not True:
                reasons = sorted(
                    {
                        str(finding.get("kind"))
                        for finding in verified.get("findings") or ()
                        if isinstance(finding, dict) and finding.get("severity") == "blocking"
                    }
                )
                self.receipt.blocked[f"{stage}.verify"] = f"not_granted: {', '.join(reasons)[:300]}"
                self.receipt.save(self.receipt_path)
                raise SeedRefusalError(f"{stage}: verification was not granted")
            self._complete(f"{stage}.verify")
        if self._pending(f"{stage}.file"):
            self._result(
                (
                    "app",
                    "modelo",
                    "work",
                    "file",
                    revision_id,
                    "--by",
                    _ACTOR,
                    "--notes",
                    "Synthetic local filing record only; never sent to AEAT",
                ),
                stage=f"{stage}.file",
            )
            self._complete(f"{stage}.file")
        self.receipt.blocked.pop(f"{stage}.verify", None)
        self._done(stage)

    def modelos(self, year: int) -> None:
        for period in QUARTERS:
            for modelo in _PERIODIC:
                self._attempt(
                    lambda modelo=modelo, period=period: self._lifecycle(
                        modelo, year, period, lambda: self._calculation_inputs(modelo, year, period)
                    )
                )
        for modelo in _ANNUAL:
            self._attempt(
                lambda modelo=modelo: self._lifecycle(
                    modelo, year, "0A", lambda: self._calculation_inputs(modelo, year, "0A")
                )
            )

    def _calculation_inputs(self, modelo: str, year: int, period: str) -> tuple[str, ...]:
        """Return the operator answers ``work calculate`` asks for this modelo and period."""
        if modelo == "303":
            inputs: tuple[str, ...] = ("--no-joint-return-elected",)
            if period == QUARTERS[-1]:
                attachment_id, sha256 = self._m303_exonerado_390_attestation(year, period)
                inputs += ("--m303-exonerado-390-attachment-id", attachment_id, "--m303-exonerado-390-sha256", sha256)
            return inputs
        if modelo == "100":
            declared = self._declared_bindings("100", year)
            casillas = tuple(argument for value in _M100_CASILLAS for argument in ("--casilla", value))
            bindings = tuple(
                argument
                for binding_id, value in _M100_BINDINGS.items()
                if binding_id in declared
                for argument in ("--binding", f"{binding_id}={value}")
            )
            return casillas + bindings
        return ()

    def _m303_exonerado_390_attestation(self, year: int, period: str) -> tuple[str, str]:
        """Attest that the filer is not exempt from Modelo 390, once per year, as the last 303 asks."""
        key = f"attest:303:{year}:{period}"
        if self._pending(key):
            attested = self._result(
                (
                    "app",
                    "modelo",
                    "work",
                    "attest-m303-exonerado-390",
                    "--year",
                    str(year),
                    "--period",
                    period,
                    "--observed-at",
                    f"{year + 1}-01-10T12:00:00+00:00",
                    "--by",
                    _ACTOR,
                ),
                stage=f"{key}.attest",
            )
            self._remember(f"{key}:attachment_id", attested["attachment_id"])
            self._remember(f"{key}:sha256", attested["sha256"])
            self._complete(key)
        return self.receipt.identifiers[f"{key}:attachment_id"], self.receipt.identifiers[f"{key}:sha256"]

    def _declared_bindings(self, modelo: str, year: int) -> frozenset[str]:
        """Read the binding ids the selected revision declares, so no other year's answer is sent."""
        listed = self._result(
            ("app", "modelo", "bindings", "list", "--modelo", modelo, "--year", str(year)),
            stage=f"bindings:{modelo}:{year}",
        )
        return frozenset(_binding_ids(listed))


def _is_investment_good(item: ReceivedInvoice) -> bool:
    return any(asset.asset_id == item.asset_id and asset.is_iva_investment_good for asset in ASSETS)


def _investment_asset_args(item: ReceivedInvoice) -> tuple[str, ...]:
    """Name the bienes-inversion record an investment deduction must reciprocate."""
    if item.asset_id is None or not _is_investment_good(item):
        return ()
    return ("--investment-asset-id", item.asset_id)


def _binding_ids(document: object) -> Iterator[str]:
    if isinstance(document, dict):
        for key, value in document.items():
            if key == "binding_id" and isinstance(value, str):
                yield value
            else:
                yield from _binding_ids(value)
    elif isinstance(document, list):
        for item in document:
            yield from _binding_ids(item)


def _modelo_190_detail(item: ReceivedInvoice, request: dict[str, object]) -> dict[str, object]:
    zero = "0.00"
    return {
        "source_id": request["invoice_id"],
        "source_allocation_id": request["allocation_id"],
        "perceptor_tax_id": item.counterparty.tax_id,
        "perceptor_legal_name": item.counterparty.name,
        "transaction_date": item.payment_date.isoformat(),
        "clave": "G",
        "subclave": "01",
        "province_code": "28",
        "territorial_deduction_clave": 0,
        "percibido_dinerario": _money(item.base),
        "retencion_practicada": _money(item.withholding),
        "incapacity_cash_perception": zero,
        "incapacity_cash_withholding": zero,
        "incapacity_kind_value": zero,
        "incapacity_kind_ingreso_a_cuenta": zero,
        "incapacity_kind_repercutido": zero,
        "foral_retention_estatal": zero,
        "foral_retention_navarra": zero,
        "foral_retention_araba": zero,
        "foral_retention_gipuzkoa": zero,
        "foral_retention_bizkaia": zero,
        "base_retenciones": _money(item.base),
        "porcentaje_retencion": "15.00",
    }


def _modelo_180_property(year: int) -> dict[str, object]:
    return {
        "property_key": "office-madrid",
        "situation": "1",
        "cadastral_reference": "1234567VK4713C0001XY",
        "recipient_province_code": "28",
        "modality": "1",
        "accrual_year": year,
        "withholding_percentage": "19.00",
        "address": {
            "province_code": "28",
            "municipality_code": "079",
            "municipality": "Madrid",
            "locality": "Madrid",
            "postal_code": "28001",
            "street_type": "CL",
            "street_name": "Ejemplo",
            "number_type": "NUM",
            "house_number": "1",
        },
    }


def _open_cli(executable: Path, *, authority_root: Path, run_dir: Path) -> InstalledCli:
    run_dir.mkdir(parents=True, exist_ok=True)
    secret = run_dir / "passphrase"
    if not secret.exists():
        secret.write_text(secrets.token_urlsafe(32), encoding="utf-8")
        os.chmod(secret, 0o600)
    (run_dir / "store").mkdir(exist_ok=True)
    return InstalledCli(
        executable,
        storage_root=run_dir / "store",
        authority_root=authority_root,
        passphrase=secret.read_text(encoding="utf-8").strip(),
    )


def run_seed(
    *,
    executable: Path,
    authority_root: Path,
    run_dir: Path,
    years: Sequence[int] = YEARS,
    stages: Sequence[str] = ("ledger", "amortization", "withholding", "modelos"),
    carry_evidence: str = "none",
) -> SeedReceipt:
    """Seed ``years`` into ``run_dir/store`` and return the receipt, raising :class:`SeedError` on a refusal."""
    cli = _open_cli(executable, authority_root=authority_root, run_dir=run_dir)
    receipt_path = run_dir / "seed-receipt.json"
    generation = authority_generation(authority_root)
    receipt = SeedReceipt.load(receipt_path) or SeedReceipt(
        scenario=SCENARIO_VERSION,
        authority_generation=generation,
        executable_sha256=hashlib.sha256(cli.executable.read_bytes()).hexdigest(),
        carry_evidence=carry_evidence,
    )
    if receipt.authority_generation != generation:
        raise SeedError("authority generation changed since this store was seeded; seed a fresh store")
    if receipt.carry_evidence != carry_evidence:
        raise SeedError(f"this store was seeded with carry evidence {receipt.carry_evidence!r}; seed a fresh store")
    seeder = _Seeder(
        cli, receipt=receipt, receipt_path=receipt_path, artifact_dir=run_dir / "evidence", first_year=min(years)
    )
    seeder.profile()
    for year in years:
        if carry_evidence == "synthetic_csv_register" and year - 1 not in years and "modelos" in stages:
            seeder.carry_in(year)
        for stage in stages:
            getattr(seeder, stage)(year)
    receipt.save(receipt_path)
    return receipt


def main(argv: Sequence[str] | None = None) -> int:
    """Seed the requested years and print the completed and blocked stages."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", required=True, type=Path)
    parser.add_argument("--authority-root", required=True, type=Path)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--years", type=int, nargs="+", default=list(YEARS))
    parser.add_argument("--stages", nargs="+", default=["ledger", "amortization", "withholding", "modelos"])
    parser.add_argument("--carry-evidence", choices=("none", "synthetic_csv_register"), default="none")
    args = parser.parse_args(argv)
    try:
        receipt = run_seed(
            executable=args.cli.resolve(),
            authority_root=args.authority_root.resolve(),
            run_dir=args.run_dir.resolve(),
            years=args.years,
            stages=args.stages,
            carry_evidence=args.carry_evidence,
        )
    except (SeedError, InstalledCliError) as exc:
        print(f"seed stopped: {exc}")
        return 2
    print(json.dumps({"completed": receipt.completed_stages[-5:], "blocked": receipt.blocked}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
