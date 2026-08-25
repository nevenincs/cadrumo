"""Profile-scoped encrypted repository for ledger classification rules.

:class:`LedgerClassificationRule` records are stored through
:class:`~cadrumo.adapters.persistence.storage.SecureBoundRepository` at the
:class:`~cadrumo.adapters.persistence.storage.SensitivityClass` declared by
:data:`cadrumo.adapters.persistence.storage.LEDGER_CLASSIFICATION_RULES_NAMESPACE`.
The bound repository serialises each rule through an
:class:`~cadrumo.adapters.persistence.storage.Envelope`, so the stored rule
pattern, actor, category, and classification stay encrypted at rest.

See Also:
    :class:`LedgerClassificationRule`
        Content-addressed payload model persisted by this repository.
    :func:`cadrumo.application.ledger.actions_classification.add_classification_rule`
        Application entry point that creates and saves a rule.
    :func:`cadrumo.application.ledger.actions_classification.apply_classification_rules`
        Application entry point that evaluates persisted rules over active
        ledger transactions.
"""

from __future__ import annotations

from typing import ClassVar, override

from pydantic import BaseModel

from ...adapters.persistence.storage import (
    LEDGER_CLASSIFICATION_RULES_NAMESPACE,
    SecureBoundRepository,
    SensitivityClass,
)
from ...domain.transactions import LedgerClassificationRule


class LedgerClassificationRuleRepository(SecureBoundRepository[LedgerClassificationRule]):
    """Encrypted profile-local store of :class:`LedgerClassificationRule` payloads.

    The namespace, sensitivity, schema version, and object-key contract come
    from
    :data:`cadrumo.adapters.persistence.storage.LEDGER_CLASSIFICATION_RULES_NAMESPACE`.
    Rules are sorted by ``(priority, created_at)`` ascending so that
    lower-priority-number rules (higher precedence) are evaluated first.
    Among same-priority rules the earliest-created rule wins.
    """

    namespace: ClassVar[str] = LEDGER_CLASSIFICATION_RULES_NAMESPACE.namespace
    sensitivity: ClassVar[SensitivityClass] = LEDGER_CLASSIFICATION_RULES_NAMESPACE.sensitivity
    schema_version: ClassVar[int] = LEDGER_CLASSIFICATION_RULES_NAMESPACE.schema_version
    payload_type: ClassVar[type[BaseModel]] = LedgerClassificationRule

    @override
    def extract_identifier(self, payload: LedgerClassificationRule) -> str:
        return payload.rule_id

    def list_rules(self) -> tuple[LedgerClassificationRule, ...]:
        """Return all stored rules in application order: (priority asc, created_at asc).

        Each element is a :class:`LedgerClassificationRule`.
        """
        return tuple(sorted(self.iter_records(), key=lambda r: (r.priority, r.created_at)))


__all__ = ["LedgerClassificationRuleRepository"]
