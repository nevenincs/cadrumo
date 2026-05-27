"""Profile-scoped encrypted repository for ledger classification rules."""

from __future__ import annotations

from typing import ClassVar

from ...adapters.persistence.storage import LEDGER_CLASSIFICATION_RULES_NAMESPACE, SensitivityClass
from ...adapters.persistence.storage.envelope._secure_repository import SecureBoundRepository
from ...domain.transactions._classification_rule import LedgerClassificationRule


class LedgerClassificationRuleRepository(SecureBoundRepository[LedgerClassificationRule]):
    """Encrypted profile-local store of ledger classification rules.

    Rules are sorted by ``(priority, created_at)`` ascending so that
    lower-priority-number rules (higher precedence) are evaluated first.
    Among same-priority rules the earliest-created rule wins.

    Follows the same pattern as ``IvaCompensationHistoryRepository``.
    """

    namespace: ClassVar[str] = LEDGER_CLASSIFICATION_RULES_NAMESPACE.namespace
    sensitivity: ClassVar[SensitivityClass] = LEDGER_CLASSIFICATION_RULES_NAMESPACE.sensitivity
    schema_version: ClassVar[int] = LEDGER_CLASSIFICATION_RULES_NAMESPACE.schema_version
    payload_type: ClassVar[type[LedgerClassificationRule]] = LedgerClassificationRule

    def extract_identifier(self, payload: LedgerClassificationRule) -> str:
        return payload.rule_id

    def list_rules(self) -> tuple[LedgerClassificationRule, ...]:
        """Return all stored rules in application order: (priority asc, created_at asc)."""

        return tuple(sorted(self.iter_records(), key=lambda r: (r.priority, r.created_at)))


__all__ = ["LedgerClassificationRuleRepository"]
