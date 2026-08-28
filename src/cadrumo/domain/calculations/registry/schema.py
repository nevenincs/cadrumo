"""Strict schema authority for AEAT registry definitions.

Each modelo revision carries an ``output_sensitivity`` field typed as
:class:`SensitivityClass` that governs the encryption tier applied to
generated output envelopes.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Annotated, Final, Literal

from pydantic import (
    BaseModel,
    BeforeValidator,
    Field,
    ValidationInfo,
    field_serializer,
    field_validator,
    model_validator,
)

from ....core import (
    M210_TIPO_RENTA_CODE_PROJECTION,
    UNDECLARED_REGISTRY_AUTHORITY_GRADE,
    CasillaId,
    FilingProjectionRef,
    Modelo,
    Period,
    PeriodKind,
    RegistryAuthorityGrade,
    RegistrySelectorPeriodCode,
    ResultDisposition,
    RevisionReviewStatus,
    TaxDomain,
    filing_projection_ref_casilla_id,
    registry_period_kind,
)
from ....core.aggregation import BindingAggregation, BindingSourceKind, BindingTypedEnumKind
from ....core.classification import SensitivityClass
from ._schema_governance import (
    validate_attribution_names_somebody,
    validate_governance_stamp_coherence,
    validate_reviewed_at_within_horizon,
)
from ._toml_helpers import as_toml_table as _as_toml_table
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
    LegalRefId,
    ModeloId,
    ParameterId,
    RelationId,
    RevisionId,
    SourceRefId,
    VerificationExpectationId,
    WorkbookParityRefId,
)
from .m303_orden_projection_models import M303AnnualOrdenAuthority
from .period_selector_match import selector_period_matches_request
from .schema_input_kind import InputKind
from .schema_rounding import RegistryRoundingCode as RegistryRoundingCode
from .schema_rounding import RegistryRoundingCodeValue
from .schema_scalars import (
    BicString as _BicString,
)
from .schema_scalars import (
    BindingSelector as _BindingSelector,
)
from .schema_scalars import (
    BindingSelectorMap as _BindingSelectorMap,
)
from .schema_scalars import (
    BindingSelectorValue as _BindingSelectorValue,
)
from .schema_scalars import (
    CalendarDate as _CalendarDate,
)
from .schema_scalars import (
    CCAACode as _CCAACode,
)
from .schema_scalars import (
    CountryCode as _CountryCode,
)
from .schema_scalars import DecimalValue as _DecimalValue
from .schema_scalars import (
    IbanString as _IbanString,
)
from .schema_scalars import (
    ModeloYear as _ModeloYear,
)
from .schema_scalars import (
    MunicipalityCode as _MunicipalityCode,
)
from .schema_scalars import (
    NifIvaString as _NifIvaString,
)
from .schema_scalars import (
    NifString as _NifString,
)
from .schema_scalars import (
    PeriodCode as _PeriodCode,
)
from .schema_scalars import (
    PersonOrEntityName as _PersonOrEntityName,
)
from .schema_scalars import (
    PostalCode as _PostalCode,
)
from .schema_scalars import (
    ProvinceCode as _ProvinceCode,
)
from .schema_scalars import (
    WorkbookCellRefStr as _WorkbookCellRefStr,
)
from .schema_scalars import (
    coerce_modelo_year as _coerce_modelo_year_impl,
)
from .schema_scalars import (
    validate_country_code as _validate_country_code_impl,
)
from .schema_scalars import (
    validate_iban_string as _validate_iban_string_impl,
)
from .schema_scalars import (
    validate_nif_string as _validate_nif_string_impl,
)
from .schema_scalars import (
    validate_period_code as _validate_period_code_impl,
)
from .schema_verification import (
    LiveCrossReferenceDecision,
    ProfilePredicateDefinition,
    RegistryVerificationPolicy,
    VerificationExpectationDefinition,
    VerificationPredicateDefinition,
    WorkbookParityReference,
    fold_reconciliation_total_casilla_ids,
)

__all__ = [
    "ApplicationLinkDefinition",
    "BindingSelector",
    "CasillaProducerInventory",
    "CasillaProducerProvenance",
    "ConstructDefinition",
    "DataBindingDefinition",
    "DeadlineWindowDefinition",
    "DecimalValue",
    "DependencyClassificationDefinition",
    "FormulaDefinition",
    "ModeloDefinition",
    "ModeloRevision",
    "ModeloScheduleDefinition",
    "RegistryCatalogues",
    "RegistrySnapshot",
    "SupportedFilingYearsCatalogue",
]

from .schema_exports import ExportLayoutDefinition, ProjectionEndpointDeclaration

from .convenio import ConvenioAuthority
from .modelo_localization import resolve_modelo_localization
from .schema_base import (
    GOVERNANCE_STAMP,
    MANIFEST_ONLY,
    SCHEMA_FAMILY,
    CalculationClass,
    LegalRefs,
    ModeloFilingCapability,
    RegistryAuthorityGradeField,
    RegistryModel,
    RevisionReviewStatusField,
    SensitivityClassField,
    SourceCitation,
    SourceRefs,
    collection_shaped_fields,
    governance_stamp_fields,
    manifest_only_fields,
    schema_family_fields,
)
from .schema_extraction import ExtractionProfileDefinition
from .schema_formula import (
    FormulaExpression,
    ParameterDefinition,
)
from .schema_references import (
    LegalParameter,
    LegalReference,
    PeriodSelector,
    SourceReference,
)
from .schema_surfaces import (
    CalculationCompletenessManifest,
    CasillaContinuidadEvolutionDefinition,
    CasillaDefinition,
    RelationDefinition,
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
        return self


class ApplicabilityRuleDefinition(RegistryModel):
    """A registry-authored modelo-applicability rule fragment.

    The TOML-authored counterpart of
    :class:`~cadrumo.domain.calculations.registry.applicability.ModeloApplicabilityRule`.
    Every closed-vocabulary field here is a plain string (or a set of them),
    never a ``domain.deadlines`` enum type: importing that package from this
    module would close an import cycle, since ``domain.deadlines`` itself
    depends on :class:`DeadlineWindowDefinition`, declared in this same
    module. Registry TOML stays free-form;
    :func:`~._applicability.hydrate_applicability_rule` is the loader
    boundary that resolves every string to its enum member, surfacing an
    unknown token as a registry load failure naming the offending value.

    Attributes:
        id: The rule's own identifier, unique within its revision.
        applicable_entity_types: :class:`~domain.deadlines.EntityType` token
            strings the modelo applies to.
        required_income_categories: :class:`~domain.deadlines.IrpfIncomeCategory`
            token strings gating a natural person's applicability. Empty means
            the modelo does not gate on income category.
        required_estimation_regimes: :class:`~domain.deadlines.IrpfEstimationRegime`
            token strings gating a natural person's applicability. Empty means
            the modelo does not gate on estimation regime.
        applicable_fiscal_residencies: :class:`~domain.deadlines.FiscalResidency`
            token strings positively keeping the modelo in scope. Empty means
            the modelo does not gate on fiscal residency.
        applicable_iva_regimes: :class:`~domain.deadlines.IVARegime` token
            strings positively keeping the modelo in scope. Empty means the
            modelo does not gate on IVA regime.
        required_payer_fact: The
            :class:`~._applicability_payer_facts.PayerFact` token string the
            modelo's applicability depends on, or ``None`` when the modelo
            does not gate on a payer fact.
        applicable_reason: Operator-facing prose for the ``APPLICABLE`` verdict.
        not_applicable_reason: Operator-facing prose for the
            ``NOT_APPLICABLE`` verdict.
        cuota_bearing: ``True`` when the modelo is a cuota self-assessment
            (see :attr:`ModeloApplicabilityRule.cuota_bearing`).
        legal_refs: Scoped registry citation keys grounding the rule.
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
    """Declare the applicable opening, closing, and payment dates for a filing."""

    id: DeadlineWindowId
    filing_year: int = Field(ge=1900, le=2999)
    period: Annotated[Period, BeforeValidator(_parse_deadline_window_period)]
    period_kind: Literal["monthly", "quarterly", "annual", "ad_hoc"]
    opens_on: date
    closes_on: date
    payment_cutoff_on: date | None = None
    applicability_condition_mode: Literal["all", "any"] = "all"
    applicability_conditions: tuple[ProfilePredicateDefinition, ...] = ()
    resultado_scope: (
        Annotated[
            ResultDisposition,
            BeforeValidator(lambda value: ResultDisposition(value) if isinstance(value, str) else value),
        ]
        | None
    ) = None
    tipo_renta_scope: tuple[str, ...] | None = None
    legal_refs: LegalRefs
    source_refs: SourceRefs

    @field_validator("tipo_renta_scope")
    @classmethod
    def _validate_tipo_renta_scope(cls, value: tuple[str, ...] | None) -> tuple[str, ...] | None:
        """Preserve official M210 codes without folding them into rate concepts."""
        if value is None:
            return None
        if not value:
            raise RegistryValidationError("deadline window tipo_renta_scope must not be empty")
        if len(set(value)) != len(value):
            raise RegistryValidationError("deadline window tipo_renta_scope entries must be unique")
        unknown_codes = tuple(code for code in value if code not in M210_TIPO_RENTA_CODE_PROJECTION)
        if unknown_codes:
            accepted = ", ".join(sorted(M210_TIPO_RENTA_CODE_PROJECTION))
            raise RegistryValidationError(
                f"deadline window tipo_renta_scope contains unknown official Modelo 210 codes "
                f"{unknown_codes!r}; accepted codes: {accepted}",
            )
        return value

    @model_validator(mode="after")
    def _validate_window(self) -> DeadlineWindowDefinition:
        if self.filing_year != self.period.filing_year:
            raise RegistryValidationError(
                f"deadline window {self.id!r} filing_year {self.filing_year} must match "
                f"period filing_year {self.period.filing_year}",
            )
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
            canonical_kind = registry_period_kind(token)
        except ValueError:
            mismatches.append(token)
            continue
        if canonical_kind not in accepted:
            mismatches.append(token)
    return tuple(mismatches)


