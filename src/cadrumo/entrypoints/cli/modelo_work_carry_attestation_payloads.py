"""Typed JSON payload for the command that states no earlier-ejercicio carry is pending.

This module uses :class:`OutputSchema`, the declared output contract.
"""

from __future__ import annotations

from ...core.identity.bucket import BucketId
from ...core.json_contract import OutputSchema


class PriorCarryPayload(OutputSchema):
    """One carry a statement answers and what the statement did to it."""

    binding_id: str
    #: The amount stated for the carry, written like ``1234.56``; ``None`` when it is stated as nothing pending.
    amount: str | None = None
    effect_words: str


class PriorCarryStatementPayload(OutputSchema):
    """One statement the declaration's form serves, in the words it serves it, and the carries it answers."""

    family: str
    action_words: str
    statement_words: str
    effect_words: str
    binding_ids: list[str]
    carries: list[PriorCarryPayload]


class WorkAttestPriorCarriesResult(OutputSchema):
    """JSON envelope for ``aeat app modelo work attest-prior-carries``.

    ``applied`` is ``False`` when the command only showed the statement and its
    check because it was not confirmed; nothing was stated then.
    """

    bucket_id: BucketId
    work_unit_id: str
    modelo: str
    filing_year: int
    applied: bool
    statements: list[PriorCarryStatementPayload]
    findings: list[str]
    receipt_id: str | None = None
    calculation_revision_id: str | None = None


__all__ = ["PriorCarryPayload", "PriorCarryStatementPayload", "WorkAttestPriorCarriesResult"]
