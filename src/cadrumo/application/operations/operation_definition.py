"""Canonical operation definition and executor-factory contracts."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeIs

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.operations import OperationDurability, OperationEffect, OperationInteractionKind
from ..operator_actions.models import ActionReference
from .capabilities import OperationCapabilities, OperationRequestStoragePolicy
from .events import OperationEventCode
from .financial_operand import OperationTransientFinancialOperandDeclaration
from .models import CredentialFreeOperationRequest, OperationDefinitionId, OperationFailureErrorCode
from .owner import OperationExecutor, OperationResumableExecutor
from .refusal_evidence import validate_refusal_code
from .registry_schema_validation import strict_model_json_schema, validate_credential_free_schema
from .secret_submission import OperationEphemeralSecretDeclaration


def _is_operation_executor(executor: object) -> TypeIs[OperationExecutor[BaseModel]]:
    """Report whether a built executor structurally implements the executor contract."""
    return isinstance(executor, OperationExecutor)


class OperationExecutorFactory(BaseModel):
    """Non-effectful descriptor binding an executor class to its request type."""

    model_config = STRICT_FROZEN_CONFIG

    request_type: type[BaseModel]
    executor_type: type[object]
    build: Callable[[], object]

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_executor_type(self) -> OperationExecutorFactory:
        if not issubclass(self.executor_type, OperationExecutor):
            raise ValueError("operation executor type must structurally implement OperationExecutor")
        return self

    def create(self) -> OperationExecutor[BaseModel]:
        """Construct and validate the declared executor without running it."""
        executor = self.build()
        if not isinstance(executor, self.executor_type) or not _is_operation_executor(executor):
            raise TypeError("operation executor factory returned an undeclared or invalid executor")
        return executor


class OperationDefinition(BaseModel):
    """Complete generic contract registered for one operation type."""

    model_config = STRICT_FROZEN_CONFIG

    definition_id: OperationDefinitionId
    request_type: type[BaseModel]
    result_type: type[BaseModel] | None
    executor_factory: OperationExecutorFactory
    phase_codes: tuple[OperationEventCode, ...] = Field(min_length=1)
    interaction_kinds: frozenset[OperationInteractionKind]
    capabilities: OperationCapabilities
    reconciliation_policy: OperationReconciliationPolicy
    permitted_frontends: frozenset[OperationFrontendProjection] = Field(min_length=1)
    action_reference: ActionReference | None = None
    ephemeral_secret: OperationEphemeralSecretDeclaration | None = None
    transient_financial_operands: tuple[OperationTransientFinancialOperandDeclaration, ...] = ()
    refusal_detail_codes: frozenset[OperationFailureErrorCode] = frozenset()
    #: Whether a refused or failed executor's bounded public error detail is
    #: recorded for its frontend. Opt-in: an operation whose refusals may
    #: quote what the operator typed -- a mistyped secret, say -- keeps the
    #: registered code alone, as every operation did before.
    public_error_detail: bool = False

    @field_validator("phase_codes")
    @classmethod
    @pydantic_validation_boundary
    def _canonical_phase_codes(cls, value: tuple[OperationEventCode, ...]) -> tuple[OperationEventCode, ...]:
        if len(set(value)) != len(value):
            raise ValueError("operation definition phase codes must be unique")
        return tuple(sorted(value))

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_factory_request_type(self) -> OperationDefinition:
        self._validate_refusal_evidence_declaration()
        self._validate_factory_request_binding()
        self._validate_request_storage()
        self._validate_ephemeral_secret()
        self._validate_transient_financial_operands()
        self._validate_owner_loss_effect()
        self._validate_checkpoint_reconciliation()
        return self

    def _validate_refusal_evidence_declaration(self) -> None:
        if self.refusal_detail_codes and self.result_type is None:
            raise ValueError("refusal evidence requires a declared result model")
        for code in self.refusal_detail_codes:
            validate_refusal_code(code)

    def _validate_factory_request_binding(self) -> None:
        if self.executor_factory.request_type is not self.request_type:
            raise ValueError("operation executor factory request type must match the definition request type")

    def _validate_owner_loss_effect(self) -> None:
        if (
            self.capabilities.durability is not OperationDurability.EPHEMERAL
            and OperationEffect.UNKNOWN not in self.capabilities.permitted_effects
        ):
            raise ValueError("operation definition must permit unknown effect for owner-loss reconciliation")

    def _validate_checkpoint_reconciliation(self) -> None:
        if self.reconciliation_policy is not OperationReconciliationPolicy.RESUME_FROM_CHECKPOINT:
            return
        if self.capabilities.durability is not OperationDurability.RESUMABLE:
            raise ValueError("checkpoint reconciliation requires resumable durability")
        if not self.interaction_kinds:
            raise ValueError("checkpoint reconciliation requires a declared interaction checkpoint")
        if not issubclass(self.executor_factory.executor_type, OperationResumableExecutor):
            raise ValueError("checkpoint reconciliation requires a resumable executor")

    def _validate_request_storage(self) -> None:
        if self.capabilities.request_storage is not OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL:
            return
        if not issubclass(self.request_type, CredentialFreeOperationRequest):
            raise ValueError(
                "credential-free journal request type must explicitly inherit CredentialFreeOperationRequest"
            )
        schema = strict_model_json_schema(self.request_type)
        validate_credential_free_schema(schema)

    def _validate_ephemeral_secret(self) -> None:
        if self.ephemeral_secret is None:
            return
        if self.capabilities.durability is not OperationDurability.RECORDED:
            raise ValueError("ephemeral secret operations require recorded durability")
        if self.reconciliation_policy is not OperationReconciliationPolicy.INTERRUPT:
            raise ValueError("ephemeral secret operations cannot resume after owner loss")
        if OperationEffect.NONE not in self.capabilities.permitted_effects:
            raise ValueError("ephemeral secret operations must permit a pre-entry none effect")

    def _validate_transient_financial_operands(self) -> None:
        """Refuse operand declarations the runtime could not honour.

        An operand lives only in the memory of the process that received it, so
        a definition that expects to resume after owner loss is declaring
        something custody cannot deliver: the restart would have to invent the
        amount or the acknowledgement.
        """
        if not self.transient_financial_operands:
            return
        kinds = [declaration.operand_kind for declaration in self.transient_financial_operands]
        if len(set(kinds)) != len(kinds):
            raise ValueError("operation definition cannot declare one financial operand kind twice")
        if self.capabilities.durability is not OperationDurability.RECORDED:
            raise ValueError("transient financial operand operations require recorded durability")
        if self.reconciliation_policy is not OperationReconciliationPolicy.INTERRUPT:
            raise ValueError("transient financial operand operations cannot resume after owner loss")
        if OperationInteractionKind.INPUT not in self.interaction_kinds:
            raise ValueError("transient financial operand operations must declare an input interaction")
        if OperationEffect.UNKNOWN not in self.capabilities.permitted_effects:
            raise ValueError("transient financial operand operations must permit an uncertain-delivery effect")


# The two enums live in the registry's central contract module. Resolving them
# here happens after the model class exists; registry imports this module after
# defining the enums and completes any deferred Pydantic fields before use.
from .registry import OperationFrontendProjection, OperationReconciliationPolicy  # noqa: E402

OperationDefinition.model_rebuild(_types_namespace=globals())


def build_single_phase_definition(
    *,
    definition_id: str,
    request_type: type[BaseModel],
    result_type: type[BaseModel] | None,
    executor_type: type[object],
    build: Callable[[], object],
    capabilities: OperationCapabilities,
    permitted_frontends: frozenset[OperationFrontendProjection],
    action_reference: ActionReference | None = None,
    ephemeral_secret: OperationEphemeralSecretDeclaration | None = None,
    transient_financial_operands: tuple[OperationTransientFinancialOperandDeclaration, ...] = (),
    refusal_detail_codes: frozenset[OperationFailureErrorCode] = frozenset(),
    public_error_detail: bool = False,
) -> OperationDefinition:
    """Declare ``definition_id`` as its own sole phase: no interactions, interrupted on owner loss."""
    return OperationDefinition(
        definition_id=definition_id,
        request_type=request_type,
        result_type=result_type,
        executor_factory=OperationExecutorFactory(
            request_type=request_type,
            executor_type=executor_type,
            build=build,
        ),
        phase_codes=(definition_id,),
        interaction_kinds=frozenset(),
        capabilities=capabilities,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=permitted_frontends,
        action_reference=action_reference,
        ephemeral_secret=ephemeral_secret,
        transient_financial_operands=transient_financial_operands,
        refusal_detail_codes=refusal_detail_codes,
        public_error_detail=public_error_detail,
    )


__all__ = ["OperationDefinition", "OperationExecutorFactory", "build_single_phase_definition"]
