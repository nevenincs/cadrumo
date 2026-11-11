"""Native encrypted-profile acceptance for ledger rule add/list/apply."""

from __future__ import annotations

import json
import sys
import time
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path

import pytest
from click.testing import Result
from pydantic import BaseModel

from cadrumo.adapters.persistence.profile.ledger_classification_rules import LedgerClassificationRuleRepository
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.application.ledger.action_ports import LedgerActionPorts
from cadrumo.application.ledger.actions_classification import add_classification_rule
from cadrumo.application.ledger.rule_contracts import LedgerRuleRowProjection
from cadrumo.application.user_profile.login_session import authenticate_profile_for_invocation, resolve_login_target
from cadrumo.core.decimal.formatting import format_decimal
from cadrumo.domain.buckets.event import (
    BucketEvent,
    BucketEventHistoryCatalogue,
    BucketEventObjectType,
    BucketEventType,
)
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.transactions.classification_rule import LedgerClassificationRule
from cadrumo.domain.transactions.enums import BusinessClassification
from cadrumo.domain.transactions.models import Transaction
from cadrumo.entrypoints.cli.ledger_rule_results import (
    RuleAddResult,
    RuleApplyAppliedPayload,
    RuleApplyMatchPayload,
    RuleApplyResult,
    RuleListResult,
)
from cadrumo.entrypoints.ledger_action_composition import compose_ledger_action_ports
from cadrumo.entrypoints.tests.ledger_rule_operation_test_support import assert_canonical_ledger_rule_update
from cadrumo.tests.cli_envelope import unwrap_cli_result

from ...native_commands.runtime_profile_cli_fixture import NativeCliProfileFixture, native_cli_profile_scope
from ...native_profile_facts import native_general_iva_facts
from .machine_secret_pipe import machine_secret_descriptor_option
from .profile_cli_support import invoke_native_profile_revealing

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]

_PROFILE_FACTS = native_general_iva_facts()
_ACTOR = "native-rule-journey"
_CATEGORY = "material_oficina"


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


