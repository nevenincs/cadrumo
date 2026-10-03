"""Native worker journeys for finalized ledger participation and rebuild."""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from ....adapters.persistence.operations.journal import OperationJournalRepository
from ....adapters.persistence.profile.calculation_observations import IvaWalletDecisionRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.participation_index import TransactionParticipationIndexRepository
from ....adapters.persistence.storage.custody.tests.enrollment_support import PROFILE_INPUT
from ....adapters.persistence.storage.errors import RepositoryError
from ....adapters.persistence.storage.master_key.active_session import (
    close_active_bucket_session,
    current_active_bucket_session,
)
from ....adapters.persistence.storage.tests.profile_capsule_runtime import (
    bound_test_profile_record,
    upsert_test_profile_facts,
)
from ....application.ledger.actions_manual import create_manual_transaction
from ....application.ledger.models import ManualLedgerTransactionCommand
from ....application.ledger.participation_operation import LEDGER_PARTICIPATION_OPERATION_DEFINITION_ID
from ....application.ledger.participation_rebuild_operation import (
    LEDGER_PARTICIPATION_REBUILD_OPERATION_DEFINITION_ID,
)
from ....application.modelo.tests.profile_fixture_values import MODELO_READY_PROFILE_FACTS
from ....application.operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ....application.operations.persistence.events import OperationEffectEvent
from ....application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    DisclosureCategory,
    DisclosurePermission,
)
from ....application.user_profile.login_session import login_profile
from ....application.user_profile.tests.profile_values import complete_profile_facts
from ....core.operations import profile_operation_subject
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.iva.schema import IvaCategory
from ....domain.iva_compensation.reconciliation import IvaCompensationReconciliationDecision
from ....domain.modelos.calculation_revision import CalculationRevisionState
from ....domain.modelos.participation_index import TransactionRevisionParticipationIndex
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact
from ....tests.cli_envelope import require_error_document, unwrap_cli_result
from ...ledger_action_composition import compose_ledger_action_ports
from .native_api_cli_support import native_api_cli_session

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


