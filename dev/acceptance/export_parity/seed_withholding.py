"""Canonical withholding stage for installed export-parity seeding."""

from __future__ import annotations

import json

from .scenario import (
    ReceivedInvoice,
    WithholdingDuty,
    build_year,
)
from .seed_inputs import (
    _modelo_180_property,
    _modelo_190_detail,
    _money,
)
from .seed_state import SeedState


class WithholdingSeedStage(SeedState):
    """Own the installed seed withholding behavior."""

    def withholding(self, year: int) -> None:
        """Capture independent withholding items while retaining explicit refusals."""
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
