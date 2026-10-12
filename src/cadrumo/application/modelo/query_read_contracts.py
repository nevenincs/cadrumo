"""Closed request and projection contracts for exact-profile modelo queries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Annotated, Literal, Protocol, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.external_constants import OutputLanguage
from ...core.filing_year import FilingYear
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.query_reports import ModeloBindingQueryRow, ModeloBindingsReport
from ..operations.models import CredentialFreeOperationRequest
from ..operations.public_period import PublicPeriod
from ..operator_actions.projection import PreconditionVerdictSnapshot
from ..state_projection import (
    CLAVES_LOCALE_DISPONIBILIDAD_POR_ORIGEN_VINCULACION_LOCALE_KEYS,
    ProjectionModeloReadiness,
)
from ..state_projection_ports import StateProjectionReadPorts
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .data_inventory import DataInventoryCasilla, DataInventoryChecklist

_Modelo = Annotated[str, Field(min_length=1, max_length=16)]

_Token = Annotated[str, Field(min_length=1, max_length=128)]

_Value = Annotated[str, Field(max_length=16_384)]


def _has_binding_filters(
    modelo: str | None,
    year: int | None,
    period_code: str | None,
    missing: bool,
    as_of: date | None,
) -> bool:
    return any((modelo is not None, year is not None, period_code is not None, missing, as_of is not None))


def _validate_binding_as_of(as_of: date | None, year: int | None) -> None:
    if as_of is not None and year is None:
        raise ValueError("as_of requires a filing year")


def _validate_binding_period(year: int | None, period_code: str | None) -> None:
    if year is not None and period_code is not None:
        Period.from_year_and_code(year, period_code)


@dataclass(frozen=True, slots=True)
class ModeloQueryReadPorts:
    """Read capability for one admitted profile."""

    bucket_id: str
    read_ports: StateProjectionReadPorts


class ModeloQueryReadPortsFactory(Protocol):
    """Executable composition binds the readiness reader to a profile."""

    def __call__(self, *, bucket_id: str, operation: PinnedAuthorityOperation) -> ModeloQueryReadPorts:
        """Return the reader for the exact requested profile."""
        ...


class ModeloBindingsListRequest(CredentialFreeOperationRequest):
    """Registry filters; an omitted modelo retains registry order."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    modelo: _Modelo | None = None
    year: FilingYear | None = None
    period_code: _Token | None = None
    missing: bool = False
    as_of: date | None = None
    catalogue_only: bool = False

    @model_validator(mode="after")
    def _scope(self) -> Self:
        if self.catalogue_only and _has_binding_filters(
            self.modelo, self.year, self.period_code, self.missing, self.as_of
        ):
            raise ValueError("catalogue-only listing cannot carry binding filters")
        _validate_binding_as_of(self.as_of, self.year)
        _validate_binding_period(self.year, self.period_code)
        return self


class ModeloBindingOverride(BaseModel):
    """One temporary preview value, never a saved binding."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    binding_id: _Token
    value: _Value


class ModeloBindingsResolveRequest(CredentialFreeOperationRequest):
    """One exact target and temporary overrides."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    modelo: _Modelo
    period: PublicPeriod
    as_of: date | None = None
    overrides: tuple[ModeloBindingOverride, ...] = ()

    @model_validator(mode="after")
    def _unique_overrides(self) -> Self:
        ids = tuple(row.binding_id for row in self.overrides)
        if len(set(ids)) != len(ids):
            raise ValueError("binding overrides must have unique ids")
        return self


class ModeloRequiresRequest(CredentialFreeOperationRequest):
    """One exact data-inventory target."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    modelo: _Modelo
    period: PublicPeriod
    language: OutputLanguage = OutputLanguage.ES


class ModeloReadinessOperationRequest(CredentialFreeOperationRequest):
    """One readiness target; absent period means the annual 0A preflight."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    modelo: _Modelo
    filing_year: FilingYear
    period: PublicPeriod | None = None
    revision_id: _Token | None = None
    language: OutputLanguage = OutputLanguage.ES

    @model_validator(mode="after")
    def _matching_period(self) -> Self:
        if self.period is not None and self.period.filing_year != self.filing_year:
            raise ValueError("readiness period must match filing year")
        return self


