"""Canonical carry stage for installed export-parity seeding."""

from __future__ import annotations

from .scenario import (
    QUARTERS,
    activity_year,
)
from .seed_contracts import (
    _ACTOR,
)
from .seed_inputs import (
    _m303_opening_balance_args,
    _money,
)
from .seed_state import SeedState


class CarrySeedStage(SeedState):
    """Own the installed seed carry behavior."""

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

    def carry_m303_compensation(self, year: int) -> None:
        """Declare the Modelo 303 compensación the prior year's last quarter left pending.

        The first quarter of ``year`` reads that balance as its cuotas pendientes
        de compensación, and the IVA wallet gate refuses it until the balance
        has an authority. A return filed outside Cadrumo enters as the IVA
        wallet's opening balance for its period, the amount being what the
        oracle's quarter left for later periods: a proven zero when that quarter
        was a result a ingresar, never an absent value.
        """
        stage = f"carry-m303:{year}"
        if not self._stage(stage):
            return
        prior, period = year - 1, QUARTERS[-1]
        if self._pending(f"{stage}.seed"):
            seeded = self._result(_m303_opening_balance_args(prior, period), stage=f"{stage}.seed")
            self._remember(f"iva-wallet:303:{prior}:{period}", seeded.get("provenance", ""))
            self._complete(f"{stage}.seed")
        self._done(stage)
