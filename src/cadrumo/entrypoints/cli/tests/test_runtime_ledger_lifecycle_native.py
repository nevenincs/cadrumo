"""Native profile-worker acceptance for the four ledger lifecycle commands."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import cast

import pytest
from click.testing import Result
from pydantic import BaseModel

from ....adapters.persistence.profile.tests.remove_draft_revision_support import seed_revision_citing_transaction
from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from ....application.ledger.actions_common import blocking_modelo_references, build_manual_ledger_result
from ....application.ledger.actions_manual import ledger_transaction_result_payload
from ....application.user_profile.login_session import authenticate_profile_for_invocation, resolve_login_target
from ....core.config import override_settings
from ....domain.buckets.event import BucketEvent, BucketEventHistoryCatalogue, BucketEventObjectType, BucketEventType
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.modelos.calculation_revision import CalculationRevisionState
from ....domain.transactions.enums import BusinessClassification, TransactionLifecycleState
from ....domain.transactions.models import Transaction
from ....tests.cli_envelope import require_error_document, unwrap_cli_result
from ...ledger_action_composition import compose_ledger_action_ports
from .._ledger_payloads import (
    LedgerAddResult,
    LedgerArchiveResult,
    LedgerExcludeResult,
    LedgerRestoreResult,
    LedgerStashResult,
)
from .cli_runner import invoke_cached_cli
from .runtime_profile_cli_fixture import NativeCliProfileFixture, RuntimeFailureObservation, native_cli_profile_scope

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]

_PROFILE_FACTS = {
    "taxpayer_type.entity_type": "natural_person",
    "identity.name": "Native",
    "identity.surnames": "Ledger Lifecycle",
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
_ACTOR = "native-lifecycle-operator"


def _invoke(profile: NativeCliProfileFixture, *command: str) -> Result:
    """Run one command against the real encrypted profile-worker fixture."""
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
    authority_operation: PinnedAuthorityOperation,
) -> str:
    """Unlock the encrypted profile for the canonical state oracle."""
    assert profile.label is not None
    close_active_bucket_session()
    login = authenticate_profile_for_invocation(
        name=profile.label,
        passphrase_callback=lambda: profile.passphrase,
        profile_decode_context=authority_operation.profile_decode_context(),
    )
    return login.bucket_id


def _expected_result(
    result_schema: type[BaseModel],
    *,
    bucket_id: str,
    transaction: Transaction,
    event_ids: tuple[str, ...],
) -> dict[str, object]:
    canonical = ledger_transaction_result_payload(
        build_manual_ledger_result(bucket_id, transaction, event_ids),
    )
    payload = canonical.model_dump(mode="json")
    payload["bucket_event_ids"] = list(event_ids)
    result = result_schema.model_validate(payload)
    dumped = result.model_dump(mode="json")
    return cast("dict[str, object]", dumped)


def _added_events(
    before: BucketEventHistoryCatalogue,
    after: BucketEventHistoryCatalogue,
) -> tuple[BucketEvent, ...]:
    """Prove that the full old history remains and return only newly appended events."""
    assert all(after.events.get(event_id) == event for event_id, event in before.events.items())
    return tuple(event for event_id, event in after.events.items() if event_id not in before.events)


def _assert_profile_activation(event: BucketEvent, *, bucket_id: str) -> None:
    assert event.bucket_id == bucket_id
    assert event.event_type is BucketEventType.PROFILE_ACTIVATED
    assert event.object_type is BucketEventObjectType.PROFILE
    assert event.object_id == bucket_id
    assert event.actor == "profile-login"
    assert event.payload_version == 1
    assert dict(event.payload) == {"active_profile": bucket_id}


def _assert_lifecycle_event(
    before: BucketEventHistoryCatalogue,
    after: BucketEventHistoryCatalogue,
    *,
    bucket_id: str,
    transaction_id: str,
    event_type: BucketEventType,
    actor: str,
    payload: dict[str, str],
) -> str:
    added = _added_events(before, after)
    activations = tuple(event for event in added if event.event_type is BucketEventType.PROFILE_ACTIVATED)
    mutations = tuple(event for event in added if event.event_type is event_type)
    assert len(added) == 2
    assert len(activations) == 1
    assert len(mutations) == 1
    _assert_profile_activation(activations[0], bucket_id=bucket_id)
    event = mutations[0]
    assert event.bucket_id == bucket_id
    assert event.event_type is event_type
    assert event.object_type is BucketEventObjectType.LEDGER_TRANSACTION
    assert event.object_id == transaction_id
    assert event.actor == actor
    assert event.payload_version == 1
    assert dict(event.payload) == payload
    return event.event_id


def _assert_no_lifecycle_write(
    before: BucketEventHistoryCatalogue,
    after: BucketEventHistoryCatalogue,
    *,
    bucket_id: str,
) -> None:
    added = _added_events(before, after)
    assert all(event.event_type is BucketEventType.PROFILE_ACTIVATED for event in added)
    assert len(added) <= 1
    if added:
        _assert_profile_activation(added[0], bucket_id=bucket_id)


def test_native_lifecycle_commands_preserve_full_results_history_and_blocker_refusal(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Exercise add/stash/restore/archive/restore/exclude through real worker routes."""
    with native_cli_profile_scope(tmp_path) as profile:
        failures: list[RuntimeFailureObservation] = []
        profile.failure_observer = failures.append
        profile.register(label="native-ledger-lifecycle", facts=_PROFILE_FACTS)
        assert profile.label is not None
        bucket_id = str(resolve_login_target(profile.label).bucket_id)

        assert _reauthenticate(profile, authority_operation=authority_operation) == bucket_id
        ports = compose_ledger_action_ports(bucket_id=bucket_id, operation=authority_operation)

        created = _invoke(
            profile,
            "app",
            "ledger",
            "add",
            "--date",
            "2026-05-07",
            "--amount",
            "123.45",
            "--direction",
            "OUTGOING",
            "--description",
            "Native lifecycle command transaction",
            "--idempotency-key",
            "native-lifecycle-command-seed",
        )
        assert created.exit_code == 0, (created.output, failures)
        created_payload = unwrap_cli_result(created)
        transaction_id = created_payload["transaction_id"]
        assert isinstance(transaction_id, str) and len(transaction_id) == 64

        assert _reauthenticate(profile, authority_operation=authority_operation) == bucket_id
        ports = compose_ledger_action_ports(bucket_id=bucket_id, operation=authority_operation)
        transaction = ports.transaction_repository.load().get(transaction_id)
        assert transaction is not None
        created_event_ids = tuple(cast("list[str]", created_payload["bucket_event_ids"]))
        assert len(created_event_ids) == 1
        assert created_payload == _expected_result(
            LedgerAddResult,
            bucket_id=bucket_id,
            transaction=transaction,
            event_ids=created_event_ids,
        )

        transitions = (
            (
                "stash",
                LedgerStashResult,
                BucketEventType.LEDGER_TRANSACTION_STASHED,
                TransactionLifecycleState.ACTIVE,
                TransactionLifecycleState.STASHED,
                "native lifecycle stash",
            ),
            (
                "restore",
                LedgerRestoreResult,
                BucketEventType.LEDGER_TRANSACTION_RESTORED,
                TransactionLifecycleState.STASHED,
                TransactionLifecycleState.ACTIVE,
                "native lifecycle restore from stash",
            ),
            (
                "archive",
                LedgerArchiveResult,
                BucketEventType.LEDGER_TRANSACTION_ARCHIVED,
                TransactionLifecycleState.ACTIVE,
                TransactionLifecycleState.ARCHIVED,
                "native lifecycle archive",
            ),
            (
                "restore",
                LedgerRestoreResult,
                BucketEventType.LEDGER_TRANSACTION_RESTORED,
                TransactionLifecycleState.ARCHIVED,
                TransactionLifecycleState.ACTIVE,
                "native lifecycle restore from archive",
            ),
            (
                "exclude",
                LedgerExcludeResult,
                BucketEventType.LEDGER_TRANSACTION_REVIEWED_EXCLUDED,
                TransactionLifecycleState.ACTIVE,
                TransactionLifecycleState.ACTIVE,
                "native lifecycle exclusion",
            ),
        )
        command_by_verb = {
            "archive": "archive",
            "stash": "stash",
            "restore": "restore",
            "exclude": "exclude",
        }
        for verb, result_schema, event_type, prior_state, next_state, reason in transitions:
            assert _reauthenticate(profile, authority_operation=authority_operation) == bucket_id
            ports = compose_ledger_action_ports(bucket_id=bucket_id, operation=authority_operation)
            before_transaction = ports.transaction_repository.load().get(transaction_id)
            assert before_transaction is not None
            assert before_transaction.lifecycle_state is prior_state
            before_history = ports.bucket_event_repository.load()

            changed = _invoke(
                profile,
                "app",
                "ledger",
                command_by_verb[verb],
                transaction_id,
                "--yes",
                "--actor",
                _ACTOR,
                "--reason",
                reason,
            )
            assert changed.exit_code == 0, (changed.output, failures)
            payload = unwrap_cli_result(changed)

            assert _reauthenticate(profile, authority_operation=authority_operation) == bucket_id
            ports = compose_ledger_action_ports(bucket_id=bucket_id, operation=authority_operation)
            after_transaction = ports.transaction_repository.load().get(transaction_id)
            assert after_transaction is not None
            assert after_transaction.lifecycle_state is next_state
            if verb == "exclude":
                assert after_transaction.business_classification is BusinessClassification.REVIEWED_EXCLUDED
                assert after_transaction.business_pct is None
            else:
                assert after_transaction.business_classification is before_transaction.business_classification
                assert after_transaction.business_pct == before_transaction.business_pct
            after_history = ports.bucket_event_repository.load()
            event_id = _assert_lifecycle_event(
                before_history,
                after_history,
                bucket_id=bucket_id,
                transaction_id=transaction_id,
                event_type=event_type,
                actor=_ACTOR,
                payload=(
                    {
                        "business_classification": BusinessClassification.REVIEWED_EXCLUDED.value,
                        "previous_classification": before_transaction.business_classification.value,
                        "reason": reason,
                        "source_command": "aeat app ledger exclude",
                    }
                    if verb == "exclude"
                    else {
                        "lifecycle_state": next_state.value,
                        "previous_lifecycle_state": prior_state.value,
                        "reason": reason,
                        "source_command": f"aeat app ledger {verb}",
                    }
                ),
            )
            result_event_ids = tuple(cast("list[str]", payload["bucket_event_ids"]))
            assert result_event_ids == (event_id,)
            assert payload == _expected_result(
                result_schema,
                bucket_id=bucket_id,
                transaction=after_transaction,
                event_ids=(event_id,),
            )
            if verb == "exclude":
                viewed = _invoke(profile, "app", "ledger", "view", transaction_id)
                assert viewed.exit_code == 0, viewed.output
                view_payload = unwrap_cli_result(viewed)
                assert view_payload["transaction_id"] == transaction_id
                assert view_payload["review_status"] == "excluded"
                assert view_payload["transaction"] == payload["transaction"]

        assert _reauthenticate(profile, authority_operation=authority_operation) == bucket_id
        ports = compose_ledger_action_ports(bucket_id=bucket_id, operation=authority_operation)
        finalized_revision_id = seed_revision_citing_transaction(
            secure_object_repository_for_active_bucket(),
            transaction_id=transaction_id,
            state=CalculationRevisionState.VERIFICADO_COMPLETO,
            period_code="1T",
            bucket_id=bucket_id,
            operation=authority_operation,
        )
        blockers = blocking_modelo_references(
            bucket_id=bucket_id,
            transaction_ids=(transaction_id,),
            work_unit_repository=ports.work_unit_repository,
            calculation_repository=ports.calculation_repository,
        )
        assert len(blockers) == 1
        blocker = blockers[0]
        assert blocker.calculation_revision_id == finalized_revision_id
        before_blocked_transaction = ports.transaction_repository.load().get(transaction_id)
        assert before_blocked_transaction is not None
        history_before_block = ports.bucket_event_repository.load()

        refused = _invoke(
            profile,
            "app",
            "ledger",
            "archive",
            transaction_id,
            "--yes",
            "--actor",
            _ACTOR,
            "--reason",
            "blocked by sealed filing",
        )
        assert refused.exit_code == 2, refused.output
        document = require_error_document(refused.output)
        assert document["command"] == "ledger.archive"
        error = cast("dict[str, object]", document["error"])
        assert error["category"] == "REFUSED"
        assert error["code"] == "REFUSED_LEDGER_LIFECYCLE_VALIDATION"
        context = cast("dict[str, object]", error["context"])
        assert context["transaction_id"] == transaction_id
        assert context["transaction_ids"] == transaction_id
        assert "transaction_ids_omitted_count" not in context
        assert context["blocking_reference_count"] == "1"
        assert context["work_unit_id"] == blocker.work_unit_id
        assert context["calculation_revision_id"] == blocker.calculation_revision_id
        assert "revision_state" not in context
        assert context["modelo"] == blocker.modelo
        assert context["filing_year"] == str(blocker.filing_year)
        assert context["period"] == blocker.period
        assert (
            context["validation_messages"]
            == "ledger transaction lifecycle transition refused because finalized modelo revisions cite the transaction"
        )

        assert _reauthenticate(profile, authority_operation=authority_operation) == bucket_id
        ports = compose_ledger_action_ports(bucket_id=bucket_id, operation=authority_operation)
        after_blocked_transaction = ports.transaction_repository.load().get(transaction_id)
        assert after_blocked_transaction == before_blocked_transaction
        _assert_no_lifecycle_write(
            history_before_block,
            ports.bucket_event_repository.load(),
            bucket_id=bucket_id,
        )

        returned_definitions = {
            observation.definition_id
            for observation in failures
            if observation.stage == "profile_operation_returned" and observation.definition_id is not None
        }
        assert returned_definitions >= {
            "ledger.add",
            "ledger.archive",
            "ledger.stash",
            "ledger.restore",
            "ledger.exclude",
        }
