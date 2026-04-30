"""Workflow inputs provider backed by the transaction catalogue."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ...deadlines import AutonomoProfile
from ..transactions._repository import TransactionCatalogueRepository
from ._models import CasillaAggregation
from ._service import aggregate_catalogue


class FinancialFilingInputsProvider:
    """Concrete workflow inputs provider for T6 financial aggregation."""

    def __init__(self, *, repository: TransactionCatalogueRepository) -> None:
        self._repository = repository

    def load_aggregation(
        self,
        *,
        modelo: str,
        period: str,
    ) -> CasillaAggregation:
        """Return the full casilla ledger for ``modelo`` and ``period``."""

        return aggregate_catalogue(self._repository.load(), modelo=modelo, period=period)

    def has_catalogue(self) -> bool:
        """Return whether a persisted transaction catalogue exists."""

        return self._repository.envelope_path.exists()

    def load_inputs(
        self,
        *,
        modelo: str,
        period: str,
        profile: AutonomoProfile,
    ) -> Mapping[str, Decimal]:
        """Return Decimal casilla values for the workflow draft builder."""

        del profile
        return self.load_aggregation(modelo=modelo, period=period).casilla_values


__all__ = ["FinancialFilingInputsProvider"]
