"""Strict schema authority for AEAT registry definitions.

Each modelo revision carries an ``output_sensitivity`` field typed as
:class:`SensitivityClass` that governs the encryption tier applied to
generated output envelopes.
"""

from __future__ import annotations

from collections.abc import Mapping
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

from ....core import Period, PeriodKind, RevisionReviewStatus, TaxDomain
from ....core.aggregation import BindingAggregation, BindingSourceKind, BindingTypedEnumKind
from ....core.classification import SensitivityClass
from .._export_field_kind import CasillaFieldKind, CasillaFieldKindValue
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
from ._period_selector_match import selector_period_matches_request
from ._schema_governance import (
    validate_attribution_names_somebody,
    validate_governance_stamp_coherence,
    validate_reviewed_at_within_horizon,
)
from ._schema_input_kind import InputKind, InputKindValue
from ._schema_rounding import RegistryRoundingCode as RegistryRoundingCode
from ._schema_rounding import RegistryRoundingCodeValue
from ._schema_scalars import (
    BicString as _BicString,
)
from ._schema_scalars import (
    BindingSelector as _BindingSelector,
)
from ._schema_scalars import (
    BindingSelectorMap as _BindingSelectorMap,
)
from ._schema_scalars import (
    BindingSelectorValue as _BindingSelectorValue,
)
from ._schema_scalars import (
    CalendarDate as _CalendarDate,
)
from ._schema_scalars import (
    CCAACode as _CCAACode,
)
from ._schema_scalars import (
    CountryCode as _CountryCode,
)
from ._schema_scalars import (
    DecimalValue as _DecimalValue,
)
from ._schema_scalars import (
    IbanString as _IbanString,
)
from ._schema_scalars import (
    ModeloYear as _ModeloYear,
)
from ._schema_scalars import (
    MunicipalityCode as _MunicipalityCode,
)
from ._schema_scalars import (
    NifIvaString as _NifIvaString,
)
from ._schema_scalars import (
    NifString as _NifString,
)
from ._schema_scalars import (
    PeriodCode as _PeriodCode,
)
from ._schema_scalars import (
    PersonOrEntityName as _PersonOrEntityName,
)
from ._schema_scalars import (
    PostalCode as _PostalCode,
)
from ._schema_scalars import (
    ProvinceCode as _ProvinceCode,
)
from ._schema_scalars import (
    WorkbookCellRefStr as _WorkbookCellRefStr,
)
from ._schema_scalars import (
    coerce_modelo_year as _coerce_modelo_year_impl,
)
from ._schema_scalars import (
    validate_country_code as _validate_country_code_impl,
)
from ._schema_scalars import (
    validate_iban_string as _validate_iban_string_impl,
)
from ._schema_scalars import (
    validate_nif_string as _validate_nif_string_impl,
)
from ._schema_scalars import (
    validate_period_code as _validate_period_code_impl,
)
from ._schema_verification import (
    RegistryVerificationPolicy,
    VerificationExpectationDefinition,
    VerificationPredicateDefinition,
)
from ._toml_helpers import as_toml_table as _as_toml_table

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
    "OneBasedExportOffset",
    "ParameterDefinition",
    "PeriodSelector",
    "ProfilePredicateDefinition",
    "RegistryCatalogues",
    "RegistryExternalLink",
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
    GOVERNANCE_STAMP,
    MANIFEST_ONLY,
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
    governance_stamp_fields,
    manifest_only_fields,
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
    RegistryExternalLink,
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
    OneBasedExportOffset,
    RelationDefinition,
    RelationPeriodAlignment,
    RelationRevisionSelector,
)

# Scalar and annotated value types live in ``_schema_scalars``; retaining these
# assignments keeps the historical ``_schema`` import surface authoritative.
DecimalValue = _DecimalValue
NifString = _NifString
ModeloYear = _ModeloYear
PeriodCode = _PeriodCode
CountryCode = _CountryCode
IbanString = _IbanString
PersonOrEntityName = _PersonOrEntityName
NifIvaString = _NifIvaString
CCAACode = _CCAACode
ProvinceCode = _ProvinceCode
PostalCode = _PostalCode
MunicipalityCode = _MunicipalityCode
BicString = _BicString
CalendarDate = _CalendarDate
WorkbookCellRefStr = _WorkbookCellRefStr
BindingSelectorValue = _BindingSelectorValue
BindingSelectorMap = _BindingSelectorMap
BindingSelector = _BindingSelector
_coerce_modelo_year = _coerce_modelo_year_impl
_validate_country_code = _validate_country_code_impl
_validate_iban_string = _validate_iban_string_impl
_validate_nif_string = _validate_nif_string_impl
_validate_period_code = _validate_period_code_impl


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


