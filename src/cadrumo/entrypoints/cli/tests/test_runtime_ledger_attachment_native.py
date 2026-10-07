"""Native profile-worker acceptance for ledger attachment and detachment."""

from __future__ import annotations

import json
import sys
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from click.testing import Result

from ....adapters.persistence.profile.tests.remove_draft_revision_support import seed_revision_citing_transaction
from ....adapters.persistence.storage.master_key.active_session import (
    close_active_bucket_session,
    current_active_bucket_session,
)
from ....adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from ....application.ledger.action_ports import LedgerActionPorts
from ....application.ledger.actions_common import blocking_modelo_references
from ....application.ledger.actions_manual import create_manual_transaction, ledger_transaction_result_payload
from ....application.ledger.attachment_mutation_operation import LedgerAttachmentStaleRevisionProjection
from ....application.ledger.models import ManualLedgerTransactionCommand, ManualLedgerTransactionResult
from ....application.user_profile.login_session import authenticate_profile_for_invocation, resolve_login_target
from ....core.config import override_settings
from ....core.decimal.formatting import format_decimal
from ....domain.attachments.enums import AttachmentKind, AttachmentSource
from ....domain.attachments.service import AttachmentBytesContent, AttachmentIngestionRequest, add_attachment
from ....domain.buckets.event import BucketEvent, BucketEventHistoryCatalogue, BucketEventObjectType, BucketEventType
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.modelos.calculation_revision import CalculationRevisionState
from ....domain.transactions.enums import TransactionDirection
from ....domain.transactions.models import BucketTransactionRef, Transaction
from ....tests.cli_envelope import unwrap_cli_result, unwrap_envelope_notices
from ...ledger_action_composition import compose_ledger_action_ports
from .._ledger_payloads import LedgerAttachResult, LedgerDetachResult
from .cli_runner import invoke_cached_cli
from .runtime_profile_cli_fixture import (
    NativeCliProfileFixture,
    RuntimeFailureObservation,
    native_cli_profile_scope,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]

