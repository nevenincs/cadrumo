"""Real encrypted profile reads through the registered paged operation."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from cadrumo.adapters.persistence.operations.secure_references import operation_secure_reference_repository
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.operations.access_resolution import OperationAccessContext, resolve_operation_access
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.registry import OperationFrontendProjection, OperationRegistry
from cadrumo.application.operations.supervisor import OperationSupervisor
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
)
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.custody_ports import profile_custody_secure_object_repository
from cadrumo.application.user_profile.login_session import authenticate_profile_for_invocation
from cadrumo.application.user_profile.operations import (
    USER_PROFILE_OPERATION_DEFINITIONS,
    build_user_profile_operation_registrations,
)
from cadrumo.application.user_profile.profile_record_repository import ProfileRecordRepository
from cadrumo.application.user_profile.projections import record_to_path_values
from cadrumo.application.user_profile.registration import register_profile_with_credentials
from cadrumo.application.user_profile.tests.profile_values import complete_profile_facts
from cadrumo.application.user_profile.validation import MODELO_WORK_PROFILE_BASELINE_MISSING_CODE
from cadrumo.application.user_profile.view_operation import (
    PROFILE_VIEW_MAX_RESULT_BYTES,
    PROFILE_VIEW_OPERATION_DEFINITION_ID,
    ProfileViewFactItem,
    ProfileViewIssueItem,
    ProfileViewOperationRequest,
    ProfileViewOperationResult,
    ProfileViewPageKind,
    ProfileViewRefusalCode,
    ProfileViewStatusItem,
    project_profile_view_result,
)
from cadrumo.application.user_profile.view_reader import read_profile_view_page
from cadrumo.application.workflow.profile_health import ProfileHealthStatus, assess_profile_record_health
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact

from .supervision_support import run_to_settlement

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]
_PROFILE_CREDENTIAL = "profile-view-test-passphrase"


def _register_profile(*, facts: tuple[UserProfileFact, ...] = ()) -> UUID:
    with bundled_indexed_authority().operation() as authority:
        registered = register_profile_with_credentials(
            label="Profile view operation",
            passphrase=_PROFILE_CREDENTIAL,
            facts=facts,
            profile_create_context=authority.profile_create_context(),
            profile_decode_context=authority.profile_decode_context(),
        )
        authenticate_profile_for_invocation(
            name=registered.profile_id,
            passphrase_callback=lambda: _PROFILE_CREDENTIAL,
            profile_decode_context=authority.profile_decode_context(),
        )
    return UUID(registered.profile_id)


def _registry() -> OperationRegistry:
    return OperationRegistry(
        definitions=USER_PROFILE_OPERATION_DEFINITIONS,
        public_registrations=build_user_profile_operation_registrations(USER_PROFILE_OPERATION_DEFINITIONS),
    )


def test_registered_view_reads_real_encrypted_profile_and_pins_continuations(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path) as root:
        profile_id = _register_profile()
        with bundled_indexed_authority().operation() as authority:
            record = ProfileRecordRepository.for_current_session(
                profile_id, profile_decode_context=authority.profile_decode_context()
            ).load(profile_id)
            with profile_custody_secure_object_repository(profile_id=profile_id, dek=b"", root=root) as objects:
                assert isinstance(objects, SecureObjectRepository)
                operands = operation_secure_reference_repository(objects=objects)
                journal = OperationJournalRepository(storage_root=root)
                supervisor = OperationSupervisor(
                    authority_operation=authority,
                    registry=_registry(),
                    journal=journal,
                    event_stream=journal,
                    leases=OperationLeaseFilesystemRepository(storage_root=root),
                    operands=operands,
                    owner_id="1" * 64,
                    lease_token_factory=lambda: "2" * 64,
                    clock=lambda: datetime.now(UTC),
                    lease_duration=timedelta(minutes=6),
                )
                request = OperationRequest(
                    definition_id=PROFILE_VIEW_OPERATION_DEFINITION_ID,
                    subject_ref=f"profile:{profile_id}",
                    payload=ProfileViewOperationRequest(profile_id=profile_id, page_kind=ProfileViewPageKind.FACTS),
                )
                created = asyncio.run(supervisor.submit(request, operation_id="a" * 64))
                terminal = asyncio.run(run_to_settlement(supervisor, created))
                assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
                assert terminal.effect is OperationEffect.NONE
                assert terminal.terminal_receipt is not None
                assert terminal.terminal_receipt.result_ref is not None
                page = asyncio.run(operands.resolve(terminal.terminal_receipt.result_ref, ProfileViewOperationResult))
                assert page.outcome == "page"
                assert page.record_revision == record.record_revision
                assert page.content_digest == record.content_digest
                projection = project_profile_view_result(page, terminal.terminal_receipt)
                assert projection.model_dump(mode="json") == page.model_dump(mode="json")
                assert len(page.model_dump_json().encode("utf-8")) <= PROFILE_VIEW_MAX_RESULT_BYTES
                observed = list(page.items)
                while page.next_cursor is not None:
                    page = read_profile_view_page(
                        ProfileViewOperationRequest(
                            profile_id=profile_id,
                            page_kind=ProfileViewPageKind.FACTS,
                            cursor=page.next_cursor,
                            expected_revision=record.record_revision,
                            expected_content_digest=record.content_digest,
                        ),
                        authority_operation=authority,
                    )
                    assert page.outcome == "page"
                    observed.extend(page.items)
                assert [(item.path, item.value) for item in observed if isinstance(item, ProfileViewFactItem)] == [
                    (path, value) for path, value in sorted(record_to_path_values(record).items())
                ]
                stale = read_profile_view_page(
                    ProfileViewOperationRequest(
                        profile_id=profile_id,
                        page_kind=ProfileViewPageKind.ISSUES,
                        expected_revision=record.record_revision,
                        expected_content_digest="0" * 64,
                    ),
                    authority_operation=authority,
                )
                assert stale.outcome == "refused"
                assert stale.refusal_code is ProfileViewRefusalCode.STALE_REVISION
                assert not stale.items and stale.next_cursor is None


def test_view_access_requires_exact_profile_and_profile_values_disclosure() -> None:
    registry = _registry()
    profile_id = uuid4()
    request = OperationRequest(
        definition_id=PROFILE_VIEW_OPERATION_DEFINITION_ID,
        subject_ref=f"profile:{profile_id}",
        payload=ProfileViewOperationRequest(profile_id=profile_id, page_kind=ProfileViewPageKind.FACTS),
    )
    context = OperationAccessContext(
        profile_id=profile_id,
        destination_id=uuid4(),
        action=AccessAction.RESULT,
        frontend=OperationFrontendProjection.CLI,
        contract=registry.lookup_public_contract(PROFILE_VIEW_OPERATION_DEFINITION_ID),
        published_authority=Availability.AVAILABLE,
    )
    result = resolve_operation_access(registry=registry, request=request, context=context)
    assert len(result.policy.disclosures) == 1
    disclosure = next(iter(result.policy.disclosures))
    assert disclosure.category is DisclosureCategory.PROFILE_VALUES
    assert disclosure.destination_id == context.destination_id
    assert disclosure.projection_id == f"{PROFILE_VIEW_OPERATION_DEFINITION_ID}.result"
    metadata = resolve_operation_access(
        registry=registry, request=request, context=replace(context, action=AccessAction.OBSERVE)
    )
    assert next(iter(metadata.policy.disclosures)).category is DisclosureCategory.OPERATION_METADATA
    for wrong in (replace(context, profile_id=uuid4()),):
        with pytest.raises(ProfileAccessRefusedError) as error:
            resolve_operation_access(registry=registry, request=request, context=wrong)
        assert error.value.reason is AccessDenialCode.PROFILE_MISMATCH
    wrong_subject = OperationRequest(
        definition_id=PROFILE_VIEW_OPERATION_DEFINITION_ID,
        subject_ref=f"profile:{uuid4()}",
        payload=request.payload,
    )
    with pytest.raises(ProfileAccessRefusedError) as error:
        resolve_operation_access(registry=registry, request=wrong_subject, context=context)
    assert error.value.reason is AccessDenialCode.PROFILE_MISMATCH


def test_indivisible_oversized_fact_refuses_without_truncating(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _register_profile()
        oversized_value = "x" * (PROFILE_VIEW_MAX_RESULT_BYTES + 1)
        monkeypatch.setattr(
            "cadrumo.application.user_profile.view_reader.record_to_path_values",
            lambda _record: {"preferences.output_language": oversized_value},
        )
        with bundled_indexed_authority().operation() as authority:
            page = read_profile_view_page(
                ProfileViewOperationRequest(profile_id=profile_id, page_kind=ProfileViewPageKind.FACTS),
                authority_operation=authority,
            )
    assert page.outcome == "refused"
    assert page.refusal_code is ProfileViewRefusalCode.ITEM_TOO_LARGE
    assert page.items == ()
    assert page.next_cursor is None


def test_status_page_uses_exact_incomplete_record_health_and_pinned_revision(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _register_profile()
        with bundled_indexed_authority().operation() as authority:
            record = ProfileRecordRepository.for_current_session(
                profile_id, profile_decode_context=authority.profile_decode_context()
            ).load(profile_id)
            page = read_profile_view_page(
                ProfileViewOperationRequest(profile_id=profile_id, page_kind=ProfileViewPageKind.STATUS),
                authority_operation=authority,
            )
            expected = assess_profile_record_health(
                record, source="env_override", label="Profile view operation", operation=authority
            )
            assert page.outcome == "page"
            assert page.record_revision == record.record_revision
            assert page.content_digest == record.content_digest
            assert page.total_items == 1 and page.next_cursor is None
            assert len(page.items) == 1
            status = page.items[0]
            assert isinstance(status, ProfileViewStatusItem)
            assert status.display_name == "Profile view operation"
            assert status.health.active_profile == str(profile_id)
            assert status.health.status is ProfileHealthStatus.INCOMPLETE
            assert status.health.missing_required == expected.missing_required
            assert status.health.precondition_verdict is not None
            assert status.health.precondition_verdict.to_verdict() == expected.precondition_verdict
            assert not status.baseline_ready and not status.projection_valid
            assert {item.path for item in status.facts} <= {
                "identity.tax_id",
                "activities.description",
                "iva.regime",
                "tax_residence.ccaa",
            }
            stale = read_profile_view_page(
                ProfileViewOperationRequest(
                    profile_id=profile_id,
                    page_kind=ProfileViewPageKind.STATUS,
                    expected_revision=record.record_revision,
                    expected_content_digest="0" * 64,
                ),
                authority_operation=authority,
            )
            assert stale.outcome == "refused"
            assert stale.refusal_code is ProfileViewRefusalCode.STALE_REVISION
            assert stale.items == ()


def test_status_page_ready_record_projects_only_declared_facts(tmp_path: Path) -> None:
    facts = tuple(
        UserProfileFact(path=path, value=value)
        for path, value in (
            ("taxpayer_type.entity_type", "natural_person"),
            ("identity.name", "Test"),
            ("identity.surnames", "Operator"),
            ("identity.tax_id", "00000000T"),
            ("activities.description", "Servicios"),
            ("censo.activity_start_date", "2026-01-01"),
            ("taxpayer_type.irpf_income_categories", "actividad_economica"),
            ("irpf.estimation_regime", "directa_normal"),
            ("tax_residence.ccaa", "madrid"),
            ("iva.regime", "GENERAL"),
            ("iva.m303_regime_composition", "general"),
            ("iva.redeme_enrolled", "false"),
            ("iva.cash_accounting_regime_enrolled", "false"),
            ("iva.voluntary_sii_enrolled", "false"),
            ("iva.hydrocarbon_deposit_advance_payment_deduction_entitled", "false"),
            ("tax_residence.jurisdiction_scope", "common_regime"),
        )
    )
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _register_profile(facts=facts)
        with bundled_indexed_authority().operation() as authority:
            page = read_profile_view_page(
                ProfileViewOperationRequest(profile_id=profile_id, page_kind=ProfileViewPageKind.STATUS),
                authority_operation=authority,
            )
            assert page.outcome == "page"
            assert len(page.items) == 1
            status = page.items[0]
            assert isinstance(status, ProfileViewStatusItem)
            assert status.health.status is ProfileHealthStatus.READY
            assert status.health.precondition_verdict is None
            assert status.baseline_ready
            assert status.projection_valid
            assert [(item.path, item.value) for item in status.facts] == [
                ("activities.description", "Servicios"),
                ("identity.tax_id", "00000000T"),
                ("iva.regime", "GENERAL"),
                ("tax_residence.ccaa", "madrid"),
            ]
            assert len(page.model_dump_json().encode("utf-8")) <= PROFILE_VIEW_MAX_RESULT_BYTES


def test_readiness_issues_adds_canonical_baseline_without_changing_schema_issues(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        with bundled_indexed_authority().operation() as authority:
            facts = complete_profile_facts(
                authority.profile_schema(),
                (
                    UserProfileFact(path="identity.tax_id", value="00000000T"),
                    UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                    UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
                ),
            )
        assert not any(fact.path == "activities.description" for fact in facts)
        profile_id = _register_profile(facts=facts)
        with bundled_indexed_authority().operation() as authority:
            repository = ProfileRecordRepository.for_current_session(
                profile_id, profile_decode_context=authority.profile_decode_context()
            )
            incomplete = repository.load(profile_id)
            record = repository.complete_setup(
                profile_id,
                expected_revision=incomplete.record_revision,
                expected_content_digest=incomplete.content_digest,
            )
            assert record.setup_state is ProfileSetupState.COMPLETE
            schema = read_profile_view_page(
                ProfileViewOperationRequest(profile_id=profile_id, page_kind=ProfileViewPageKind.ISSUES),
                authority_operation=authority,
            )
            readiness = read_profile_view_page(
                ProfileViewOperationRequest(profile_id=profile_id, page_kind=ProfileViewPageKind.READINESS_ISSUES),
                authority_operation=authority,
            )
            assert schema.outcome == readiness.outcome == "page"
            assert schema.valid and readiness.valid
            assert not any(
                isinstance(item, ProfileViewIssueItem)
                and item.code == MODELO_WORK_PROFILE_BASELINE_MISSING_CODE
                and item.path == "activities.description"
                for item in schema.items
            )
            assert any(
                isinstance(item, ProfileViewIssueItem)
                and item.code == MODELO_WORK_PROFILE_BASELINE_MISSING_CODE
                and item.path == "activities.description"
                for item in readiness.items
            )
            assert len(
                {(item.code, item.path) for item in readiness.items if isinstance(item, ProfileViewIssueItem)}
            ) == len(readiness.items)
            assert readiness.record_revision == schema.record_revision == record.record_revision
            assert readiness.content_digest == schema.content_digest == record.content_digest


def test_readiness_issues_pages_and_pins_like_other_view_streams(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _register_profile()
        with bundled_indexed_authority().operation() as authority:
            first = read_profile_view_page(
                ProfileViewOperationRequest(
                    profile_id=profile_id, page_kind=ProfileViewPageKind.READINESS_ISSUES, limit=1
                ),
                authority_operation=authority,
            )
            assert first.outcome == "page" and first.next_cursor == 1 and first.total_items > 1
            assert len(first.items) == 1 and isinstance(first.items[0], ProfileViewIssueItem)
            second = read_profile_view_page(
                ProfileViewOperationRequest(
                    profile_id=profile_id,
                    page_kind=ProfileViewPageKind.READINESS_ISSUES,
                    cursor=first.next_cursor,
                    limit=1,
                    expected_revision=first.record_revision,
                    expected_content_digest=first.content_digest,
                ),
                authority_operation=authority,
            )
            assert second.outcome == "page" and second.cursor == 1 and len(second.items) == 1
            stale = read_profile_view_page(
                ProfileViewOperationRequest(
                    profile_id=profile_id,
                    page_kind=ProfileViewPageKind.READINESS_ISSUES,
                    cursor=first.next_cursor,
                    expected_revision=first.record_revision,
                    expected_content_digest="0" * 64,
                ),
                authority_operation=authority,
            )
            assert stale.outcome == "refused"
            assert stale.refusal_code is ProfileViewRefusalCode.STALE_REVISION
            assert stale.items == () and stale.next_cursor is None
