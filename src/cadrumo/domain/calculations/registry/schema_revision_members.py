"""Revision-member declarations for the AEAT calculation registry.

These models describe revision-owned fragments connecting a filing definition
to applications, construct closure, cross-modelo dependencies, and operator
applicability.  Consumers import each canonical declaration from this module;
the ``ModeloRevision`` aggregate merely consumes their collection types.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from ....core.casilla_id import CasillaId
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
    RelationId,
    VerificationExpectationId,
    WorkbookParityRefId,
)
from .modelo_localization import resolve_modelo_localization
from .relation_dependency import (
    RelationDependencyTreatmentField,
)
from .schema_base import LegalRefs, RegistryModel, SourceRefs

__all__ = [
    "ApplicabilityRuleDefinition",
    "ApplicationLinkDefinition",
    "ConstructDefinition",
    "DependencyClassificationDefinition",
]


class ApplicationLinkDefinition(RegistryModel):
    """Declare one application surface that requires this registry authority."""

    id: ApplicationLinkId
    surface: Literal[
        "calculation",
        "filing",
        "review",
        "approval",
        "reconciliation",
        "export",
        "deadline",
        "portal",
        "extractor",
        "workflow",
        "communication",
        "payer_delivery",
    ]
    consumer: str
    requires_snapshot: Literal[True]
    legal_refs: LegalRefs
    source_refs: SourceRefs


class ConstructDefinition(RegistryModel):
    """Declare one legally grounded construct and the revision members it joins."""

    id: ConstructId
    localization_key: str = Field(min_length=1, exclude=True, repr=False)
    legal_refs: LegalRefs
    source_refs: SourceRefs
    casilla_ids: tuple[CasillaId, ...] = ()
    formulas: tuple[FormulaId, ...] = ()
    parameters: tuple[ParameterId, ...] = ()
    bindings: tuple[BindingId, ...] = ()
    relations: tuple[RelationId, ...] = ()
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
        resolved = resolve_modelo_localization((self.localization_key,), locale=locale, required=True)
        assert resolved is not None
        return resolved

    @property
    def title(self) -> str:
        """Return the strict official-Spanish construct title."""
        return self.get_title("es")

    @field_validator(
        "casilla_ids",
        "formulas",
        "parameters",
        "bindings",
        "relations",
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
    def _member_ids_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError("construct member ids must be unique")
        return value

    @model_validator(mode="after")
    def _validate_membership(self) -> ConstructDefinition:
        member_groups = (
            self.casilla_ids,
            self.formulas,
            self.parameters,
            self.bindings,
            self.relations,
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
    relation_refs: tuple[RelationId, ...] = ()
    legal_refs: LegalRefs
    source_refs: SourceRefs

    @field_validator("target_constructs", "relation_refs")
    @classmethod
    def _tuple_values_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError("dependency classification tuple entries must be unique")
        return value

    @model_validator(mode="after")
    def _validate_classification(self) -> DependencyClassificationDefinition:
        if self.treatment == "non_dependency":
            if self.target_constructs or self.relation_refs:
                raise RegistryValidationError(
                    f"non-dependency classification {self.id!r} must not declare target members",
                )
            return self
        if not self.target_constructs:
            raise RegistryValidationError(f"dependency classification {self.id!r} must declare target_constructs")
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
    legal_refs: LegalRefs

    @field_validator(
        "applicable_entity_types",
        "required_income_categories",
        "required_estimation_regimes",
        "applicable_fiscal_residencies",
        "applicable_iva_regimes",
    )
    @classmethod
    def _tuple_values_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError("applicability rule tuple entries must be unique")
        return value