filing_schedule_period_kind_mismatches = _filing_schedule_period_kind_mismatches
"""Public facade for the filing-schedule period-kind consistency predicate."""


class ModeloScheduleDefinition(RegistryModel):
    """Declare the filing periods and profile conditions for a modelo schedule."""

    id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.-]+$")
    period_kind: Literal["monthly", "quarterly", "annual", "ad_hoc"]
    periods: tuple[RegistrySelectorPeriodCode, ...] = Field(min_length=1)
    profile_condition_mode: Literal["all", "any"] = "all"
    profile_conditions: tuple[ProfilePredicateDefinition, ...] = ()
    legal_refs: LegalRefs
    source_refs: SourceRefs

    @property
    def is_periodic(self) -> bool:
        """Whether this schedule requires complete recurring deadline coverage."""
        return self.period_kind in ("monthly", "quarterly")

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
    """Declare one typed source-to-casilla binding in a registry revision."""

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
        from .binding_selector_utils import canonical_selector_key_hint
        from .bindings import selector_model_for_source

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
        from .binding_selector_utils import selector_against_model
        from .bindings import selector_model_for_source

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
    """Declare the grounded formula that produces one target casilla."""

    id: FormulaId
    target_casilla_id: CasillaId
    expression: FormulaExpression
    rounding: RegistryRoundingCodeValue = None
    legal_refs: LegalRefs
    source_refs: SourceRefs
    source_citations: tuple[SourceCitation, ...] = Field(default_factory=tuple)


