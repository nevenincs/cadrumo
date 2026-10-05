"""Revision operations retain typed results and actual publication effects."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.application.modelo.calculation import visible_calculation_casilla_values
from cadrumo.application.modelo.calculation_actions import calculate_modelo_revision
from cadrumo.application.modelo.revision_inventory_operation import (
    MODELO_WORK_REVISIONS_OPERATION_DEFINITION_ID,
    ModeloWorkRevisionsProjection,
    ModeloWorkRevisionsRequest,
)
from cadrumo.application.modelo.revision_operation_access import compose_modelo_revision_access
from cadrumo.application.modelo.revision_snapshot_operation import (
    MODELO_WORK_REVISION_SNAPSHOT_OPERATION_DEFINITION_ID,
    ModeloWorkRevisionSnapshotProjection,
    ModeloWorkRevisionSnapshotRequest,
)
from cadrumo.application.modelo.work_amend_contracts import (
    ModeloWorkAmendBaseline,
    ModeloWorkAmendOverride,
    ModeloWorkAmendRequest,
)
from cadrumo.application.modelo.work_verification_contracts import (
    ModeloWorkVerifyPublicResultV2,
    ModeloWorkVerifyRequest,
)
from cadrumo.application.operations.access_resolution import OperationAccessContext, resolve_operation_access
from cadrumo.application.operations.frontend_requests import (
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.public_scalar import PublicDecimal
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import AccessAction, AccessDenialCode, AccessScope, Availability
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.operation_access_policy import operation_scope_refusal
from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.modelos.calculation_revision_amendment import CalculationRevisionAmendmentKind
from cadrumo.entrypoints.tests.modelo_operation_test_support import (
    FIRST_QUARTER_PRIOR_PERIOD_BINDINGS,
    MODELO_OPERATION_TEST_ACTOR,
    seeded_modelo_calculation_revision,
    seeded_modelo_verification_report,
)

from ..adapter_composition import build_calculation_action_ports, build_verification_repository_bundle
from .test_registered_executor_conformance import (
    _CloseWitness,
    _runtime,
    _seeded_modelo_filing_record,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize("already_verified", [False, True])
def test_verification_projects_persisted_report_and_authoritative_noop(
    tmp_path: Path, *, already_verified: bool, operation: PinnedAuthorityOperation
) -> None:
    """A fresh attempt writes a report; a sealed retry returns it without effects."""
    with _runtime(tmp_path / "verify", cleanup=_CloseWitness()) as (driver, registry, profile_id):
        if already_verified:
            revision_id, _report_id = seeded_modelo_verification_report(profile_id, operation=operation)
        else:
            revision_id = seeded_modelo_calculation_revision(profile_id, operation=operation)
        revision = CalculationRevisionCatalogueRepository().load().get(revision_id)
        assert revision is not None
        unit = WorkUnitCatalogueRepository().load().get(revision.work_unit_id)
        assert unit is not None
        payload = ModeloWorkVerifyRequest(calculation_revision_id=revision_id, actor=MODELO_OPERATION_TEST_ACTOR)
        request = OperationRequest(definition_id="modelo.work.verify", subject_ref=unit.work_unit_id, payload=payload)
        contract = registry.lookup_public_contract(request.definition_id)
        assert contract.result_schema is not None
        context = OperationAccessContext(
            profile_id=profile_id,
            destination_id=uuid4(),
            action=AccessAction.SUBMIT,
            frontend=OperationFrontendProjection.CLI,
            contract=contract,
            published_authority=Availability.AVAILABLE,
            authority_operation=operation,
        )
        access = resolve_operation_access(registry=registry, request=request, context=context)
        assert access.request.periods == frozenset({unit.period})
        assert AccessAction.COMMIT in access.policy.actions
        with pytest.raises(ProfileAccessRefusedError) as denied:
            resolve_operation_access(
                registry=registry,
                request=OperationRequest(definition_id=request.definition_id, subject_ref=revision_id, payload=payload),
                context=context,
            )
        assert denied.value.reason is AccessDenialCode.OPERATION_DENIED
        repositories = build_verification_repository_bundle(str(profile_id), operation=operation)
        bound = compose_modelo_revision_access(lambda _profile_id, *, operation: repositories)
        with pytest.raises(ProfileAccessRefusedError) as foreign:
            bound(request, replace(context, profile_id=uuid4()))
        assert foreign.value.reason is AccessDenialCode.PROFILE_MISMATCH

        submitted, observed = asyncio.run(
            driver.run(definition_id=request.definition_id, subject_ref=request.subject_ref, payload=payload)
        )
        terminal = observed.projection
        assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
        assert terminal.effect is (OperationEffect.NONE if already_verified else OperationEffect.UPDATED)
        assert terminal.result_ref is not None and terminal.result_ref != revision_id
        resolved = asyncio.run(
            driver.services.result.resolve(
                OperationResultProjectionRequestV1(
                    operation_id=submitted.receipt.operation_id,
                    terminal_revision=terminal.revision,
                    definition_contract_digest=contract.definition_contract_digest,
                    result_schema=contract.result_schema,
                ),
                ModeloWorkVerifyPublicResultV2,
            )
        )
        assert isinstance(resolved, OperationResultProjectionSuccessV1)
        projection = resolved.projection
        report = VerificationReportCatalogueRepository().load().get(projection.verification_report_id)
        assert report is not None
        assert projection.verification.to_verification().report == report
        assert projection.verification.published is not already_verified
        assert projection.advisories.work_unit_id == unit.work_unit_id
        assert projection.advisories.calculation_revision_id == revision_id
        assert projection.advisories.period == unit.period.registry_token
        assert projection.calculation_revision_id == revision_id
        assert projection.completeness_status == report.completeness_status.value
        assert projection.granted_verificado_completo is report.granted_verificado_completo
        assert projection.finding_count == len(report.findings)
        assert projection.missing_required_casilla_count == len(report.missing_required_casilla_ids)


def test_revision_snapshot_reads_exact_historical_revision_under_sealed_period(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """The encrypted snapshot reads the requested historical revision without mutation authority."""
    with _runtime(tmp_path / "revision-snapshot", cleanup=_CloseWitness()) as (driver, registry, profile_id):
        historical_revision_id = seeded_modelo_calculation_revision(profile_id, operation=operation)
        historical = CalculationRevisionCatalogueRepository().load().get(historical_revision_id)
        assert historical is not None
        unit = WorkUnitCatalogueRepository().load().get(historical.work_unit_id)
        assert unit is not None

        newer = calculate_modelo_revision(
            historical.work_unit_id,
            ports=build_calculation_action_ports(bucket_id=str(profile_id), operation=operation),
            actor=MODELO_OPERATION_TEST_ACTOR,
            casilla_inputs={validated_casilla_id("06"): Decimal("0")},
            binding_values=FIRST_QUARTER_PRIOR_PERIOD_BINDINGS,
        )
        assert newer.calculation_revision_id != historical_revision_id
        assert newer.created_at > historical.created_at
        persisted_revisions = CalculationRevisionCatalogueRepository().load().for_work_unit(historical.work_unit_id)
        assert {revision.calculation_revision_id for revision in persisted_revisions} >= {
            historical_revision_id,
            newer.calculation_revision_id,
        }

        payload = ModeloWorkRevisionSnapshotRequest(
            profile_id=profile_id,
            calculation_revision_id=historical_revision_id,
        )
        request = OperationRequest(
            definition_id=MODELO_WORK_REVISION_SNAPSHOT_OPERATION_DEFINITION_ID,
            subject_ref=historical.work_unit_id,
            payload=payload,
        )
        contract = registry.lookup_public_contract(request.definition_id)
        submit_context = OperationAccessContext(
            profile_id=profile_id,
            destination_id=uuid4(),
            action=AccessAction.SUBMIT,
            frontend=OperationFrontendProjection.CLI,
            contract=contract,
            published_authority=Availability.AVAILABLE,
            authority_operation=operation,
        )
        submitted_access = resolve_operation_access(registry=registry, request=request, context=submit_context)
        assert submitted_access.request.periods == frozenset({unit.period})
        assert AccessAction.COMMIT not in submitted_access.policy.actions

        sealed_result_context = replace(
            submit_context,
            action=AccessAction.RESULT,
            admitted_request=submitted_access.request,
            authority_operation=None,
        )
        result_access = resolve_operation_access(registry=registry, request=request, context=sealed_result_context)
        assert result_access.request.periods == frozenset({unit.period})
        assert AccessAction.COMMIT not in result_access.policy.actions
        with pytest.raises(ProfileAccessRefusedError) as foreign_profile:
            resolve_operation_access(
                registry=registry,
                request=OperationRequest(
                    definition_id=request.definition_id,
                    subject_ref=request.subject_ref,
                    payload=payload.model_copy(update={"profile_id": uuid4()}),
                ),
                context=submit_context,
            )
        assert foreign_profile.value.reason is AccessDenialCode.PROFILE_MISMATCH

        submitted, observed = asyncio.run(
            driver.run(
                definition_id=request.definition_id,
                subject_ref=request.subject_ref,
                payload=payload,
            )
        )
        terminal = observed.projection
        assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
        assert terminal.effect is OperationEffect.NONE
        assert terminal.result_ref is not None and terminal.result_ref != historical_revision_id
        assert contract.result_schema is not None
        resolved = asyncio.run(
            driver.services.result.resolve(
                OperationResultProjectionRequestV1(
                    operation_id=submitted.receipt.operation_id,
                    terminal_revision=terminal.revision,
                    definition_contract_digest=contract.definition_contract_digest,
                    result_schema=contract.result_schema,
                ),
                ModeloWorkRevisionSnapshotProjection,
            )
        )
        assert isinstance(resolved, OperationResultProjectionSuccessV1)
        projection = resolved.projection
        assert projection.profile_id == profile_id
        assert projection.unit.work_unit_id == historical.work_unit_id
        assert projection.calculation.calculation_revision_id == historical_revision_id
        snapshot_casilla_values: dict[str, str] = {}
        for item in projection.calculation.casilla_values:
            assert isinstance(item.value, PublicDecimal)
            snapshot_casilla_values[item.key] = item.value.decimal
        assert snapshot_casilla_values == {
            str(casilla_id): str(value)
            for casilla_id, value in visible_calculation_casilla_values(historical, operation=operation).items()
        }
        snapshot_inputs = {item.key: item.value for item in projection.calculation.input_values_by_casilla_id}
        assert snapshot_inputs == historical.input_values_by_casilla_id
        assert snapshot_inputs != newer.input_values_by_casilla_id
        assert projection.unit.period == projection.calculation.period


def test_amendment_access_uses_exact_filing_source_profile_subject_and_period(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """The amendment subject and access period come from the persisted filing chain."""
    with _runtime(tmp_path / "amend-access", cleanup=_CloseWitness()) as (_driver, registry, profile_id):
        filing_record_id, casilla_id = _seeded_modelo_filing_record(profile_id, operation=operation)
        filing = ModeloRecordCatalogueRepository().load().get(filing_record_id)
        assert filing is not None
        revision = CalculationRevisionCatalogueRepository().load().get(filing.calculation_revision_id)
        assert revision is not None
        unit = WorkUnitCatalogueRepository().load().get(filing.work_unit_id)
        assert unit is not None

        payload = ModeloWorkAmendRequest(
            baseline=ModeloWorkAmendBaseline(from_filing_record_id=filing_record_id),
            amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
            overrides=(ModeloWorkAmendOverride(casilla_id=casilla_id, value="101"),),
            reason="corrected source amount",
            actor=MODELO_OPERATION_TEST_ACTOR,
        )
        request = OperationRequest(
            definition_id="modelo.work.amend",
            subject_ref=unit.work_unit_id,
            payload=payload,
        )
        contract = registry.lookup_public_contract(request.definition_id)
        context = OperationAccessContext(
            profile_id=profile_id,
            destination_id=uuid4(),
            action=AccessAction.SUBMIT,
            frontend=OperationFrontendProjection.CLI,
            contract=contract,
            published_authority=Availability.AVAILABLE,
            authority_operation=operation,
        )

        access = resolve_operation_access(registry=registry, request=request, context=context)

        assert filing.work_unit_id == unit.work_unit_id == revision.work_unit_id
        assert filing.period == unit.period
        assert access.request.profile_id == profile_id
        assert access.request.periods == frozenset({filing.period})
        assert AccessAction.COMMIT in access.policy.actions

        repositories = build_verification_repository_bundle(str(profile_id), operation=operation)
        bound = compose_modelo_revision_access(lambda _profile_id, *, operation: repositories)
        with pytest.raises(ProfileAccessRefusedError) as foreign_profile:
            bound(request, replace(context, profile_id=uuid4()))
        assert foreign_profile.value.reason is AccessDenialCode.PROFILE_MISMATCH

        wrong_subject = OperationRequest(
            definition_id=request.definition_id,
            subject_ref=revision.calculation_revision_id,
            payload=payload,
        )
        with pytest.raises(ProfileAccessRefusedError) as foreign_subject:
            bound(wrong_subject, context)
        assert foreign_subject.value.reason is AccessDenialCode.OPERATION_DENIED


@pytest.mark.timeout(90)
def test_unfiltered_revision_inventory_requires_all_periods_and_returns_complete_encrypted_rows(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """Profile-wide discovery refuses every bounded ceiling and returns the full stored inventory."""
    with _runtime(tmp_path / "revision-inventory", cleanup=_CloseWitness()) as (driver, registry, profile_id):
        revision_ids = (
            seeded_modelo_calculation_revision(profile_id, operation=operation),
            seeded_modelo_calculation_revision(profile_id, operation=operation),
        )
        stored = CalculationRevisionCatalogueRepository().load()
        first_revision = stored.get(revision_ids[0])
        assert first_revision is not None
        first_unit = WorkUnitCatalogueRepository().load().get(first_revision.work_unit_id)
        assert first_unit is not None

        payload = ModeloWorkRevisionsRequest(profile_id=profile_id, work_unit_id=None)
        request = OperationRequest(
            definition_id=MODELO_WORK_REVISIONS_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(profile_id)),
            payload=payload,
        )
        contract = registry.lookup_public_contract(request.definition_id)
        context = OperationAccessContext(
            profile_id=profile_id,
            destination_id=uuid4(),
            action=AccessAction.SUBMIT,
            frontend=OperationFrontendProjection.CLI,
            contract=contract,
            published_authority=Availability.AVAILABLE,
            authority_operation=operation,
        )
        access = resolve_operation_access(registry=registry, request=request, context=context)
        assert access.request.period_independent is True
        assert access.request.periods == frozenset()
        assert access.policy.requires_all_periods is True
        assert AccessAction.COMMIT not in access.policy.actions

        for periods, allow_period_independent in (
            (frozenset({first_unit.period}), True),
            (frozenset({first_unit.period}), False),
            (frozenset(), True),
        ):
            bounded_scope = AccessScope(
                operations=frozenset({request.definition_id}),
                actions=frozenset({AccessAction.SUBMIT}),
                disclosures=frozenset(),
                periods=periods,
                allow_period_independent=allow_period_independent,
                allow_delegation=False,
            )
            refusal = operation_scope_refusal(request=access.request, policy=access.policy, scope=bounded_scope)
            assert refusal is not None
            assert refusal.code is AccessDenialCode.PERIOD_DENIED

        unrestricted_scope = AccessScope(
            operations=frozenset({request.definition_id}),
            actions=frozenset({AccessAction.SUBMIT}),
            disclosures=frozenset(),
            periods=None,
            allow_period_independent=True,
            allow_delegation=False,
        )
        assert operation_scope_refusal(request=access.request, policy=access.policy, scope=unrestricted_scope) is None

        submitted, observed = asyncio.run(
            driver.run(definition_id=request.definition_id, subject_ref=request.subject_ref, payload=payload)
        )
        terminal = observed.projection
        assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
        assert terminal.effect is OperationEffect.NONE
        assert terminal.result_ref is not None
        assert contract.result_schema is not None
        result = asyncio.run(
            driver.services.result.resolve(
                OperationResultProjectionRequestV1(
                    operation_id=submitted.receipt.operation_id,
                    terminal_revision=terminal.revision,
                    definition_contract_digest=contract.definition_contract_digest,
                    result_schema=contract.result_schema,
                ),
                ModeloWorkRevisionsProjection,
            )
        )
        assert isinstance(result, OperationResultProjectionSuccessV1)
        projection = result.projection
        assert projection.profile_id == profile_id
        assert projection.work_unit_id_filter is None
        assert {item.calculation_revision_id for item in projection.revisions} == set(stored.revisions)
        assert len(projection.revisions) == len(stored.revisions)
