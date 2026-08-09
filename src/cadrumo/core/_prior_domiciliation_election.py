"""The operator's election for an earlier Modelo 303 direct debit.

This election describes AEAT's page-three ``X`` marker for a rectificativa.
It is deliberately independent from both the amendment kind and the payment
election for the return currently being filed: it changes neither the current
result disposition nor any account selection.
"""

from __future__ import annotations

from enum import StrEnum


class PriorDomiciliationElection(StrEnum):
    """Whether to retain or cancel/modify an eligible prior direct debit."""

    KEEP = "keep"
    CANCEL_OR_MODIFY = "cancel_or_modify"


__all__ = ["PriorDomiciliationElection"]
