"""Revision-member declarations for the AEAT calculation registry.

These models describe revision-owned fragments connecting a filing definition
to applications, construct closure, cross-modelo dependencies, and operator
applicability.  Consumers import each canonical declaration from this module;
the ``ModeloRevision`` aggregate merely consumes their collection types.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BeforeValidator, Field, field_validator, model_validator

from ....core.casilla_id import CasillaId
from ....core.errors.hierarchy import pydantic_validation_boundary
from .errors import RegistryValidationError
from .ids import (
    ApplicabilityRuleId,
    ApplicationLinkId,
    BindingId,
    ConstructId,
    CrossReferenceId,
    DeadlineWindowId,
    DependencyClassificationId,
    ExportLayoutId,
    ExtractionProfileId,
    FormulaId,
    ModeloId,
    ParameterId,
    VerificationExpectationId,
    WorkbookParityRefId,
)
from .modelo_localization import require_modelo_localization
from .relation_dependency import (
    RelationDependencyTreatmentField,
)
from .schema_base import LegalRefs, RegistryModel, SourceRefs, coerce_enum_member

__all__ = [
    "ApplicabilityExclusionDefinition",
    "ApplicabilityRuleDefinition",
    "ApplicationLinkDefinition",
    "ConstructDefinition",
    "DependencyClassificationDefinition",
]


class ApplicationLinkSurface(StrEnum):
    """Which product surface consumes a declared application link.

    Distinct from the extraction surfaces and the live verification surfaces: those name
    an artefact and an AEAT endpoint respectively, while this names a part of the
    product. The three share no token by accident.
    """

    CALCULATION = "calculation"
    FILING = "filing"
    REVIEW = "review"
    APPROVAL = "approval"
    RECONCILIATION = "reconciliation"
    EXPORT = "export"
    DEADLINE = "deadline"
    PORTAL = "portal"
    EXTRACTOR = "extractor"
    WORKFLOW = "workflow"
    COMMUNICATION = "communication"
    PAYER_DELIVERY = "payer_delivery"


ApplicationLinkSurfaceField = Annotated[
    ApplicationLinkSurface, BeforeValidator(coerce_enum_member(ApplicationLinkSurface))
]
"""Registry token hydrated into a ApplicationLinkSurface member."""


class ApplicationLinkDefinition(RegistryModel):
    """Declare one application surface that requires this registry authority."""

    id: ApplicationLinkId
    surface: ApplicationLinkSurfaceField
    consumer: str
    requires_snapshot: Literal[True]
    legal_refs: LegalRefs
    source_refs: SourceRefs


class ConstructDefinition(RegistryModel):
    """Declare one legally grounded construct and the revision members it joins."""

    id: ConstructId
    localization_keys: tuple[str, ...] = Field(min_length=1, exclude=True, repr=False)
    legal_refs: LegalRefs
    source_refs: SourceRefs
    casilla_ids: tuple[CasillaId, ...] = ()
    formulas: tuple[FormulaId, ...] = ()
    parameters: tuple[ParameterId, ...] = ()
    bindings: tuple[BindingId, ...] = ()
    export_layouts: tuple[ExportLayoutId, ...] = ()
    extraction_profiles: tuple[ExtractionProfileId, ...] = ()
    live_cross_references: tuple[CrossReferenceId, ...] = ()
    workbook_parity_refs: tuple[WorkbookParityRefId, ...] = ()
    verification_expectations: tuple[VerificationExpectationId, ...] = ()
    application_links: tuple[ApplicationLinkId, ...] = ()
    deadline_windows: tuple[DeadlineWindowId, ...] = ()
    filing_schedules: tuple[str, ...] = ()
    dependency_classifications: tuple[DependencyClassificationId, ...] = ()

    def get_title(self, locale: str) -> str:
        """Resolve the construct title from the shared catalogue."""
        return require_modelo_localization(self.localization_keys, locale=locale)

    @property
    def title(self) -> str:
        """Return the strict official-Spanish construct title."""
        return self.get_title("es")

    @field_validator(
        "casilla_ids",
        "formulas",
        "parameters",
        "bindings",
        "export_layouts",
        "extraction_profiles",
        "live_cross_references",
        "workbook_parity_refs",
        "verification_expectations",
        "application_links",
        "deadline_windows",
        "filing_schedules",
        "dependency_classifications",
    )
    @classmethod
    @pydantic_validation_boundary
    def _member_ids_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError("construct member ids must be unique")
        return value

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_membership(self) -> ConstructDefinition:
        member_groups = (
            self.casilla_ids,
            self.formulas,
            self.parameters,
            self.bindings,
            self.export_layouts,
            self.extraction_profiles,
            self.live_cross_references,
            self.workbook_parity_refs,
            self.verification_expectations,
            self.application_links,
            self.deadline_windows,
            self.filing_schedules,
            self.dependency_classifications,
        )
        if not any(member_groups):
            raise RegistryValidationError(f"construct {self.id!r} must declare at least one revision member")
        return self


class DependencyClassificationDefinition(RegistryModel):
    """Classify how one source modelo contributes to this modelo's authority."""

    id: DependencyClassificationId
    source_modelo: ModeloId
    treatment: RelationDependencyTreatmentField
    taxpayer_files_source: bool = True
    conditional_on_economic_activity: bool = False
    target_constructs: tuple[ConstructId, ...] = ()
    binding_refs: tuple[BindingId, ...] = ()
    legal_refs: LegalRefs
    source_refs: SourceRefs

    @field_validator("target_constructs", "binding_refs")
    @classmethod
    @pydantic_validation_boundary
    def _tuple_values_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError("dependency classification tuple entries must be unique")
        return value

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_classification(self) -> DependencyClassificationDefinition:
        if self.treatment == "non_dependency":
            if self.target_constructs or self.binding_refs:
                raise RegistryValidationError(
                    f"non-dependency classification {self.id!r} must not declare target members",
                )
            return self
        if not self.target_constructs:
            raise RegistryValidationError(f"dependency classification {self.id!r} must declare target_constructs")
        return self


