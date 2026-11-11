"""Native worker journeys for finalized ledger participation and rebuild."""

from __future__ import annotations

import sys
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from cadrumo.adapters.persistence.profile.calculation_observations import IvaWalletDecisionRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.participation_index import TransactionParticipationIndexRepository
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import PROFILE_INPUT
from cadrumo.adapters.persistence.storage.master_key.active_session import (
    close_active_bucket_session,
    current_active_bucket_session,
)
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    bound_test_profile_record,
    upsert_test_profile_facts,
)
from cadrumo.application.ledger.models import ManualLedgerTransactionCommand
from cadrumo.application.ledger.participation_operation import LEDGER_PARTICIPATION_OPERATION_DEFINITION_ID
from cadrumo.application.ledger.participation_rebuild_operation import (
    LEDGER_PARTICIPATION_REBUILD_OPERATION_DEFINITION_ID,
)
from cadrumo.application.ledger.tests.manual_transaction_support import create_manual_transaction
from cadrumo.application.operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from cadrumo.application.user_profile.login_session import authenticate_profile_for_invocation
from cadrumo.application.user_profile.tests.persona_profile_facts import directa_normal_tax_id, persona_fact_strings
from cadrumo.application.user_profile.tests.profile_values import complete_profile_facts
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot
from cadrumo.domain.iva.schema import IvaCategory
from cadrumo.domain.iva_compensation.reconciliation import IvaCompensationReconciliationDecision
from cadrumo.domain.modelos.calculation_revision import CalculationRevision, CalculationRevisionState
from cadrumo.domain.modelos.participation_index import TransactionRevisionParticipationIndex
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionDirection
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact
from cadrumo.entrypoints.ledger_action_composition import compose_ledger_action_ports
from cadrumo.tests.cli_envelope import require_error_document, unwrap_cli_result
from cadrumo_client.contracts.access_vocabulary import (
    AccessAction,
    AccessScope,
    DisclosureCategory,
    DisclosurePermission,
)
from cadrumo_runtime.host.tests.frontend.cli.native_api_cli_support import NativeApiCliSession, native_api_cli_session

