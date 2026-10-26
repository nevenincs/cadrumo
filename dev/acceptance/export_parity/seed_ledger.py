"""Canonical ledger stage for installed export-parity seeding."""

from __future__ import annotations

from .scenario import (
    ASSETS,
    build_year,
)
from .seed_assets import AssetSeedStage
from .seed_invoices import InvoiceSeedStage


def _register_year_assets(self: LedgerSeedStage, year: int) -> None:
    """Register year assets."""
    for asset in ASSETS:
        carried_in = year == self.first_year and asset.in_service.year < year
        if (asset.in_service.year == year or carried_in) and self._pending(f"register-{asset.asset_id}"):
            self._asset(asset, carried_in=carried_in)
            self._complete(f"register-{asset.asset_id}")


class LedgerSeedStage(InvoiceSeedStage, AssetSeedStage):
    """Own the installed seed ledger behavior."""

    def ledger(self, year: int) -> None:
        """Seed each public invoice, settlement, quota and asset once for this year."""
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
        _register_year_assets(self, year)
        self._done(stage)
