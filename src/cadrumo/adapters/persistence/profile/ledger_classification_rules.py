"""Encrypted persistence adapter for ledger classification rules."""

from __future__ import annotations

from typing import override

from ....application.ledger.rule_repository import ledger_classification_rule_object_key
from ....domain.transactions.classification_rule import LedgerClassificationRule
from ..storage._secure_object_namespaces import LEDGER_CLASSIFICATION_RULES_NAMESPACE
from ..storage.envelope._secure_repository import SecureBoundRepository


class LedgerClassificationRuleRepository(SecureBoundRepository[LedgerClassificationRule]):
    """Store profile-local rules through the governed encrypted namespace."""

    namespace = LEDGER_CLASSIFICATION_RULES_NAMESPACE.namespace
    sensitivity = LEDGER_CLASSIFICATION_RULES_NAMESPACE.sensitivity
    schema_version = LEDGER_CLASSIFICATION_RULES_NAMESPACE.schema_version
    payload_type = LedgerClassificationRule

    @override
    def extract_identifier(self, payload: LedgerClassificationRule) -> str:
        """Return the rule's content-addressed natural key."""
        return ledger_classification_rule_object_key(payload)

    def list_rules(self) -> tuple[LedgerClassificationRule, ...]:
        """Return rules in precedence order: priority, then creation time."""
        return tuple(sorted(self.iter_records(), key=lambda rule: (rule.priority, rule.created_at)))


__all__ = ["LedgerClassificationRuleRepository"]
