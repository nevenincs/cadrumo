"""Encrypted-boundary proofs for ledger classification-rule persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from .....domain.transactions import BusinessClassification, LedgerClassificationRule
from .....tests.secure_sql import (
    isolated_runtime_profile,
    mutate_encrypted_secure_object_json,
    read_db_at_rest_bytes,
)
from ...storage.sql import SecureObjectRow
from ..ledger_classification_rules import LedgerClassificationRuleRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def _rule(
    *,
    pattern: str,
    classification: BusinessClassification,
    priority: int,
    created_at: datetime,
) -> LedgerClassificationRule:
    return LedgerClassificationRule.create(
        description_pattern=pattern,
        classification=classification,
        category_id="software_suscripcion",
        priority=priority,
        actor="operator-sensitive-rule-author",
        created_at=created_at,
    )


def test_rules_roundtrip_strictly_in_precedence_order_and_remain_encrypted(tmp_path: Path) -> None:
    """Every non-default rule fact survives while sensitive text stays off disk."""
    later_high_priority = _rule(
        pattern="SECRET-HIGH-PRIORITY-VENDOR",
        classification=BusinessClassification.BUSINESS,
        priority=1,
        created_at=datetime(2026, 8, 2, 9, 0, tzinfo=UTC),
    )
    earlier_low_priority = _rule(
        pattern="SECRET-LOW-PRIORITY-VENDOR",
        classification=BusinessClassification.PERSONAL,
        priority=90,
        created_at=datetime(2026, 8, 1, 9, 0, tzinfo=UTC),
    )

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repository = LedgerClassificationRuleRepository(objects=profile.repository)
        repository.save(earlier_low_priority)
        repository.save(later_high_priority)

        loaded = LedgerClassificationRuleRepository(objects=profile.repository).list_rules()
        at_rest = read_db_at_rest_bytes(profile.paths.database_file)

    assert loaded == (later_high_priority, earlier_low_priority)
    assert b"SECRET-HIGH-PRIORITY-VENDOR" not in at_rest
    assert b"operator-sensitive-rule-author" not in at_rest
    assert b"software_suscripcion" not in at_rest


def test_rule_load_refuses_a_tampered_invalid_pattern(tmp_path: Path) -> None:
    """The real encrypted load path validates rather than laundering tampered facts."""
    original = _rule(
        pattern="VALID-PERSISTED-PATTERN",
        classification=BusinessClassification.BUSINESS,
        priority=7,
        created_at=datetime(2026, 8, 3, 10, 0, tzinfo=UTC),
    )

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repository = LedgerClassificationRuleRepository(objects=profile.repository)
        repository.save(original)
        statement = select(SecureObjectRow).where(
            SecureObjectRow.namespace == repository.namespace,
            SecureObjectRow.object_key == original.rule_id,
        )

        def invalidate_pattern(envelope: dict[str, object]) -> None:
            payload = envelope["payload"]
            assert isinstance(payload, dict)
            assert payload["description_pattern"] == original.description_pattern
            payload["description_pattern"] = "["

        mutate_encrypted_secure_object_json(
            profile.repository._engine,
            row_statement=statement,
            mutate=invalidate_pattern,
        )

        with pytest.raises(ValidationError):
            tuple(repository.iter_records())
