"""Calculation-summary operation custody, schema, and canonical verifier wiring."""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....core.config import override_settings
from ....core.hashing import sha256_hex
from ....core.operations import OperationEffect, profile_operation_subject
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.capabilities import OperationRequestStoragePolicy, OperationSensitiveInputPolicy
from ...operations.models import OperationRequest
from ...operations.owner import OperationExecutorContext
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ...user_profile.access_contracts import AccessAction, AccessDenialCode, Availability, DisclosureCategory
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..calculation_report_verification import (
    CalculationSummaryCheckName,
    CalculationSummaryStoreContext,
    CalculationSummaryVerification,
    CalculationSummaryVerificationCheck,
    CalculationSummaryVerificationLayer,
    CalculationSummaryVerificationOutcome,
    CalculationSummaryVerificationReason,
)
from ..calculation_report_verification_operation import (
    MODELO_CALCULATION_REPORT_VERIFY_OPERATION_DEFINITION_ID,
    ModeloCalculationReportVerificationPorts,
    ModeloCalculationReportVerificationProjection,
    ModeloCalculationReportVerificationRequest,
    ModeloCalculationReportVerificationResult,
    build_modelo_calculation_report_verify_definition,
    build_modelo_calculation_report_verify_registration,
)
from ..calculation_summary_pdf_ports import CalculationSummaryPdfContents
from ..export_ports import ModeloExportPorts
from ..review_package_signing_ports import ReviewPackageSigningKeypairReader

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")
_AUTHORITY = cast(PinnedAuthorityOperation, object())
_SOURCE = b"local summary bytes"


def _request(path: Path) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=MODELO_CALCULATION_REPORT_VERIFY_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=ModeloCalculationReportVerificationRequest(
            profile_id=_PROFILE, source_path=str(path), source_sha256=sha256_hex(_SOURCE)
        ),
    )


def _context(request, stored: list[BaseModel], effects: list[OperationEffect]) -> OperationExecutorContext:
    class Events:
        async def phase(self, _phase: str) -> None:
            pass

        async def effect(self, effect: OperationEffect) -> None:
            effects.append(effect)

    class Operands:
        async def put(self, operand: BaseModel, *, written_at: datetime) -> str:
            assert written_at.tzinfo is not None
            stored.append(operand)
            return "f" * 64

    return cast(
        OperationExecutorContext,
        cast(
            object,
            SimpleNamespace(
                identity=SimpleNamespace(definition_id=request.definition_id, subject_ref=request.subject_ref),
                authority_operation=_AUTHORITY,
                events=Events(),
                operands=Operands(),
            ),
        ),
    )


def _unavailable_factory(*, profile_id: UUID, operation: PinnedAuthorityOperation):
    pytest.fail("verification ports must not be accessed")


def test_foreign_profile_is_refused_before_source_access(tmp_path: Path) -> None:
    source_reads: list[Path] = []

    def read(path: Path) -> bytes:
        source_reads.append(path)
        return _SOURCE

    definition = build_modelo_calculation_report_verify_definition(_unavailable_factory, source_reader=read)
    request = _request(tmp_path / "summary.pdf")
    stored: list[BaseModel] = []
    effects: list[OperationEffect] = []
    with (
        override_settings(cadrumo_active_profile=str(_OTHER_PROFILE)),
        pytest.raises(ProfileAccessRefusedError) as error,
    ):
        asyncio.run(definition.executor_factory.create().execute(request, _context(request, stored, effects)))
    assert error.value.reason is AccessDenialCode.PROFILE_MISMATCH
    assert source_reads == []
    assert stored == []
    assert effects == []


def test_source_drift_is_refused_before_profile_reads(tmp_path: Path) -> None:
    path = tmp_path / "summary.pdf"
    path.write_bytes(b"changed summary bytes")
    definition = build_modelo_calculation_report_verify_definition(_unavailable_factory)
    request = _request(path)
    stored: list[BaseModel] = []
    effects: list[OperationEffect] = []
    with override_settings(cadrumo_active_profile=str(_PROFILE)), pytest.raises(ProfileAccessRefusedError) as error:
        asyncio.run(definition.executor_factory.create().execute(request, _context(request, stored, effects)))
    assert error.value.reason is AccessDenialCode.OPERATION_DENIED
    assert stored == []
    assert effects == []


