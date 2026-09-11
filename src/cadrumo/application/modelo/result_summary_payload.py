"""Application-owned result-summary payload contract.

The result-summary row is a typed projection of the application calculation
summary.  Display adapters may add transport envelopes, but they do not own a
second declaration of this row.
"""

from __future__ import annotations

from ...core.casilla_id import CasillaId
from ...core.json_contract import OutputSchema
from .result_summary import ResultSummaryRole


class ResultSummaryRowPayload(OutputSchema):
    """One headline result-summary row selected from a calculation revision."""

    role: ResultSummaryRole
    casilla_id: CasillaId
    value: str
    label: str


__all__ = ["ResultSummaryRowPayload"]