type CasillaProducerKind = Literal["formula", "manual", "upstream", "relation", "informational", "projection_only"]


@dataclass(frozen=True, slots=True)
class CasillaProducerProvenance:
    """One lossless producer path for a revision-local casilla.

    The record retains the real schema declarations instead of copying or
    flattening their legal/source provenance.  A relation-backed binding emits
    one record per relation declaration, so distinct relation ids and their
    independent provenance remain visible even when they target the same
    binding and casilla.
    """

    casilla: CasillaDefinition
    producer_kind: CasillaProducerKind
    reason: str
    formula: FormulaDefinition | None = None
    binding: DataBindingDefinition | None = None
    relation: RelationDefinition | None = None

    @property
    def producer_legal_refs(self) -> tuple[LegalRefId, ...]:
        """Return the existing legal refs on this path's producer declaration."""
        if self.relation is not None:
            return tuple(self.relation.legal_refs)
        if self.binding is not None:
            return tuple(self.binding.legal_refs)
        if self.formula is not None:
            return tuple(self.formula.legal_refs)
        if self.producer_kind in _CASILLA_GROUNDED_PRODUCER_KINDS:
            return tuple(self.casilla.legal_refs)
        return ()

    @property
    def producer_source_refs(self) -> tuple[SourceRefId, ...]:
        """Return the existing source refs on this path's producer declaration."""
        if self.relation is not None:
            return tuple(self.relation.source_refs)
        if self.binding is not None:
            return tuple(self.binding.source_refs)
        if self.formula is not None:
            return tuple(self.formula.source_refs)
        if self.producer_kind in _CASILLA_GROUNDED_PRODUCER_KINDS:
            return tuple(self.casilla.source_refs)
        return ()


#: Producer kinds whose grounding lives on the CASILLA itself. None of them has a
#: producer declaration of its own to carry legal or source refs: a manual value
#: is operator-supplied, an informational casilla produces nothing, and a
#: projection-only casilla is populated from its canonical typed row, which is a
#: runtime projection rather than a registry row with provenance. Omitting
#: projection_only dropped the grounding of 366 Modelo 303 casillas -- every one
#: of which declares legal_refs -- from their producer trace.
_CASILLA_GROUNDED_PRODUCER_KINDS: Final[frozenset[str]] = frozenset(
    {"manual", "informational", "projection_only"},
)


@dataclass(frozen=True, slots=True)
class CasillaProducerInventory:
    """Revision-local inventory of casilla producers and declarations.

    Formula targets are indexed in both directions without collapsing duplicate
    declarations.  The ``producer_kind_by_casilla`` and
    ``producer_reason_by_casilla`` maps keep intentional non-formula rows
    visible: manual rows are operator-supplied, bound rows are upstream
    producers, and relation-prefill bindings are cross-model handoffs.  Their
    legal/source provenance remains on the casilla and binding definitions;
    this inventory only names the declared production path and its reason.
    """

    formula_ids_by_target: Mapping[CasillaId, tuple[FormulaId, ...]]
    formula_ids_by_id: Mapping[FormulaId, tuple[FormulaDefinition, ...]]
    formula_ids_by_casilla: Mapping[CasillaId, tuple[FormulaId, ...]]
    computed_casilla_ids: frozenset[CasillaId]
    producer_kind_by_casilla: Mapping[CasillaId, CasillaProducerKind]
    producer_reason_by_casilla: Mapping[CasillaId, str]
    producer_provenance_by_casilla: Mapping[CasillaId, tuple[CasillaProducerProvenance, ...]]


def _frozen_index[K, V](index: Mapping[K, Sequence[V]]) -> dict[K, tuple[V, ...]]:
    """Freeze an accumulating list-valued index into its published immutable form.

    Every producer index accumulates into lists rather than overwriting, so a
    duplicate declaration stays visible instead of being hidden by a
    last-write-wins assignment; freezing is the last step before publication.
    """
    return {key: tuple(values) for key, values in index.items()}


