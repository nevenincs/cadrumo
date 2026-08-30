"""Application-owned persistence contract for ledger classification rules.

Rule creation, priority ordering, and first-match policy belong to the ledger
application surface. Encrypting those rules and selecting a concrete profile
store belong to the persistence adapter. This module therefore owns only the
repository operations the policy needs, their explicit bucket-scoped lifetime,
and the rule's natural object key.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Protocol

from ...domain.transactions.classification_rule import LedgerClassificationRule


def ledger_classification_rule_object_key(rule: LedgerClassificationRule) -> str:
    """Return the canonical natural key for one classification rule."""
    return rule.rule_id


class LedgerClassificationRuleRepositoryProtocol(Protocol):
    """Persistence operations required by classification-rule policy."""

    def save(self, payload: LedgerClassificationRule) -> None:
        """Persist one rule under its content-addressed identity."""
        ...

    def list_rules(self) -> tuple[LedgerClassificationRule, ...]:
        """Return rules in application precedence order."""
        ...


class LedgerClassificationRuleRepositoryFactory(Protocol):
    """Construct a classification-rule repository for one profile bucket."""

    def __call__(self, *, bucket_id: str) -> LedgerClassificationRuleRepositoryProtocol:
        """Return the encrypted repository bound to ``bucket_id``."""
        ...


_BOUND_LEDGER_CLASSIFICATION_RULE_REPOSITORY_FACTORY: ContextVar[LedgerClassificationRuleRepositoryFactory] = (
    ContextVar("cadrumo_ledger_classification_rule_repository_factory")
)


@contextmanager
def bind_ledger_classification_rule_repository_factory(
    factory: LedgerClassificationRuleRepositoryFactory,
) -> Generator[LedgerClassificationRuleRepositoryFactory]:
    """Bind one outward-composed classification-rule repository factory."""
    token = _BOUND_LEDGER_CLASSIFICATION_RULE_REPOSITORY_FACTORY.set(factory)
    try:
        yield factory
    finally:
        _BOUND_LEDGER_CLASSIFICATION_RULE_REPOSITORY_FACTORY.reset(token)


def ledger_classification_rule_repository(*, bucket_id: str) -> LedgerClassificationRuleRepositoryProtocol:
    """Resolve the explicitly composed repository for ``bucket_id``."""
    try:
        factory = _BOUND_LEDGER_CLASSIFICATION_RULE_REPOSITORY_FACTORY.get()
    except LookupError as error:
        raise RuntimeError("ledger classification-rule persistence has not been composed") from error
    return factory(bucket_id=bucket_id)


__all__ = [
    "LedgerClassificationRuleRepositoryFactory",
    "LedgerClassificationRuleRepositoryProtocol",
    "bind_ledger_classification_rule_repository_factory",
    "ledger_classification_rule_object_key",
    "ledger_classification_rule_repository",
]
