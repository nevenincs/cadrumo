"""Real encrypted wizard attempts preserve publication and missing-input boundaries."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest

from ....adapters.persistence.operations.secure_references import operation_secure_reference_repository
from ....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ....application.modelo import calculate_input
from ....application.modelo.calculation_action_ports import CalculationActionPortsFactory
from ....application.modelo.registry_discovery import registry_bindings_for_scope
from ....application.modelo.wizard_attempt_operation import (
    MODELO_WORK_WIZARD_ATTEMPT_OPERATION_DEFINITION_ID,
    ModeloWorkWizardAttemptExecutor,
    ModeloWorkWizardAttemptProjection,
    ModeloWorkWizardAttemptRequest,
)
from ....application.modelo.work_calculation_contracts import (
    ModeloWorkCalculateCallerContext,
    ModeloWorkCalculateRequest,
)
from ....application.operations.models import OperationIdentity, OperationRequest
from ....application.operations.owner import OperationExecutorContext
from ....core.aggregation import BindingSourceKind
from ....core.external_constants import OutputLanguage
from ....core.operations import OperationEffect
from ....core.period import Period
from ....domain.attachments.protocols import AttachmentStoreProtocol
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.errors import RegistryValidationError
from .file_flow_test_support import calculation_ports_for_test
from .test_work_missing_input_publication import (
    _PROFILE_ID,
    _REQUIRED_MANUAL_BINDING,
    _YEAR,
    _profile,
    _work_and_repositories,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


class _Cancellation:
    @asynccontextmanager
    async def irreversible_section(self) -> AsyncIterator[None]:
        yield


class _Events:
    def __init__(self) -> None:
        self.effects: list[OperationEffect] = []

    async def phase(self, _code: str) -> None:
        pass

    async def effect(self, effect: OperationEffect) -> None:
        self.effects.append(effect)


def _executor_context(
    *, unit_id: str, operation: PinnedAuthorityOperation, events: _Events, operands: object
) -> OperationExecutorContext:
    return cast(
        OperationExecutorContext,
        cast(
            object,
            SimpleNamespace(
                identity=OperationIdentity(
                    operation_id="a" * 64,
                    definition_id=MODELO_WORK_WIZARD_ATTEMPT_OPERATION_DEFINITION_ID,
                    subject_ref=unit_id,
                ),
                authority_operation=operation,
                events=events,
                cancellation=_Cancellation(),
                operands=operands,
            ),
        ),
    )


def _real_request(unit_id: str, *, binding_values: dict[str, str]) -> OperationRequest[ModeloWorkWizardAttemptRequest]:
    from ....application.modelo.calculation_request_fields import (
        ModeloCalculationInputFieldsV1,
        ModeloCalculationOverride,
    )

    return OperationRequest[ModeloWorkWizardAttemptRequest](
        definition_id=MODELO_WORK_WIZARD_ATTEMPT_OPERATION_DEFINITION_ID,
        subject_ref=unit_id,
        payload=ModeloWorkWizardAttemptRequest(
            profile_id=UUID(_PROFILE_ID),
            output_language=OutputLanguage.CA,
            calculation=ModeloWorkCalculateRequest(
                work_unit_id=unit_id,
                actor="operator",
                caller_context=ModeloWorkCalculateCallerContext.EXPLICIT,
                inputs=ModeloCalculationInputFieldsV1(
                    binding_overrides=tuple(
                        ModeloCalculationOverride(key=key, value=value) for key, value in binding_values.items()
                    )
                ),
            ),
        ),
    )


def test_real_missing_input_attempt_persists_encrypted_needs_input_without_revision(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID) as profile:
        _profile()
        snapshot = operation.snapshot("100", filing_year=_YEAR, period="0A")
        unit, work_repo, revision_repo, event_repo = _work_and_repositories(operation)
        binding_values: dict[str, str] = {
            str(binding.id): "0"
            for binding in snapshot.revision.bindings
            if binding.source is BindingSourceKind.MANUAL_INPUT and binding.id != _REQUIRED_MANUAL_BINDING
        }
        request = _real_request(unit.work_unit_id, binding_values=binding_values)
        operands = operation_secure_reference_repository(objects=profile.repository)
        events = _Events()
        with calculation_ports_for_test(
            bucket_id=_PROFILE_ID,
            work_unit_repository=work_repo,
            calculation_repository=revision_repo,
            bucket_event_repository=event_repo,
        ) as ports:
            executor = ModeloWorkWizardAttemptExecutor(
                calculation_action_ports_factory=cast(CalculationActionPortsFactory, cast(object, lambda **_kw: ports)),
                attachment_store_factory=cast(Callable[[str], AttachmentStoreProtocol], cast(object, lambda _id: None)),
            )
            reference = asyncio.run(
                executor.execute(
                    request,
                    _executor_context(unit_id=unit.work_unit_id, operation=operation, events=events, operands=operands),
                )
            )
        result = asyncio.run(operands.resolve(reference, ModeloWorkWizardAttemptProjection))
        assert result.outcome.kind == "needs_input"
        assert _REQUIRED_MANUAL_BINDING not in binding_values
        assert result.outcome.step.key not in binding_values
        declared = next(
            row
            for row in registry_bindings_for_scope(str(unit.modelo), period=unit.period, operation=operation).rows
            if str(row.binding_id) == result.outcome.step.key
        )
        assert result.outcome.step.legal_refs == tuple(declared.legal_refs)
        assert result.outcome.step.source_refs == tuple(declared.source_refs)
        assert result.outcome.step.legal_refs and result.outcome.step.source_refs
        assert result.profile_id == UUID(_PROFILE_ID)
        assert result.output_language is OutputLanguage.CA
        assert events.effects == [OperationEffect.UNKNOWN]
        assert revision_repo.load().revisions == {}
        stored = work_repo.load().get(unit.work_unit_id)
        assert stored is not None and stored.current_calculation_revision_id is None


def test_real_calculated_attempt_keeps_ordinary_public_result_and_updated_effect(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID) as profile:
        _profile()
        period = Period.from_year_and_code(2025, "2T")
        snapshot = operation.snapshot("123", filing_year=2025, period="2T")
        unit, work_repo, revision_repo, event_repo = _work_and_repositories(
            operation, modelo="123", period=period, revision_id=snapshot.revision.id
        )
        request = _real_request(unit.work_unit_id, binding_values={})
        operands = operation_secure_reference_repository(objects=profile.repository)
        events = _Events()
        with calculation_ports_for_test(
            bucket_id=_PROFILE_ID,
            work_unit_repository=work_repo,
            calculation_repository=revision_repo,
            bucket_event_repository=event_repo,
        ) as ports:
            executor = ModeloWorkWizardAttemptExecutor(
                calculation_action_ports_factory=cast(CalculationActionPortsFactory, cast(object, lambda **_kw: ports)),
                attachment_store_factory=cast(Callable[[str], AttachmentStoreProtocol], cast(object, lambda _id: None)),
            )
            reference = asyncio.run(
                executor.execute(
                    request,
                    _executor_context(unit_id=unit.work_unit_id, operation=operation, events=events, operands=operands),
                )
            )
        result = asyncio.run(operands.resolve(reference, ModeloWorkWizardAttemptProjection))
        assert result.outcome.kind == "calculated"
        assert result.outcome.result.result_version == 2
        assert result.outcome.result.revision_published
        assert result.outcome.result.work_unit_id == unit.work_unit_id
        assert events.effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
        revisions = revision_repo.load().revisions
        assert result.outcome.result.calculation_revision_id in revisions


def test_postpublication_same_tag_does_not_persist_needs_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID) as profile:
        _profile()
        period = Period.from_year_and_code(2025, "2T")
        snapshot = operation.snapshot("123", filing_year=2025, period="2T")
        unit, work_repo, revision_repo, event_repo = _work_and_repositories(
            operation, modelo="123", period=period, revision_id=snapshot.revision.id
        )

        def fail_after_publication(*_args: object, **_kwargs: object) -> None:
            raise RegistryValidationError(
                "injected post-publication diagnostic failure",
                translated_message="errors.calc.binding_value_missing",
                context={"binding_id": _REQUIRED_MANUAL_BINDING},
            )

        monkeypatch.setattr(calculate_input, "modelo_202_modality_for_record", fail_after_publication)
        request = _real_request(unit.work_unit_id, binding_values={})
        operands = operation_secure_reference_repository(objects=profile.repository)
        events = _Events()
        with calculation_ports_for_test(
            bucket_id=_PROFILE_ID,
            work_unit_repository=work_repo,
            calculation_repository=revision_repo,
            bucket_event_repository=event_repo,
        ) as ports:
            executor = ModeloWorkWizardAttemptExecutor(
                calculation_action_ports_factory=cast(CalculationActionPortsFactory, cast(object, lambda **_kw: ports)),
                attachment_store_factory=cast(Callable[[str], AttachmentStoreProtocol], cast(object, lambda _id: None)),
            )
            with pytest.raises(RegistryValidationError) as refused:
                asyncio.run(
                    executor.execute(
                        request,
                        _executor_context(
                            unit_id=unit.work_unit_id, operation=operation, events=events, operands=operands
                        ),
                    )
                )
        assert type(refused.value) is RegistryValidationError
        assert events.effects == [OperationEffect.UNKNOWN]
        revisions = revision_repo.load().revisions
        assert len(revisions) == 1
        stored = work_repo.load().get(unit.work_unit_id)
        assert stored is not None and stored.current_calculation_revision_id in revisions