_PROFILE_FACTS = {
    "taxpayer_type.entity_type": "natural_person",
    "identity.name": "Native",
    "identity.surnames": "Attachment",
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
_PDF_BYTES = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"
_SEED_AT = datetime(2026, 5, 8, 10, 15, tzinfo=UTC)


def _invoke(profile: NativeCliProfileFixture, *command: str) -> Result:
    """Invoke one installed CLI command with the real test-profile secret."""
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
    """Unlock the profile for the encrypted canonical-state oracle."""
    assert profile.label is not None
    close_active_bucket_session()
    login = authenticate_profile_for_invocation(
        name=profile.label,
        passphrase_callback=lambda: profile.passphrase,
        profile_decode_context=authority_operation.profile_decode_context(),
    )
    active = current_active_bucket_session()
    assert active is not None
    assert active.bucket_id == login.bucket_id
    return login.bucket_id


def _expected_result(
    *,
    result_type: type[LedgerAttachResult] | type[LedgerDetachResult],
    bucket_id: str,
    transaction: Transaction,
    event_ids: tuple[str, ...],
) -> dict[str, object]:
    canonical = ledger_transaction_result_payload(
        ManualLedgerTransactionResult(
            ref=BucketTransactionRef(bucket_id=bucket_id, transaction_id=transaction.transaction_id),
            transaction=transaction,
            bucket_event_ids=event_ids,
        )
    )
    payload = {
        **canonical.model_dump(mode="json"),
        "bucket_event_ids": list(event_ids),
    }
    if result_type is LedgerAttachResult:
        result = LedgerAttachResult.model_validate(payload)
    else:
        result = LedgerDetachResult.model_validate(payload)
    dumped = result.model_dump(mode="json")
    assert all(isinstance(key, str) for key in dumped)
    return {key: value for key, value in dumped.items()}


def _new_event(
    history_before: BucketEventHistoryCatalogue,
    history_after: BucketEventHistoryCatalogue,
    *,
    bucket_id: str,
    mutation_type: BucketEventType,
) -> BucketEvent:
    """Separate one ledger mutation from the known profile-login activation."""
    assert all(history_after.events.get(key) == event for key, event in history_before.events.items())
    added = tuple(event for key, event in history_after.events.items() if key not in history_before.events)
    mutations = tuple(event for event in added if event.event_type is mutation_type)
    activations = tuple(event for event in added if event.event_type is BucketEventType.PROFILE_ACTIVATED)
    assert len(added) == 2
    assert len(mutations) == 1
    assert len(activations) == 1
    activation = activations[0]
    assert activation.bucket_id == bucket_id
    assert activation.event_type is BucketEventType.PROFILE_ACTIVATED
    assert activation.object_type is BucketEventObjectType.PROFILE
    assert activation.object_id == bucket_id
    assert activation.actor == "profile-login"
    assert activation.payload_version == 1
    assert dict(activation.payload) == {"active_profile": bucket_id}
    return mutations[0]


def _assert_event(
    event: BucketEvent,
    *,
    bucket_id: str,
    transaction_id: str,
    attachment_id: str,
    linked: bool,
    amount: Decimal,
) -> str:
    expected_type = BucketEventType.ATTACHMENT_LINKED if linked else BucketEventType.ATTACHMENT_REMOVED
    mutation_kind = "attachment_linked" if linked else "attachment_removed"
    assert event.bucket_id == bucket_id
    assert event.event_type is expected_type
    assert event.object_type is BucketEventObjectType.ATTACHMENT
    assert event.object_id == attachment_id
    assert event.actor == "native-attachment-operator"
    assert event.payload_version == 1
    assert dict(event.payload) == {
        "amount": format_decimal(amount),
        "currency": "EUR",
        "direction": TransactionDirection.OUTGOING.value,
        "linked": "true" if linked else "false",
        "mutation_kind": mutation_kind,
        "previous_transaction_id": transaction_id,
        "source_command": f"aeat app ledger {'attach' if linked else 'detach'}",
        "transaction_id": transaction_id,
    }
    return event.event_id


def _expected_stale_notice(blocker: LedgerAttachmentStaleRevisionProjection) -> dict[str, object]:
    from ....core.i18n.render import tr

    return {
        "severity": "warning",
        "code": "ledger.attach.finalized_revision_stale",
        "message": tr(
            "cli.ledger.attach.finalized_revision_stale",
            modelo=blocker.modelo,
            filing_year=str(blocker.filing_year),
            period=blocker.period,
            locale="en",
        ),
        "action": None,
        "context": {
            "work_unit_id": blocker.work_unit_id,
            "calculation_revision_id": blocker.calculation_revision_id,
            "revision_state": blocker.revision_state,
            "modelo": blocker.modelo,
            "filing_year": str(blocker.filing_year),
            "period": blocker.period,
            "reason": "finalized_revision_predates_evidence",
            "actionability": "finalized_revision_has_no_safe_recovery_action",
        },
    }


def _expected_session_scoped_auth_notice() -> dict[str, object]:
    from ....core.i18n.render import tr

    return {
        "severity": "warning",
        "code": "config.login.session_not_persisted",
        "message": tr("cli.config.login.notices.session_invocation_scoped", locale="en"),
        "action": None,
        "context": None,
    }


def _assert_stale_notice_and_blocker(
    result: Result,
    *,
    bucket_id: str,
    transaction_id: str,
    finalized_revision_id: str,
    ports: LedgerActionPorts,
) -> None:
    blockers = blocking_modelo_references(
        bucket_id=bucket_id,
        transaction_ids=(transaction_id,),
        work_unit_repository=ports.work_unit_repository,
        calculation_repository=ports.calculation_repository,
    )
    assert tuple(blocker.calculation_revision_id for blocker in blockers) == (finalized_revision_id,)
    stale_projection = tuple(LedgerAttachmentStaleRevisionProjection.from_blocker(item) for item in blockers)
    assert len(stale_projection) == 1
    assert unwrap_envelope_notices(result.output) == [
        _expected_stale_notice(stale_projection[0]),
        _expected_session_scoped_auth_notice(),
    ]


def test_native_attach_detach_preserve_full_results_history_and_historical_manifest(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """One encrypted profile proves both registered writes and the stale revision notice."""
    with native_cli_profile_scope(tmp_path) as profile:
        failures: list[RuntimeFailureObservation] = []
        profile.failure_observer = failures.append
        profile.register(label="native-ledger-attachment", facts=_PROFILE_FACTS)
        assert profile.label is not None
        bucket_id = str(resolve_login_target(profile.label).bucket_id)

        assert _reauthenticate(profile, authority_operation=authority_operation) == bucket_id
        ports = compose_ledger_action_ports(bucket_id=bucket_id, operation=authority_operation)
        created = create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id=bucket_id,
                booked_date=date(2026, 5, 7),
                amount=Decimal("123.45"),
                direction=TransactionDirection.OUTGOING,
                description="Native attachment operation transaction",
                actor="native-attachment-seed",
                idempotency_key="native-ledger-attachment-seed",
            ),
            ports=ports,
            occurred_at=_SEED_AT,
        )
        transaction_id = created.transaction.transaction_id
        attachment = add_attachment(
            ports.attachment_store,
            content=AttachmentBytesContent(data=_PDF_BYTES),
            request=AttachmentIngestionRequest(
                kind=AttachmentKind.INVOICE_PDF,
                source=AttachmentSource.INLINE,
                source_reference="native-attachment-conformance",
                mime_type="application/pdf",
                captured_at=_SEED_AT,
                bucket_id=bucket_id,
                captured_by="native-attachment-seed",
                source_command="native encrypted attachment fixture",
            ),
        )
        finalized_revision_id = seed_revision_citing_transaction(
            secure_object_repository_for_active_bucket(),
            transaction_id=transaction_id,
            state=CalculationRevisionState.VERIFICADO_COMPLETO,
            period_code="1T",
            bucket_id=bucket_id,
            operation=authority_operation,
        )
        transaction_before = ports.transaction_repository.load().get(transaction_id)
        assert transaction_before is not None
        assert transaction_before.attachment_ids == ()
        manifest_before = ports.attachment_store.load_manifest(attachment.attachment_id)
        assert manifest_before.linked_transaction_ids == ()
        history_before_attach = ports.bucket_event_repository.load()
        close_active_bucket_session()

        attached = _invoke(
            profile,
            "app",
            "ledger",
            "attach",
            transaction_id,
            "--attachment-id",
            attachment.attachment_id,
            "--actor",
            "native-attachment-operator",
        )
        assert attached.exit_code == 0, (attached.output, failures)
        attach_payload = unwrap_cli_result(attached)

        assert _reauthenticate(profile, authority_operation=authority_operation) == bucket_id
        ports = compose_ledger_action_ports(bucket_id=bucket_id, operation=authority_operation)
        attached_transaction = ports.transaction_repository.load().get(transaction_id)
        assert attached_transaction is not None
        assert attached_transaction.attachment_ids == (attachment.attachment_id,)
        history_after_attach = ports.bucket_event_repository.load()
        attach_event = _new_event(
            history_before_attach,
            history_after_attach,
            bucket_id=bucket_id,
            mutation_type=BucketEventType.ATTACHMENT_LINKED,
        )
        attach_event_id = _assert_event(
            attach_event,
            bucket_id=bucket_id,
            transaction_id=transaction_id,
            attachment_id=attachment.attachment_id,
            linked=True,
            amount=Decimal("123.45"),
        )
        assert len(history_after_attach.events) == len(history_before_attach.events) + 2
        linked_manifest = ports.attachment_store.load_manifest(attachment.attachment_id)
        assert linked_manifest.linked_transaction_ids == (transaction_id,)
        assert ports.attachment_store.read_bytes(attachment.attachment_id) == _PDF_BYTES
        assert attach_payload == _expected_result(
            result_type=LedgerAttachResult,
            bucket_id=bucket_id,
            transaction=attached_transaction,
            event_ids=(attach_event_id,),
        )
        _assert_stale_notice_and_blocker(
            attached,
            bucket_id=bucket_id,
            transaction_id=transaction_id,
            finalized_revision_id=finalized_revision_id,
            ports=ports,
        )
        assert linked_manifest != manifest_before

        close_active_bucket_session()
        detached = _invoke(
            profile,
            "app",
            "ledger",
            "detach",
            transaction_id,
            "--attachment-id",
            attachment.attachment_id,
            "--actor",
            "native-attachment-operator",
        )
        assert detached.exit_code == 0, (detached.output, failures)
        detach_payload = unwrap_cli_result(detached)

        assert _reauthenticate(profile, authority_operation=authority_operation) == bucket_id
        ports = compose_ledger_action_ports(bucket_id=bucket_id, operation=authority_operation)
        detached_transaction = ports.transaction_repository.load().get(transaction_id)
        assert detached_transaction is not None
        assert detached_transaction.attachment_ids == ()
        history_after_detach = ports.bucket_event_repository.load()
        detach_event = _new_event(
            history_after_attach,
            history_after_detach,
            bucket_id=bucket_id,
            mutation_type=BucketEventType.ATTACHMENT_REMOVED,
        )
        detach_event_id = _assert_event(
            detach_event,
            bucket_id=bucket_id,
            transaction_id=transaction_id,
            attachment_id=attachment.attachment_id,
            linked=False,
            amount=Decimal("123.45"),
        )
        assert len(history_after_detach.events) == len(history_after_attach.events) + 2
        assert history_after_detach.events[attach_event_id] == attach_event
        detached_manifest = ports.attachment_store.load_manifest(attachment.attachment_id)
        assert detached_manifest == linked_manifest
        assert detached_manifest.linked_transaction_ids == (transaction_id,)
        assert ports.attachment_store.read_bytes(attachment.attachment_id) == _PDF_BYTES
        assert detach_payload == _expected_result(
            result_type=LedgerDetachResult,
            bucket_id=bucket_id,
            transaction=detached_transaction,
            event_ids=(detach_event_id,),
        )
        _assert_stale_notice_and_blocker(
            detached,
            bucket_id=bucket_id,
            transaction_id=transaction_id,
            finalized_revision_id=finalized_revision_id,
            ports=ports,
        )

        returned_definitions = {
            observation.definition_id
            for observation in failures
            if observation.stage == "profile_operation_returned" and observation.definition_id is not None
        }
        assert returned_definitions >= {"ledger.attach", "ledger.detach"}