def _producer_provenance(
    casilla: CasillaDefinition,
    kind: CasillaProducerKind,
    reason: str,
    *,
    formulas: Sequence[FormulaDefinition] = (),
    binding: DataBindingDefinition | None = None,
    relations: Sequence[RelationDefinition] = (),
) -> tuple[CasillaProducerProvenance, ...]:
    """Build the provenance records for one classified production path.

    A declaration that resolves to several real registry rows -- several formula
    declarations sharing one id, several relations targeting one binding -- emits
    one record per row, so their independent legal provenance stays visible. A
    declaration that resolves to none still emits a single record carrying the
    reason, which is what keeps an unresolved producer auditable instead of
    absent.
    """
    if formulas:
        return tuple(
            CasillaProducerProvenance(
                casilla=casilla,
                producer_kind=kind,
                reason=reason,
                formula=formula,
            )
            for formula in formulas
        )
    if relations:
        return tuple(
            CasillaProducerProvenance(
                casilla=casilla,
                producer_kind=kind,
                reason=reason,
                binding=binding,
                relation=relation,
            )
            for relation in relations
        )
    return (
        CasillaProducerProvenance(
            casilla=casilla,
            producer_kind=kind,
            reason=reason,
            binding=binding,
        ),
    )


def _bound_casilla_producer(
    casilla: CasillaDefinition,
    *,
    bindings_by_id: Mapping[BindingId, DataBindingDefinition],
    relations_by_binding: Mapping[BindingId, Sequence[RelationDefinition]],
) -> tuple[CasillaProducerKind, str, tuple[CasillaProducerProvenance, ...]]:
    """Classify a ``bound`` casilla from the binding its declaration names.

    A binding declaring :attr:`~core.BindingSourceKind.RELATION_PREFILL` is a
    relation handoff; any other binding is an ordinary upstream value. A missing
    binding declaration stays ``upstream`` and says so in its reason rather than
    silently reclassifying -- the declaration, not the resolution, is what the
    inventory reports.
    """
    binding = bindings_by_id.get(casilla.binding) if casilla.binding is not None else None
    if binding is None:
        reason = "upstream production is declared by input_kind='bound' but its binding declaration is missing"
        return "upstream", reason, _producer_provenance(casilla, "upstream", reason)
    if binding.source is BindingSourceKind.RELATION_PREFILL:
        reason = f"relation production uses binding {binding.id!r} with source {binding.source.value!r}"
        return (
            "relation",
            reason,
            _producer_provenance(
                casilla,
                "relation",
                reason,
                binding=binding,
                relations=relations_by_binding.get(binding.id, ()),
            ),
        )
    reason = f"upstream production uses binding {binding.id!r} with source {binding.source.value!r}"
    return "upstream", reason, _producer_provenance(casilla, "upstream", reason, binding=binding)


def _casilla_producer(
    casilla: CasillaDefinition,
    *,
    formulas_by_id: Mapping[FormulaId, Sequence[FormulaDefinition]],
    bindings_by_id: Mapping[BindingId, DataBindingDefinition],
    relations_by_binding: Mapping[BindingId, Sequence[RelationDefinition]],
) -> tuple[CasillaProducerKind, str, tuple[CasillaProducerProvenance, ...]]:
    """Classify one casilla's declared production path, with its reason.

    An explicit formula declaration wins over the input kind, because it is the
    narrower statement of the same fact. The classification is descriptive:
    validation still owns whether a formula direction is closed.
    """
    if casilla.formula is not None:
        reason = f"deterministic formula producer declaration {casilla.formula!r}"
        return (
            "formula",
            reason,
            _producer_provenance(
                casilla,
                "formula",
                reason,
                formulas=formulas_by_id.get(casilla.formula, ()),
            ),
        )
    if casilla.input_kind is InputKind.COMPUTED:
        reason = "computed casilla requires a deterministic formula producer"
        return "formula", reason, _producer_provenance(casilla, "formula", reason)
    if casilla.input_kind is InputKind.MANUAL:
        reason = (
            "manual production is intentional operator-supplied input; "
            "casilla legal_refs/source_refs remain its provenance"
        )
        return "manual", reason, _producer_provenance(casilla, "manual", reason)
    if casilla.input_kind is InputKind.BOUND:
        return _bound_casilla_producer(
            casilla,
            bindings_by_id=bindings_by_id,
            relations_by_binding=relations_by_binding,
        )
    if casilla.input_kind is InputKind.PROJECTION_ONLY:
        reason = "projection-only casilla is populated exclusively from its canonical typed row"
        return "projection_only", reason, _producer_provenance(casilla, "projection_only", reason)
    reason = "informational casilla is intentionally not a calculation producer"
    return "informational", reason, _producer_provenance(casilla, "informational", reason)


