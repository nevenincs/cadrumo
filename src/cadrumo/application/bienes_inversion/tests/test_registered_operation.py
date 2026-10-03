"""Declaration executor refusals and effects follow the durable write boundary."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import cast
from uuid import UUID

import pytest
from pydantic import BaseModel, ValidationError

import cadrumo.application.bienes_inversion.registered_operation as registered_operation_module
from cadrumo.application.bienes_inversion.declare_command import (
    BienInversionDeclarationCommand,
    build_bien_inversion_record,
)
from cadrumo.application.bienes_inversion.registered_operation import (
    BIENES_INVERSION_DECLARE_OPERATION_DEFINITION_ID,
    BIENES_INVERSION_DUPLICATE_REFUSAL_CODE,
    BIENES_INVERSION_VALIDATION_REFUSAL_CODE,
    BienesInversionDeclareRequest,
    BienesInversionOperationExecutionResult,
    BienesInversionOperationExecutor,
)
from cadrumo.application.operations.models import OperationIdentity, OperationRequest
from cadrumo.application.operations.owner import OperationExecutorContext
from cadrumo.application.operations.public_scalar import PublicDecimal
from cadrumo.application.operations.refusal_evidence import OperationRefusalEvidence
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
        self.authority_operation = authority_operation
        self.events = _Events()
        self.cancellation = _Cancellation()
        self.operands = _Operands(self.cancellation)


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
    monkeypatch: pytest.MonkeyPatch,
    operation: PinnedAuthorityOperation,
    overrides: dict[str, object],
    expected_reason: str,
) -> None:
    monkeypatch.setattr(registered_operation_module, "require_active_bucket_id", lambda: str(_PROFILE))
    repository = _Repository()
    factory = _RepositoryFactory(repository)
    context = _Context(operation)
    executor = BienesInversionOperationExecutor(
        factory,
        definition_id=BIENES_INVERSION_DECLARE_OPERATION_DEFINITION_ID,
    )

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


def test_duplicate_from_repository_add_settles_as_none_without_write(
    monkeypatch: pytest.MonkeyPatch,
    operation: PinnedAuthorityOperation,
) -> None:
    monkeypatch.setattr(registered_operation_module, "require_active_bucket_id", lambda: str(_PROFILE))
    repository = _Repository(records=(_existing_record(operation),))
    factory = _RepositoryFactory(repository)
    context = _Context(operation)
    executor = BienesInversionOperationExecutor(
        factory,
        definition_id=BIENES_INVERSION_DECLARE_OPERATION_DEFINITION_ID,
    )

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
    monkeypatch.setattr(registered_operation_module, "require_active_bucket_id", lambda: str(_PROFILE))
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
        registered_operation_module,
        "BienesInversionOperationExecutionResult",
        fail_result_construction,
    )

    with pytest.raises(ValidationError) as raised:
        asyncio.run(
            executor.execute(_request(), cast(OperationExecutorContext, context)),
        )

    assert raised.value is construction_error
    assert context.events.effects == [OperationEffect.UNKNOWN]
    assert factory.bucket_ids == [str(_PROFILE)]
    assert repository.add_attempts == 1
    assert repository.writes == 1
    assert tuple(row.identifier for row in repository.register.records) == ("bien-1",)
    assert context.operands.value is None
