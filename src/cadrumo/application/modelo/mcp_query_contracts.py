"""Closed agent-facing contracts for modelo queries.

These Pydantic types contain only bounded fields admitted by the MCP read
contract. Their definitions are shared directly by operation registration and
consumer tests.
"""

from __future__ import annotations

from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.errors.hierarchy import CadrumoError
from ...core.external_constants import OutputLanguage
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.calculations.registry.binding_value_contract import BindingDataType, BindingValueChannel
from ..ledger.preflight import LedgerPreflightIssueReason
from ..operations.public_period import PublicPeriod
from ..state_projection import ModeloProfileRefusalCause, ModeloRegistryRefusalCause
from .query_read_contracts import ModeloBindingRowV1, ModeloReadinessMissingBindingV1

MAX_TYPED_BINDING_VALUE_LENGTH = 16_384

MODELO_BINDINGS_RESOLVE_TYPED_OPERATION_DEFINITION_ID = "modelo.bindings.resolve.typed"
MODELO_READINESS_SUMMARY_OPERATION_DEFINITION_ID = "modelo.readiness.summary"


class ModeloBindingValueContractUnsupportedError(CadrumoError):
    """The pinned binding lacks an official grammar for agent value disclosure."""

    def __init__(self, *, binding_id: str = "", channel: BindingValueChannel | None = None) -> None:
        """Carry only the fixed unsupported-contract refusal text."""
        self.binding_id = binding_id
        self.channel = channel
        super().__init__("modelo binding value contract unsupported")


class ModeloBindingValueInvalidError(CadrumoError):
    """The caller value does not satisfy its pinned official value contract."""

    def __init__(self, *, binding_id: str = "", channel: BindingValueChannel | None = None) -> None:
        """Carry only the fixed invalid-value refusal text."""
        self.binding_id = binding_id
        self.channel = channel
        super().__init__("modelo binding value invalid")


class ModeloTypedBindingValue(BaseModel):
    """Exact canonical override value with its declared legal type and channel."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    binding_id: Annotated[str, Field(min_length=1, max_length=128)]
    data_type: BindingDataType
    channel: BindingValueChannel
    value: Annotated[str, Field(min_length=1, max_length=MAX_TYPED_BINDING_VALUE_LENGTH, repr=False)]


class ModeloBindingsResolveTypedProjection(BaseModel):
    """Complete pinned binding preview with only contract-validated values."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    result_version: Literal[1] = 1
    operation: Literal["modelo.bindings.resolve.typed"] = MODELO_BINDINGS_RESOLVE_TYPED_OPERATION_DEFINITION_ID
    authority_generation: ContentDigest
    profile_id: UUID
    modelo: str
    revision: str
    filing_year: int | None
    period: str | None
    override_count: int
    binding_count: int
    bindings: tuple[ModeloBindingRowV1, ...]
    validated_overrides: tuple[ModeloTypedBindingValue, ...]

    @model_validator(mode="after")
    def _all_values_present(self) -> Self:
        if self.override_count != len(self.validated_overrides) or self.binding_count != len(self.bindings):
            raise ValueError("binding preview count mismatch")
        overrides = {row.binding_id: row.value for row in self.validated_overrides}
        if len(overrides) != self.override_count:
            raise ValueError("duplicate validated binding override")
        if {row.binding_id: row.override for row in self.bindings if row.override is not None} != overrides:
            raise ValueError("binding preview omits a validated override")
        return self


class ModeloReadinessSafeRecovery(BaseModel):
    """Allowlisted recovery identity for the canonical setup-incomplete limb."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    failed_condition_id: Literal["profile.setup.declared_complete"]
    action_id: Literal["operator.profile.complete_setup"]
    missing_argument_names: tuple[str, ...]


class ModeloReadinessSafeLedgerIssue(BaseModel):
    """Transaction address and closed reason without freeform detail."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    transaction_id: str
    reason: LedgerPreflightIssueReason


class ModeloReadinessSafeMissingRequirement(BaseModel):
    """One missing profile field identified by canonical schema keys."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    section_key: Annotated[str, Field(min_length=1, max_length=64)]
    field_key: Annotated[str, Field(min_length=1, max_length=128)]
    legal_refs: tuple[str, ...]
    modelos: tuple[str, ...]


class ModeloReadinessSummaryProjection(BaseModel):
    """Every canonical readiness axis, with typed causes and bounded facts."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    result_version: Literal[1] = 1
    operation: Literal["modelo.readiness.summary"] = MODELO_READINESS_SUMMARY_OPERATION_DEFINITION_ID
    authority_generation: ContentDigest
    profile_id: UUID
    language: OutputLanguage
    modelo: str
    revision_id: str
    filing_year: int
    period: PublicPeriod
    ready: bool
    profile_ready: bool
    per_operation_requirements_assessed: bool
    profile_refusal_cause: ModeloProfileRefusalCause | None
    profile_recovery: ModeloReadinessSafeRecovery | None
    registry_ready: bool
    registry_refusal_cause: ModeloRegistryRefusalCause | None
    binding_ready: bool
    missing: tuple[ModeloReadinessSafeMissingRequirement, ...]
    missing_bindings: tuple[ModeloReadinessMissingBindingV1, ...]
    ledger_preflight_required: bool
    ledger_ready: bool | None
    ledger_period: PublicPeriod | None
    ledger_checked_transaction_count: int
    ledger_issues: tuple[ModeloReadinessSafeLedgerIssue, ...]
