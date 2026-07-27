"""Strict schema authority for AEAT registry definitions.

Each modelo revision carries an ``output_sensitivity`` field typed as
:class:`SensitivityClass` that governs the encryption tier applied to
generated output envelopes.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    BeforeValidator,
    Field,
    ValidationInfo,
    field_serializer,
    field_validator,
    model_validator,
)

from ....core import REVIEWED_REVISION_REVIEW_STATUSES, Period, RevisionReviewStatus, TaxDomain
from ....core.aggregation import BindingAggregation, BindingSourceKind, BindingTypedEnumKind
from ....core.classification import SensitivityClass
from .._export_field_kind import CasillaFieldKind, CasillaFieldKindValue

# Scalar and annotated value types live in `_schema_scalars`; these assignments
# preserve the historical `_schema` import surface for tests and consumers.
from . import _schema_scalars as _scalars
from ._aeat_hosts import first_aeat_host
from ._errors import RegistryValidationError
from ._ids import (
    ApplicationLinkId,
    BindingId,
    CasillaId,
    ConstructId,
    CrossReferenceId,
    DeadlineWindowId,
    DependencyClassificationId,
    ExportLayoutId,
    ExtractionProfileId,
    FormulaId,
    LegalRefId,
    ModeloId,
    OracleId,
    ParameterId,
    RelationId,
    RevisionId,
    SourceRefId,
    SupportRemovalDecisionId,
    VerificationExpectationId,
    WorkbookFixtureId,
    WorkbookOutputId,
    WorkbookParityRefId,
)
from ._schema_input_kind import InputKind, InputKindValue
from ._schema_rounding import RegistryRoundingCode as RegistryRoundingCode
from ._schema_rounding import RegistryRoundingCodeValue

__all__ = [
    "AlgorithmBindingDefinition",
    "AlgorithmProviderDefinition",
    "ApplicationLinkDefinition",
    "BboxAnchorSpec",
    "BindingSelector",
    "BracketEntry",
    "CalculationClass",
    "CalculationCompletenessCasilla",
    "CalculationCompletenessManifest",
    "CasillaAlias",
    "CasillaConstraints",
    "CasillaContinuidadEvolutionDefinition",
    "CasillaDefinition",
    "CasillaFieldKind",
    "CasillaFieldKindValue",
    "ConstructDefinition",
    "ConvenioAuthority",
    "DataBindingDefinition",
    "DateAxis",
    "DatedValue",
    "DeadlineWindowDefinition",
    "DecimalValue",
    "DependencyClassificationDefinition",
    "EvidenceTier",
    "ExportFieldDefinition",
    "ExportLayoutDefinition",
    "ExportRecordDefinition",
    "ExtractionProfileDefinition",
    "ExtractionTargetDefinition",
    "FormulaDefinition",
    "FormulaExpression",
    "FormulaOperator",
    "InputKind",
    "InputKindValue",
    "KeyedBracketEntry",
    "LegalParameter",
    "LegalReference",
    "LegalRefs",
    "LiveCrossReferenceDecision",
    "ModeloDefinition",
    "ModeloFilingCapability",
    "ModeloRevision",
    "ModeloScheduleDefinition",
    "ParameterDefinition",
    "PeriodSelector",
    "ProfilePredicateDefinition",
    "RegistryCatalogues",
    "RegistryModel",
    "RegistryRoundingCode",
    "RegistryRoundingCodeValue",
    "RegistrySnapshot",
    "RegistrySnapshotRef",
    "RegistryVerificationPolicy",
    "RelationDefinition",
    "RelationPeriodAlignment",
    "RelationRevisionSelector",
    "ReviewStatus",
    "SensitivityClassField",
    "SourceCitation",
    "SourceCitationText",
    "SourceReference",
    "SourceRefs",
    "SupportRemovalDecisionDefinition",
    "TemporalApplicability",
    "VerificationExpectationDefinition",
    "VerificationPredicateDefinition",
    "WorkbookParityReference",
]

from ._convenio import ConvenioAuthority
from ._schema_base import (
    CalculationClass,
    DateAxis,
    EvidenceTier,
    FormulaOperator,
    LegalRefs,
    ModeloFilingCapability,
    RegistryModel,
    ReviewStatus,
    RevisionReviewStatusField,
    SensitivityClassField,
    SourceCitation,
    SourceCitationText,
    SourceRefs,
)
from ._schema_extraction import BboxAnchorSpec, ExtractionProfileDefinition, ExtractionTargetDefinition
from ._schema_formula import (
    BracketEntry,
    DatedValue,
    FormulaExpression,
    KeyedBracketEntry,
    ParameterDefinition,
)
from ._schema_references import (
    LegalParameter,
    LegalReference,
    PeriodSelector,
    RegistrySnapshotRef,
    SourceReference,
    TemporalApplicability,
)
from ._schema_surfaces import (
    AlgorithmBindingDefinition,
    AlgorithmProviderDefinition,
    CalculationCompletenessCasilla,
    CalculationCompletenessManifest,
    CasillaAlias,
    CasillaConstraints,
    CasillaContinuidadEvolutionDefinition,
    CasillaDefinition,
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
    RelationDefinition,
    RelationPeriodAlignment,
    RelationRevisionSelector,
)

DecimalValue = _scalars.DecimalValue
NifString = _scalars.NifString
ModeloYear = _scalars.ModeloYear
PeriodCode = _scalars.PeriodCode
CountryCode = _scalars.CountryCode
IbanString = _scalars.IbanString
PersonOrEntityName = _scalars.PersonOrEntityName
NifIvaString = _scalars.NifIvaString
CCAACode = _scalars.CCAACode
ProvinceCode = _scalars.ProvinceCode
PostalCode = _scalars.PostalCode
MunicipalityCode = _scalars.MunicipalityCode
BicString = _scalars.BicString
CalendarDate = _scalars.CalendarDate
WorkbookCellRefStr = _scalars.WorkbookCellRefStr
BindingSelectorValue = _scalars.BindingSelectorValue
BindingSelectorMap = _scalars.BindingSelectorMap
BindingSelector = _scalars.BindingSelector
_coerce_modelo_year = _scalars._coerce_modelo_year
_validate_country_code = _scalars._validate_country_code
_validate_iban_string = _scalars._validate_iban_string
_validate_nif_string = _scalars._validate_nif_string
_validate_period_code = _scalars._validate_period_code


ProfileFactValue = bool | int | str


class ProfilePredicateDefinition(RegistryModel):
    field: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z_][A-Za-z0-9_.-]*$")
    op: Literal["equals", "not_equals"]
    value: ProfileFactValue
    explanation: str = Field(min_length=1)
    legal_refs: LegalRefs
    source_refs: SourceRefs


class LiveCrossReferenceDecision(RegistryModel):
    id: CrossReferenceId
    evidence_tier: EvidenceTier
    surface: Literal[
        "open_simulator",
        "integration_test_service",
        "public_read_surface",
        "authenticated_read_surface",
        "authenticated_simulator",
        "static_official_documentation",
    ]
    guard_policy_id: str
    allowed_hosts: tuple[str, ...] = ()
    allowed_methods: tuple[str, ...] = ()
    forbidden_actions: tuple[str, ...] = Field(min_length=1)
    synthetic_data_allowed: bool
    requires_authentication: bool
    requires_aeat_authorization: bool
    legal_refs: LegalRefs
    source_refs: SourceRefs
    # Optional: id of an oracle adapter registered in LiveParityCatalogue.
    # When set, the calculation engine looks up the bound adapter to drive
    # synthetic-payload verification under the cross-reference's policy.
    # Resolution against the catalogue happens at calculation time, not at
    # registry-load time, so the registry remains loadable when adapters
    # are imported lazily.
    oracle_id: OracleId | None = None
    # Optional applicability gate: when non-empty the cross-reference is
    # only applicable to a taxpayer profile whose values satisfy these
    # predicates under the chosen mode. An empty tuple (the default) means
    # the cross-reference is unconditionally applicable. Used to gate
    # optional surfaces (GROI / IXVI for ROI-enrolled subjects, OSS
    # bindings for OSS-enrolled subjects, etc.).
    applicability_condition_mode: Literal["all", "any"] = "all"
    applicability_predicates: tuple[ProfilePredicateDefinition, ...] = ()

    @field_validator("oracle_id")
    @classmethod
    def _oracle_id_shape(cls, value: str | None) -> str | None:
        if value is None:
            return None
        # kebab-case ASCII identifier: lowercase alpha start, alphanumerics
        # plus hyphens, no trailing hyphen.
        if not value[0].isalpha() or not value[0].islower():
            raise RegistryValidationError("oracle_id must start with a lowercase ASCII letter")
        if value.endswith("-"):
            raise RegistryValidationError("oracle_id must not end with a hyphen")
        for char in value:
            if not (char.islower() and char.isascii()) and not char.isdigit() and char != "-":
                raise RegistryValidationError(
                    f"oracle_id contains unsupported character {char!r}; "
                    f"only lowercase ASCII letters, digits, and hyphens are permitted",
                )
        return value

    @model_validator(mode="after")
    def _validate_cross_reference(self) -> LiveCrossReferenceDecision:
        self._validate_evidence_tier_alignment()
        self._validate_allowed_hosts_declared()
        self._validate_authentication_constraints()
        self._validate_synthetic_data_constraints()
        for method in self.allowed_methods:
            self._validate_allowed_method(method)
        if self.applicability_condition_mode == "any" and not self.applicability_predicates:
            raise RegistryValidationError(f"cross-reference {self.id!r} any-mode requires applicability predicates")
        return self

    def _validate_evidence_tier_alignment(self) -> None:
        """The evidence_tier must match the surface's regulatory class.

        Live surfaces (simulators, integration test services) carry
        executable parity evidence; read surfaces and static
        documentation carry observation evidence only.
        """
        if (
            self.surface in {"open_simulator", "integration_test_service", "authenticated_simulator"}
            and self.evidence_tier != "executable_parity_evidence"
        ):
            raise RegistryValidationError(
                f"cross-reference {self.id!r} live surface requires executable parity evidence",
            )
        if (
            self.surface in {"public_read_surface", "authenticated_read_surface"}
            and self.evidence_tier == "executable_parity_evidence"
        ):
            raise RegistryValidationError(
                f"cross-reference {self.id!r} read surface is observation evidence, not parity",
            )
        if self.surface == "static_official_documentation" and self.evidence_tier == "executable_parity_evidence":
            raise RegistryValidationError(
                f"cross-reference {self.id!r} static documentation is not executable parity evidence",
            )

    def _validate_allowed_hosts_declared(self) -> None:
        """Every non-static surface must declare its allowed_hosts."""
        if (
            self.surface
            in {
                "open_simulator",
                "integration_test_service",
                "public_read_surface",
                "authenticated_read_surface",
                "authenticated_simulator",
            }
            and not self.allowed_hosts
        ):
            raise RegistryValidationError(f"cross-reference {self.id!r} must declare allowed_hosts")

    def _validate_authentication_constraints(self) -> None:
        """Per-surface auth + AEAT-authorization requirements.

        Open simulators and public reads must not require auth;
        authenticated reads must require both auth and AEAT
        authorization; authenticated simulators must require auth.
        """
        if self.surface == "open_simulator" and self.requires_authentication:
            raise RegistryValidationError(f"cross-reference {self.id!r} open simulator must not require authentication")
        if self.surface == "public_read_surface" and self.requires_authentication:
            raise RegistryValidationError(
                f"cross-reference {self.id!r} public read surface must not require authentication",
            )
        if self.surface == "authenticated_read_surface" and not self.requires_authentication:
            raise RegistryValidationError(
                f"cross-reference {self.id!r} authenticated read surface must require authentication",
            )
        if self.surface == "authenticated_read_surface" and not self.requires_aeat_authorization:
            raise RegistryValidationError(
                f"cross-reference {self.id!r} authenticated read surface must require authorization",
            )
        if self.surface == "authenticated_simulator" and not self.requires_authentication:
            raise RegistryValidationError(
                f"cross-reference {self.id!r} authenticated simulator must require authentication",
            )

    def _validate_synthetic_data_constraints(self) -> None:
        """Read surfaces and static docs must not accept synthetic data.

        Additionally, no cross-reference whose ``allowed_hosts`` include an
        AEAT-owned host (suffix match against ``agenciatributaria.gob.es``
        or ``aeat.es``) may declare ``synthetic_data_allowed = true``.
        Synthetic taxpayer, counterparty, declaration, profile, or form
        data is prohibited on AEAT-hosted live surfaces; the surface
        shape (``open_simulator`` / ``authenticated_simulator``) does not
        license synthetic input against AEAT infrastructure.
        """
        if self.surface in {"public_read_surface", "authenticated_read_surface"} and self.synthetic_data_allowed:
            raise RegistryValidationError(f"cross-reference {self.id!r} read surface must not accept synthetic data")
        if self.surface == "static_official_documentation" and self.synthetic_data_allowed:
            raise RegistryValidationError(
                f"cross-reference {self.id!r} static documentation cannot accept synthetic data",
            )
        if self.synthetic_data_allowed:
            aeat_host = first_aeat_host(self.allowed_hosts)
            if aeat_host is not None:
                raise RegistryValidationError(
                    f"cross-reference {self.id!r} declares synthetic_data_allowed = true "
                    f"on AEAT-hosted allowed host {aeat_host!r}; synthetic data is prohibited "
                    f"on AEAT-hosted live surfaces",
                )

    def _validate_allowed_method(self, method: str) -> None:
        """Per-surface HTTP method allowlist + uppercase shape requirement."""
        if method.upper() != method:
            raise RegistryValidationError(f"cross-reference {self.id!r} allowed_methods must be uppercase")
        if self.surface in {"public_read_surface", "authenticated_read_surface"} and method not in {
            "GET",
            "HEAD",
            "OPTIONS",
        }:
            raise RegistryValidationError(
                f"cross-reference {self.id!r} read surface method {method!r} is not read-only",
            )
        # authenticated_simulator declares the AEAT-prescribed query
        # method (POST is the GROI / IXVI form-submit mechanism). The
        # remote-state guard's HTTP-method check stays strict for
        # ``kind="http"`` operations; only the cross-reference's
        # allowed_methods declaration is widened.
        if self.surface == "authenticated_simulator" and method not in {"GET", "HEAD", "OPTIONS", "POST"}:
            raise RegistryValidationError(
                f"cross-reference {self.id!r} authenticated simulator method "
                f"{method!r} not in (GET, HEAD, OPTIONS, POST)",
            )


class WorkbookParityReference(RegistryModel):
    id: WorkbookParityRefId
    workbook_source: SourceRefId
    fixture_id: WorkbookFixtureId
    formula_coverage: Literal["formula_form", "static_layout", "record_design_layout", "unsupported_binary_xls"]
    runner_required: bool
    output_cells: Mapping[WorkbookOutputId, WorkbookCellRefStr] = Field(default_factory=dict)
    tolerance: DecimalValue = Decimal("0.00")
    legal_refs: LegalRefs
    source_refs: SourceRefs

    @model_validator(mode="after")
    def _validate_workbook_reference(self) -> WorkbookParityReference:
        if self.formula_coverage == "formula_form" and not self.runner_required:
            raise RegistryValidationError(f"workbook parity reference {self.id!r} formula coverage requires a runner")
        if self.formula_coverage != "formula_form" and self.runner_required:
            raise RegistryValidationError(f"workbook parity reference {self.id!r} runner requires formula coverage")
        if self.runner_required and not self.output_cells:
            raise RegistryValidationError(f"workbook parity reference {self.id!r} requires output_cells")
        if self.workbook_source not in self.source_refs:
            raise RegistryValidationError(
                f"workbook parity reference {self.id!r} source_refs must include workbook_source",
            )
        return self


class VerificationExpectationDefinition(RegistryModel):
    id: VerificationExpectationId
    computed_casilla_ids: tuple[CasillaId, ...]
    reconcile_when_present_casilla_ids: tuple[CasillaId, ...] = ()
    externally_grounded_casilla_ids: tuple[CasillaId, ...] = ()
    reconciliation_total_casilla_ids: Mapping[Literal["ingresar", "devolver"], CasillaId] = Field(
        default_factory=dict,
    )
    tolerance: DecimalValue
    rounding: str
    min_coverage: DecimalValue = Field(ge=Decimal("0"), le=Decimal("1"))
    discrepancy_causes: tuple[
        Literal["extraction_unreliable", "unmodelled_rule", "rounding", "correctness_divergence"],
        ...,
    ] = Field(min_length=1)
    legal_refs: LegalRefs
    source_refs: SourceRefs

    @field_validator("computed_casilla_ids")
    @classmethod
    def _computed_casilla_ids_unique(cls, value: tuple[CasillaId, ...]) -> tuple[CasillaId, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError("verification expectation computed_casilla_ids must be unique")
        return value

    @field_validator("reconcile_when_present_casilla_ids")
    @classmethod
    def _reconcile_when_present_unique(cls, value: tuple[CasillaId, ...]) -> tuple[CasillaId, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError(
                "verification expectation reconcile_when_present_casilla_ids must be unique",
            )
        return value

    @field_validator("externally_grounded_casilla_ids")
    @classmethod
    def _externally_grounded_unique(cls, value: tuple[CasillaId, ...]) -> tuple[CasillaId, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError(
                "verification expectation externally_grounded_casilla_ids must be unique",
            )
        return value

    @model_validator(mode="after")
    def _reconcile_when_present_disjoint(self) -> VerificationExpectationDefinition:
        overlap = set(self.reconcile_when_present_casilla_ids) & set(self.computed_casilla_ids)
        if overlap:
            raise RegistryValidationError(
                "verification expectation reconcile_when_present_casilla_ids must be disjoint from "
                f"computed_casilla_ids (overlap: {sorted(overlap)})",
            )
        return self

    @model_validator(mode="after")
    def _externally_grounded_subset(self) -> VerificationExpectationDefinition:
        reconciled = set(self.computed_casilla_ids) | set(self.reconcile_when_present_casilla_ids)
        outside = set(self.externally_grounded_casilla_ids) - reconciled
        if outside:
            raise RegistryValidationError(
                "verification expectation externally_grounded_casilla_ids must be a subset of "
                f"computed_casilla_ids | reconcile_when_present_casilla_ids (outside: {sorted(outside)})",
            )
        return self


class ApplicationLinkDefinition(RegistryModel):
    id: ApplicationLinkId
    surface: Literal[
        "calculation",
        "filing",
        "review",
        "verification",
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


class SupportRemovalDecisionDefinition(RegistryModel):
    id: SupportRemovalDecisionId
    subject_type: Literal[
        "export_layout",
        "extraction_profile",
        "filing_path",
        "application_link",
        "live_cross_reference",
        "workbook_parity_ref",
        "verification_expectation",
        "deadline_window",
        "filing_schedule",
    ]
    subject_id: str = Field(min_length=1, max_length=160)
    decision: Literal["remove_from_filing_grade"]
    reason: Literal[
        "missing_legal_authority",
        "missing_official_source",
        "unsafe_remote_state",
        "unsupported_official_format",
        "out_of_scope",
    ]
    evidence_note: str = Field(min_length=1, max_length=2048)
    legal_refs: LegalRefs
    source_refs: SourceRefs


class ConstructDefinition(RegistryModel):
    id: ConstructId
    title: str = Field(min_length=1, max_length=200)
    legal_refs: LegalRefs
    source_refs: SourceRefs
    casilla_ids: tuple[CasillaId, ...] = ()
    formulas: tuple[FormulaId, ...] = ()
    parameters: tuple[ParameterId, ...] = ()
    bindings: tuple[BindingId, ...] = ()
    algorithm_providers: tuple[str, ...] = ()
    algorithm_bindings: tuple[str, ...] = ()
    relations: tuple[RelationId, ...] = ()
    export_layouts: tuple[ExportLayoutId, ...] = ()
    extraction_profiles: tuple[ExtractionProfileId, ...] = ()
    live_cross_references: tuple[CrossReferenceId, ...] = ()
    workbook_parity_refs: tuple[WorkbookParityRefId, ...] = ()
    verification_expectations: tuple[VerificationExpectationId, ...] = ()
    application_links: tuple[ApplicationLinkId, ...] = ()
    deadline_windows: tuple[DeadlineWindowId, ...] = ()
    filing_schedules: tuple[str, ...] = ()
    support_removal_decisions: tuple[SupportRemovalDecisionId, ...] = ()
    dependency_classifications: tuple[DependencyClassificationId, ...] = ()

    @field_validator(
        "casilla_ids",
        "formulas",
        "parameters",
        "bindings",
        "algorithm_providers",
        "algorithm_bindings",
        "relations",
        "export_layouts",
        "extraction_profiles",
        "live_cross_references",
        "workbook_parity_refs",
        "verification_expectations",
        "application_links",
        "deadline_windows",
        "filing_schedules",
        "support_removal_decisions",
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
            self.algorithm_providers,
            self.algorithm_bindings,
            self.relations,
            self.export_layouts,
            self.extraction_profiles,
            self.live_cross_references,
            self.workbook_parity_refs,
            self.verification_expectations,
            self.application_links,
            self.deadline_windows,
            self.filing_schedules,
            self.support_removal_decisions,
            self.dependency_classifications,
        )
        if not any(member_groups):
            raise RegistryValidationError(f"construct {self.id!r} must declare at least one revision member")
        return self


class DependencyClassificationDefinition(RegistryModel):
    id: DependencyClassificationId
    source_modelo: ModeloId
    treatment: Literal["direct_annual_settlement", "factual_evidence", "non_dependency"]
    taxpayer_files_source: bool = True
    """Whether the taxpayer FILES the source modelo (True) or merely SUFFERS its withholding (False).

    True (default) for modelos the taxpayer is the obligor of (e.g. 130/131 pagos fraccionados the
    autónomo files). False for retenciones the taxpayer SUFFERS but the PAYER files (e.g. 111/115/
    123/193) - the taxpayer cannot file these, so the M100 cross-period dependency on them is not a
    filing the taxpayer must evidence; the clean-state gate scopes such a dependency out as
    not-applicable (advisory), the value coming from the income certificate (operator override or a
    filed source where one exists). A regulated payee/payer distinction, grounded per the AEAT M100
    dictionary and LIRPF art. 99 (retenciones e ingresos a cuenta).
    """
    conditional_on_economic_activity: bool = False
    """Whether the taxpayer files the source modelo ONLY when they have economic activity.

    True for pagos-fraccionados modelos an autónomo files IFF they carry on an economic
    activity (130 estimación directa / 131 objetiva). The clean-state gate scopes such a
    dependency out as not-applicable when the taxpayer has DECLARED income categories that do
    not include actividad económica (a salaried/rental-only filer never files 130/131). Fail-
    closed: when economic-activity status is undeclared the dependency stays enforced. Only
    meaningful together with ``taxpayer_files_source = true``. Grounded in LIRPF art. 99 /
    RIRPF art. 109 (pago fraccionado of actividades económicas).
    """
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
        if self.treatment == "direct_annual_settlement" and not self.relation_refs:
            raise RegistryValidationError(f"dependency classification {self.id!r} must declare relation_refs")
        return self


def _parse_deadline_window_period(value: object) -> Period:
    """Hydrate a deadline-window period through :class:`~core.Period`."""
    if isinstance(value, Period):
        return value
    if isinstance(value, Mapping):
        try:
            return Period.model_validate(value)
        except ValueError as exc:
            raise ValueError(f"invalid deadline window period mapping {value!r}: {exc}") from exc
    if not isinstance(value, str):
        raise ValueError(f"deadline window period must be a string or Period, got {type(value).__name__}")

    try:
        return Period.from_string(value)
    except ValueError as exc:
        raise ValueError(f"invalid deadline window period {value!r}: {exc}") from exc


class DeadlineWindowDefinition(RegistryModel):
    id: DeadlineWindowId
    filing_year: int = Field(ge=1900, le=2999)
    period: Annotated[Period, BeforeValidator(_parse_deadline_window_period)]
    period_kind: Literal["monthly", "quarterly", "annual", "ad_hoc"]
    opens_on: date
    closes_on: date
    payment_cutoff_on: date | None = None
    applicability_condition_mode: Literal["all", "any"] = "all"
    applicability_conditions: tuple[ProfilePredicateDefinition, ...] = ()
    legal_refs: LegalRefs
    source_refs: SourceRefs

    @model_validator(mode="after")
    def _validate_window(self) -> DeadlineWindowDefinition:
        if self.opens_on > self.closes_on:
            raise RegistryValidationError(f"deadline window {self.id!r} opens_on must not be after closes_on")
        if self.payment_cutoff_on is not None and self.payment_cutoff_on > self.closes_on:
            raise RegistryValidationError(f"deadline window {self.id!r} payment_cutoff_on must not be after closes_on")
        if self.applicability_condition_mode == "any" and not self.applicability_conditions:
            raise RegistryValidationError(f"deadline window {self.id!r} any-mode requires applicability conditions")
        return self


class ModeloScheduleDefinition(RegistryModel):
    id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.-]+$")
    period_kind: Literal["monthly", "quarterly", "annual", "ad_hoc"]
    periods: tuple[str, ...] = Field(min_length=1)
    profile_condition_mode: Literal["all", "any"] = "all"
    profile_conditions: tuple[ProfilePredicateDefinition, ...] = ()
    legal_refs: LegalRefs
    source_refs: SourceRefs

    @field_validator("periods")
    @classmethod
    def _periods_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError("filing schedule periods must be unique")
        return value

    @model_validator(mode="after")
    def _validate_schedule(self) -> ModeloScheduleDefinition:
        if self.profile_condition_mode == "any" and not self.profile_conditions:
            raise RegistryValidationError(f"filing schedule {self.id!r} any-mode requires profile conditions")
        return self


class DataBindingDefinition(RegistryModel):
    id: BindingId
    source: BindingSourceKind
    # Accepts a raw authoring mapping (the TOML shape, and the shape every
    # constructor call site in the test suite passes) in addition to an
    # already-typed selector model: ``_coerce_selector`` (a ``mode="before"``
    # validator, below) hydrates either into the source-family model at
    # construction, so the declared input type must cover both.
    selector: BindingSelector | Mapping[str, object]
    aggregation: BindingAggregation | None = None
    typed_enum: BindingTypedEnumKind | None = None
    """Closed-set enum class name a consumer routes the binding value through.

    LIVE field (do NOT remove). Typed as the closed
    :class:`~core.aggregation.BindingTypedEnumKind` reference (F8 — was a
    bare ``str``); declared in registry TOML for the bindings that bridge a
    closed-membership substrate axis — ``"censo_event_kind"`` (M036), ``"CCAA"``
    and ``"EstimacionDirectaModalidad"`` (M100), ``"LegalEntityForm"`` (M200) —
    and surfaced by the operator-facing ``bindings list`` CLI table
    (``_modelo_discovery_cli.py``), the
    :class:`~domain.calculations.registry._query_reports.ModeloBindingQueryRow`
    query projection, the borrador binding resolver, and the Sheets-pull edit router.
    Because a :class:`~enum.StrEnum` serialises to its value, those ``str``
    consumers stay byte-compatible. It is the closed-set *annotation* on the
    binding, distinct from the ``input_channel`` (how a formula consumes the
    value); a binding may carry a ``typed_enum`` yet still be a numeric
    ``decimal`` channel. The loader's raw TOML token is hydrated to its member
    by :meth:`~domain.calculations.registry.DataBindingDefinition._coerce_typed_enum`
    at the boundary (an unknown token raises).
    Gated by
    ``test_schema_hygiene.py::test_renta_typed_binding_candidates_declare_substrate_enum_class``.
    """
    legal_refs: LegalRefs
    source_refs: SourceRefs
    source_citations: tuple[SourceCitation, ...] = Field(default_factory=tuple)
    # AEAT borrador pre-fill tier: the third, AEAT-live prefill tier, distinct
    # from the local relation prefill (`_relation_prefill`) and previous-filing
    # direct-carry (`_binding_prefill`) tiers. The three share only the word
    # "prefill" and must not be merged.
    aeat_prefilled: bool = False

    @field_validator("source", mode="before")
    @classmethod
    def _coerce_source(cls, value: object) -> object:
        """Hydrate the registry TOML's raw ``source`` string into its enum member.

        The authoring tree declares ``source`` as a plain string (``"profile"``,
        ``"ledger_iva_aggregation"``, ...). Under the strict model config a
        :class:`~core.BindingSourceKind` field requires the actual member,
        not its value, so the raw string from ``model_validate`` would be
        rejected. Coercing the known closed-set string to its member at the
        boundary keeps the TOML plain while preserving strict rejection of an
        unknown source (:class:`~core.BindingSourceKind` raises on an
        invalid value). This is the source-kind sibling of
        :meth:`~core.aggregation.BindingAggregation._coerce_op`.
        """
        if isinstance(value, str) and not isinstance(value, BindingSourceKind):
            return BindingSourceKind(value)
        return value

    @field_validator("selector", mode="before")
    @classmethod
    def _coerce_selector(cls, value: object, info: ValidationInfo) -> object:
        """Hydrate a raw selector mapping into its source-family model."""
        if isinstance(value, BaseModel):
            return value
        source = info.data.get("source") if isinstance(info.data, Mapping) else None
        binding_id = info.data.get("id") if isinstance(info.data, Mapping) else "<unknown>"

        from ._binding_selector_utils import _canonical_selector_key_hint
        from ._bindings import selector_model_for_source

        selector_model = selector_model_for_source(source)
        if selector_model is None:
            source_value = source.value if isinstance(source, BindingSourceKind) else str(source)
            raise RegistryValidationError(
                f"binding {binding_id!r} source {source_value!r} is not a registry binding source "
                "or has no selector model",
            )
        try:
            return selector_model.model_validate(value)
        except ValueError as exc:
            selector = {str(key): item for key, item in value.items()} if isinstance(value, Mapping) else {}
            hint = _canonical_selector_key_hint(selector, selector_model)
            raise RegistryValidationError(
                f"binding {binding_id!r} (source={source!r}) selector violates {selector_model.__name__}: {exc}{hint}",
            ) from exc

    @field_serializer("selector")
    def _serialize_selector(self, selector: object) -> dict[str, object]:
        """Serialise the concrete selector model as the authored selector mapping."""
        if isinstance(selector, BaseModel):
            return {
                str(key): value
                for key, value in selector.model_dump(
                    exclude={"source"},
                    exclude_none=True,
                    exclude_unset=True,
                ).items()
            }
        if isinstance(selector, Mapping):
            return {str(key): value for key, value in selector.items() if key != "source"}
        raise RegistryValidationError(
            f"binding {self.id!r} selector serializer requires a mapping or model, got {type(selector).__name__}",
        )

    @field_validator("typed_enum", mode="before")
    @classmethod
    def _coerce_typed_enum(cls, value: object) -> object:
        """Hydrate the registry TOML's raw ``typed_enum`` token into its member.

        The authoring tree declares ``typed_enum`` as a plain string (the name
        of the substrate enum class — ``"censo_event_kind"``, ``"CCAA"``,
        ``"EstimacionDirectaModalidad"``, ``"LegalEntityForm"``). Under the
        strict model config a :class:`~core.aggregation.BindingTypedEnumKind`
        field requires the actual member, not its value, so the raw string from
        ``model_validate`` would be rejected. Coercing the known closed-set token
        to its member at the boundary keeps the TOML plain while preserving
        strict rejection of an unknown annotation
        (:class:`~core.aggregation.BindingTypedEnumKind` raises on an invalid
        value). This is the ``typed_enum`` sibling of :meth:`_coerce_source`.
        """
        if isinstance(value, str) and not isinstance(value, BindingTypedEnumKind):
            return BindingTypedEnumKind(value)
        return value

    @model_validator(mode="after")
    def _validate_selector_shape(self) -> DataBindingDefinition:
        """Validate the hydrated selector against its source family's schema at construction.

        Dispatches on :attr:`source` through the discriminated-union selector
        table (``_BINDING_SELECTOR_REGISTRY`` in
        :mod:`~domain.calculations.registry._bindings`, surfaced by
        :func:`~domain.calculations.registry._bindings.selector_model_for_source`):
        the raw authoring mapping
        is hydrated into the per-family model and re-validated the moment the
        binding is constructed, promoting the
        selector-shape half of the former snapshot-build-only gate
        (:func:`~domain.calculations.registry._bindings.validate_binding_selector_shape`)
        up into the model.

        This strictly TIGHTENS validation: a misshapen selector (an unknown key,
        a retired key name, an out-of-set ``fact`` literal) now fails at
        construction rather than only when the snapshot-build section validator
        runs. The op/fact cross-invariants — which depend on the separate
        :attr:`aggregation` field — remain owned by ``validate_binding_selector_shape``
        at snapshot build, so a binding whose selector is well-shaped but whose
        op/fact pairing is wrong stays constructible (the build gate rejects it).
        A source absent from the selector registry is mesh-only or unregistered
        and is refused as a registry binding source.

        The accessor and validator are imported lazily because
        :mod:`~domain.calculations.registry._bindings`
        imports :class:`DataBindingDefinition` from this module; the lazy import
        breaks the cycle, matching the snapshot-build validators
        (``_validate_reference_sections``, ``_validate_registry_scope``). The
        shared
        :func:`~domain.calculations.registry._binding_selector_utils.selector_against_model`
        runs the
        SAME normalisation and emits the SAME diagnostic the build gate does, so
        a construction-time refusal and a build-time refusal carry identical
        text.
        """
        from ._binding_selector_utils import selector_against_model
        from ._bindings import selector_model_for_source

        selector_model = selector_model_for_source(self.source)
        if selector_model is None:
            raise RegistryValidationError(
                f"binding {self.id!r} source {self.source.value!r} is not a registry binding source "
                "or has no selector model",
            )
        diagnostics = selector_against_model(self, selector_model)
        if diagnostics:
            raise RegistryValidationError(diagnostics[0])
        return self


class FormulaDefinition(RegistryModel):
    id: FormulaId
    target_casilla_id: CasillaId
    expression: FormulaExpression
    rounding: RegistryRoundingCodeValue = None
    legal_refs: LegalRefs
    source_refs: SourceRefs
    source_citations: tuple[SourceCitation, ...] = Field(default_factory=tuple)


KNOWN_PROFILE_FLAG_ADVISORY_FIELDS: frozenset[str] = frozenset(
    {
        "art109_activity_income_withholding_ge_70pct",
        # ue_eee_status: TaxpayerProfile derived property (True iff
        # country_of_fiscal_residence is an EU/EEA code, post-Brexit). Consumed
        # by profile_flag_enabled directly and by
        # casilla_equals_implies_profile_flag for the M210 IRNR
        # tipo_renta="ue_residente" residence cross-check.
        "ue_eee_status",
    },
)


KNOWN_VERIFICATION_PREDICATE_OPERATORS: frozenset[str] = frozenset(
    {
        # advisory_when_positive(["casilla_id"]) — single-casilla positive
        # advisory: FIRES (ADVISORY shown) iff the one named casilla resolves
        # strictly > 0. The minimal "this box is populated, review the
        # downstream treatment" prompt for a value the calculation chain does
        # not yet fully model. ADVISORY-only (no BLOCKING_RULE branch). Authored
        # for the Modelo 100 anualidades por alimentos a favor de los hijos
        # (casilla 0527): the separate-escala treatment (LIRPF art. 64 / art. 75)
        # is applied without the statutory mínimo-por-descendientes gating in the
        # current cuota chain, so a payer declaring anualidades may be
        # under-taxed — surfaced as a non-blocking prompt to review the cuota,
        # per no-silent-under-declaration, pending the full separate-escala
        # modelling. Single casilla id, so it routes through the generic
        # _casilla_list_predicate_failures (arity 1) at registry build; see the
        # advisory_when_positive branch in _evaluate_advisory_predicate_fires.
        "advisory_when_positive",
        "advisory_when_ratio_ge",
        "all_nonzero",
        # at_most_one_positive(["id1", "id2", ...]) — mutual-exclusion
        # invariant: no more than one listed casilla may resolve strictly > 0.
        # As a BLOCKING_RULE it refuses overstatement shapes where alternative
        # calculation lanes are both populated. As an ADVISORY it fires on the
        # same contradiction without blocking. Authored for Modelo 202
        # modalidad art. 40.3 clave 32, whose official instructions say
        # "clave [18] (o clave [26])": B1 and B2 resultado-previo lanes are
        # alternatives, and the arithmetic formula can only add the two
        # zero-default lanes safely when at most one is positive.
        "at_most_one_positive",
        "any_nonzero",
        "cap_le_when_positive",
        # casilla_equals_implies_nonzero(["antecedent_casilla_id", "literal",
        # "consequent_casilla_id"]) — categorical-conditional material
        # implication: when the operator-entered raw text value of the named
        # TEXT antecedent casilla equals the literal, the named consequent
        # (Decimal) casilla must be non-zero. ADVISORY-only (no BLOCKING_RULE
        # branch is implemented), mirroring the existing equals (BLOCKING-only)
        # / advisory_when_ratio_ge (ADVISORY-only) asymmetry. Authored for the
        # M210 IRNR inmobiliaria branch (tipo_renta == "inmobiliaria" implies a
        # non-zero base_imponible), the one shape implies_nonzero cannot
        # express because its trigger is a categorical equality, not a
        # numeric antecedent. See the casilla_equals_implies_nonzero branch in
        # _evaluate_advisory_predicate_fires.
        "casilla_equals_implies_nonzero",
        # casilla_equals_implies_profile_flag(["antecedent_casilla_id", "literal",
        # "profile_field"]) — categorical-antecedent / profile-state-consequent
        # conditional advisory: FIRES (ADVISORY shown) when the operator-entered
        # raw text value of the named TEXT antecedent casilla equals the literal
        # AND the named boolean TaxpayerProfile field/property is False.
        # ADVISORY-only (no BLOCKING_RULE branch is implemented), sibling of
        # casilla_equals_implies_nonzero (whose consequent reads a Decimal
        # casilla) and profile_flag_enabled (whose antecedent is
        # unconditional). Authored for the M210 IRNR
        # tipo_renta="ue_residente" reduced-rate election (TRLIRNR Art 25.1.a):
        # the categorical rate choice was not cross-checked against the
        # declared country_of_fiscal_residence, so a non-EU/EEA filer could
        # self-declare the reduced 19% rate reserved for EU/EEE residents. See
        # the casilla_equals_implies_profile_flag branch in
        # _evaluate_advisory_predicate_fires.
        "casilla_equals_implies_profile_flag",
        # casilla_equals_implies_diverges(["antecedent_casilla_id", "literal",
        # "casilla_a_id", "casilla_b_id"]) — categorical-conditional
        # divergence check: when the operator-entered raw text value of the
        # named TEXT antecedent casilla equals the literal, the two named
        # (Decimal) casillas must not differ by more than one cent.
        # ADVISORY-only (no BLOCKING_RULE branch is implemented), sibling of
        # casilla_equals_implies_nonzero (consequent test "== 0") and
        # advisory_when_computed_diverges (no categorical gate). Authored for
        # the M131/M100 estimación-objetiva índice corrector de exceso (b.3),
        # incompatible per Orden HAC/1347/2024 Anexo II instrucción 2.3 with
        # the índices correctores especiales (a.2 autotaxi, a.4 transporte de
        # mercancías/mudanzas) for the activities that carry both. See the
        # casilla_equals_implies_diverges branch in
        # _evaluate_advisory_predicate_fires.
        "casilla_equals_implies_diverges",
        # deduccion_requires_adquisicion_before(["amount_casilla_id",
        # "acquisition_date_casilla_id", "construction_date_casilla_id",
        # "cutoff_iso"]) — eligibility-conditional advisory: FIRES (ADVISORY
        # shown) when the named amount (Decimal) casilla is strictly positive
        # (a deducción is claimed) AND neither eligibility signal is present —
        # the acquisition-date TEXT casilla holding a date strictly before the
        # cutoff, nor the construction-date TEXT casilla being non-empty. The
        # one no-silent-over-declaration shape the numeric/categorical operators
        # cannot express because its trigger combines a claimed amount with a
        # DATE-threshold eligibility test read from the operator-entered raw
        # text. ADVISORY-only (no BLOCKING_RULE branch). Authored for the
        # Modelo 100 deducción por inversión en vivienda habitual, whose
        # transitional régimen (LIRPF DT 18ª) admits only dwellings acquired
        # before 01-01-2013 (or pre-2013 construction). See the
        # deduccion_requires_adquisicion_before branch in
        # _evaluate_advisory_predicate_fires.
        "deduccion_requires_adquisicion_before",
        # advisory_when_computed_diverges(["declared_id", "computed_id"]) —
        # table-driven-engine-vs-operator-declared discrepancy: FIRES (ADVISORY
        # shown) when the named COMPUTED reference casilla resolves strictly >
        # 0 (the table-driven engine has coverage for the declared activity)
        # AND it differs from the named operator-declared casilla by more than
        # one cent. A zero computed casilla holds trivially (the engine has no
        # table coverage for the declared epígrafe/módulos — nothing to
        # compare against, so no advisory). ADVISORY-only (no BLOCKING_RULE
        # branch is implemented): the computed reference intentionally omits
        # fases 2ª/3ª correcting factors the taxpayer may legitimately claim,
        # so a discrepancy is a prompt to review, not a refusal. Authored for
        # the M131 estimación-objetiva módulos engine (casilla 01 "Suma de
        # rendimientos netos" vs the internal
        # modulos-rendimiento-neto-actividad reference), guarding against a
        # silent under-declaration. See the
        # advisory_when_computed_diverges branch in
        # _evaluate_advisory_predicate_fires.
        "advisory_when_computed_diverges",
        # equals(["lhs_id", "rhs_id"]) — consistency invariant: the two named
        # casillas must hold the same value. Authored for the M303 official
        # Diseño box projections (Stage 2): each numbered box copies a semantic
        # source, so box == source must hold for VERIFICADO_COMPLETO. The
        # projection cannot drift within one evaluation; the predicate's value is
        # catching a future mis-edit (a box re-flipped to manual, or a projection
        # pointed at the wrong source). See the equals branch in
        # _evaluate_predicate_expression.
        "equals",
        "implies_any_nonzero",
        "implies_nonzero",
        "profile_field_required",
        # profile_flag_enabled("profile_field_name") — profile-state advisory:
        # FIRES (ADVISORY shown) iff the named boolean TaxpayerProfile field is
        # true. ADVISORY-only. Authored for the M130 Art. 109 activity-income
        # coverage fact, where the legal 70% test is declared in the
        # profile/deadline layer, not inferred from a casilla-amount ratio.
        "profile_flag_enabled",
        # roll_forward_balances(["closing_id", "opening_id", "applied_id",
        # "base_id"]) — carry-forward stock continuity: the closing balance must
        # reconcile to opening − applied + max(0, −base) within a one-cent
        # tolerance. The arithmetic continuity primitive the predicate language
        # lacked; authored for the Modelo 200 BIN total-pendiente roll-forward
        # (00671 = 00670 − DP200014:00547 + max(0, −DP200014:00552)) and general
        # to any "stock = prior stock − consumed + newly-generated-from-a-signed-
        # base" carry (BIN, pending credits, recargo carryforward). As a
        # BLOCKING_RULE it holds when the balance reconciles; as an ADVISORY it
        # fires when it does not. See the roll_forward_balances branch in
        # _evaluate_predicate_expression / _evaluate_advisory_predicate_fires.
        "roll_forward_balances",
    },
)


class VerificationPredicateDefinition(RegistryModel):
    """A cross-casilla invariant that must hold for VERIFICADO_COMPLETO to be granted.

    Layer 2 of the hybrid verification strategy.  Layer 1 handles
    single-casilla required gates via ``CasillaDefinition.required``; this
    class handles multi-casilla structural invariants (e.g. ``if ingresos
    is non-zero then rendimiento neto must also be present``).

    ``expression`` uses a minimal predicate DSL:

    - ``advisory_when_positive(["casilla_id"])`` — single-casilla positive
      advisory: FIRES (ADVISORY shown) iff the one named casilla value is
      strictly ``> 0``. A zero or absent value holds trivially (no advisory).
      ADVISORY-only: no ``BLOCKING_RULE`` branch is implemented (a positive box
      is not itself an error — the advisory only prompts an operator review).
      Authored for the Modelo 100 anualidades por alimentos a favor de los
      hijos (casilla 0527), whose separate-escala treatment (LIRPF art. 64 for
      the state scale, art. 75 for the autonomic scale) is applied in the
      current cuota chain without the statutory mínimo-por-descendientes
      gating, so a payer declaring anualidades may be under-taxed; the advisory
      surfaces a non-blocking prompt to review the cuota pending the full
      separate-escala modelling, per no-silent-under-declaration. Routes through
      the generic single-casilla-list validation (exact arity 1) at registry
      build. See the ``advisory_when_positive`` branch in
      ``_evaluate_advisory_predicate_fires``.
    - ``all_nonzero(["id1", "id2", ...])`` — every listed casilla value must
      be non-zero (i.e. the filing invariant requires them all to be present
      and non-zero simultaneously).
    - ``any_nonzero(["id1", "id2", ...])`` — at least one listed casilla
      value must be non-zero.
    - ``at_most_one_positive(["id1", "id2", ...])`` — no more than one
      listed casilla may be strictly positive. Missing values read as zero.
      Authored for alternative result lanes such as Modelo 202 art. 40.3
      claves 18/26, where the downstream formula uses both zero-default
      lanes but the official instruction permits only one positive lane.
    - ``cap_le_when_positive(["limited_id", "ceiling_id"])`` — when the
      ceiling casilla is strictly positive, the limited casilla MUST NOT
      exceed the ceiling, enforcing AEAT cap rules like Modelo 131 C11 ≤ C10
      and Modelo 130 C15 ≤ C14 ("en ningún caso podrá
      figurar... un importe superior a la cantidad positiva consignada").
      Predicate holds when ceiling ≤ 0; the cap applies only when the
      operator's gross liability is positive.
    - ``implies_nonzero(["antecedent_id", "consequent_id"])`` — material
      implication with a strictly-positive antecedent test: predicate
      holds iff ``casilla_values[antecedent] <= 0`` OR
      ``casilla_values[consequent] != 0``. Authored for AEAT cuota-mínima
      invariants of the shape "cuando C01 sea positivo, C07 debe ser
      distinta de cero" (M131 EO cuota mínima, M130/M303 régimen
      simplificado analogues). The antecedent is strictly-positive rather
      than non-zero to mirror the regulatory phrasing; a casilla with a
      negative value does not trigger the implication. A missing
      consequent value evaluates to ``Decimal(0)`` and therefore
      violates the predicate when the antecedent is positive.
    - ``implies_any_nonzero(["antecedent_id", "c1_id", "c2_id", ...])`` —
      the N-consequent generalisation of ``implies_nonzero``: predicate
      holds iff ``casilla_values[antecedent] <= 0`` OR **at least one**
      listed consequent is non-zero. Authored for the Modelo 303
      official-Diseño contradiction where a computed total
      (``iva.cuota-devengada-total``, ``iva.cuota-deducible-total``) is
      strictly positive but **every** constituent official numbered box
      (the dr303 base/cuota tranche cells the operator transcribes to the
      AEAT sede) is still zero — a silent under-declaration the verify
      gate would otherwise grant with zero findings. ADVISORY (the
      official numbered boxes are an operator-entered layer the calculate
      path does not auto-populate, so the contradiction is surfaced as a
      non-blocking alert rather than a refusal). The first consequent
      slot onward is the constituent set; a single consequent reduces to
      ``implies_nonzero``.
    - ``profile_field_required("profile_field_name", "applicability_filter")``
      — profile-state-aware conditional non-zero requirement. Returns
      ``True`` (predicate holds) when the named ``applicability_filter``
      evaluates ``False`` against the TaxpayerProfile, OR when the named
      profile field is present and non-empty. Returns ``False``
      (predicate violated) only when the applicability filter activates
      AND the profile field is ``None`` / empty. A sibling of
      ``implies_nonzero`` — the conditional non-zero requirement is the
      same semantic shape, but the gating signal is profile state (e.g.
      fiscal_residency, ue_eee_status) rather than another casilla value.
      First use site: M210 representante-fiscal gate (TRLIRNR Art 10).
    - ``profile_flag_enabled("profile_field_name")`` — profile-state
      advisory: predicate FIRES (ADVISORY shown) iff the named boolean
      TaxpayerProfile field is true. ADVISORY-only. Authored for the Modelo
      130 Art. 109 activity-income coverage profile fact: the legal 70%
      threshold is an income-coverage/profile fact, not a ratio between
      retenciones amount and gross income casillas.
    - ``casilla_equals_implies_nonzero(["antecedent_casilla_id", "literal",
      "consequent_casilla_id"])`` — categorical-conditional material
      implication: predicate FIRES (ADVISORY shown) iff the operator-entered
      raw text value of the named antecedent (TEXT) casilla equals the
      literal AND the named consequent (Decimal) casilla is zero. A missing
      or differing antecedent value holds trivially (no advisory), same
      convention as the numeric-antecedent operators. ADVISORY-only: no
      ``BLOCKING_RULE`` branch is implemented, mirroring the existing
      ``equals`` (BLOCKING-only) / ``advisory_when_ratio_ge`` (ADVISORY-only)
      asymmetry. Authored for the M210 IRNR inmobiliaria branch, the one
      shape ``implies_nonzero`` cannot express because its trigger is a
      categorical equality (``tipo_renta == "inmobiliaria"``) rather than
      a numeric antecedent, guarding against a silent under-declaration.
    - ``deduccion_requires_adquisicion_before(["amount_casilla_id",
      "acquisition_date_casilla_id", "construction_date_casilla_id",
      "cutoff_iso"])`` — eligibility-conditional advisory: FIRES (ADVISORY
      shown) iff the named amount (Decimal) casilla is strictly positive (a
      deducción is claimed) AND no pre-cutoff eligibility signal is recorded,
      i.e. the acquisition-date TEXT casilla does NOT hold a date strictly
      before ``cutoff_iso`` AND the construction-date TEXT casilla is empty. A
      claimed amount with a pre-cutoff acquisition date, a non-empty
      construction date, or a zero/absent amount holds trivially (no advisory).
      ADVISORY-only: no ``BLOCKING_RULE`` branch is implemented, mirroring the
      ``casilla_equals_implies_nonzero`` / ``advisory_when_ratio_ge``
      ADVISORY-only convention. Authored for the Modelo 100 deducción por
      inversión en vivienda habitual, whose transitional régimen (LIRPF DT 18ª)
      admits only dwellings acquired before 01-01-2013 (or pre-2013
      construction); a post-2013 acquirer claiming the abolished deducción
      would silently over-declare the deducción (under-declare tax), the
      no-silent-under-declaration shape neither ``implies_nonzero`` (numeric
      antecedent) nor ``casilla_equals_implies_nonzero`` (categorical text
      equality) can express because its trigger is a DATE threshold.
    - ``casilla_equals_implies_diverges(["antecedent_casilla_id", "literal",
      "casilla_a_id", "casilla_b_id"])`` — categorical-conditional divergence
      check: predicate FIRES (ADVISORY shown) iff the operator-entered raw
      text value of the named antecedent (TEXT) casilla equals the literal
      AND the two named (Decimal) casillas differ by more than one cent. A
      missing or differing antecedent value, or two casillas within a cent of
      each other, holds trivially (no advisory). Sibling of
      ``casilla_equals_implies_nonzero`` (that operator's consequent test is
      "== 0"; this operator's is "casilla_a != casilla_b"). ADVISORY-only: no
      ``BLOCKING_RULE`` branch is implemented, mirroring the
      ``casilla_equals_implies_nonzero`` / ``advisory_when_computed_diverges``
      ADVISORY-only convention. Authored for the M131/M100 estimación-objetiva
      índice corrector de exceso (b.3): Orden HAC/1347/2024 Anexo II
      instrucción 2.3 declares the índice corrector de exceso INCOMPATIBLE
      with the índices correctores especiales (a.2 autotaxi, a.4 transporte de
      mercancías/mudanzas) for the activities that carry both — a
      no-silent-under-declaration shape neither ``implies_nonzero`` (numeric
      antecedent) nor ``advisory_when_computed_diverges`` (no categorical
      gate) can express because the trigger combines a categorical epígrafe
      equality with a Decimal-pair divergence.
    """

    predicate_id: str = Field(min_length=1, max_length=128)
    legal_refs: LegalRefs
    expression: str = Field(min_length=1, max_length=512)
    finding_kind: Literal["BLOCKING_RULE", "ADVISORY"] = "BLOCKING_RULE"


class ModeloRevision(RegistryModel):
    """A single versioned form layout and calculation ruleset for one modelo.

    The ``orden_aplicabilidad`` field names the legal-catalogue
    :class:`LegalReference` id(s) of the ordenes ministeriales that approve or
    amend this revision's form for its declared applicability window
    (e.g. ``["orden-hac-277-2026:art-3"]`` for M100 ejercicio 2025).

    The field is mandatory at validation time: every revision must cite the
    Ordenes that approve or amend the form for its applicability window.

    The governance stamp — ``engineered_by``, ``review_status``, ``reviewed_by``,
    ``reviewed_at`` — is the revision's *declared* provenance. Authorship and
    signoff are facts about the people and agents who built the revision, so
    nothing in the tree can derive them. The whole block is optional and its
    absence reads as :attr:`RevisionReviewStatus.PENDING_REVIEW`: an unstamped
    revision is a visible unreviewed backlog entry, never a silent pass.
    """

    id: RevisionId
    label: str | None = None
    valid_from: date
    valid_to: date | None = None
    period_selector: PeriodSelector
    legal_refs: LegalRefs
    source_refs: SourceRefs
    # Required by validate_orden_aplicabilidad; kept default-empty so the
    # validator can report a grounded registry failure instead of a parse error.
    orden_aplicabilidad: tuple[LegalRefId, ...] = ()
    parameters: tuple[ParameterDefinition, ...] = ()
    casillas: tuple[CasillaDefinition, ...] = ()
    formulas: tuple[FormulaDefinition, ...] = ()
    bindings: tuple[DataBindingDefinition, ...] = ()
    algorithm_providers: tuple[AlgorithmProviderDefinition, ...] = ()
    algorithm_bindings: tuple[AlgorithmBindingDefinition, ...] = ()
    relations: tuple[RelationDefinition, ...] = ()
    export_layouts: tuple[ExportLayoutDefinition, ...] = ()
    extraction_profiles: tuple[ExtractionProfileDefinition, ...] = ()
    live_cross_references: tuple[LiveCrossReferenceDecision, ...] = ()
    workbook_parity_refs: tuple[WorkbookParityReference, ...] = ()
    verification_expectations: tuple[VerificationExpectationDefinition, ...] = ()
    application_links: tuple[ApplicationLinkDefinition, ...] = ()
    deadline_windows: tuple[DeadlineWindowDefinition, ...] = ()
    filing_schedules: tuple[ModeloScheduleDefinition, ...] = ()
    support_removal_decisions: tuple[SupportRemovalDecisionDefinition, ...] = ()
    constructs: tuple[ConstructDefinition, ...] = ()
    dependency_classifications: tuple[DependencyClassificationDefinition, ...] = ()
    completeness_manifest: CalculationCompletenessManifest | None = None
    verification_predicates: tuple[VerificationPredicateDefinition, ...] = ()
    continuidad_validation: Literal["advisory", "strict"] = "advisory"
    casilla_continuidad_evolutions: tuple[CasillaContinuidadEvolutionDefinition, ...] = ()
    engineered_by: str | None = None
    review_status: RevisionReviewStatusField = RevisionReviewStatus.PENDING_REVIEW
    reviewed_by: str | None = None
    reviewed_at: date | None = None

    @field_validator("engineered_by", "reviewed_by")
    @classmethod
    def _attribution_names_somebody(cls, value: str | None, info: ValidationInfo) -> str | None:
        """Refuse an attribution that is declared but names nobody.

        A length constraint counts whitespace, so ``reviewed_by = "   "`` would
        satisfy one while leaving the claim exactly as unfalsifiable as the
        omission :meth:`_validate_governance_stamp` refuses — and a blank
        reviewer renders in a conformance report as a signed-off revision.
        Omission is the honest way to say nobody reviewed it.
        """
        if value is not None and not value.strip():
            raise RegistryValidationError(
                f"revision governance field {info.field_name!r} must name somebody; "
                f"omit the field instead of declaring it blank",
            )
        return value

    @field_validator("reviewed_at")
    @classmethod
    def _reviewed_at_is_within_the_signoff_horizon(cls, value: date | None) -> date | None:
        """Refuse a signoff date no auditor could ever check.

        See :data:`REVISION_REVIEW_DATE_CEILING` for why the horizon is a fixed
        calendar date rather than a reading of the local clock.
        """
        if value is not None and value >= REVISION_REVIEW_DATE_CEILING:
            raise RegistryValidationError(
                f"revision governance field 'reviewed_at' is {value.isoformat()}, beyond the signoff horizon "
                f"{REVISION_REVIEW_DATE_CEILING.isoformat()}; a review dated there records no signoff anyone can check",
            )
        return value

    @model_validator(mode="after")
    def _validate_window(self) -> ModeloRevision:
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise RegistryValidationError("revision valid_to must be on or after valid_from")
        return self

    @model_validator(mode="after")
    def _validate_governance_stamp(self) -> ModeloRevision:
        """Bind the reviewer identity to the claim that a review happened.

        A reviewed status without a reviewer or a date is an unfalsifiable
        claim, and a reviewer recorded against ``pending_review`` is a review
        the status denies. Both directions refuse so the stamp cannot say one
        thing on the status axis and another on the attribution axis.
        """
        companions = {"reviewed_by": self.reviewed_by, "reviewed_at": self.reviewed_at}
        if self.review_status in REVIEWED_REVISION_REVIEW_STATUSES:
            missing = sorted(name for name, value in companions.items() if value is None)
            if missing:
                raise RegistryValidationError(
                    f"revision {self.id!r} declares review_status={self.review_status.value!r} but omits "
                    f"{missing!r}; a reviewed revision must name its reviewer and the date of review",
                )
            return self
        present = sorted(name for name, value in companions.items() if value is not None)
        if present:
            raise RegistryValidationError(
                f"revision {self.id!r} declares review_status="
                f"{RevisionReviewStatus.PENDING_REVIEW.value!r} but also declares {present!r}; "
                f"record the review by advancing review_status, or drop the reviewer fields",
            )
        return self


REVISION_REVIEW_DATE_CEILING: date = date(2100, 1, 1)
"""Exclusive upper bound on a governance stamp's ``reviewed_at`` signoff date.

A signoff dated beyond any living reviewer's horizon is not a signoff: it is a
sentinel or a template artefact wearing a date, and it renders in a conformance
report as an operator countersignature. The bound refuses that class.

The ceiling is a fixed calendar date rather than a reading of the local clock,
deliberately. The registry is the authority behind every calculation the
application performs, so a validation rule that consults the wall clock makes
the shipped tree's validity a property of the machine that loads it: a
container whose clock is behind reality, or a stamp written the other side of a
timezone boundary, would refuse the whole registry and take the product with
it. A false refusal here costs incomparably more than a missed absurd date, and
a fixed ceiling is identical on every machine in every year.

The bound is therefore an absurdity floor, not a freshness check: it catches the
sentinel (``3999-12-31``, ``9999-12-31``) that no auditor could ever check, and
deliberately does not catch a near-future typo. Freshness is a governance
question for the dev-side conformance audit, where consulting the clock costs
one contributor a re-run rather than bricking the registry.
"""


REVISION_GOVERNANCE_FIELDS: frozenset[str] = frozenset(
    {"engineered_by", "review_status", "reviewed_by", "reviewed_at"},
)
"""The :class:`ModeloRevision` fields that make up the declared governance stamp.

The stamp is an authorship and signoff claim about a whole revision, so it must
be readable in one place: the revision's own ``revision.toml`` manifest. The
loader refuses these keys anywhere else in the fragment tree. Named here beside
the field declarations so a rename is caught at one site.
"""


class ModeloDefinition(RegistryModel):
    id: ModeloId
    title: str
    official_name: str
    tax_domain: Annotated[TaxDomain, BeforeValidator(lambda v: TaxDomain(v) if isinstance(v, str) else v)]
    cadence: Literal["monthly", "quarterly", "annual", "ad_hoc", "profile_based"]
    jurisdiction: Literal["ES-AEAT"]
    calculation_class: CalculationClass = "filing"
    output_sensitivity: SensitivityClassField = SensitivityClass.FINANCIAL
    capabilities: Annotated[frozenset[ModeloFilingCapability], BeforeValidator(frozenset)] = frozenset()
    legal_refs: LegalRefs
    source_refs: SourceRefs
    revisions: Mapping[RevisionId, ModeloRevision]

    def has_capability(self, name: ModeloFilingCapability) -> bool:
        """Return whether this modelo declares the given capability."""
        return name in self.capabilities

    @model_validator(mode="after")
    def _validate_revisions(self) -> ModeloDefinition:
        if not self.revisions:
            raise RegistryValidationError(f"modelo {self.id!r} must declare at least one revision")
        for key, revision in self.revisions.items():
            if key != revision.id:
                raise RegistryValidationError(f"revision key {key!r} does not match revision id {revision.id!r}")
        return self


class RegistryCatalogues(RegistryModel):
    legal: Mapping[LegalRefId, LegalReference]
    sources: Mapping[SourceRefId, SourceReference]
    parameters: Mapping[str, LegalParameter] = Field(default_factory=dict)
    convenio: ConvenioAuthority = Field(default_factory=ConvenioAuthority.empty)


@dataclass(frozen=True, slots=True)
class RegistryVerificationPolicy:
    """Folded verification policy across a snapshot's verification expectations.

    Owns the registry-grounded projection (union of computed casilla ids, the
    union of reconcile-when-present casilla ids, the strictest tolerance, the
    strictest coverage floor) so the application verification surface consumes
    it rather than re-deriving the fold.

    ``computed_casilla_ids`` are the coverage-gated reconciliation targets: a
    filing that fails to reconcile them below ``min_coverage`` is NEEDS_REVIEW.
    ``reconcile_when_present_casilla_ids`` are value-reconciled when the filing
    prints them (a filed-vs-computed divergence surfaces a discrepancy) but are
    excluded from the coverage denominator, so enrolling a situational casilla
    can never lower coverage and flip a legitimate filing's verdict.

    ``externally_grounded_casilla_ids`` is the third, orthogonal axis: of the
    casillas a filing reconciles (``computed_casilla_ids`` or
    ``reconcile_when_present_casilla_ids``), which have an AEAT-authoritative
    independent oracle expected value backing their reconciliation, rather than
    only the app's own engine.
    """

    expectation_ids: tuple[VerificationExpectationId, ...]
    computed_casilla_ids: frozenset[CasillaId]
    reconcile_when_present_casilla_ids: frozenset[CasillaId]
    externally_grounded_casilla_ids: frozenset[CasillaId]
    tolerance: Decimal
    min_coverage: Decimal


class RegistrySnapshot(RegistryModel):
    modelo: ModeloDefinition
    revision: ModeloRevision
    filing_period: Period | None = None
    filing_year: int = Field(ge=2000, le=2099)
    # Accepts normal period codes and declared event-period names; upstream
    # PeriodSelector + ModeloScheduleDefinition constrain the token set.
    period: str = Field(min_length=1, max_length=32)
    legal: Mapping[LegalRefId, LegalReference]
    sources: Mapping[SourceRefId, SourceReference]
    extraction_profiles: Mapping[ExtractionProfileId, ExtractionProfileDefinition]
    live_cross_references: Mapping[CrossReferenceId, LiveCrossReferenceDecision]
    workbook_parity_refs: Mapping[WorkbookParityRefId, WorkbookParityReference]
    verification_expectations: Mapping[VerificationExpectationId, VerificationExpectationDefinition]
    application_links: Mapping[ApplicationLinkId, ApplicationLinkDefinition]
    deadline_windows: Mapping[DeadlineWindowId, DeadlineWindowDefinition]
    filing_schedules: Mapping[str, ModeloScheduleDefinition]
    support_removal_decisions: Mapping[SupportRemovalDecisionId, SupportRemovalDecisionDefinition]
    constructs: Mapping[ConstructId, ConstructDefinition]
    dependency_classifications: Mapping[DependencyClassificationId, DependencyClassificationDefinition]
    convenio: ConvenioAuthority = Field(default_factory=ConvenioAuthority.empty)

    @model_validator(mode="after")
    def _validate_filing_period_consistency(self) -> RegistrySnapshot:
        if self.filing_period is None:
            return self
        if self.filing_period.filing_year != self.filing_year:
            raise RegistryValidationError("snapshot filing_period year must match filing_year")
        if self.filing_period.registry_token != self.period:
            raise RegistryValidationError("snapshot filing_period code must match period")
        return self

    def verification_policy(self) -> RegistryVerificationPolicy:
        """Fold this snapshot's verification expectations into one policy.

        Returns the registry-grounded :class:`RegistryVerificationPolicy` (union
        of computed casilla ids, strictest tolerance, strictest coverage floor).

        Raises:
            RegistryValidationError: When the snapshot declares no verification
                expectations.
        """
        expectations = tuple(self.verification_expectations.values())
        if not expectations:
            raise RegistryValidationError("registry verification requires verification expectations")
        return RegistryVerificationPolicy(
            expectation_ids=tuple(expectation.id for expectation in expectations),
            computed_casilla_ids=frozenset(
                casilla_id for expectation in expectations for casilla_id in expectation.computed_casilla_ids
            ),
            reconcile_when_present_casilla_ids=frozenset(
                casilla_id
                for expectation in expectations
                for casilla_id in expectation.reconcile_when_present_casilla_ids
            ),
            externally_grounded_casilla_ids=frozenset(
                casilla_id for expectation in expectations for casilla_id in expectation.externally_grounded_casilla_ids
            ),
            tolerance=min(expectation.tolerance for expectation in expectations),
            min_coverage=max(expectation.min_coverage for expectation in expectations),
        )


def filing_period_from_scope(filing_year: int, period: str) -> Period | None:
    """Return a core :class:`Period` when the registry token is a real filing-period code."""
    try:
        return Period.from_year_and_code(filing_year, period)
    except ValueError:
        return None