_YEAR = filing_year_envelope().horizon

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
    login = authenticate_profile_for_invocation(
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
        ("source", date(_YEAR, 2, 15), "121.00", "100.00", "21.00"),
        ("outside", date(_YEAR - 1, 2, 10), "60.50", "50.00", "10.50"),
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


@dataclass(frozen=True)
class _CanonicalParticipation:
    """The verified revision and participation index read from the encrypted profile."""

    bucket_id: str
    revision_repository: CalculationRevisionCatalogueRepository
    revisions_before: Mapping[str, CalculationRevision]
    index: TransactionRevisionParticipationIndex
    payload: dict[str, object]


def _calculate_and_verify_303(
    api: NativeApiCliSession[dict[str, str]], authority_operation: PinnedAuthorityOperation
) -> tuple[str, str]:
    """Create, calculate and verify the first-quarter modelo 303 work unit under the human password."""
    created = api.invoke_password(
        "app",
        "modelo",
        "work",
        "create",
        "--modelo",
        "303",
        "--year",
        str(_YEAR),
        "--period",
        "1T",
    )
    assert created.exit_code == 0, created.output
    work_unit_id = unwrap_cli_result(created).get("work_unit_id")
    assert isinstance(work_unit_id, str) and work_unit_id

    period = Period.from_year_and_code(_YEAR, "1T")
    _reauthenticate_profile(
        profile_label=api.profile_label,
        profile_id=api.profile_id,
        authority_operation=authority_operation,
    )
    IvaWalletDecisionRepository().save_decision(
        IvaCompensationReconciliationDecision(
            taxpayer_nif=directa_normal_tax_id(),
            target_year=_YEAR,
            target_period=period,
            target_registry_snapshot_ref=published_snapshot("303", filing_year=_YEAR, period="1T").snapshot_ref,
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
            wallet_captured_at=datetime(_YEAR, 4, 1, 10, tzinfo=UTC),
            decided_at=datetime(_YEAR, 4, 1, 10, tzinfo=UTC),
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
    return work_unit_id, calculation_revision_id


def _read_canonical_participation(
    api: NativeApiCliSession[dict[str, str]],
    authority_operation: PinnedAuthorityOperation,
    *,
    work_unit_id: str,
    calculation_revision_id: str,
) -> _CanonicalParticipation:
    """Only the in-window source transaction participates in the verified revision."""
    seeded = api.prepared
    period = Period.from_year_and_code(_YEAR, "1T")
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
    assert canonical_entry.filing_year == _YEAR
    assert canonical_entry.filing_record_id is None
    assert participation_repository.load(seeded["outside"]).participations == ()
    canonical_payload = canonical_index.model_dump(mode="json")
    close_active_bucket_session()
    return _CanonicalParticipation(bucket_id, revision_repository, revisions_before, canonical_index, canonical_payload)


def _assert_lookup_returns_canonical_index(
    api: NativeApiCliSession[dict[str, str]], canonical: _CanonicalParticipation
) -> None:
    seeded = api.prepared
    lookup = api.invoke_credential_reference("app", "ledger", "participation", seeded["source"])
    assert lookup.exit_code == 0, lookup.output
    assert unwrap_cli_result(lookup) == canonical.payload
    empty_lookup = api.invoke_credential_reference("app", "ledger", "participation", seeded["outside"])
    assert empty_lookup.exit_code == 0, empty_lookup.output
    assert unwrap_cli_result(empty_lookup) == {"transaction_id": seeded["outside"], "participations": []}


def _plant_stale_index(
    api: NativeApiCliSession[dict[str, str]],
    authority_operation: PinnedAuthorityOperation,
    canonical: _CanonicalParticipation,
) -> dict[str, Any]:
    """Save a participation for the outside transaction that no revision supports."""
    _reauthenticate_profile(
        profile_label=api.profile_label,
        profile_id=api.profile_id,
        authority_operation=authority_operation,
    )
    participation_repository = TransactionParticipationIndexRepository(bucket_id=canonical.bucket_id)
    stale_index = TransactionRevisionParticipationIndex(
        transaction_id=api.prepared["outside"],
        participations=canonical.index.participations,
    )
    participation_repository.save(stale_index)
    stale_payload = stale_index.model_dump(mode="json")
    close_active_bucket_session()
    return stale_payload


def _assert_rebuild_without_commit_is_denied(
    api: NativeApiCliSession[dict[str, str]],
    authority_operation: PinnedAuthorityOperation,
    canonical: _CanonicalParticipation,
    stale_payload: dict[str, Any],
) -> None:
    seeded = api.prepared
    refused_rebuild = api.invoke_credential_reference("app", "ledger", "participation", "rebuild")
    assert refused_rebuild.exit_code == 2, refused_rebuild.output
    refusal = require_error_document(refused_rebuild.output)["error"]
    assert refusal["code"] == "REFUSED_RUNTIME_FRONTEND", refusal
    context = refusal["context"]
    assert context == {"reason": "operation_denied", "request_faults": "", "sign_in": "null"}, refusal
    # Missing COMMIT is denied at admission, so there is no operation
    # receipt to inspect. Verify the actual encrypted records stayed intact
    # below, and retain the successful human rebuild as the positive control.
    assert "operation_id" not in context
    assert api.runtime_health().ready
    assert "stale_removed_count" not in refused_rebuild.output

    _reauthenticate_profile(
        profile_label=api.profile_label,
        profile_id=api.profile_id,
        authority_operation=authority_operation,
    )
    assert canonical.revision_repository.load(operation=authority_operation).revisions == canonical.revisions_before
    after_denial_repository = TransactionParticipationIndexRepository(bucket_id=canonical.bucket_id)
    assert after_denial_repository.load(seeded["source"]).model_dump(mode="json") == canonical.payload
    assert after_denial_repository.load(seeded["outside"]).model_dump(mode="json") == stale_payload
    assert after_denial_repository.exists(seeded["outside"])
    close_active_bucket_session()


def _assert_human_rebuild_prunes_only_the_stale_index(
    api: NativeApiCliSession[dict[str, str]],
    authority_operation: PinnedAuthorityOperation,
    canonical: _CanonicalParticipation,
) -> None:
    seeded = api.prepared
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
    assert canonical.revision_repository.load(operation=authority_operation).revisions == canonical.revisions_before
    rebuilt_repository = TransactionParticipationIndexRepository(bucket_id=canonical.bucket_id)
    assert rebuilt_repository.load(seeded["source"]).model_dump(mode="json") == canonical.payload
    assert rebuilt_repository.load(seeded["outside"]).participations == ()
    assert not rebuilt_repository.exists(seeded["outside"])
    close_active_bucket_session()


def test_native_participation_reads_canonical_index_rebuilds_and_requires_commit(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
    run_cadrumo_cli,
) -> None:
    """Lookup preserves the verified index; rebuild prunes stale cache under COMMIT authority."""

    def prepare_profile(profile_id: UUID, root: Path) -> dict[str, str]:
        facts_by_path = persona_fact_strings({"censo.activity_start_date": date(_YEAR, 1, 1).isoformat()})
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
        invoke_cli=run_cadrumo_cli,
    ) as api:
        close_active_bucket_session()
        assert set(api.prepared) == {"source", "outside"}

        work_unit_id, calculation_revision_id = _calculate_and_verify_303(api, authority_operation)
        canonical = _read_canonical_participation(
            api,
            authority_operation,
            work_unit_id=work_unit_id,
            calculation_revision_id=calculation_revision_id,
        )
        _assert_lookup_returns_canonical_index(api, canonical)
        stale_payload = _plant_stale_index(api, authority_operation, canonical)
        _assert_rebuild_without_commit_is_denied(api, authority_operation, canonical, stale_payload)
        _assert_human_rebuild_prunes_only_the_stale_index(api, authority_operation, canonical)