class SchemaFamilyDispositionDeclaration(RegistryModel):
    """A revision's declared reason that one of its schema families does not apply.

    The only way an empty family reads as anything but
    :attr:`RegistrySchemaFamilyDisposition.BLOCKED_PENDING_EVIDENCE`, and it is
    deliberately expensive to make: a substantive claim about what the law does
    not require of this modelo, so it carries a reason somebody wrote and the
    references it stands on.

    The alternative — an allowlist of families permitted to be empty — was
    rejected as the shape of the problem rather than its solution. An allowlist
    entry records that somebody wanted the check quiet; this records what they
    claim and what backs it, which is the thing a later reviewer can disagree
    with.
    """

    reason: str = Field(min_length=1, max_length=1024)
    legal_refs: LegalRefs
    source_refs: SourceRefs


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

    ``authority_grade`` is the revision's *declared* authority reach, a separate
    subject from the stamp: the stamp says who signed the revision off, the grade
    says how far the revision's authority extends. It shares the stamp's
    manifest-only placement guarantee — it is a claim about the whole revision,
    so it must be readable in ``revision.toml`` rather than merged in from a
    fragment thousands deep — and it shares the fail-closed shape, reading as
    :data:`~cadrumo.core.UNDECLARED_REGISTRY_AUTHORITY_GRADE` when absent. It is
    deliberately optional rather than defaulted on the field, so an ungraded
    revision stays distinguishable from one explicitly graded at that same
    floor; :attr:`effective_authority_grade` is the reading, and
    :attr:`is_graded` the distinction.

    ``export_layouts`` is the AUTHORED form, not the one that ships. A record
    carrying ``binding_record`` is authored thin on purpose -- its envelope
    constants only -- and
    :func:`~._export.derive_export_layouts_from_bindings` materialises the real
    fields at snapshot build. Modelo 369's ``t36904`` is 9 authored fields and
    161 derived ones against a design sheet requiring 161; modelo 390's
    ``page-05`` is 6 and 105. Any consumer comparing a layout against an official
    record design MUST resolve through that function, which is the stage
    :func:`~._validate_export_layout_coverage.validate_export_layout_record_coverage`
    measures. Reading this attribute for that purpose reports every materialised
    field as an unwritten position: it produced 22 confident false
    silent-data-loss findings across modelos 369, 390 and 131, twice, in trees
    that were already stamped and verified.
    """

    id: RevisionId
    localization_key: str = Field(min_length=1, exclude=True, repr=False)
    valid_from: date
    valid_to: Annotated[date | None, MANIFEST_ONLY] = None
    period_selector: PeriodSelector
    legal_refs: Annotated[LegalRefs, MANIFEST_ONLY]
    source_refs: SourceRefs
    # Required by validate_orden_aplicabilidad; kept default-empty so the
    # validator can report a grounded registry failure instead of a parse error.
    orden_aplicabilidad: Annotated[tuple[LegalRefId, ...], MANIFEST_ONLY] = ()
    parameters: Annotated[tuple[ParameterDefinition, ...], SCHEMA_FAMILY] = ()
    casillas: Annotated[tuple[CasillaDefinition, ...], SCHEMA_FAMILY] = ()
    formulas: Annotated[tuple[FormulaDefinition, ...], SCHEMA_FAMILY] = ()
    bindings: Annotated[tuple[DataBindingDefinition, ...], SCHEMA_FAMILY] = ()
    relations: Annotated[tuple[RelationDefinition, ...], SCHEMA_FAMILY] = ()
    projection_endpoints: Annotated[tuple[ProjectionEndpointDeclaration, ...], SCHEMA_FAMILY] = ()
    export_layouts: Annotated[tuple[ExportLayoutDefinition, ...], SCHEMA_FAMILY] = ()
    extraction_profiles: Annotated[tuple[ExtractionProfileDefinition, ...], SCHEMA_FAMILY] = ()
    live_cross_references: Annotated[tuple[LiveCrossReferenceDecision, ...], SCHEMA_FAMILY] = ()
    workbook_parity_refs: Annotated[tuple[WorkbookParityReference, ...], SCHEMA_FAMILY] = ()
    verification_expectations: Annotated[tuple[VerificationExpectationDefinition, ...], SCHEMA_FAMILY] = ()
    application_links: Annotated[tuple[ApplicationLinkDefinition, ...], SCHEMA_FAMILY] = ()
    deadline_windows: Annotated[tuple[DeadlineWindowDefinition, ...], SCHEMA_FAMILY] = ()
    filing_schedules: Annotated[tuple[ModeloScheduleDefinition, ...], SCHEMA_FAMILY] = ()
    constructs: Annotated[tuple[ConstructDefinition, ...], SCHEMA_FAMILY] = ()
    dependency_classifications: Annotated[tuple[DependencyClassificationDefinition, ...], SCHEMA_FAMILY] = ()
    applicability: Annotated[tuple[ApplicabilityRuleDefinition, ...], SCHEMA_FAMILY] = ()
    completeness_manifest: CalculationCompletenessManifest | None = None
    verification_predicates: Annotated[tuple[VerificationPredicateDefinition, ...], SCHEMA_FAMILY] = ()
    continuidad_validation: Literal["advisory", "strict"] = "advisory"
    casilla_continuidad_evolutions: Annotated[tuple[CasillaContinuidadEvolutionDefinition, ...], SCHEMA_FAMILY] = ()
    authority_grade: Annotated[RegistryAuthorityGradeField | None, MANIFEST_ONLY] = None
    family_dispositions: Annotated[Mapping[str, SchemaFamilyDispositionDeclaration], MANIFEST_ONLY] = Field(
        default_factory=dict,
    )
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

    @property
    def is_graded(self) -> bool:
        """Return whether this revision declares an authority grade at all.

        The distinction :attr:`effective_authority_grade` deliberately erases: an
        ungraded revision and one declared at the floor read as the same scope
        but are not the same claim, and only one of them is a backlog entry.
        """
        return self.authority_grade is not None

    @property
    def effective_authority_grade(self) -> RegistryAuthorityGrade:
        """Return the authority reach to act on, reading absence fail-closed.

        An undeclared grade reads as
        :data:`~cadrumo.core.UNDECLARED_REGISTRY_AUTHORITY_GRADE` — the lowest
        rung — so a revision nobody has graded confers scheduling reach and
        nothing more. Consumers read the reach here rather than each deciding
        for itself what a missing declaration means.
        """
        return self.authority_grade if self.authority_grade is not None else UNDECLARED_REGISTRY_AUTHORITY_GRADE

    def get_label(self, locale: str) -> str | None:
        """Resolve the optional revision label from the shared catalogue."""
        return resolve_modelo_localization((self.localization_key,), locale=locale, required=False)

    @property
    def label(self) -> str | None:
        """Return the optional official-Spanish revision label."""
        return self.get_label("es")

    def projection_endpoint_index(self) -> Mapping[FilingProjectionRef, tuple[ProjectionEndpointDeclaration, ...]]:
        """Index declared projection endpoints without concealing duplicates.

        Generated layouts deliberately do not participate in this authority:
        their fields must later prove an exact bijection with this revision-owned
        declaration index.
        """
        declarations_by_ref: dict[FilingProjectionRef, list[ProjectionEndpointDeclaration]] = {}
        for declaration in self.projection_endpoints:
            declarations_by_ref.setdefault(declaration.projection_ref, []).append(declaration)
        return _frozen_index(declarations_by_ref)

    def projection_declarations_for_casilla(self, casilla_id: CasillaId) -> tuple[ProjectionEndpointDeclaration, ...]:
        """Return declarations whose typed reference addresses ``casilla_id``."""
        return tuple(
            declaration
            for reference, declarations in self.projection_endpoint_index().items()
            if filing_projection_ref_casilla_id(reference) == casilla_id
            for declaration in declarations
        )

    def producer_inventory(self) -> CasillaProducerInventory:
        """Return the typed producer/declaration inventory for this revision.

        Formula ids are retained as tuples in every index so an invalid
        duplicate cannot be hidden by a last-write-wins dictionary.  A
        non-formula casilla is classified from its existing typed declaration:
        ``manual`` is operator input, ordinary ``bound`` rows are upstream
        values, and ``relation_prefill`` rows are relation handoffs.  These
        classifications are descriptive; validation still owns whether a
        formula direction is closed.
        """
        formulas_by_target: dict[CasillaId, list[FormulaId]] = {}
        formulas_by_id: dict[FormulaId, list[FormulaDefinition]] = {}
        for formula in self.formulas:
            formulas_by_target.setdefault(formula.target_casilla_id, []).append(formula.id)
            formulas_by_id.setdefault(formula.id, []).append(formula)

        formula_declarations_by_casilla: dict[CasillaId, list[FormulaId]] = {}
        bindings_by_id = {binding.id: binding for binding in self.bindings}
        relations_by_binding: dict[BindingId, list[RelationDefinition]] = {}
        for relation in self.relations:
            relations_by_binding.setdefault(relation.target_binding, []).append(relation)
        computed_casilla_ids: set[CasillaId] = set()
        producer_kind_by_casilla: dict[CasillaId, CasillaProducerKind] = {}
        producer_reason_by_casilla: dict[CasillaId, str] = {}
        producer_provenance_by_casilla: dict[CasillaId, list[CasillaProducerProvenance]] = {}

        for casilla in self.casillas:
            if casilla.input_kind is InputKind.COMPUTED:
                computed_casilla_ids.add(casilla.id)
            if casilla.formula is not None:
                formula_declarations_by_casilla.setdefault(casilla.id, []).append(casilla.formula)

            kind, reason, provenance = _casilla_producer(
                casilla,
                formulas_by_id=formulas_by_id,
                bindings_by_id=bindings_by_id,
                relations_by_binding=relations_by_binding,
            )
            producer_kind_by_casilla[casilla.id] = kind
            producer_reason_by_casilla[casilla.id] = reason
            producer_provenance_by_casilla.setdefault(casilla.id, []).extend(provenance)

        return CasillaProducerInventory(
            formula_ids_by_target=_frozen_index(formulas_by_target),
            formula_ids_by_id=_frozen_index(formulas_by_id),
            formula_ids_by_casilla=_frozen_index(formula_declarations_by_casilla),
            computed_casilla_ids=frozenset(computed_casilla_ids),
            producer_kind_by_casilla=producer_kind_by_casilla,
            producer_reason_by_casilla=producer_reason_by_casilla,
            producer_provenance_by_casilla=_frozen_index(producer_provenance_by_casilla),
        )

    @model_validator(mode="after")
    def _validate_family_dispositions(self) -> ModeloRevision:
        """Refuse an inapplicability claim that names no family or contradicts one.

        Both directions are silent corruption otherwise. A declaration keyed on a
        typo names no family, so it resolves nothing while reading as though it
        did; and a declaration against a family that HOLDS content asserts the
        law does not require what the revision already declares, which is a
        contradiction the coverage projection would have to arbitrate.
        """
        for family in self.family_dispositions:
            if family not in REVISION_SCHEMA_FAMILY_FIELDS:
                raise RegistryValidationError(
                    f"revision {self.id!r} declares a family disposition for {family!r}, which is not a schema "
                    f"family; enrolled families are {sorted(REVISION_SCHEMA_FAMILY_FIELDS)!r}",
                )
            if getattr(self, family):
                raise RegistryValidationError(
                    f"revision {self.id!r} declares family {family!r} not applicable but also declares "
                    f"{len(getattr(self, family))} of them; drop the disposition or drop the content",
                )
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

REVISION_SCHEMA_FAMILY_FIELDS: frozenset[str] = schema_family_fields(ModeloRevision)
"""Every :class:`ModeloRevision` field whose emptiness is a coverage question.

