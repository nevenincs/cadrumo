"""Strict Pydantic records for the backend-owned operator surface contract."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RootSurfaceName(StrEnum):
    """Accepted root command surfaces."""

    CONFIG = "config"
    APP = "app"


class ModeloLifecycleStep(StrEnum):
    """Canonical modelo lifecycle steps exposed to operators."""

    CALCULATE = "calculate"
    VERIFY = "verify"
    FILE = "file"


class SourceKind(StrEnum):
    """Canonical source-kind taxonomy from the CLI workflow redesign ADRs."""

    LEDGER_TRANSACTION = "ledger_transaction"
    PURCHASE_INVOICE_EVIDENCE = "purchase_invoice_evidence"
    PAYABLE_INVOICE = "payable_invoice"
    COLLECTIBLE_INVOICE = "collectible_invoice"


class RootSurface(BaseModel):
    """Backend ownership record for an accepted root surface."""

    model_config = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")

    name: RootSurfaceName
    purpose: str = Field(min_length=1)
    owns_storage_maintenance: bool
    owns_operational_workflow: bool
    required_children: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("required_children")
    @classmethod
    def _children_are_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("root surface children must be unique")
        return value


class RetiredOperatorSurface(BaseModel):
    """Rejected historical surface and the accepted replacement direction."""

    model_config = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")

    name: str = Field(min_length=1)
    replacement: str | None
    suggestion: str | None
    reason: str = Field(min_length=1)


class LifecycleContract(BaseModel):
    """Modelo lifecycle vocabulary and live-submission safety contract."""

    model_config = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")

    steps: tuple[ModeloLifecycleStep, ...]
    internal_filed_term: str = "internal filed"
    live_submission_enabled: bool = False
    live_submission_wording: str = "live submission is permanently disabled"

    @field_validator("steps")
    @classmethod
    def _steps_are_canonical(cls, value: tuple[ModeloLifecycleStep, ...]) -> tuple[ModeloLifecycleStep, ...]:
        expected = (
            ModeloLifecycleStep.CALCULATE,
            ModeloLifecycleStep.VERIFY,
            ModeloLifecycleStep.FILE,
        )
        if value != expected:
            raise ValueError("modelo lifecycle must be calculate -> verify -> file")
        return value

    @field_validator("live_submission_enabled")
    @classmethod
    def _live_submission_is_forbidden(cls, value: bool) -> bool:
        if value:
            raise ValueError("live submission must remain disabled")
        return value


class SourceKindAlias(BaseModel):
    """Input-only alias mapped to a canonical source kind."""

    model_config = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")

    alias: str = Field(min_length=1)
    canonical: SourceKind


class ServiceOwner(BaseModel):
    """Application/domain package that owns an operator-facing capability."""

    model_config = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")

    capability: str = Field(min_length=1)
    owner: str = Field(pattern=r"^aeat\.(application|domain|adapters|core)(\.[a-z_][a-z0-9_]*)*$")
    notes: str = Field(min_length=1)


class OperatorSurfaceLogFields(BaseModel):
    """Stable non-secret log fields emitted by operator-surface services."""

    model_config = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")

    contract_name: str = "operator_surface"
    root_count: int
    retired_surface_count: int
    lifecycle: str
    source_kind_count: int

    def as_extra(self) -> dict[str, object]:
        """Return a logging ``extra`` payload with stable field names."""

        return {
            "contract_name": self.contract_name,
            "root_count": self.root_count,
            "retired_surface_count": self.retired_surface_count,
            "lifecycle": self.lifecycle,
            "source_kind_count": self.source_kind_count,
        }


class OperatorSurfaceContract(BaseModel):
    """Complete backend-owned contract consumed by future CLI adapters."""

    model_config = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")

    schema_version: str = "1"
    roots: tuple[RootSurface, ...]
    retired_surfaces: tuple[RetiredOperatorSurface, ...]
    lifecycle: LifecycleContract
    source_kinds: tuple[SourceKind, ...]
    source_kind_aliases: tuple[SourceKindAlias, ...]
    service_owners: tuple[ServiceOwner, ...]
    log_fields: OperatorSurfaceLogFields
    error_codes: tuple[str, ...]

    @field_validator("roots")
    @classmethod
    def _roots_are_exact(cls, value: tuple[RootSurface, ...]) -> tuple[RootSurface, ...]:
        names = tuple(root.name for root in value)
        expected = (RootSurfaceName.CONFIG, RootSurfaceName.APP)
        if names != expected:
            raise ValueError("operator roots must be exactly config and app")
        return value

    @field_validator("source_kinds")
    @classmethod
    def _source_kinds_are_exact(cls, value: tuple[SourceKind, ...]) -> tuple[SourceKind, ...]:
        expected = (
            SourceKind.LEDGER_TRANSACTION,
            SourceKind.PURCHASE_INVOICE_EVIDENCE,
            SourceKind.PAYABLE_INVOICE,
            SourceKind.COLLECTIBLE_INVOICE,
        )
        if value != expected:
            raise ValueError("source kinds must match the accepted four-kind taxonomy")
        return value
