"""Canonical assets stage for installed export-parity seeding."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from decimal import Decimal

from .scenario import (
    ASSETS,
    ActivityAsset,
)
from .seed_contracts import (
    _ACTOR,
)
from .seed_inputs import (
    _money,
)
from .seed_state import SeedState


class AssetSeedStage(SeedState):
    """Own the installed seed assets behavior."""

    def _prior_acquisition(self, asset: ActivityAsset, *, stage: str) -> str:
        """Record the payment of a carried-in asset on its in-service date; the register needs a ledger row."""
        description = f"Synthetic prior acquisition {asset.asset_id}"
        existing = self._stored_transaction(description)
        if existing is not None:
            return existing
        iva = asset.basis * Decimal("0.21")
        added = self._result(
            (
                "app",
                "ledger",
                "add",
                "--date",
                asset.in_service.isoformat(),
                "--amount",
                _money(asset.basis + iva),
                "--direction",
                "OUTGOING",
                "--description",
                description,
                "--classification",
                "BUSINESS",
                "--taxable-base",
                _money(asset.basis),
                "--iva-rate",
                "0.21",
                "--iva-amount",
                _money(iva),
            ),
            stage=f"{stage}.acquisition",
        )
        return str(added["transaction_id"])

    def _asset(self, asset: ActivityAsset, *, carried_in: bool = False) -> None:
        """Register one asset; a carried-in asset predates the store and brings its accumulated history."""
        stage = f"asset.{asset.asset_id}"
        if carried_in:
            # Acquired before the first seeded year: the register still names a ledger payment,
            # so that payment is recorded on its own date first.
            transaction_id = self._prior_acquisition(asset, stage=stage)
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
                "non_deductible_iva": "0.00",
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