def _reauthenticate_profile(
    *,
    profile_label: str,
    profile_id: UUID,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Open the encrypted oracle with the same real password used by the CLI fixture."""
    close_active_bucket_session()
    login = login_profile(
        name=profile_label,
        passphrase_callback=lambda: PROFILE_INPUT,
        profile_decode_context=authority_operation.profile_decode_context(),
    )
    assert login.bucket_id == str(profile_id)
    active = current_active_bucket_session()
    assert active is not None
    assert active.bucket_id == str(profile_id)


def _seed_canonical_transactions(
    *,
    profile_id: UUID,
    authority_operation: PinnedAuthorityOperation,
) -> dict[str, str]:
    """Seed normal encrypted ledger rows through the canonical application action."""
    bucket_id = str(profile_id)
    ports = compose_ledger_action_ports(bucket_id=bucket_id, operation=authority_operation)
    seeded: dict[str, str] = {}
    for label, booked_date, amount, taxable_base, iva_amount in (
        ("source", date(2025, 2, 15), "121.00", "100.00", "21.00"),
        ("outside", date(2026, 2, 10), "60.50", "50.00", "10.50"),
    ):
        created = create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id=bucket_id,
                booked_date=booked_date,
                amount=Decimal(amount),
                direction=TransactionDirection.INCOMING,
                description=f"Native participation {label} transaction",
                business_classification=BusinessClassification.BUSINESS,
                category_id="material_oficina",
                taxable_base=Decimal(taxable_base),
                iva_rate=Decimal("0.21"),
                iva_amount=Decimal(iva_amount),
                iva_category=IvaCategory("domestic_general"),
                actor="native-participation-reader",
                idempotency_key=f"native-participation-{label}",
            ),
            ports=ports,
            occurred_at=datetime.combine(booked_date, datetime.min.time(), tzinfo=UTC),
        )
        transaction_id = created.transaction.transaction_id
        assert len(transaction_id) == 64
        seeded[label] = transaction_id
    return seeded


def test_native_participation_reads_canonical_index_rebuilds_and_requires_commit(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Lookup preserves the verified index; rebuild prunes stale cache under COMMIT authority."""

    def prepare_profile(profile_id: UUID, root: Path) -> dict[str, str]:
        facts_by_path = {
            fact.path: (str(fact.value).lower() if isinstance(fact.value, bool) else str(fact.value))
            for fact in MODELO_READY_PROFILE_FACTS
        }
        facts_by_path["censo.activity_start_date"] = "2025-01-01"
        facts = complete_profile_facts(
            authority_operation.profile_schema(),
            facts=tuple(UserProfileFact(path=path, value=value) for path, value in facts_by_path.items()),
        )
        populated = upsert_test_profile_facts(profile_id, facts, root=root)
        with bound_test_profile_record(profile_id, root=root) as repository:
            ready = repository.complete_setup(
                profile_id,
                expected_revision=populated.record_revision,
                expected_content_digest=populated.content_digest,
            )
        assert ready.setup_state is ProfileSetupState.COMPLETE
        return _seed_canonical_transactions(profile_id=profile_id, authority_operation=authority_operation)

    def scope_for_destination(client_id: UUID) -> AccessScope:
        result_schema_ids = (
            LEDGER_PARTICIPATION_OPERATION_DEFINITION_ID + ".result",
            LEDGER_PARTICIPATION_REBUILD_OPERATION_DEFINITION_ID + ".result",
        )
        return AccessScope(
            operations=frozenset(
                {
                    LEDGER_PARTICIPATION_OPERATION_DEFINITION_ID,
                    LEDGER_PARTICIPATION_REBUILD_OPERATION_DEFINITION_ID,
                }
            ),
            actions=frozenset(
                {
                    AccessAction.SUBMIT,
                    AccessAction.START,
                    AccessAction.RESUME,
                    AccessAction.OBSERVE,
                    AccessAction.RESULT,
                    AccessAction.CANCEL,
                    AccessAction.DETACH,
                }
            ),
            disclosures=frozenset(
                {
                    DisclosurePermission(
                        destination_id=client_id,
                        projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                        category=DisclosureCategory.OPERATION_METADATA,
                    ),
                    *(
                        DisclosurePermission(
                            destination_id=client_id,
                            projection_id=schema_id,
                            category=DisclosureCategory.TAX_VALUES,
                        )
                        for schema_id in result_schema_ids
                    ),
                }
            ),
            periods=None,
            allow_period_independent=True,
            allow_delegation=False,
        )

    with native_api_cli_session(
        tmp_path,
        scope_for_destination=scope_for_destination,
        prepare_profile=prepare_profile,
    ) as api:
        close_active_bucket_session()
        seeded = api.prepared
        assert set(seeded) == {"source", "outside"}

        created = api.invoke_password(
            "app",
            "modelo",
            "work",
            "create",
            "--modelo",
            "303",
            "--year",
            "2025",
            "--period",
            "1T",
        )
        assert created.exit_code == 0, created.output
        work_unit_id = unwrap_cli_result(created).get("work_unit_id")
        assert isinstance(work_unit_id, str) and work_unit_id

        period = Period.from_year_and_code(2025, "1T")
        _reauthenticate_profile(
            profile_label=api.profile_label,
            profile_id=api.profile_id,
            authority_operation=authority_operation,
        )
        IvaWalletDecisionRepository().save_decision(
            IvaCompensationReconciliationDecision(
                taxpayer_nif="12345678Z",
                target_year=2025,
                target_period=period,
                target_registry_snapshot_ref=published_snapshot("303", filing_year=2025, period="1T").snapshot_ref,
                source_registry_snapshot_refs=(),
                selected_authority="aeat_wallet",
                selected_amount=Decimal("0.00"),
                wallet_amount=Decimal("0.00"),
                local_recurrence_amount=None,
                override_amount=None,
                divergence="match",
                blocked=False,
                stale_wallet=False,
                reason_identity="first_period_zero_aeat_wallet",
                wallet_captured_at=datetime(2025, 4, 1, 10, tzinfo=UTC),
                decided_at=datetime(2025, 4, 1, 10, tzinfo=UTC),
            )
        )
        close_active_bucket_session()

        calculated = api.invoke_password(
            "app",
            "modelo",
            "work",
            "calculate",
            work_unit_id,
            "--joint-return-elected",
        )
        assert calculated.exit_code == 0, calculated.output
        calculation_revision_id = unwrap_cli_result(calculated).get("calculation_revision_id")
        assert isinstance(calculation_revision_id, str) and calculation_revision_id
        verified = api.invoke_password("app", "modelo", "work", "verify", work_unit_id)
        assert verified.exit_code == 0, verified.output
        assert unwrap_cli_result(verified).get("granted_verificado_completo") is True

        _reauthenticate_profile(
            profile_label=api.profile_label,
            profile_id=api.profile_id,
            authority_operation=authority_operation,
        )
        bucket_id = str(api.profile_id)
        revision_repository = CalculationRevisionCatalogueRepository(bucket_id=bucket_id)
        revisions_before = revision_repository.load(operation=authority_operation).revisions
        revision = revisions_before[calculation_revision_id]
        assert revision.state is CalculationRevisionState.VERIFICADO_COMPLETO
        assert revision.source_transaction_ids == (seeded["source"],)
        assert seeded["outside"] not in revision.source_transaction_ids
        work_units = WorkUnitCatalogueRepository(bucket_id=bucket_id).load()
        work_unit = work_units.get(work_unit_id)
        assert work_unit is not None

        participation_repository = TransactionParticipationIndexRepository(bucket_id=bucket_id)
        canonical_index = participation_repository.load(seeded["source"])
        assert canonical_index.transaction_id == seeded["source"]
        assert len(canonical_index.participations) == 1
        canonical_entry = canonical_index.participations[0]
        assert canonical_entry.calculation_revision_id == calculation_revision_id
        assert canonical_entry.work_unit_id == work_unit.work_unit_id
        assert canonical_entry.modelo == work_unit.modelo
        assert canonical_entry.period == period
        assert canonical_entry.filing_year == 2025
        assert canonical_entry.filing_record_id is None
        assert participation_repository.load(seeded["outside"]).participations == ()
        canonical_payload = canonical_index.model_dump(mode="json")
        close_active_bucket_session()

        lookup = api.invoke_credential_reference("app", "ledger", "participation", seeded["source"])
        assert lookup.exit_code == 0, lookup.output
        assert unwrap_cli_result(lookup) == canonical_payload
        empty_lookup = api.invoke_credential_reference("app", "ledger", "participation", seeded["outside"])
        assert empty_lookup.exit_code == 0, empty_lookup.output
        assert unwrap_cli_result(empty_lookup) == {"transaction_id": seeded["outside"], "participations": []}

        _reauthenticate_profile(
            profile_label=api.profile_label,
            profile_id=api.profile_id,
            authority_operation=authority_operation,
        )
        participation_repository = TransactionParticipationIndexRepository(bucket_id=bucket_id)
        stale_index = TransactionRevisionParticipationIndex(
            transaction_id=seeded["outside"],
            participations=canonical_index.participations,
        )
        participation_repository.save(stale_index)
        stale_payload = stale_index.model_dump(mode="json")
        close_active_bucket_session()

        refused_rebuild = api.invoke_credential_reference("app", "ledger", "participation", "rebuild")
        assert refused_rebuild.exit_code == 2, refused_rebuild.output
        refusal = require_error_document(refused_rebuild.output)["error"]
        assert refusal["code"] == "REFUSED_CLI_BOUNDARY"
        context = refusal["context"]
        assert isinstance(context, dict)
        operation_id = context.get("operation_id")
        assert isinstance(operation_id, str) and operation_id
        runtime_health = api.runtime_health()
        safe_diagnostics: dict[str, object] = {
            "refusal": {
                "code": refusal.get("code"),
                "category": refusal.get("category"),
                **{key: context.get(key) for key in ("reason", "effect", "terminal_condition")},
                "terminal_condition_present": "terminal_condition" in context,
                "operation_id_present": True,
            },
            "journal": None,
            "runtime_health": {
                "ready": runtime_health.ready,
                "stop_requested": runtime_health.stop_requested,
                "serve_task_done": runtime_health.serve_task_done,
            },
            "runtime_failure_observations": tuple(
                {
                    "stage": observation.stage,
                    "action": observation.action,
                    "exception_type": observation.exception_type,
                    "reason": observation.reason,
                    "request_type": observation.request_type,
                    "response_type": observation.response_type,
                    "definition_id": observation.definition_id,
                    "operation_exchange": observation.operation_exchange,
                    "phase": observation.phase,
                    "traceback_locations": observation.traceback_locations,
                }
                for observation in api.runtime_failure_observations
            ),
            "runtime_failure_events": tuple(
                {
                    "stage": observation.stage,
                    "action": observation.action,
                    "phase": observation.phase,
                    "exception_type": observation.exception_type,
                    "reason": observation.reason,
                    "request_type": observation.request_type,
                    "definition_id": observation.definition_id,
                    "traceback_locations": observation.traceback_locations,
                }
                for observation in api.runtime_failure_events
            ),
        }
        try:
            snapshot = asyncio.run(
                OperationJournalRepository(storage_root=tmp_path / "cadrumo-storage").load(operation_id)
            )
        except RepositoryError:
            safe_diagnostics["journal"] = {"available": False}
        else:
            receipt = snapshot.terminal_receipt
            safe_effect_values = {"none", "updated", "partial", "unknown"}
            effect_event_values = tuple(
                event.effect.value
                for event in snapshot.events
                if isinstance(event, OperationEffectEvent) and event.effect.value in safe_effect_values
            )
            receipt_ref = None if receipt is None else receipt.refusal_ref
            safe_diagnostics["journal"] = {
                "available": True,
                "identity_matches_expected_request": (
                    snapshot.identity.operation_id == operation_id
                    and snapshot.identity.definition_id == LEDGER_PARTICIPATION_REBUILD_OPERATION_DEFINITION_ID
                    and snapshot.identity.subject_ref == profile_operation_subject(str(api.profile_id))
                ),
                "lifecycle": snapshot.lifecycle.value,
                "terminal_condition": None
                if snapshot.terminal_condition is None
                else snapshot.terminal_condition.value,
                "effect": snapshot.effect.value,
                "phase_code": None if snapshot.phase_code is None else str(snapshot.phase_code),
                "events": tuple((event.kind.value, str(event.code)) for event in snapshot.events),
                "effect_events": effect_event_values,
                "receipt_terminal_condition": None if receipt is None else receipt.condition.value,
                "receipt_effect": None if receipt is None else receipt.effect.value,
                "receipt_refusal_ref": (
                    receipt_ref if receipt_ref in {"REFUSED_PROFILE_ACCESS"} else "<redacted-unrecognized-ref>"
                ),
                "failure_error_code": (
                    None if receipt is None or receipt.failure_error_code is None else str(receipt.failure_error_code)
                ),
            }
        safe_diagnostics_json = json.dumps(safe_diagnostics, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        assert "stale_removed_count" not in refused_rebuild.output

        _reauthenticate_profile(
            profile_label=api.profile_label,
            profile_id=api.profile_id,
            authority_operation=authority_operation,
        )
        assert revision_repository.load(operation=authority_operation).revisions == revisions_before
        after_denial_repository = TransactionParticipationIndexRepository(bucket_id=bucket_id)
        assert after_denial_repository.load(seeded["source"]).model_dump(mode="json") == canonical_payload
        assert after_denial_repository.load(seeded["outside"]).model_dump(mode="json") == stale_payload
        assert after_denial_repository.exists(seeded["outside"])
        close_active_bucket_session()

        assert context["reason"] == "REFUSED_PROFILE_ACCESS", safe_diagnostics_json
        assert context["effect"] == "none", safe_diagnostics_json
        assert context["terminal_condition"] == "refused", safe_diagnostics_json

        rebuilt = api.invoke_password("app", "ledger", "participation", "rebuild")
        assert rebuilt.exit_code == 0, rebuilt.output
        rebuild_payload = unwrap_cli_result(rebuilt)
        assert rebuild_payload == {
            "transaction_count": 1,
            "participation_count": 1,
            "revision_count": 1,
            "stale_removed_count": 1,
        }

        _reauthenticate_profile(
            profile_label=api.profile_label,
            profile_id=api.profile_id,
            authority_operation=authority_operation,
        )
        assert revision_repository.load(operation=authority_operation).revisions == revisions_before
        rebuilt_repository = TransactionParticipationIndexRepository(bucket_id=bucket_id)
        assert rebuilt_repository.load(seeded["source"]).model_dump(mode="json") == canonical_payload
        assert rebuilt_repository.load(seeded["outside"]).participations == ()
        assert not rebuilt_repository.exists(seeded["outside"])
        close_active_bucket_session()
