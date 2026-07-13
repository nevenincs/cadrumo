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
from typing import Annotated

import typer
from pydantic import ValidationError

from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ...core import M210PayerMode
from ...core.i18n import tr
from ...domain.transactions import M210IncomeClassification, TransactionDirection, TransactionValidationError
from ._common import _bad
from ._ledger_support import _ledger_transaction_validation_bad, _parse_decimal

M210TipoRentaCodeOpt = Annotated[
    str | None,
    typer.Option("--m210-tipo-renta-code", help=tr("cli.ledger.classify.m210_tipo_renta_code_help")),
]
M210GrossIncomeAmountOpt = Annotated[
    str | None,
    typer.Option(
        "--m210-gross-income-amount",
        help=tr("cli.ledger.classify.m210_gross_income_amount_help"),
    ),
]
M210ApplicableRateOpt = Annotated[
    str | None,
    typer.Option("--m210-applicable-rate", help=tr("cli.ledger.classify.m210_applicable_rate_help")),
]
M210PayerModeOpt = Annotated[
    M210PayerMode | None,
    typer.Option("--m210-payer-mode", help=tr("cli.ledger.classify.m210_payer_mode_help")),
]
M210PayerIdOpt = Annotated[
    str | None,
    typer.Option("--m210-payer-id", help=tr("cli.ledger.classify.m210_payer_id_help")),
]
M210AssetOrRightIdOpt = Annotated[
    str | None,
    typer.Option("--m210-asset-or-right-id", help=tr("cli.ledger.classify.m210_asset_or_right_id_help")),
]


@dataclass(frozen=True, slots=True)
class M210LedgerClassifyOptions:
    """Raw M210 options received by the public ``ledger classify`` command."""

    tipo_renta_code: str | None
    gross_income_amount: str | None
    applicable_rate: str | None
    payer_mode: M210PayerMode | None
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
        from_csv: str | None,
        auto_split: bool,
    ) -> None:
        """Keep explicit M210 evidence separate from LLM and CSV classification."""
        if not self.requested:
            return
        if llm_requested or read_evidence or saturate or auto_split:
            raise _bad(tr("cli.ledger.classify.m210_explicit_direct_only"))
        if from_csv is not None:
            raise _bad(tr("cli.ledger.classify.m210_explicit_direct_only"))

    def to_income_classification(
        self,
        *,
        transaction_repository: TransactionCatalogueRepository,
        transaction_id: str,
    ) -> M210IncomeClassification | None:
        """Build the explicit typed classification after direct-route validation.

        Args:
            transaction_repository: The active
                :class:`TransactionCatalogueRepository` used to load the transaction.
            transaction_id: Identifier of the incoming transaction to classify.

        Returns:
            The explicit M210 classification, or ``None`` when no M210 option
            was supplied.

        Raises:
            typer.BadParameter: If options are incomplete or invalid, or the
                selected transaction is absent or not incoming.
        """
        if not self.requested:
            return None
        required_values = (
            self.tipo_renta_code,
            self.gross_income_amount,
            self.applicable_rate,
            self.payer_mode,
        )
        if any(value is None for value in required_values):
            raise _bad(tr("cli.ledger.classify.m210_required_options"))
        transaction = transaction_repository.load().get(transaction_id)
        if transaction is None or transaction.direction is not TransactionDirection.INCOMING:
            raise _bad(tr("cli.ledger.classify.m210_incoming_only"))
        try:
            return M210IncomeClassification(
                official_tipo_renta_code=self.tipo_renta_code,
                gross_income_amount=_parse_decimal(self.gross_income_amount, label="m210-gross-income-amount"),
                applicable_rate=_parse_decimal(self.applicable_rate, label="m210-applicable-rate"),
                payer_mode=self.payer_mode,
                payer_id=self.payer_id,
                asset_or_right_id=self.asset_or_right_id,
            )
        except (ValidationError, TransactionValidationError) as exc:
            raise _ledger_transaction_validation_bad(exc) from exc


__all__ = [
    "M210ApplicableRateOpt",
    "M210AssetOrRightIdOpt",
    "M210GrossIncomeAmountOpt",
    "M210LedgerClassifyOptions",
    "M210PayerIdOpt",
    "M210PayerModeOpt",
    "M210TipoRentaCodeOpt",
]
