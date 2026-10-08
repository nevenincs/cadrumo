"""Native encrypted-profile acceptance for ledger rule add/list/apply."""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path

import pytest
from click.testing import Result
from pydantic import BaseModel

from ....adapters.persistence.profile.ledger_classification_rules import LedgerClassificationRuleRepository
from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....application.ledger.action_ports import LedgerActionPorts
from ....application.ledger.rule_contracts import LedgerRuleRowProjection
from ....application.user_profile.login_session import authenticate_profile_for_invocation, resolve_login_target
from ....core.config import override_settings
from ....core.decimal.formatting import format_decimal
from ....domain.buckets.event import BucketEvent, BucketEventObjectType, BucketEventType
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.transactions.classification_rule import LedgerClassificationRule
from ....domain.transactions.enums import BusinessClassification
from ....tests.cli_envelope import unwrap_cli_result
from ...ledger_action_composition import compose_ledger_action_ports
from ...tests.ledger_rule_operation_test_support import assert_canonical_ledger_rule_update
from .._ledger_rule_payloads import (
    RuleAddResult,
    RuleApplyAppliedPayload,
    RuleApplyMatchPayload,
    RuleApplyResult,
    RuleListResult,
)
from .cli_runner import invoke_cached_cli
from .runtime_profile_cli_fixture import NativeCliProfileFixture, native_cli_profile_scope

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]

_PROFILE_FACTS = {
    "taxpayer_type.entity_type": "natural_person",
    "identity.name": "Native",
    "identity.surnames": "Rule Journey",
    "activities.description": "design",
    "censo.activity_start_date": "2025-01-01",
    "tax_residence.jurisdiction_scope": "common_regime",
    "iva.regime": "GENERAL",
    "iva.m303_regime_composition": "general",
    "iva.redeme_enrolled": "false",
    "iva.cash_accounting_regime_enrolled": "false",
    "iva.voluntary_sii_enrolled": "false",
    "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
}
_ACTOR = "native-rule-journey"
_CATEGORY = "material_oficina"


def _invoke(profile: NativeCliProfileFixture, *command: str) -> Result:
    """Run one command through the actual profile worker and CLI executable."""
    assert profile.label is not None
    close_active_bucket_session()
    with override_settings(cadrumo_cli_reveal_identifiers=True):
        result = invoke_cached_cli(
            (
                "--language",
                "en",
                "--format",
                "json",
                "--profile",
                profile.label,
                "--profile-secrets-stdin",
                *command,
            ),
            input=json.dumps({"profile_passphrase": profile.passphrase}),
        )
    assert profile.passphrase not in result.output
    return result


def _reauthenticate(
    profile: NativeCliProfileFixture,
    *,
    operation: PinnedAuthorityOperation,
) -> str:
    """Unlock the exact encrypted profile for a canonical readback."""
    assert profile.label is not None
    close_active_bucket_session()
    login = authenticate_profile_for_invocation(
        name=profile.label,
        passphrase_callback=lambda: profile.passphrase,
        profile_decode_context=operation.profile_decode_context(),
    )
    return login.bucket_id


def _canonical_ports(
    profile: NativeCliProfileFixture,
    *,
    operation: PinnedAuthorityOperation,
) -> tuple[str, LedgerActionPorts, LedgerClassificationRuleRepository]:
    bucket_id = _reauthenticate(profile, operation=operation)
    expected_bucket_id = str(resolve_login_target(profile.label or "").bucket_id)
    assert bucket_id == expected_bucket_id
    ports = compose_ledger_action_ports(bucket_id=bucket_id, operation=operation)
    return bucket_id, ports, LedgerClassificationRuleRepository(bucket_id=bucket_id)


def _added_events(before: Mapping[str, BucketEvent], after: Mapping[str, BucketEvent]) -> tuple[BucketEvent, ...]:
    """Keep the whole prior append-only history and return only later rows."""
    assert all(after.get(event_id) == event for event_id, event in before.items())
    return tuple(event for event_id, event in after.items() if event_id not in before)