class ModeloBindingEncodedOptionV1(BaseModel):
    """One complete registry boolean encoding."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    encoded_value: str
    boolean_meaning: bool
    registry_value: str


class ModeloBindingRowV1(BaseModel):
    """Grounded binding row shared by list and preview."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    modelo: str
    revision: str
    filing_year: int | None
    period: str | None
    binding_id: str
    source: str
    readiness_locale_key: str
    typed_enum: str | None
    input_channel: str
    borrador_capable: bool
    legal_refs: tuple[str, ...]
    source_refs: tuple[str, ...]
    relation_inputs: tuple[str, ...]
    encoded_options: tuple[ModeloBindingEncodedOptionV1, ...]
    override: str | None = None

    @classmethod
    def from_report_row(
        cls, report: ModeloBindingsReport, row: ModeloBindingQueryRow, *, override: str | None = None
    ) -> Self:
        """Copy one registry row with its scope and complete legal grounding."""
        return cls(
            modelo=report.code,
            revision=report.revision,
            filing_year=report.filing_year,
            period=report.period,
            binding_id=row.binding_id,
            source=row.provider.kind,
            readiness_locale_key=CLAVES_LOCALE_DISPONIBILIDAD_POR_ORIGEN_VINCULACION_LOCALE_KEYS[row.provider.kind],
            typed_enum=row.typed_enum,
            input_channel=row.input_channel,
            borrador_capable=row.borrador_capable,
            legal_refs=row.legal_refs,
            source_refs=row.source_refs,
            relation_inputs=row.relation_inputs,
            encoded_options=tuple(
                ModeloBindingEncodedOptionV1(
                    encoded_value=item.encoded_value,
                    boolean_meaning=item.boolean_meaning,
                    registry_value=item.registry_value,
                )
                for item in row.encoded_options
            ),
            override=override,
        )


class ModeloBindingsListProjection(BaseModel):
    """Full ordered registry listing with explicit filters and count."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    result_version: Literal[1] = 1
    operation: Literal["modelo.bindings.list"] = "modelo.bindings.list"
    authority_generation: ContentDigest
    profile_id: UUID
    modelo_filter: str | None
    year_filter: int | None
    period_filter: str | None
    missing_filter: bool
    catalogue_only: bool
    known_modelos: tuple[str, ...]
    binding_count: int
    bindings: tuple[ModeloBindingRowV1, ...]


class ModeloBindingsResolveProjection(BaseModel):
    """Full ordered exact-scope preview with unsaved overrides."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    result_version: Literal[1] = 1
    operation: Literal["modelo.bindings.resolve"] = "modelo.bindings.resolve"
    authority_generation: ContentDigest
    profile_id: UUID
    modelo: str
    revision: str
    filing_year: int | None
    period: str | None
    override_count: int
    binding_count: int
    bindings: tuple[ModeloBindingRowV1, ...]


class ModeloInventoryCasillaV1(BaseModel):
    """One canonical checklist row and its provenance."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    casilla_id: str
    number: str
    label: str
    legal_refs: tuple[str, ...]
    source_refs: tuple[str, ...]
    binding_id: str | None
    binding_source: str | None

    @classmethod
    def from_casilla(cls, row: DataInventoryCasilla) -> Self:
        """Copy one canonical checklist row without shortening its references."""
        return cls(
            casilla_id=row.casilla_id,
            number=row.number,
            label=row.label,
            legal_refs=row.legal_refs,
            source_refs=row.source_refs,
            binding_id=row.binding_id,
            binding_source=row.binding_source,
        )


class ModeloRequiresProjection(BaseModel):
    """Every canonical checklist bucket and profile gap, in source order."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    result_version: Literal[1] = 1
    operation: Literal["modelo.requires"] = "modelo.requires"
    authority_generation: ContentDigest
    profile_id: UUID
    language: OutputLanguage
    modelo: str
    revision: str
    filing_year: int
    period: str
    required_manual: tuple[ModeloInventoryCasillaV1, ...]
    optional_manual: tuple[ModeloInventoryCasillaV1, ...]
    detail_row_fields: tuple[ModeloInventoryCasillaV1, ...]
    ledger_derivable: tuple[ModeloInventoryCasillaV1, ...]
    profile_derivable: tuple[ModeloInventoryCasillaV1, ...]
    previous_filing: tuple[ModeloInventoryCasillaV1, ...]
    relation_prefill: tuple[ModeloInventoryCasillaV1, ...]
    live_observation: tuple[ModeloInventoryCasillaV1, ...]
    unbucketed_sources: tuple[ModeloInventoryCasillaV1, ...]
    unresolved_profile_bindings: tuple[str, ...]
    unresolved_profile_keys: tuple[str, ...]
    profile_checked: bool

    @classmethod
    def from_checklist(
        cls,
        profile_id: UUID,
        checklist: DataInventoryChecklist,
        *,
        language: OutputLanguage,
        authority_generation: ContentDigest,
    ) -> Self:
        """Preserve every canonical checklist section in declaration order."""

        def rows(source: tuple[DataInventoryCasilla, ...]) -> tuple[ModeloInventoryCasillaV1, ...]:
            return tuple(ModeloInventoryCasillaV1.from_casilla(row) for row in source)

        return cls(
            authority_generation=authority_generation,
            profile_id=profile_id,
            language=language,
            modelo=checklist.modelo,
            revision=checklist.revision_id,
            filing_year=checklist.filing_year,
            period=checklist.period,
            required_manual=rows(checklist.required_manual),
            optional_manual=rows(checklist.optional_manual),
            detail_row_fields=rows(checklist.detail_row_fields),
            ledger_derivable=rows(checklist.ledger_derivable),
            profile_derivable=rows(checklist.profile_derivable),
            previous_filing=rows(checklist.previous_filing),
            relation_prefill=rows(checklist.relation_prefill),
            live_observation=rows(checklist.live_observation),
            unbucketed_sources=rows(checklist.unbucketed_sources),
            unresolved_profile_bindings=checklist.unresolved_profile_bindings,
            unresolved_profile_keys=checklist.unresolved_profile_keys,
            profile_checked=checklist.profile_checked,
        )