def _seed_transaction(profile: NativeCliProfileFixture, bucket_id: str, description: str) -> str:
    """Add the unclassified outgoing transaction that the rule is expected to match."""
    added_transaction = invoke_native_profile_revealing(
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
    return transaction_id


def _add_rule_and_read_back(
    profile: NativeCliProfileFixture, pattern: str, operation: PinnedAuthorityOperation
) -> tuple[LedgerClassificationRule, tuple[LedgerClassificationRule, ...]]:
    """The added rule equals the one the canonical repository stores."""
    rule_add = invoke_native_profile_revealing(
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

    bucket_id, _, rule_repository = _canonical_ports(profile, operation=operation)
    assert profile.label is not None
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
    return stored_rule, rules_after_add


def _assert_rule_list_matches_repository(profile: NativeCliProfileFixture, operation: PinnedAuthorityOperation) -> None:
    listed = invoke_native_profile_revealing(profile, "app", "ledger", "rule", "list")
    assert listed.exit_code == 0, listed.output
    list_result = _typed_payload(RuleListResult, listed)
    bucket_id, _, rule_repository = _canonical_ports(profile, operation=operation)
    assert profile.label is not None
    assert bucket_id == str(resolve_login_target(profile.label).bucket_id)
    expected_rows = tuple(LedgerRuleRowProjection.from_rule(rule) for rule in rule_repository.list_rules())
    assert len(expected_rows) == 1
    expected_list_result = RuleListResult.model_validate(
        {"rules": [row.model_dump(mode="python") for row in expected_rows]}
    )
    assert list_result == expected_list_result


def _assert_dry_run_is_read_only(
    profile: NativeCliProfileFixture,
    operation: PinnedAuthorityOperation,
    *,
    transaction_id: str,
    description: str,
    stored_rule: LedgerClassificationRule,
    rules_after_add: tuple[LedgerClassificationRule, ...],
) -> tuple[Transaction, BucketEventHistoryCatalogue]:
    """The preview names the match but leaves the transaction, history and rules unchanged."""
    _, ports, _ = _canonical_ports(profile, operation=operation)
    transaction_before_preview = ports.transaction_repository.load().get(transaction_id)
    assert transaction_before_preview is not None
    assert transaction_before_preview.business_classification is BusinessClassification.NOT_YET_PROCESSED
    history_before_preview = ports.bucket_event_repository.load()

    preview = invoke_native_profile_revealing(profile, "app", "ledger", "rule", "apply", "--dry-run", "--actor", _ACTOR)
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

    _, ports, rule_repository = _canonical_ports(profile, operation=operation)
    transaction_after_preview = ports.transaction_repository.load().get(transaction_id)
    assert transaction_after_preview == transaction_before_preview
    history_after_preview = ports.bucket_event_repository.load()
    dry_run_additions = _added_events(history_before_preview.events, history_after_preview.events)
    assert not dry_run_additions
    assert rule_repository.list_rules() == rules_after_add
    return transaction_before_preview, history_after_preview


def _assert_apply_classifies_with_history(
    profile: NativeCliProfileFixture,
    operation: PinnedAuthorityOperation,
    *,
    transaction_id: str,
    stored_rule: LedgerClassificationRule,
    rules_after_add: tuple[LedgerClassificationRule, ...],
    transaction_before_preview: Transaction,
    history_after_preview: BucketEventHistoryCatalogue,
) -> None:
    """Applying classifies once, appends exactly one classification event and keeps the rules."""
    apply_result_raw = invoke_native_profile_revealing(profile, "app", "ledger", "rule", "apply", "--actor", _ACTOR)
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

    bucket_id, ports, rule_repository = _canonical_ports(profile, operation=operation)
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
    assert not activation_events
    assert len(live_additions) == 1
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

        transaction_id = _seed_transaction(profile, bucket_id, description)
        stored_rule, rules_after_add = _add_rule_and_read_back(profile, pattern, authority_operation)
        _assert_rule_list_matches_repository(profile, authority_operation)
        transaction_before_preview, history_after_preview = _assert_dry_run_is_read_only(
            profile,
            authority_operation,
            transaction_id=transaction_id,
            description=description,
            stored_rule=stored_rule,
            rules_after_add=rules_after_add,
        )
        _assert_apply_classifies_with_history(
            profile,
            authority_operation,
            transaction_id=transaction_id,
            stored_rule=stored_rule,
            rules_after_add=rules_after_add,
            transaction_before_preview=transaction_before_preview,
            history_after_preview=history_after_preview,
        )


def test_native_catastrophic_pattern_is_answered_typed_by_the_real_worker_on_trial_and_apply(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A planted catastrophic pattern reaches the real worker and comes back typed, in bounded time, unwritten."""
    catastrophic = "(a+)+$"
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="native-ledger-rule-overrun", facts=_PROFILE_FACTS)
        assert profile.label is not None
        bucket_id = str(resolve_login_target(profile.label).bucket_id)
        transaction_id = _seed_transaction(profile, bucket_id, "a" * 27 + "!")

        started = time.monotonic()
        trial = invoke_native_profile_revealing(
            profile,
            "app",
            "ledger",
            "rule",
            "trial",
            "--transaction-id",
            transaction_id,
            *machine_secret_descriptor_option({"description_pattern": catastrophic}),
        )
        trial_seconds = time.monotonic() - started
        assert trial.exit_code == 0, trial.output
        assert unwrap_cli_result(trial) == {"outcome": "overrun", "hits": [], "pending": []}
        assert trial_seconds < 15

        refused_add = invoke_native_profile_revealing(
            profile,
            "app",
            "ledger",
            "rule",
            "add",
            "--description-pattern",
            catastrophic,
            "--classification",
            "BUSINESS",
            "--category-id",
            _CATEGORY,
            "--priority",
            "7",
            "--actor",
            _ACTOR,
        )
        assert refused_add.exit_code != 0, refused_add.output
        assert "REFUSED_CLI_VALIDATION_BOUNDARY" in refused_add.output
        _, ports, rule_repository = _canonical_ports(profile, operation=authority_operation)
        assert rule_repository.list_rules() == ()

        # A rule stored before the add door bounded its pattern still meets apply, which must answer it typed.
        stored_rule = add_classification_rule(
            bucket_id=bucket_id,
            description_pattern=catastrophic,
            classification=BusinessClassification.BUSINESS,
            category_id=_CATEGORY,
            priority=7,
            actor=_ACTOR,
            rule_repository=rule_repository,
        )
        rules_after_add = rule_repository.list_rules()
        assert rules_after_add == (stored_rule,)
        transaction_before = ports.transaction_repository.load().get(transaction_id)
        history_before = ports.bucket_event_repository.load()

        started = time.monotonic()
        refused = invoke_native_profile_revealing(profile, "app", "ledger", "rule", "apply", "--actor", _ACTOR)
        apply_seconds = time.monotonic() - started
        assert refused.exit_code != 0, refused.output
        assert stored_rule.rule_id in refused.output
        assert apply_seconds < 15

        _, ports, rule_repository = _canonical_ports(profile, operation=authority_operation)
        assert ports.transaction_repository.load().get(transaction_id) == transaction_before
        assert ports.bucket_event_repository.load().events == history_before.events
        assert rule_repository.list_rules() == rules_after_add

        # The worker answers the next operation at once: nothing of the overrun is left running in it.
        started = time.monotonic()
        listed = invoke_native_profile_revealing(profile, "app", "ledger", "rule", "list")
        assert listed.exit_code == 0, listed.output
        assert time.monotonic() - started < 5
