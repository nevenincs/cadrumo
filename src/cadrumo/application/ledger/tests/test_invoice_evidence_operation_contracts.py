"""Exact-profile invoice evidence operations declare truthful access and review binding."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....core.config_support import LLMProvider
from ....core.operations import OperationEffect, profile_operation_subject
from ....domain.iva.classification import InvoiceKind
from ...local_reader import LocalReaderStatus
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationRequest
from ...operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationRegistry,
)
from ...user_profile.access_contracts import AccessAction, Availability, DisclosureCategory
from ..invoice_evidence_confirm_operation import (
    LEDGER_EVIDENCE_CONFIRM_OPERATION_DEFINITION_ID,
    LedgerEvidenceConfirmRequest,
    build_ledger_evidence_confirm_definition,
    build_ledger_evidence_confirm_registration,
)
from ..invoice_evidence_extract_operation import (
    LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID,
    LedgerEvidenceExtractRequest,
    build_ledger_evidence_extract_definition,
    build_ledger_evidence_extract_registration,
)
from ..invoice_evidence_operation import InvoiceEvidenceOperationPorts, InvoiceEvidenceOperationPortsFactory
from ..invoice_evidence_readiness_operation import (
    LEDGER_EVIDENCE_READER_READINESS_OPERATION_DEFINITION_ID,
    LedgerEvidenceReaderReadinessRequest,
    build_ledger_evidence_reader_readiness_definition,
    build_ledger_evidence_reader_readiness_registration,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")


def _registrations() -> tuple[OperationRegistry, tuple[OperationPublicDefinitionRegistrationV1, ...]]:
    def unused_factory(
        *,
        bucket_id: str,
        before_consent_save: Callable[[], None] | None = None,
        after_consent_save: Callable[[bool], None] | None = None,
    ) -> InvoiceEvidenceOperationPorts:
        raise AssertionError("contract tests never open a profile bundle")

    typed_factory: InvoiceEvidenceOperationPortsFactory = unused_factory
    definitions = (
        build_ledger_evidence_reader_readiness_definition(cast(Callable[[], LocalReaderStatus], lambda: None)),
        build_ledger_evidence_extract_definition(typed_factory),
        build_ledger_evidence_confirm_definition(typed_factory),
    )
    registrations = (
        build_ledger_evidence_reader_readiness_registration(definitions[0]),
        build_ledger_evidence_extract_registration(definitions[1]),
        build_ledger_evidence_confirm_registration(definitions[2]),
    )
    ordered = tuple(sorted(registrations, key=lambda registration: registration.contract.definition_id))
    return OperationRegistry(definitions=definitions, public_registrations=ordered), registrations


def _context(registration: OperationPublicDefinitionRegistrationV1) -> OperationAccessContext:
    return OperationAccessContext(
        profile_id=_PROFILE,
        destination_id=uuid4(),
        action=AccessAction.RESULT,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
    )


def _request(definition_id: str, payload: BaseModel) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=payload,
    )


def test_readiness_is_profile_metadata_while_document_operations_require_all_periods() -> None:
    registry, registrations = _registrations()
    payloads: tuple[BaseModel, ...] = (
        LedgerEvidenceReaderReadinessRequest(profile_id=_PROFILE),
        LedgerEvidenceExtractRequest(profile_id=_PROFILE, evidence_id="e" * 16),
        LedgerEvidenceConfirmRequest(
            profile_id=_PROFILE,
            evidence_id="e" * 16,
            expected_source_sha256="a" * 64,
            expected_draft_review_sha256="b" * 64,
            kind=InvoiceKind.RECEIVED,
        ),
    )
    ids = (
        LEDGER_EVIDENCE_READER_READINESS_OPERATION_DEFINITION_ID,
        LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID,
        LEDGER_EVIDENCE_CONFIRM_OPERATION_DEFINITION_ID,
    )
    for index, (definition_id, payload, registration) in enumerate(zip(ids, payloads, registrations, strict=True)):
        context = _context(registration)
        resolved = resolve_operation_access(
            registry=registry,
            request=_request(definition_id, payload),
            context=context,
        )
        assert resolved.request.profile_id == _PROFILE
        assert resolved.policy.requires_all_periods is (index != 0)
        assert any(
            disclosure.destination_id == context.destination_id
            and disclosure.category
            is (DisclosureCategory.PROFILE_VALUES if index == 0 else DisclosureCategory.TAX_VALUES)
            for disclosure in resolved.policy.disclosures
        )
        assert (AccessAction.COMMIT in resolved.policy.actions) is (index == 2)


def test_only_explicit_off_host_extraction_acquires_commit_and_cannot_use_an_attachment_alone() -> None:
    registry, registrations = _registrations()
    off_host = LedgerEvidenceExtractRequest(
        profile_id=_PROFILE,
        evidence_id="e" * 16,
        off_host_provider=LLMProvider.ANTHROPIC,
        acknowledge_off_host=True,
    )
    resolved = resolve_operation_access(
        registry=registry,
        request=_request(LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID, off_host),
        context=_context(registrations[1]),
    )
    assert AccessAction.COMMIT in resolved.policy.actions

    with pytest.raises(ValidationError):
        LedgerEvidenceExtractRequest(
            profile_id=_PROFILE,
            attachment_id="a" * 64,
            off_host_provider=LLMProvider.ANTHROPIC,
            acknowledge_off_host=True,
        )
    with pytest.raises(ValidationError):
        LedgerEvidenceExtractRequest(profile_id=_PROFILE, evidence_id="e" * 16, acknowledge_off_host=True)


def test_confirmation_requires_both_review_addresses_and_canonical_amounts() -> None:
    with pytest.raises(ValidationError):
        LedgerEvidenceConfirmRequest.model_validate(
            {
                "profile_id": _PROFILE,
                "evidence_id": "e" * 16,
                "expected_source_sha256": "a" * 64,
                "kind": InvoiceKind.RECEIVED,
            }
        )
    with pytest.raises(ValidationError):
        LedgerEvidenceConfirmRequest(
            profile_id=_PROFILE,
            evidence_id="e" * 16,
            expected_source_sha256="a" * 64,
            expected_draft_review_sha256="b" * 64,
            kind=InvoiceKind.RECEIVED,
            taxable_base="nan",
        )


def test_three_definitions_never_reconcile_into_a_second_consent_or_confirmation() -> None:
    registry, _ = _registrations()
    for definition_id in (
        LEDGER_EVIDENCE_READER_READINESS_OPERATION_DEFINITION_ID,
        LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID,
        LEDGER_EVIDENCE_CONFIRM_OPERATION_DEFINITION_ID,
    ):
        definition = registry.lookup(definition_id)
        assert definition.reconciliation_policy.value == "interrupt"
        assert definition.capabilities.replay.value == "none"
        assert OperationEffect.UNKNOWN in definition.capabilities.permitted_effects
