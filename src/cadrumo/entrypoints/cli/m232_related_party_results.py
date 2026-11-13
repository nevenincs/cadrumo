"""Typed JSON payloads for the Modelo 232 related-party statement CLI.

This module uses :class:`OutputSchema`, the declared output contract. Every
payload is the operator's own statement; none names a counterparty's tax
identifier.
"""

from __future__ import annotations

from ...core.identity.bucket import BucketId
from ...core.json_contract import OutputSchema


class Modelo232StatedPayload(OutputSchema):
    """What every stated payload carries: its ejercicio, state and the revision it is stored at."""

    ejercicio: int
    state: str
    state_label: str
    stated_at: str
    withdrawn_at: str | None = None
    revision_id: str


class Modelo232OperationPayload(Modelo232StatedPayload):
    """One stated related-party or tax-haven operation."""

    operation_id: str
    operation_kind: str
    operation_kind_label: str
    counterparty_name: str
    counterparty_country: str
    tipo_vinculacion: str | None = None
    tipo_operacion: str | None = None
    valuation_method: str | None = None
    direction: str | None = None
    direction_label: str | None = None
    specific_operation: bool
    amount_eur: str
    exclusion: str | None = None
    exclusion_label: str | None = None
    description: str | None = None
    participation_percent: str | None = None
    parent_name: str | None = None


class Modelo232NoneStatementPayload(Modelo232StatedPayload):
    """One statement that the ejercicio had no related-party and no tax-haven operations."""

    statement_id: str
    note: str


class Modelo232TurnoverStatementPayload(Modelo232StatedPayload):
    """One statement of the ejercicio's cifra de negocios and its source."""

    statement_id: str
    turnover_eur: str
    source: str
    source_label: str
    source_reference: str


class Modelo232GroundPayload(OutputSchema):
    """What one art. 2 ground shows."""

    ground: str
    ground_label: str
    state: str
    state_label: str
    largest_total_eur: str | None = None
    limit_eur: str | None = None


class Modelo232VerdictPayload(OutputSchema):
    """What the stated records decide about Modelo 232 for the ejercicio."""

    obligation: str
    obligation_label: str
    basis: str
    basis_label: str
    grounds: list[Modelo232GroundPayload]
    counted_operations: int
    excluded_operations: int
    excluded_total_eur: str
    turnover_eur: str | None = None
    turnover_source: str | None = None
    note: str | None = None


class Modelo232RelatedPartyListResult(OutputSchema):
    """JSON envelope for ``aeat app ledger operaciones-vinculadas list``."""

    bucket_id: BucketId
    ejercicio: int
    guard_revision_id: str
    operations: list[Modelo232OperationPayload]
    none_statements: list[Modelo232NoneStatementPayload]
    turnover_statements: list[Modelo232TurnoverStatementPayload]
    verdict: Modelo232VerdictPayload | None = None


class Modelo232OperationResult(OutputSchema):
    """JSON envelope for ``state-operation`` and ``withdraw-operation``."""

    bucket_id: BucketId
    operation: Modelo232OperationPayload


class Modelo232NoneStatementResult(OutputSchema):
    """JSON envelope for ``state-none`` and ``withdraw-none``."""

    bucket_id: BucketId
    none_statement: Modelo232NoneStatementPayload


class Modelo232TurnoverStatementResult(OutputSchema):
    """JSON envelope for ``state-turnover`` and ``withdraw-turnover``."""

    bucket_id: BucketId
    turnover_statement: Modelo232TurnoverStatementPayload


__all__ = [
    "Modelo232GroundPayload",
    "Modelo232NoneStatementPayload",
    "Modelo232NoneStatementResult",
    "Modelo232OperationPayload",
    "Modelo232OperationResult",
    "Modelo232RelatedPartyListResult",
    "Modelo232StatedPayload",
    "Modelo232TurnoverStatementPayload",
    "Modelo232TurnoverStatementResult",
    "Modelo232VerdictPayload",
]