class ModeloReadinessMissingRequirementV1(BaseModel):
    """One missing profile requirement and its legal grounding."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    section_key: str
    field_key: str
    selector: str
    label: str
    legal_refs: tuple[str, ...]
    modelos: tuple[str, ...]


class ModeloReadinessMissingBindingV1(BaseModel):
    """One unresolved calculation binding."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    binding_id: str
    source: str
    input_channel: str


class ModeloReadinessLedgerIssueV1(BaseModel):
    """One ledger preflight issue with its transaction address."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    transaction_id: str
    reason: str
    detail: str


class ModeloReadinessProjection(BaseModel):
    """All canonical readiness axes, including unassessed and recovery facts."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    result_version: Literal[1] = 1
    operation: Literal["modelo.readiness"] = "modelo.readiness"
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
    profile_refusal: str
    profile_precondition_verdict: PreconditionVerdictSnapshot | None
    registry_ready: bool
    registry_refusal: str
    binding_ready: bool
    missing: tuple[ModeloReadinessMissingRequirementV1, ...]
    missing_bindings: tuple[ModeloReadinessMissingBindingV1, ...]
    ledger_preflight_required: bool
    ledger_ready: bool | None
    ledger_period: PublicPeriod | None
    ledger_checked_transaction_count: int
    ledger_issues: tuple[ModeloReadinessLedgerIssueV1, ...]

    @classmethod
    def from_report(
        cls,
        profile_id: UUID,
        report: ProjectionModeloReadiness,
        *,
        language: OutputLanguage,
        authority_generation: ContentDigest,
    ) -> Self:
        """Copy all readiness axes from the canonical report."""
        if str(report.profile_id) != str(profile_id):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        return cls(
            authority_generation=authority_generation,
            profile_id=profile_id,
            language=language,
            modelo=report.modelo,
            revision_id=report.revision_id,
            filing_year=report.filing_year,
            period=PublicPeriod.from_period(report.period),
            ready=report.ready,
            profile_ready=report.profile_ready,
            per_operation_requirements_assessed=report.per_operation_requirements_assessed,
            profile_refusal=report.profile_refusal,
            profile_precondition_verdict=(
                PreconditionVerdictSnapshot.from_verdict(report.profile_precondition_verdict)
                if report.profile_precondition_verdict is not None
                else None
            ),
            registry_ready=report.registry_ready,
            registry_refusal=report.registry_refusal,
            binding_ready=report.binding_ready,
            missing=tuple(
                ModeloReadinessMissingRequirementV1(
                    section_key=row.section_key,
                    field_key=row.field_key,
                    selector=row.selector,
                    label=row.label,
                    legal_refs=row.legal_refs,
                    modelos=row.modelos,
                )
                for row in report.missing
            ),
            missing_bindings=tuple(
                ModeloReadinessMissingBindingV1(
                    binding_id=row.binding_id,
                    source=row.source.value,
                    input_channel=row.input_channel,
                )
                for row in report.missing_bindings
            ),
            ledger_preflight_required=report.ledger_preflight_required,
            ledger_ready=report.ledger_ready,
            ledger_period=(
                PublicPeriod.from_period(report.ledger_period) if report.ledger_period is not None else None
            ),
            ledger_checked_transaction_count=report.ledger_checked_transaction_count,
            ledger_issues=tuple(
                ModeloReadinessLedgerIssueV1(
                    transaction_id=row.transaction_id,
                    reason=row.reason.value,
                    detail=row.detail,
                )
                for row in report.ledger_issues
            ),
        )
