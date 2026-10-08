"""Declaration executor refusals and effects follow the durable write boundary."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import cast
from uuid import UUID

import pytest
from pydantic import BaseModel, ValidationError

import cadrumo.application.bienes_inversion.registered_executor as registered_executor_module
from cadrumo.application.bienes_inversion.declare_command import (
    BienInversionDeclarationCommand,
    build_bien_inversion_record,
)
from cadrumo.application.bienes_inversion.registered_contracts import (
    BIENES_INVERSION_DECLARE_OPERATION_DEFINITION_ID,
    BIENES_INVERSION_DUPLICATE_REFUSAL_CODE,
    BIENES_INVERSION_VALIDATION_REFUSAL_CODE,
)
from cadrumo.application.bienes_inversion.registered_execution_result import BienesInversionOperationExecutionResult
from cadrumo.application.bienes_inversion.registered_executor import BienesInversionOperationExecutor
from cadrumo.application.bienes_inversion.registered_requests import BienesInversionDeclareRequest
from cadrumo.application.operations.models import OperationIdentity, OperationRequest
from cadrumo.application.operations.owner import OperationExecutorContext
from cadrumo.application.operations.public_scalar import PublicDecimal
from cadrumo.application.operations.refusal_evidence import OperationRefusalEvidence
from cadrumo.application.user_profile.access_contracts import AccessDenialCode
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.core.config import override_settings
from cadrumo.core.operations import OperationEffect, profile_operation_subject
from cadrumo.domain.bienes_inversion.register import (
    BienesInversionIvaRegister,
    BienInversionIvaRecord,
    BienInversionRecordError,
)
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.governed_fact_scope import validating_governed_facts

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_DUPLICATE_MESSAGE = "adapters.persistence.profile.bienes_inversion.errors.record_already_exists"


class _Events:
    def __init__(self) -> None:
        self.effects: list[OperationEffect] = []
        self.phases: list[str] = []

    async def phase(self, phase: str) -> None:
        self.phases.append(phase)

    async def effect(self, effect: OperationEffect) -> None:
        self.effects.append(effect)


class _Cancellation:
    def __init__(self) -> None:
        self.inside = False

    @asynccontextmanager
    async def irreversible_section(self):
        self.inside = True
        try:
            yield
        finally:
            self.inside = False


class _Operands:
    def __init__(self, cancellation: _Cancellation) -> None:
        self._cancellation = cancellation
        self.value: BaseModel | None = None

    async def put(self, value: BaseModel, *, written_at: object) -> str:
        del written_at
        assert self._cancellation.inside
        self.value = value
        return "d" * 64


class _Context:
    def __init__(self, authority_operation: PinnedAuthorityOperation) -> None:
        self.identity = OperationIdentity(
            operation_id="c" * 64,
            definition_id=BIENES_INVERSION_DECLARE_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(_PROFILE)),
        )
        self._authority_operation = authority_operation
        self.authority_operation_reads = 0
        self.events = _Events()
        self.cancellation = _Cancellation()
        self.operands = _Operands(self.cancellation)

    @property
    def authority_operation(self) -> PinnedAuthorityOperation:
        self.authority_operation_reads += 1
        return self._authority_operation


class _Repository:
    """Canonical register shape with visible add attempts and durable writes."""

    def __init__(self, *, records: tuple[BienInversionIvaRecord, ...] = ()) -> None:
        self.register = BienesInversionIvaRegister(records=records)
        self.add_attempts = 0
        self.writes = 0

    def load(self) -> BienesInversionIvaRegister:
        return self.register

    def add(self, record: BienInversionIvaRecord) -> BienesInversionIvaRegister:
        self.add_attempts += 1
        if any(existing.identifier == record.identifier for existing in self.register.records):
            raise BienInversionRecordError(
                f"bien de inversion {record.identifier!r} already exists",
                context={"record_id": record.identifier},
                translated_message=_DUPLICATE_MESSAGE,
            )
        self.register = BienesInversionIvaRegister(records=(*self.register.records, record))
        self.writes += 1
        return self.register


class _RepositoryFactory:
    def __init__(self, repository: _Repository) -> None:
        self.repository = repository
        self.bucket_ids: list[str] = []

    def __call__(self, *, bucket_id: str) -> _Repository:
        self.bucket_ids.append(bucket_id)
        return self.repository


class _RequiredValue(BaseModel):
    value: str


def _request(**overrides: object) -> OperationRequest[BaseModel]:
    fields: dict[str, object] = {
        "profile_id": _PROFILE,
        "identifier": "bien-1",
        "description": "Delivery van",
        "acquisition_year": 2024,
        "acquisition_ledger_id": "ledger-1",
        "cuota_soportada": PublicDecimal(decimal="2100.00"),
        "prorrata_inicial_pct": PublicDecimal(decimal="60"),
        "kind": "mueble",
    }
    fields.update(overrides)
    payload = BienesInversionDeclareRequest.model_validate(fields, strict=True)
    return OperationRequest[BaseModel](
        definition_id=BIENES_INVERSION_DECLARE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=payload,
    )


def _existing_record(authority_operation: PinnedAuthorityOperation) -> BienInversionIvaRecord:
    with validating_governed_facts(authority_operation):
        return build_bien_inversion_record(
            BienInversionDeclarationCommand(
                identifier="bien-1",
                description="Existing delivery van",
                acquisition_year=2024,
                acquisition_ledger_id="ledger-existing",
                cuota_soportada=Decimal("2100.00"),
                prorrata_inicial_pct=Decimal("60"),
                kind="mueble",
            ),
        )


@pytest.mark.parametrize(
    ("overrides", "expected_reason"),
    [
        ({"disposal_year": 2026}, "disposal_incomplete"),
        ({"kind": "not-a-registered-kind"}, "validation"),
    ],
)
def test_known_declaration_refusal_has_no_repository_write(
    operation: PinnedAuthorityOperation,
    overrides: dict[str, object],
    expected_reason: str,
) -> None:
    repository = _Repository()
    factory = _RepositoryFactory(repository)
    context = _Context(operation)
    executor = BienesInversionOperationExecutor(
        factory,
        definition_id=BIENES_INVERSION_DECLARE_OPERATION_DEFINITION_ID,
    )

    with override_settings(cadrumo_active_profile=str(_PROFILE)):
        result = asyncio.run(
            executor.execute(_request(**overrides), cast(OperationExecutorContext, context)),
        )

    assert isinstance(result, OperationRefusalEvidence)
    assert result.refusal_code == BIENES_INVERSION_VALIDATION_REFUSAL_CODE
    assert context.events.effects == [OperationEffect.NONE]
    assert factory.bucket_ids == []
    assert repository.add_attempts == 0
    assert repository.writes == 0
    assert isinstance(context.operands.value, BienesInversionOperationExecutionResult)
    assert context.operands.value.refusal is not None
    assert context.operands.value.refusal.reason == expected_reason


@pytest.mark.parametrize("mismatch", ["request_subject", "context_definition", "context_subject", "active_profile"])
def test_profile_mismatch_refuses_before_phase_or_repository_access(
    operation: PinnedAuthorityOperation,
    mismatch: str,
) -> None:
    other_profile = UUID("5aa00000-0000-4000-8000-0000000000bb")
    request = _request()
    if mismatch == "request_subject":
        request = request.model_copy(update={"subject_ref": profile_operation_subject(str(other_profile))})
    context = _Context(operation)
    if mismatch == "context_definition":
        context.identity = OperationIdentity(
            operation_id="c" * 64,
            definition_id="ledger.bienes_inversion.other",
            subject_ref=profile_operation_subject(str(_PROFILE)),
        )
    elif mismatch == "context_subject":
        context.identity = OperationIdentity(
            operation_id="c" * 64,
            definition_id=BIENES_INVERSION_DECLARE_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(other_profile)),
        )

    repository = _Repository()
    factory = _RepositoryFactory(repository)
    executor = BienesInversionOperationExecutor(
        factory,
        definition_id=BIENES_INVERSION_DECLARE_OPERATION_DEFINITION_ID,
    )
    active_profile = str(other_profile) if mismatch == "active_profile" else str(_PROFILE)

    with override_settings(cadrumo_active_profile=active_profile), pytest.raises(ProfileAccessRefusedError) as refused:
        asyncio.run(executor.execute(request, cast(OperationExecutorContext, context)))

    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH
    assert context.events.phases == []
    assert context.events.effects == []
    assert context.authority_operation_reads == 0
    assert factory.bucket_ids == []
    assert repository.add_attempts == 0
    assert repository.writes == 0


def test_duplicate_from_repository_add_settles_as_none_without_write(
    operation: PinnedAuthorityOperation,
) -> None:
    repository = _Repository(records=(_existing_record(operation),))
    factory = _RepositoryFactory(repository)
    context = _Context(operation)
    executor = BienesInversionOperationExecutor(
        factory,
        definition_id=BIENES_INVERSION_DECLARE_OPERATION_DEFINITION_ID,
    )

    with override_settings(cadrumo_active_profile=str(_PROFILE)):
        result = asyncio.run(
            executor.execute(_request(), cast(OperationExecutorContext, context)),
        )

    assert isinstance(result, OperationRefusalEvidence)
    assert result.refusal_code == BIENES_INVERSION_DUPLICATE_REFUSAL_CODE
    assert context.events.effects == [OperationEffect.UNKNOWN, OperationEffect.NONE]
    assert context.events.effects[-1] is OperationEffect.NONE
    assert factory.bucket_ids == [str(_PROFILE)]
    assert repository.add_attempts == 1
    assert repository.writes == 0
    assert tuple(row.identifier for row in repository.register.records) == ("bien-1",)
    assert isinstance(context.operands.value, BienesInversionOperationExecutionResult)
    assert context.operands.value.refusal is not None
    assert context.operands.value.refusal.reason == "duplicate_identifier"


def test_validation_error_after_repository_write_remains_unknown(
    monkeypatch: pytest.MonkeyPatch,
    operation: PinnedAuthorityOperation,
) -> None:
    repository = _Repository()
    factory = _RepositoryFactory(repository)
    context = _Context(operation)
    executor = BienesInversionOperationExecutor(
        factory,
        definition_id=BIENES_INVERSION_DECLARE_OPERATION_DEFINITION_ID,
    )
    with pytest.raises(ValidationError) as captured:
        _RequiredValue.model_validate({})
    construction_error = captured.value

    def fail_result_construction(**_kwargs: object) -> None:
        raise construction_error

    monkeypatch.setattr(
        registered_executor_module,
        "BienesInversionOperationExecutionResult",
        fail_result_construction,
    )

    with override_settings(cadrumo_active_profile=str(_PROFILE)), pytest.raises(ValidationError) as raised:
        asyncio.run(executor.execute(_request(), cast(OperationExecutorContext, context)))

    assert raised.value is construction_error
    assert context.events.effects == [OperationEffect.UNKNOWN]
    assert factory.bucket_ids == [str(_PROFILE)]
    assert repository.add_attempts == 1
    assert repository.writes == 1
    assert tuple(row.identifier for row in repository.register.records) == ("bien-1",)
    assert context.operands.value is None
