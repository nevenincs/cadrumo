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

import typer
from pydantic import ValidationError

from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ...core.i18n.render import tr
from ...core.irnr import M210PayerMode
from ...domain.transactions.errors import TransactionValidationError
from ...domain.transactions.m210_income_classification import M210IncomeClassification
from ._common import bad
from ._ledger_support import ledger_transaction_validation_no_recovery, ledger_validation_bad, parse_decimal_option


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

    def to_income_classification(
        self,
        *,
        transaction_repository: TransactionCatalogueRepository,
        transaction_id: str,
    ) -> M210IncomeClassification | None:
        """Parse the operator's options and hand them to the application resolver.

        Argv arrives as strings, so decimal parsing stays here; the completeness
        rule and the incoming-only rule belong to the declaration itself and are
        decided by the resolver.

        Args:
            transaction_repository: The active repository supplying the row.
            transaction_id: Identifier of the transaction to classify.

        Returns:
            The explicit M210 classification, or ``None`` when no M210 option
            was supplied.

        Raises:
            typer.BadParameter: If options are incomplete or invalid, or the
                selected transaction is absent or not incoming.
        """
        from ...application.ledger.m210_classification import resolve_m210_income_classification

        if not self.requested:
            return None
        try:
            gross_income_amount = parse_decimal_option(
                self.gross_income_amount,
                label="m210-gross-income-amount",
            )
            applicable_rate = parse_decimal_option(self.applicable_rate, label="m210-applicable-rate")
            return resolve_m210_income_classification(
                bucket_id=transaction_repository.bucket_id,
                transaction_id=transaction_id,
                tipo_renta_code=self.tipo_renta_code,
                gross_income_amount=gross_income_amount,
                applicable_rate=applicable_rate,
                payer_mode=self.payer_mode,
                payer_id=self.payer_id,
                asset_or_right_id=self.asset_or_right_id,
                transaction_repository=transaction_repository,
            )
        except ValidationError as exc:
            raise ledger_validation_bad(exc) from exc
        except TransactionValidationError as exc:
            raise _m210_refusal(exc) from exc


def _m210_refusal(exc: TransactionValidationError) -> typer.BadParameter | TransactionValidationError:
    """Map the resolver's refusal to the message naming what to fix.

    Discriminated on the context key the resolver sets for each case, so a
    partially answered declaration and a wrong-direction row do not collapse
    into one message an operator cannot act on.
    """
    context = getattr(exc, "context", None) or {}
    if "required_direction" in context:
        return bad(tr("cli.ledger.classify.m210_incoming_only"))
    if "missing" in context:
        return bad(tr("cli.ledger.classify.m210_required_options"))
    return ledger_transaction_validation_no_recovery(exc)


__all__ = [
    "M210LedgerClassifyOptions",
]