def test_closed_public_projection_preserves_all_verification_checks() -> None:
    checks = tuple(
        CalculationSummaryVerificationCheck(
            check=CalculationSummaryCheckName.TEXT_LAYER,
            layer=CalculationSummaryVerificationLayer.DOCUMENT,
            reason=reason,
            detail=f"page {index}: á",
        )
        for index, reason in enumerate(CalculationSummaryVerificationReason)
    )
    verification = CalculationSummaryVerification(
        outcome=CalculationSummaryVerificationOutcome.REFUSED,
        checks=checks,
        store_checked=True,
        signing_key_fingerprint="a" * 64,
        calculation_revision_id="b" * 64,
        report_sha256="c" * 64,
        statement_sha256="d" * 64,
    )
    projection = ModeloCalculationReportVerificationProjection(
        profile_id=_PROFILE,
        source_sha256=sha256_hex(_SOURCE),
        verification=ModeloCalculationReportVerificationResult.from_verification(verification),
    )
    restored = ModeloCalculationReportVerificationProjection.model_validate_json(projection.model_dump_json())
    assert restored.verification.to_verification() == verification
    assert restored.verification.to_verification().reasons == tuple(CalculationSummaryVerificationReason)
    with pytest.raises(ValidationError):
        ModeloCalculationReportVerificationProjection.model_validate_json(
            projection.model_dump_json().replace('"result_version":1', '"result_version":1,"extra":true')
        )


def test_registration_requires_all_periods_and_excludes_commit_without_reads(tmp_path: Path) -> None:
    definition = build_modelo_calculation_report_verify_definition(_unavailable_factory)
    registration = build_modelo_calculation_report_verify_registration(definition)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    request = _request(tmp_path / "absent.pdf")
    for action, category in (
        (AccessAction.OBSERVE, DisclosureCategory.OPERATION_METADATA),
        (AccessAction.RESULT, DisclosureCategory.TAX_VALUES),
    ):
        context = OperationAccessContext(
            profile_id=_PROFILE,
            destination_id=uuid4(),
            action=action,
            frontend=OperationFrontendProjection.CLI,
            contract=registration.contract,
            published_authority=Availability.AVAILABLE,
            authority_operation=_AUTHORITY,
        )
        access = resolve_operation_access(registry=registry, request=request, context=context)
        assert access.request.period_independent is True
        assert access.request.periods == frozenset()
        assert access.policy.requires_all_periods is True
        assert AccessAction.COMMIT not in access.policy.actions
        assert next(iter(access.policy.disclosures)).category is category
    assert definition.capabilities.permitted_effects == frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN})
    assert definition.capabilities.request_storage is OperationRequestStoragePolicy.SECURE_REFERENCE
    assert definition.capabilities.sensitive_input is OperationSensitiveInputPolicy.SECURE_REFERENCE
    assert definition.permitted_frontends == frozenset(
        {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}
    )


def test_executor_uses_canonical_verifier_and_same_source_bytes(tmp_path: Path) -> None:
    path = tmp_path / "summary.pdf"
    path.write_bytes(_SOURCE)
    seen_sources: list[bytes] = []
    factory_calls: list[tuple[UUID, PinnedAuthorityOperation]] = []

    def reader(source: bytes, /) -> CalculationSummaryPdfContents:
        seen_sources.append(source)
        return CalculationSummaryPdfContents(
            attachments={},
            product_metadata=None,
            visible_layer_sha256="e" * 64,
            visible_layer_overlays=(),
            page_text="",
        )

    def factory(*, profile_id: UUID, operation: PinnedAuthorityOperation) -> ModeloCalculationReportVerificationPorts:
        factory_calls.append((profile_id, operation))
        return ModeloCalculationReportVerificationPorts(
            profile_id=profile_id,
            reader=reader,
            store=CalculationSummaryStoreContext(
                active_bucket_id=str(profile_id),
                export_ports=cast(ModeloExportPorts, object()),
                signing_keypair=cast(ReviewPackageSigningKeypairReader, object()),
                operation=operation,
            ),
        )

    definition = build_modelo_calculation_report_verify_definition(factory)
    request = _request(path)
    stored: list[BaseModel] = []
    effects: list[OperationEffect] = []
    with override_settings(cadrumo_active_profile=str(_PROFILE)):
        reference = asyncio.run(
            definition.executor_factory.create().execute(request, _context(request, stored, effects))
        )
    assert reference == "f" * 64
    assert factory_calls == [(_PROFILE, _AUTHORITY)]
    assert seen_sources == [_SOURCE]
    assert effects == [OperationEffect.NONE]
    projection = ModeloCalculationReportVerificationProjection.model_validate(stored[0])
    assert projection.profile_id == _PROFILE
    assert projection.source_sha256 == sha256_hex(_SOURCE)
    verification = projection.verification.to_verification()
    assert verification.outcome is CalculationSummaryVerificationOutcome.REFUSED
    assert verification.store_checked is False
    assert tuple(row.check for row in verification.checks) == (
        CalculationSummaryCheckName.PDF,
        CalculationSummaryCheckName.CADRUMO_REPORT,
    )
    assert verification.reasons == (CalculationSummaryVerificationReason.NOT_A_CADRUMO_REPORT,)
