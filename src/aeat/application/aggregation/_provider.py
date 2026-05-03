"""Workflow inputs provider backed by the persisted transaction catalogue.

Bridges the :class:`aeat.domain.transactions.TransactionCatalogueRepository`
to :class:`aeat.application.filing` consumers by aggregating classified
transactions into casilla totals on demand via
:func:`aeat.application.aggregation.aggregate_catalogue`.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ...core.logging import get_logger
from ...domain.deadlines import AutonomoProfile
from ...domain.transactions import TransactionCatalogueRepository
from ._models import CasillaAggregation
from ._service import aggregate_catalogue

_logger = get_logger(__name__)


class FinancialFilingInputsProvider:
    """Concrete workflow inputs provider for financial transaction aggregation.

    Loads the catalogue from a
    :class:`aeat.domain.transactions.TransactionCatalogueRepository`
    and delegates aggregation to
    :func:`aeat.application.aggregation.aggregate_catalogue`.
    """

    def __init__(self, *, repository: TransactionCatalogueRepository) -> None:
        """Bind the provider to the persisted transaction catalogue.

        Args:
            repository: Repository over the encrypted transaction
                catalogue envelope.
        """
        self._repository = repository

    def load_aggregation(
        self,
        *,
        modelo: str,
        period: str,
    ) -> CasillaAggregation:
        """Return the full casilla ledger for ``modelo`` and ``period``.

        Args:
            modelo: Modelo identifier (e.g. ``"130"``).
            period: Period token accepted by
                :class:`aeat.application.aggregation.Period`.

        Returns:
            The :class:`CasillaAggregation` produced by
            :func:`aeat.application.aggregation.aggregate_catalogue`.
        """

        return aggregate_catalogue(self._repository.load(), modelo=modelo, period=period)

    def has_catalogue(self) -> bool:
        """Return whether a persisted transaction catalogue exists on disk."""
        exists = self._repository.envelope_path.exists()
        if not exists:
            _logger.debug("transaction catalogue not found at %s", self._repository.envelope_path)
        return exists

    def load_inputs(
        self,
        *,
        modelo: str,
        period: str,
        profile: AutonomoProfile,
    ) -> Mapping[str, Decimal]:
        """Return :class:`~decimal.Decimal` casilla values for the draft builder.

        Args:
            modelo: Modelo identifier.
            period: Period token.
            profile: Operator profile (presently ignored; reserved for
                future per-profile filtering).

        Returns:
            A frozen mapping of casilla code to summed
            :class:`~decimal.Decimal` value.
        """

        del profile
        return self.load_aggregation(modelo=modelo, period=period).casilla_values


__all__ = ["FinancialFilingInputsProvider"]