The revision's declared content collections, read back off the
:data:`SCHEMA_FAMILY` markers rather than hand-listed. This is the denominator
of the per-revision coverage manifest: one disposition row per member, always,
so a family nobody has built is a row saying so rather than an absence.

Meant to equal :data:`REVISION_COLLECTION_SHAPED_FIELDS`, and gated against it.
Neither set alone is sufficient - see :class:`SchemaFamilyMarker`.
"""

REVISION_COLLECTION_SHAPED_FIELDS: frozenset[str] = collection_shaped_fields(ModeloRevision)
"""Every :class:`ModeloRevision` field annotated as a tuple of a schema model.

Computed from the annotations alone, which is precisely what makes it the right
check on :data:`REVISION_SCHEMA_FAMILY_FIELDS`: a contributor adding a
collection cannot forget to appear here, because appearing here is a
consequence of the type they wrote rather than a step they took.
"""

REVISION_MANIFEST_ONLY_FIELDS: frozenset[str] = manifest_only_fields(ModeloRevision)
"""Every :class:`ModeloRevision` field that may be declared only in ``revision.toml``.

A superset of :data:`REVISION_GOVERNANCE_FIELDS` by construction, since
:class:`GovernanceStampMarker` is a :class:`ManifestOnlyMarker`. Beyond the
governance stamp it carries the legally load-bearing scalars ``legal_refs``,
``orden_aplicabilidad`` and ``valid_to``, which share the stamp's readability
hazard and raise its stakes, and ``authority_grade``, which is a claim about how
far the whole revision's authority reaches and so belongs in the one file a
reviewer opens; :mod:`.._schema_governance` records how a deep
fragment can otherwise supply a revision's legal grounding while
``revision.toml`` reads as though it did not.
"""


class ModeloDefinition(RegistryModel):
    """Declare a modelo and its complete collection of revision authorities."""

    id: ModeloId
    title_localization_key: str = Field(min_length=1, exclude=True, repr=False)
    official_name_localization_key: str = Field(min_length=1, exclude=True, repr=False)
    tax_domain: Annotated[TaxDomain, BeforeValidator(lambda v: TaxDomain(v) if isinstance(v, str) else v)]
    cadence: Literal["monthly", "quarterly", "annual", "ad_hoc", "profile_based"]
    jurisdiction: Literal["ES-AEAT"]
    calculation_class: CalculationClass = "filing"
    output_sensitivity: SensitivityClassField = SensitivityClass.FINANCIAL
    capabilities: Annotated[frozenset[ModeloFilingCapability], BeforeValidator(frozenset)] = frozenset()
    legal_refs: LegalRefs
    source_refs: SourceRefs
    revisions: Mapping[RevisionId, ModeloRevision]

    def get_title(self, locale: str) -> str:
        """Resolve the Modelo title from the shared catalogue."""
        resolved = resolve_modelo_localization((self.title_localization_key,), locale=locale, required=True)
        assert resolved is not None
        return resolved

    def get_official_name(self, locale: str) -> str:
        """Resolve the official Modelo name from the shared catalogue."""
        resolved = resolve_modelo_localization((self.official_name_localization_key,), locale=locale, required=True)
        assert resolved is not None
        return resolved

    @property
    def title(self) -> str:
        """Return the strict official-Spanish Modelo title."""
        return self.get_title("es")

    @property
    def official_name(self) -> str:
        """Return the strict official-Spanish Modelo name."""
        return self.get_official_name("es")

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


def _union_across_expectations[T](
    expectations: Sequence[VerificationExpectationDefinition],
    select: Callable[[VerificationExpectationDefinition], Iterable[T]],
) -> frozenset[T]:
    """Union one declared set across every expectation folded into a policy.

    The fold is a union rather than an intersection on purpose: an id any single
    expectation declares is in scope for the snapshot's policy, so a second
    expectation cannot narrow the first one's declared coverage away.
    """
    return frozenset(value for expectation in expectations for value in select(expectation))


class SupportedFilingYearsCatalogue(RegistryModel):
    """The registry's sole declaration of filing years the product supports."""

    years: tuple[int, ...] = Field(min_length=1)

    @field_validator("years")
    @classmethod
    def _years_are_unique_and_ordered(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        if any(year < 2000 or year > 2099 for year in value):
            raise RegistryValidationError("supported filing years must be between 2000 and 2099")
        if tuple(sorted(set(value))) != value:
            raise RegistryValidationError("supported filing years must be unique and in ascending order")
        return value


class RegistryCatalogues(RegistryModel):
    """Collect the registry-wide legal, source, parameter, and support catalogues."""

    legal: Mapping[LegalRefId, LegalReference]
    sources: Mapping[SourceRefId, SourceReference]
    parameters: Mapping[str, LegalParameter] = Field(default_factory=dict)
    convenio: ConvenioAuthority = Field(default_factory=ConvenioAuthority.empty)
    supplementary_ordenes: Mapping[Modelo, M303AnnualOrdenAuthority] = Field(
        default_factory=dict[Modelo, M303AnnualOrdenAuthority],
    )
    supported_filing_years: SupportedFilingYearsCatalogue | None = None


class RegistrySnapshot(RegistryModel):
    """Represent the resolved immutable authority for one modelo filing coordinate."""

    modelo: ModeloDefinition
    revision: ModeloRevision
    filing_period: Period | None = None
    filing_year: int = Field(ge=2000, le=2099)
    # Accepts normal period codes and declared event-period names; upstream
    # PeriodSelector + ModeloScheduleDefinition constrain the token set.
    period: RegistrySelectorPeriodCode
    legal: Mapping[LegalRefId, LegalReference]
    sources: Mapping[SourceRefId, SourceReference]
    extraction_profiles: Mapping[ExtractionProfileId, ExtractionProfileDefinition]
    live_cross_references: Mapping[CrossReferenceId, LiveCrossReferenceDecision]
    workbook_parity_refs: Mapping[WorkbookParityRefId, WorkbookParityReference]
    verification_expectations: Mapping[VerificationExpectationId, VerificationExpectationDefinition]
    application_links: Mapping[ApplicationLinkId, ApplicationLinkDefinition]
    deadline_windows: Mapping[DeadlineWindowId, DeadlineWindowDefinition]
    filing_schedules: Mapping[str, ModeloScheduleDefinition]
    constructs: Mapping[ConstructId, ConstructDefinition]
    dependency_classifications: Mapping[DependencyClassificationId, DependencyClassificationDefinition]
    convenio: ConvenioAuthority = Field(default_factory=ConvenioAuthority.empty)
    supplementary_ordenes: Mapping[Modelo, M303AnnualOrdenAuthority] = Field(
        default_factory=dict[Modelo, M303AnnualOrdenAuthority],
    )

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
        self._validate_identifier_keyed_map("constructs", self.constructs)
        self._validate_identifier_keyed_map("dependency_classifications", self.dependency_classifications)
        return self

    @model_validator(mode="after")
    def _validate_filing_period_consistency(self) -> RegistrySnapshot:
        """Reconcile :attr:`filing_period` against :attr:`filing_year` and :attr:`period`.

        This covers fewer snapshots than its name suggests, and the shortfall is
        correct rather than a gap. A snapshot addressed by an administrative censo
        coordinate — Modelo 036's ``alta`` / ``modificacion`` / ``baja``, Modelo
        145's ``comunicacion`` / ``variacion`` — has no ``filing_period`` to
        reconcile, because those coordinates name a registration event rather than
        a period a filing occupies and so cannot become a typed ``Period`` at all.
        The early return is the only honest answer for them.

        Modelo 210's symbolic selector ``EVENT-N`` skips it too, for a different
        reason worth separating: it is not an event name but a token standing for
        a SET of periods, which the revision matcher expands to the concrete
        ``EVENT-1`` / ``EVENT-2`` operator scopes. Those concrete scopes DO carry a
        filing period and are reconciled normally; only the symbolic form is
        skipped, because a set has no single period to check against. Verified
        against the registry rather than assumed: the complete skipped set is
        M036 ``alta``/``modificacion``/``baja``, M145 ``comunicacion``/``variacion``,
        and M210 ``EVENT-N``.

        It is stated here because the reduced coverage is invisible at the call
        site: nothing about a passing snapshot build reveals that a whole class of
        coordinates skipped this check. Do not read a green build as evidence that
        every snapshot's filing period was reconciled.
        """
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
            computed_casilla_ids=_union_across_expectations(
                expectations,
                lambda expectation: expectation.computed_casilla_ids,
            ),
            reconcile_when_present_casilla_ids=_union_across_expectations(
                expectations,
                lambda expectation: expectation.reconcile_when_present_casilla_ids,
            ),
            externally_grounded_casilla_ids=_union_across_expectations(
                expectations,
                lambda expectation: expectation.externally_grounded_casilla_ids,
            ),
            reconciliation_total_casilla_ids=fold_reconciliation_total_casilla_ids(expectations),
            tolerance=min(expectation.tolerance for expectation in expectations),
            min_coverage=max(expectation.min_coverage for expectation in expectations),
            rounding_codes=frozenset(expectation.rounding for expectation in expectations),
            discrepancy_causes=_union_across_expectations(
                expectations,
                lambda expectation: expectation.discrepancy_causes,
            ),
        )


def filing_period_from_scope(filing_year: int, period: str) -> Period | None:
    """Return a core :class:`Period` when the registry token is a real filing-period code."""
    try:
        return Period.from_year_and_code(filing_year, period)
    except ValueError:
        return None
