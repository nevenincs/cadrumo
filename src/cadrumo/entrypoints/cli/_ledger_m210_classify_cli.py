"""Explicit Modelo 210 income classification options for ``ledger classify``.

The generic classify command owns public routing and patch persistence. This
module owns only the M210-specific option shape and turns a complete operator
selection into the typed transaction classification consumed by the IRNR ledger
projection. It deliberately does not infer a M210 code from generic categories;
the active :class:`TransactionCatalogueRepository` supplies the selected
transaction.
"""

from __future__ import annotations

from dataclasses import dataclass

from ...core.i18n.render import tr
from .common import bad


@dataclass(frozen=True, slots=True)
class M210LedgerClassifyOptions:
    """Raw M210 options received by the public ``ledger classify`` command."""

    tipo_renta_code: str | None
    gross_income_amount: str | None
    applicable_rate: str | None
    payer_mode: str | None
    payer_id: str | None
    asset_or_right_id: str | None

    @property
    def requested(self) -> bool:
        """Return whether the operator supplied any explicit M210 option."""
        return any(
            value is not None
            for value in (
                self.tipo_renta_code,
                self.gross_income_amount,
                self.applicable_rate,
                self.payer_mode,
                self.payer_id,
                self.asset_or_right_id,
            )
        )

    def refuse_non_direct_routes(
        self,
        *,
        llm_requested: bool,
        read_evidence: bool,
        saturate: bool,
        file: str | None,
        auto_split: bool,
    ) -> None:
        """Keep explicit M210 evidence separate from LLM and CSV classification."""
        if not self.requested:
            return
        if llm_requested or read_evidence or saturate or auto_split:
            raise bad(tr("cli.ledger.classify.m210_explicit_direct_only"))
        if file is not None:
            raise bad(tr("cli.ledger.classify.m210_explicit_direct_only"))


__all__ = [
    "M210LedgerClassifyOptions",
]