_SCHEDULE_PERIOD_KINDS: dict[str, frozenset[PeriodKind]] = {
    "monthly": frozenset({PeriodKind.MONTHLY}),
    "quarterly": frozenset({PeriodKind.QUARTERLY, PeriodKind.INSTALMENT, PeriodKind.EXTENDED}),
    "annual": frozenset({PeriodKind.ANNUAL}),
    # Event/administrative tokens are EXTENDED in the canonical classifier.
    # Modelo 840 deliberately uses 0A as the exercise coordinate for an ad-hoc
    # IAE filing, so ANNUAL is also an admitted token shape for this schedule
    # contract; legal/source grounding still owns whether that declaration is
    # correct for a particular modelo.
    "ad_hoc": frozenset({PeriodKind.EXTENDED, PeriodKind.ANNUAL}),
}


def _filing_schedule_period_kind_mismatches(period_kind: str, periods: tuple[str, ...]) -> tuple[str, ...]:
    """Return schedule tokens whose canonical cadence contradicts ``period_kind``."""
    accepted = _SCHEDULE_PERIOD_KINDS[period_kind]
    mismatches: list[str] = []
    for token in periods:
        try:
            canonical_kind = Period.from_year_and_code(2000, token).kind
        except ValueError:
            mismatches.append(token)
            continue
        if canonical_kind not in accepted:
            mismatches.append(token)
    return tuple(mismatches)


filing_schedule_period_kind_mismatches = _filing_schedule_period_kind_mismatches
"""Public facade for the filing-schedule period-kind consistency predicate."""


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
        mismatches = _filing_schedule_period_kind_mismatches(self.period_kind, self.periods)
        if mismatches:
            raise RegistryValidationError(
                f"filing schedule {self.id!r} period_kind {self.period_kind!r} contradicts periods {mismatches!r}",
            )
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
        source: object = info.data.get("source")
        binding_id: object = info.data.get("id", "<unknown>")
        from ._binding_selector_utils import canonical_selector_key_hint
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
            selector = _as_toml_table(value) or {}
            hint = canonical_selector_key_hint(selector, selector_model)
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


class ModeloRevision(RegistryModel):
    """A single versioned form layout and calculation ruleset for one modelo.

    The ``orden_aplicabilidad`` field names the legal-catalogue
    :class:`LegalReference` id(s) of the ordenes ministeriales that approve or
    amend this revision's form for its declared applicability window
    (e.g. ``["orden-hac-277-2026:art-3"]`` for M100 ejercicio 2025).

    The field is mandatory at validation time: every revision must cite the
    Ordenes that approve or amend the form for its applicability window.

    The governance stamp — ``engineered_by``, ``review_status``, ``reviewed_by``,
    ``reviewed_at`` — is the revision's *declared* provenance, optional and
    fail-closed to :attr:`RevisionReviewStatus.PENDING_REVIEW` on absence. Its
    rules and the reasoning behind them live in :mod:`.._schema_governance`,
    which the validators below delegate to.
    """

    id: RevisionId
    label: str | None = None
    valid_from: date
    valid_to: Annotated[date | None, MANIFEST_ONLY] = None
    period_selector: PeriodSelector
    legal_refs: Annotated[LegalRefs, MANIFEST_ONLY]
    source_refs: SourceRefs
    # Required by validate_orden_aplicabilidad; kept default-empty so the
    # validator can report a grounded registry failure instead of a parse error.
    orden_aplicabilidad: Annotated[tuple[LegalRefId, ...], MANIFEST_ONLY] = ()
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
    engineered_by: Annotated[str | None, GOVERNANCE_STAMP] = None
    review_status: Annotated[RevisionReviewStatusField, GOVERNANCE_STAMP] = RevisionReviewStatus.PENDING_REVIEW
    reviewed_by: Annotated[str | None, GOVERNANCE_STAMP] = None
    reviewed_at: Annotated[date | None, GOVERNANCE_STAMP] = None

    @field_validator("engineered_by", "reviewed_by")
    @classmethod
    def _attribution_names_somebody(cls, value: str | None, info: ValidationInfo) -> str | None:
        """Refuse an attribution that is declared but names nobody."""
        return validate_attribution_names_somebody(value, field_name=info.field_name)

    @field_validator("reviewed_at")
    @classmethod
    def _reviewed_at_is_within_the_signoff_horizon(cls, value: date | None) -> date | None:
        """Refuse a signoff date no auditor could ever check."""
        return validate_reviewed_at_within_horizon(value)

    @model_validator(mode="after")
    def _validate_window(self) -> ModeloRevision:
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise RegistryValidationError("revision valid_to must be on or after valid_from")
        return self

    @model_validator(mode="after")
    def _validate_governance_stamp(self) -> ModeloRevision:
        """Bind the reviewer identity to the claim that a review happened."""
        validate_governance_stamp_coherence(
            revision_id=self.id,
            review_status=self.review_status,
            reviewed_by=self.reviewed_by,
            reviewed_at=self.reviewed_at,
        )
        return self


