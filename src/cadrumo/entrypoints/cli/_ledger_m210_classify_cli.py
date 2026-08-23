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

from pydantic import ValidationError

from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ...core import M210PayerMode
from ...core.i18n import tr
from ...domain.transactions import M210IncomeClassification, TransactionDirection, TransactionValidationError
from ._common import _bad
from ._ledger_support import _ledger_transaction_validation_no_recovery, _ledger_validation_bad, _parse_decimal


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
            raise _bad(tr("cli.ledger.classify.m210_explicit_direct_only"))
        if file is not None:
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
        required = self._require_complete_options()
        self._require_incoming_transaction(
            transaction_repository=transaction_repository,
            transaction_id=transaction_id,
        )
        return self._build_classification(required)

    def _require_complete_options(self) -> tuple[str, str, str, M210PayerMode]:
        """Return the four required M210 options, refusing an incomplete selection."""
        tipo_renta_code = self.tipo_renta_code
        gross_income_amount = self.gross_income_amount
        applicable_rate = self.applicable_rate
        payer_mode = self.payer_mode
        if tipo_renta_code is None or gross_income_amount is None or applicable_rate is None or payer_mode is None:
            raise _bad(tr("cli.ledger.classify.m210_required_options"))
        return tipo_renta_code, gross_income_amount, applicable_rate, payer_mode

    @staticmethod
    def _require_incoming_transaction(
        *,
        transaction_repository: TransactionCatalogueRepository,
        transaction_id: str,
    ) -> None:
        """Refuse when the selected transaction is absent or not incoming."""
        transaction = transaction_repository.load().get(transaction_id)
        if transaction is None or transaction.direction is not TransactionDirection.INCOMING:
            raise _bad(tr("cli.ledger.classify.m210_incoming_only"))

    def _build_classification(
        self,
        required: tuple[str, str, str, M210PayerMode],
    ) -> M210IncomeClassification:
        """Parse the numeric options and build the typed classification."""
        tipo_renta_code, gross_income_amount, applicable_rate, payer_mode = required
        try:
            parsed_gross_income_amount = _parse_decimal(
                gross_income_amount,
                label="m210-gross-income-amount",
            )
            parsed_applicable_rate = _parse_decimal(applicable_rate, label="m210-applicable-rate")
            if parsed_gross_income_amount is None or parsed_applicable_rate is None:
                raise _bad(tr("cli.ledger.classify.m210_required_options"))
            return M210IncomeClassification(
                official_tipo_renta_code=tipo_renta_code,
                gross_income_amount=parsed_gross_income_amount,
                applicable_rate=parsed_applicable_rate,
                payer_mode=payer_mode,
                payer_id=self.payer_id,
                asset_or_right_id=self.asset_or_right_id,
            )
        except ValidationError as exc:
            raise _ledger_validation_bad(exc) from exc
        except TransactionValidationError as exc:
            raise _ledger_transaction_validation_no_recovery(exc) from None


__all__ = [
    "M210LedgerClassifyOptions",
]