def _typed_payload[ResultT: BaseModel](schema: type[ResultT], result: Result) -> ResultT:
    return schema.model_validate_json(json.dumps(unwrap_cli_result(result)))


def _assert_rule_matches_repository(
    actual: RuleAddResult,
    stored: LedgerClassificationRule,
) -> None:
    expected = RuleAddResult.model_validate(stored.model_dump(mode="python"))
    assert actual == expected
    assert actual.rule_id == stored.rule_id
    assert actual.description_pattern == stored.description_pattern
    assert actual.classification is stored.classification
    assert actual.category_id == stored.category_id
    assert actual.priority == stored.priority
    assert actual.actor == stored.actor
    assert actual.created_at == stored.created_at


def test_native_rule_add_list_dry_run_and_apply_preserve_encrypted_meaning(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Add/list a rule, prove preview is read-only, then verify real classification history."""
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="native-ledger-rule-journey", facts=_PROFILE_FACTS)
        assert profile.label is not None
        bucket_id = str(resolve_login_target(profile.label).bucket_id)
        description = f"Native Rule Matched Transaction {bucket_id.replace('-', '')}"
        pattern = f"^{description}$"

        added_transaction = _invoke(
            profile,
            "app",
            "ledger",
            "add",
            "--date",
            "2026-05-08",
            "--amount",
            "78.90",
            "--direction",
            "OUTGOING",
            "--description",
            description,
            "--actor",
            _ACTOR,
            "--idempotency-key",
            f"native-rule-seed-{bucket_id.replace('-', '')}",
        )
        assert added_transaction.exit_code == 0, added_transaction.output
        transaction_id = unwrap_cli_result(added_transaction)["transaction_id"]
        assert isinstance(transaction_id, str) and len(transaction_id) == 64

        rule_add = _invoke(
            profile,
            "app",
            "ledger",
            "rule",
            "add",
            "--description-pattern",
            pattern,
            "--classification",
            "BUSINESS",
            "--category-id",
            _CATEGORY,
            "--priority",
            "7",
            "--actor",
            _ACTOR,
        )
        assert rule_add.exit_code == 0, rule_add.output
        add_result = _typed_payload(RuleAddResult, rule_add)

        bucket_id, ports, rule_repository = _canonical_ports(profile, operation=authority_operation)
        assert bucket_id == str(resolve_login_target(profile.label).bucket_id)
        rules_after_add = rule_repository.list_rules()
        assert len(rules_after_add) == 1
        stored_rule = rules_after_add[0]
        _assert_rule_matches_repository(add_result, stored_rule)
        assert stored_rule.description_pattern == pattern
        assert stored_rule.classification is BusinessClassification.BUSINESS
        assert stored_rule.category_id == _CATEGORY
        assert stored_rule.priority == 7
        assert stored_rule.actor == _ACTOR

        listed = _invoke(profile, "app", "ledger", "rule", "list")
        assert listed.exit_code == 0, listed.output
        list_result = _typed_payload(RuleListResult, listed)
        bucket_id, ports, rule_repository = _canonical_ports(profile, operation=authority_operation)
        assert bucket_id == str(resolve_login_target(profile.label).bucket_id)
        expected_rows = tuple(LedgerRuleRowProjection.from_rule(rule) for rule in rule_repository.list_rules())
        assert len(expected_rows) == 1
        expected_list_result = RuleListResult.model_validate(
            {"rules": [row.model_dump(mode="python") for row in expected_rows]}
        )
        assert list_result == expected_list_result

        transaction_before_preview = ports.transaction_repository.load().get(transaction_id)
        assert transaction_before_preview is not None
        assert transaction_before_preview.business_classification is BusinessClassification.NOT_YET_PROCESSED
        history_before_preview = ports.bucket_event_repository.load()

        preview = _invoke(profile, "app", "ledger", "rule", "apply", "--dry-run", "--actor", _ACTOR)
        assert preview.exit_code == 0, preview.output
        preview_result = _typed_payload(RuleApplyResult, preview)
        assert preview_result == RuleApplyResult(
            dry_run=True,
            would_match=[
                RuleApplyMatchPayload(
                    transaction_id=transaction_id,
                    description=description,
                    matched_rule_id=stored_rule.rule_id,
                    classification=BusinessClassification.BUSINESS,
                )
            ],
            count=1,
        )

        bucket_id, ports, rule_repository = _canonical_ports(profile, operation=authority_operation)
        transaction_after_preview = ports.transaction_repository.load().get(transaction_id)
        assert transaction_after_preview == transaction_before_preview
        history_after_preview = ports.bucket_event_repository.load()
        dry_run_additions = _added_events(history_before_preview.events, history_after_preview.events)
        assert all(event.event_type is BucketEventType.PROFILE_ACTIVATED for event in dry_run_additions)
        assert rule_repository.list_rules() == rules_after_add

        apply_result_raw = _invoke(profile, "app", "ledger", "rule", "apply", "--actor", _ACTOR)
        assert apply_result_raw.exit_code == 0, apply_result_raw.output
        apply_result = _typed_payload(RuleApplyResult, apply_result_raw)
        assert apply_result == RuleApplyResult(
            rules_evaluated=1,
            transactions_scanned=1,
            matched=1,
            skipped_already_classified=0,
            no_match=0,
            applied=[
                RuleApplyAppliedPayload(
                    transaction_id=transaction_id,
                    matched_rule_id=stored_rule.rule_id,
                    classification=BusinessClassification.BUSINESS,
                )
            ],
        )

        bucket_id, ports, rule_repository = _canonical_ports(profile, operation=authority_operation)
        transaction_after_apply = ports.transaction_repository.load().get(transaction_id)
        assert transaction_after_apply is not None
        assert transaction_after_apply.transaction_id == transaction_before_preview.transaction_id
        assert transaction_after_apply.business_classification is BusinessClassification.BUSINESS
        assert transaction_after_apply.category_id == _CATEGORY
        assert transaction_after_apply.classified_by == f"rule:{stored_rule.rule_id}"
        assert transaction_after_apply.classification_reason == "aeat app ledger rule apply"
        assert transaction_after_apply.classification_confidence == Decimal("1")
        assert rule_repository.list_rules() == rules_after_add

        history_after_apply = ports.bucket_event_repository.load()
        live_additions = _added_events(history_after_preview.events, history_after_apply.events)
        activation_events = tuple(
            event for event in live_additions if event.event_type is BucketEventType.PROFILE_ACTIVATED
        )
        classification_events = tuple(
            event for event in live_additions if event.event_type is BucketEventType.LEDGER_TRANSACTION_CLASSIFIED
        )
        assert len(activation_events) == 1
        assert len(classification_events) == 1
        event = classification_events[0]
        assert (
            assert_canonical_ledger_rule_update(
                transaction_before_preview,
                transaction_after_apply,
                rule=stored_rule,
                actor=_ACTOR,
                occurred_at=event.occurred_at,
                ports=ports,
            )
            == classification_events
        )
        assert event.bucket_id == bucket_id
        assert event.object_type is BucketEventObjectType.LEDGER_TRANSACTION
        assert event.object_id == transaction_id
        assert event.actor == _ACTOR
        assert event.payload_version == 1
        assert dict(event.payload) == {
            "amount": format_decimal(transaction_before_preview.raw.amount),
            "category_id": _CATEGORY,
            "classification": BusinessClassification.BUSINESS.value,
            "currency": transaction_before_preview.raw.currency,
            "direction": transaction_before_preview.direction.value,
            "mutation_kind": "classification",
            "previous_transaction_id": transaction_id,
            "source_command": "aeat app ledger rule apply",
        }