REVISION_GOVERNANCE_FIELDS: frozenset[str] = governance_stamp_fields(ModeloRevision)
"""The :class:`ModeloRevision` fields that make up the declared governance stamp.

Derived from the :data:`GOVERNANCE_STAMP` marker on the field declarations rather
than hand-listed, and the sole input to the loader's placement refusal. See
:mod:`.._schema_governance` for why the stamp must be readable in the manifest
alone and why marking the field is the whole of enrolling it.

This set is the stamp VOCABULARY, narrower than
:data:`REVISION_MANIFEST_ONLY_FIELDS`: it is what the conformance tooling reads
as declared provenance and what the stamp writer emits, so a field pinned to
the manifest for legal-grounding reasons must not appear here.
"""

REVISION_MANIFEST_ONLY_FIELDS: frozenset[str] = manifest_only_fields(ModeloRevision)
"""Every :class:`ModeloRevision` field that may be declared only in ``revision.toml``.

A superset of :data:`REVISION_GOVERNANCE_FIELDS` by construction, since
:class:`GovernanceStampMarker` is a :class:`ManifestOnlyMarker`. Beyond the
governance stamp it carries the legally load-bearing scalars ``legal_refs``,
``orden_aplicabilidad`` and ``valid_to``, which share the stamp's readability
hazard and raise its stakes; :mod:`.._schema_governance` records how a deep
fragment can otherwise supply a revision's legal grounding while
``revision.toml`` reads as though it did not.
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

    @staticmethod
    def _validate_identifier_keyed_map(field_name: str, values: Mapping[str, object]) -> None:
        """Require every snapshot map key to name the payload stored beneath it."""
        for key, payload in values.items():
            payload_id = getattr(payload, "id", None)
            if not isinstance(payload_id, str):
                raise RegistryValidationError(
                    f"snapshot {field_name} payload beneath key {key!r} has no string id",
                )
            if key != payload_id:
                raise RegistryValidationError(
                    f"snapshot {field_name} key {key!r} does not match payload id {payload_id!r}",
                )

    @model_validator(mode="after")
    def _validate_identifier_keyed_maps(self) -> RegistrySnapshot:
        """Keep all nested lookup identities aligned with their typed payloads."""
        self._validate_identifier_keyed_map("legal", self.legal)
        self._validate_identifier_keyed_map("sources", self.sources)
        self._validate_identifier_keyed_map("extraction_profiles", self.extraction_profiles)
        self._validate_identifier_keyed_map("live_cross_references", self.live_cross_references)
        self._validate_identifier_keyed_map("workbook_parity_refs", self.workbook_parity_refs)
        self._validate_identifier_keyed_map("verification_expectations", self.verification_expectations)
        self._validate_identifier_keyed_map("application_links", self.application_links)
        self._validate_identifier_keyed_map("deadline_windows", self.deadline_windows)
        self._validate_identifier_keyed_map("filing_schedules", self.filing_schedules)
        self._validate_identifier_keyed_map("support_removal_decisions", self.support_removal_decisions)
        self._validate_identifier_keyed_map("constructs", self.constructs)
        self._validate_identifier_keyed_map("dependency_classifications", self.dependency_classifications)
        return self

    @model_validator(mode="after")
    def _validate_filing_period_consistency(self) -> RegistrySnapshot:
        if self.filing_period is None:
            return self
        if self.filing_period.filing_year != self.filing_year:
            raise RegistryValidationError("snapshot filing_period year must match filing_year")
        if not selector_period_matches_request(self.period, self.filing_period.registry_token):
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
            rounding_codes=frozenset(expectation.rounding for expectation in expectations),
            discrepancy_causes=frozenset(
                cause for expectation in expectations for cause in expectation.discrepancy_causes
            ),
        )


def filing_period_from_scope(filing_year: int, period: str) -> Period | None:
    """Return a core :class:`Period` when the registry token is a real filing-period code."""
    try:
        return Period.from_year_and_code(filing_year, period)
    except ValueError:
        return None