class ApplicabilityExclusionDefinition(RegistryModel):
    """One registry-authored exclusion from a modelo-applicability rule.

    An exclusion is a conjunction of typed conditions on declared profile
    facts; it takes effect only when every declared condition holds. Each
    condition reads one axis: ``entity_types`` and ``iva_regimes`` match a
    declared token, ``lacking_income_categories`` holds when the profile
    declares none of the listed IRPF categories, ``declaration_role_selection``
    names a selection of the third-party declaration-role catalogue whose roles
    the filer holds, and ``payer_fact`` reads a payer-applicability fact whose
    declared answer must equal ``payer_fact_declared``.

    ``outcome`` is the verdict a holding exclusion yields: ``not_applicable``
    for a legal exclusion, or ``incomplete`` when the declared facts cannot
    settle the obligation on their own. Either way the verdict carries this
    entry's own ``reason`` and ``legal_refs``.
    """

    id: Annotated[str, Field(min_length=1)]
    outcome: Literal["not_applicable", "incomplete"] = "not_applicable"
    entity_types: tuple[str, ...] = ()
    iva_regimes: tuple[str, ...] = ()
    lacking_income_categories: tuple[str, ...] = ()
    declaration_role_selection: str | None = None
    payer_fact: str | None = None
    payer_fact_declared: bool = True
    reason: Annotated[str, Field(min_length=1)]
    legal_refs: LegalRefs

    @field_validator("entity_types", "iva_regimes", "lacking_income_categories")
    @classmethod
    @pydantic_validation_boundary
    def _tuple_values_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError("applicability exclusion tuple entries must be unique")
        return value

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_conditions(self) -> ApplicabilityExclusionDefinition:
        conditions = (
            self.entity_types,
            self.iva_regimes,
            self.lacking_income_categories,
            self.declaration_role_selection,
            self.payer_fact,
        )
        if not any(conditions):
            raise RegistryValidationError(f"applicability exclusion {self.id!r} must declare at least one condition")
        if self.payer_fact is None and not self.payer_fact_declared:
            raise RegistryValidationError(
                f"applicability exclusion {self.id!r} sets payer_fact_declared without naming a payer_fact",
            )
        return self


class ApplicabilityRuleDefinition(RegistryModel):
    """A registry-authored modelo-applicability rule fragment.

    Closed-vocabulary values remain registry strings. The loader-owned hydration
    boundary resolves them to deadline-domain enums, avoiding a cycle back into
    this schema package.
    """

    id: ApplicabilityRuleId
    applicable_entity_types: Annotated[tuple[str, ...], Field(min_length=1)]
    required_income_categories: tuple[str, ...] = ()
    required_estimation_regimes: tuple[str, ...] = ()
    applicable_fiscal_residencies: tuple[str, ...] = ()
    applicable_iva_regimes: tuple[str, ...] = ()
    required_payer_fact: str | None = None
    applicable_reason: Annotated[str, Field(min_length=1)]
    not_applicable_reason: Annotated[str, Field(min_length=1)]
    cuota_bearing: bool = False
    exclusions: tuple[ApplicabilityExclusionDefinition, ...] = ()
    legal_refs: LegalRefs

    @field_validator("exclusions")
    @classmethod
    @pydantic_validation_boundary
    def _exclusion_ids_unique(
        cls,
        value: tuple[ApplicabilityExclusionDefinition, ...],
    ) -> tuple[ApplicabilityExclusionDefinition, ...]:
        ids = [exclusion.id for exclusion in value]
        if len(set(ids)) != len(ids):
            raise RegistryValidationError("applicability rule exclusion ids must be unique")
        return value

    @field_validator(
        "applicable_entity_types",
        "required_income_categories",
        "required_estimation_regimes",
        "applicable_fiscal_residencies",
        "applicable_iva_regimes",
    )
    @classmethod
    @pydantic_validation_boundary
    def _tuple_values_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError("applicability rule tuple entries must be unique")
        return value
