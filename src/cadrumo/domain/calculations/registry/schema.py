"""Strict schema authority for AEAT registry definitions.

Each modelo revision carries an ``output_sensitivity`` field typed as
:class:`SensitivityClass` that governs the encryption tier applied to
generated output envelopes.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Annotated, Final, Literal

from pydantic import (
    BeforeValidator,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

from ....core.aggregation import BindingAggregation, BindingSourceKind
from ....core.authority_grade import UNDECLARED_REGISTRY_AUTHORITY_GRADE, RegistryAuthorityGrade
from ....core.casilla_id import CasillaId
from ....core.classification.policies import SensitivityClass
from ....core.filing_projection_ref import FilingProjectionRef, filing_projection_ref_casilla_id
from ....core.frozen_mapping import FROZEN_MAPPING
from ....core.modelo import Modelo
from ....core.period import Period, RegistrySelectorPeriodCode
from ....core.revision_review import RevisionReviewStatus
from ....core.tax_domain import TaxDomain
from .binding_provider import BindingProvider
from .binding_temporal import (
    AllRevisionContexts,
    AuthoredBinding,
    BindingApplicability,
    BindingAuthorship,
)
from .binding_terminal_origin import TerminalOriginExpectation
from .binding_value_contract import BindingValueChannel, BindingValueContract
from .errors import RegistryValidationError
from .ids import (
    ApplicationLinkId,
    BindingId,
    ConstructId,
    CrossReferenceId,
    DeadlineWindowId,
    DependencyClassificationId,
    ExtractionProfileId,
    FormulaId,
    LegalRefId,
    ModeloId,
    RevisionId,
    SourceRefId,
    VerificationExpectationId,
    WorkbookParityRefId,
)
from .m303_orden_projection_models import M303AnnualOrdenAuthority
from .period_selector_match import selector_period_matches_request
from .schema_governance import (
    validate_attribution_names_somebody,
    validate_governance_stamp_coherence,
    validate_review_scope,
    validate_reviewed_at_within_horizon,
)
from .schema_input_kind import InputKind
from .schema_references import RegistryExternalLink, RegistrySnapshotRef, TemporalSupportEnvelope
from .schema_rounding import RegistryRoundingCode as RegistryRoundingCode
from .schema_rounding import RegistryRoundingCodeValue
from .schema_scalars import (
    BicString as _BicString,
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
from .schema_verification import (
    LiveCrossReferenceDecision,
    RegistryVerificationPolicy,
    VerificationExpectationDefinition,
    VerificationPredicateDefinition,
    WorkbookParityReference,
    fold_reconciliation_total_casilla_ids,
)

__all__ = [
    "BindingDefinition",
    "CasillaProducerInventory",
    "CasillaProducerProvenance",
    "DecimalValue",
    "DeclaredPredecessor",
    "FormulaDefinition",
    "ModeloDefinition",
    "ModeloRevision",
    "NoPredecessor",
    "RegistryCatalogues",
    "RegistrySnapshot",
    "SociedadesAnnualManualCoverageCatalogue",
    "SociedadesAnnualManualCoverageDisposition",
    "SociedadesAnnualManualCoverageStatus",
    "SupportedFilingYearsCatalogue",
]

from ....core.filing_year import FilingYear
from .convenio import ConvenioAuthority
from .facts.schema import GovernedFactCatalogue
from .identifier_evolutions import IdentifierEvolution
from .modelo_localization import require_modelo_localization, resolve_modelo_localization
from .revision_contracts import (
    DeclaredPredecessor,
    NoPredecessor,
    RegistryRevisionDeclaration,
    validate_revision_predecessors,
)
from .schema_base import (
    CHAIN_FAMILY,
    GOVERNANCE_STAMP,
    MANIFEST_ONLY,
    SCHEMA_FAMILY,
    CalculationClass,
    CalculationClassField,
    LegalRefs,
    ModeloFilingCapability,
    RegistryAuthorityGradeField,
    RegistryModel,
    RevisionReviewStatusField,
    SensitivityClassField,
    SourceCitation,
    SourceRefs,
    coerce_enum_member,
    governance_stamp_fields,
    manifest_only_fields,
    schema_family_fields,
)
from .schema_deadlines import DeadlineWindowDefinition as _DeadlineWindowDefinition
from .schema_deadlines import ModeloScheduleDefinition as _ModeloScheduleDefinition
from .schema_exports import ExportLayoutDefinition, ProjectionEndpointDeclaration
from .schema_extraction import ExtractionProfileDefinition
from .schema_formula import (
    FormulaExpression,
    ParameterDefinition,
)
from .schema_references import LegalReference, SourceReference
from .schema_revision_members import (
    ApplicabilityRuleDefinition as _ApplicabilityRuleDefinition,
)
from .schema_revision_members import (
    ApplicationLinkDefinition as _ApplicationLinkDefinition,
)
from .schema_revision_members import (
    ConstructDefinition as _ConstructDefinition,
)
from .schema_revision_members import (
    DependencyClassificationDefinition as _DependencyClassificationDefinition,
)
from .schema_surfaces import (
    CalculationCompletenessManifest,
    CasillaContinuidadEvolutionDefinition,
    CasillaDefinition,
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


class ContinuidadValidationMode(StrEnum):
    """How strictly casilla continuity is validated for a revision."""

    ADVISORY = "advisory"
    STRICT = "strict"


ContinuidadValidationModeField = Annotated[
    ContinuidadValidationMode, BeforeValidator(coerce_enum_member(ContinuidadValidationMode))
]
"""Registry token hydrated into a ContinuidadValidationMode member."""


class ModeloCadence(StrEnum):
    """How often a modelo is filed.

    ``PROFILE_BASED`` is not a period: it says the cadence is decided by the taxpayer's
    own circumstances, which is why it cannot be compared against the others as a
    frequency.
    """

    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"
    AD_HOC = "ad_hoc"
    PROFILE_BASED = "profile_based"


ModeloCadenceField = Annotated[ModeloCadence, BeforeValidator(coerce_enum_member(ModeloCadence))]
"""Registry token hydrated into a ModeloCadence member."""


class BindingDefinition(RegistryModel):
    """Declare one typed source-to-casilla binding in a registry revision.

    The declaration is a closed statement in four parts: :attr:`provider` names
    WHERE the value comes from as one member of the discriminated
    :data:`~.binding_provider.BindingProvider` union, :attr:`value` states the
    typed contract the value honours, :attr:`aggregation` states how several
    source facts fold into one, and :attr:`terminal_origins` states the classes
    of terminal fact the resolved value is allowed to rest on -- the authored
    half of the provenance audit.

    The former ``source`` token and untyped ``selector`` mapping are gone: they
    were two fields that could disagree, and the union makes the tag part of the
    member. :attr:`source` survives as a read-only projection of the member's
    discriminator for consumers that still key on the source kind alone.
    """

    id: BindingId
    provider: BindingProvider
    value: BindingValueContract
    aggregation: BindingAggregation | None = None
    applicability: BindingApplicability = AllRevisionContexts()
    terminal_origins: tuple[TerminalOriginExpectation, ...] = ()
    authorship: BindingAuthorship = AuthoredBinding()
    # AEAT borrador pre-fill tier: the third, AEAT-live prefill tier, distinct
    # from the local relation prefill (`_relation_prefill`) and previous-filing
    # direct-carry (`_binding_prefill`) tiers. The three share only the word
    # "prefill" and must not be merged.
    aeat_prefilled: bool = False
    legal_refs: LegalRefs
    source_refs: SourceRefs
    source_citations: tuple[SourceCitation, ...] = Field(default_factory=tuple)

    @property
    def source(self) -> BindingSourceKind:
        """Return the provider member's discriminator as its source kind.

        A projection, never a stored field: the discriminator IS the source
        kind, so the two can no longer disagree the way the former sibling
        ``source`` column could.
        """
        return BindingSourceKind(self.provider.kind)

    @model_validator(mode="after")
    def _validate_row_set_terminal_cardinality(self) -> BindingDefinition:
        """Refuse a row collection that claims exactly one terminal fact.

        A row family rests on however many terminal facts the period produced,
        including none: ``exactly_one`` would make an empty row family
        indistinguishable from a missing one, which is the collapse
        :mod:`binding_terminal_origin`'s cardinality axis exists to prevent.
        Whether the rows are grouped or provider-native is the registration's
        question; the cardinality is contract-local, so it is checked here.
        """
        if self.value.channel is not BindingValueChannel.ROW_SET:
            return self
        offending = tuple(
            expectation.source_class.value
            for expectation in self.terminal_origins
            if expectation.cardinality == "exactly_one"
        )
        if offending:
            raise RegistryValidationError(
                f"binding {self.id!r}: a row_set value cannot rest on an exactly_one terminal origin",
                context={"id": self.id, "source_classes": list(offending)},
            )
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


class CasillaProducerKind(StrEnum):
    """What produces a casilla's value in the compiled registry."""

    FORMULA = "formula"
    """A grounded formula computes it."""

    MANUAL = "manual"
    """The taxpayer supplies it directly."""

    UPSTREAM = "upstream"
    """It arrives from another modelo's output."""

    RELATION = "relation"
    """A declared relation prefills it."""

    INFORMATIONAL = "informational"
    """It is carried for information and settles nothing."""

    PROJECTION_ONLY = "projection_only"
    """It exists only in a projection, with no producer of its own."""


CasillaProducerKindField = Annotated[CasillaProducerKind, BeforeValidator(coerce_enum_member(CasillaProducerKind))]
"""Registry ``producer_kind`` token hydrated into a member."""


@dataclass(frozen=True, slots=True)
class CasillaProducerProvenance:
    """One lossless producer path for a revision-local casilla.

    The record retains the real schema declarations instead of copying or
    flattening their legal/source provenance, so a producer's own grounding
    stays visible rather than being restated on the casilla.
    """

    casilla: CasillaDefinition
    producer_kind: CasillaProducerKindField
    reason: str
    formula: FormulaDefinition | None = None
    binding: BindingDefinition | None = None

    @property
    def producer_legal_refs(self) -> tuple[LegalRefId, ...]:
        """Return the existing legal refs on this path's producer declaration."""
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
_CASILLA_GROUNDED_PRODUCER_KINDS: Final[frozenset[CasillaProducerKind]] = frozenset(
    {
        CasillaProducerKind.MANUAL,
        CasillaProducerKind.INFORMATIONAL,
        CasillaProducerKind.PROJECTION_ONLY,
    },
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
    producer_kind_by_casilla: Mapping[CasillaId, CasillaProducerKindField]
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
    binding: BindingDefinition | None = None,
) -> tuple[CasillaProducerProvenance, ...]:
    """Build the provenance records for one classified production path.

    A declaration that resolves to several real registry rows -- several formula
    declarations sharing one id -- emits one record per row, so their
    independent legal provenance stays visible. A
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
    bindings_by_id: Mapping[BindingId, BindingDefinition],
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
        return CasillaProducerKind.UPSTREAM, reason, _producer_provenance(casilla, CasillaProducerKind.UPSTREAM, reason)
    if binding.source is BindingSourceKind.RELATION_PREFILL:
        reason = f"relation production uses binding {binding.id!r} with source {binding.source.value!r}"
        return (
            CasillaProducerKind.RELATION,
            reason,
            _producer_provenance(casilla, CasillaProducerKind.RELATION, reason, binding=binding),
        )
    reason = f"upstream production uses binding {binding.id!r} with source {binding.source.value!r}"
    return (
        CasillaProducerKind.UPSTREAM,
        reason,
        _producer_provenance(casilla, CasillaProducerKind.UPSTREAM, reason, binding=binding),
    )


def _casilla_producer(
    casilla: CasillaDefinition,
    *,
    formulas_by_id: Mapping[FormulaId, Sequence[FormulaDefinition]],
    bindings_by_id: Mapping[BindingId, BindingDefinition],
) -> tuple[CasillaProducerKind, str, tuple[CasillaProducerProvenance, ...]]:
    """Classify one casilla's declared production path, with its reason.

    An explicit formula declaration wins over the input kind, because it is the
    narrower statement of the same fact. The classification is descriptive:
    validation still owns whether a formula direction is closed.
    """
    if casilla.formula is not None:
        reason = f"deterministic formula producer declaration {casilla.formula!r}"
        return (
            CasillaProducerKind.FORMULA,
            reason,
            _producer_provenance(
                casilla,
                CasillaProducerKind.FORMULA,
                reason,
                formulas=formulas_by_id.get(casilla.formula, ()),
            ),
        )
    if casilla.input_kind is InputKind.COMPUTED:
        reason = "computed casilla requires a deterministic formula producer"
        return CasillaProducerKind.FORMULA, reason, _producer_provenance(casilla, CasillaProducerKind.FORMULA, reason)
    if casilla.input_kind is InputKind.MANUAL:
        reason = (
            "manual production is intentional operator-supplied input; "
            "casilla legal_refs/source_refs remain its provenance"
        )
        return CasillaProducerKind.MANUAL, reason, _producer_provenance(casilla, CasillaProducerKind.MANUAL, reason)
    if casilla.input_kind is InputKind.BOUND:
        return _bound_casilla_producer(casilla, bindings_by_id=bindings_by_id)
    if casilla.input_kind is InputKind.PROJECTION_ONLY:
        reason = "projection-only casilla is populated exclusively from its canonical typed row"
        return (
            CasillaProducerKind.PROJECTION_ONLY,
            reason,
            _producer_provenance(casilla, CasillaProducerKind.PROJECTION_ONLY, reason),
        )
    reason = "informational casilla is intentionally not a calculation producer"
    return (
        CasillaProducerKind.INFORMATIONAL,
        reason,
        _producer_provenance(casilla, CasillaProducerKind.INFORMATIONAL, reason),
    )


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


class ModeloRevision(RegistryRevisionDeclaration):
    """A single versioned form layout and calculation ruleset for one modelo.

    The ``orden_aplicabilidad`` field names the legal-catalogue
    :class:`LegalReference` id(s) of the ordenes ministeriales that approve or
    amend this revision's form for its declared applicability window
    (e.g. ``["orden-hac-277-2026:art-3"]`` for M100 ejercicio 2025).

    The field is mandatory at validation time: every revision must cite the
    Ordenes that approve or amend the form for its applicability window.

    The governance stamp — ``engineered_by``, ``review_status``, ``reviewed_by``,
    ``reviewed_at``, ``reviewed_against`` — is the revision's *declared*
    provenance, optional and fail-closed to
    :attr:`RevisionReviewStatus.PENDING_REVIEW` on absence. ``reviewed_against``
    is the review's scope on an edition that names a predecessor: the predecessor
    the stated rows were reviewed against, required on a reviewed delta edition
    and refused everywhere else. Like ``predecessor`` it is excluded from
    serialisation when absent, so a revision without it dumps exactly as it did
    before the key existed. Its
    rules and the reasoning behind them live in :mod:`..schema_governance`,
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
    :func:`~dev.registry.compiler.validate_export_layout_coverage.validate_export_layout_record_coverage`
    measures. Reading this attribute for that purpose reports every materialised
    field as an unwritten position: it produced 22 confident false
    silent-data-loss findings across modelos 369, 390 and 131, twice, in trees
    that were already stamped and verified.

    ``predecessor`` is the revision's explicit declaration of the sibling
    edition it is authored relative to. A revision is delta-authored only when
    it declares one; nothing infers a predecessor from rows the revision leaves
    out, so a revision without the key is a full-copy revision stating every row
    itself. Absent reads as ``None`` and is excluded from serialisation, so a
    revision that does not declare the key dumps exactly as it did before the
    key existed. A :class:`NoPredecessor` is the grounded statement that the
    revision chains to no sibling at all, which absence cannot say. Either
    declaration is a claim about the whole revision, so it is manifest-only: a
    section fragment declaring it is refused. The modelo validates the declared
    edges together as a forest through
    :func:`~.revision_predecessor_forest.validate_predecessor_forest`, and
    each edge against the editions' validity dates through
    :func:`~.revision_predecessor_date_agreement.validate_predecessor_date_agreement`.

    ``casilla_source_refs`` is the edition's default source grounding for its
    casilla rows, declared once rather than restated on every row. It is a
    different fact from ``source_refs``, which cites what the edition as a whole
    stands on. The loader fills it into every casilla row, and every row's
    ``constraints`` table, that states no ``source_refs`` of its own. In the same
    pass ``orden_aplicabilidad`` fills the ``legal_refs`` of every row and
    constraints table that states none, because the edition's approving ordenes
    are already declared there once and a second field would duplicate them. A
    row or constraints table stating its own value keeps it whole: the default
    replaces nothing and is never merged into a stated value, and an explicitly
    empty value is refused rather than defaulted. The defaults are applied after
    predecessor inheritance, so a row inherited from a predecessor and stating
    none takes this edition's defaults, never the predecessor's; source
    references are declared per edition. Like ``predecessor`` it is excluded
    from serialisation when absent, and manifest-only, since it grounds rows
    across every fragment of the edition.

    A casilla row or its ``constraints`` table may instead state
    ``additional_source_refs``: the procedure or form citations that belong to
    the box's concept rather than to the edition's design. Such a table's
    ``source_refs`` is the edition's ``casilla_source_refs`` followed by those
    additions, duplicates removed and the default first. The additions travel
    with the row, so an inherited row extends the default of the edition it now
    sits in. A table stating both keys, additions that are empty, or additions
    in an edition declaring no ``casilla_source_refs`` is refused. The key is
    consumed by the loader and never reaches this model.

    ``binding_source_refs`` and ``formula_source_refs`` are the same fact for
    the binding and formula families, and carry the same member-side rule: a
    row stating no ``source_refs`` takes the edition default, a row stating
    ``additional_source_refs`` takes the default followed by its additions, and
    a row stating ``source_refs`` keeps them whole. Three fields rather than one
    because the three families are grounded in different documents -- a
    modelo's casillas in its diseno de registros, its bindings in that design's
    record layout, its formulas in the approving orden's instructions -- and one
    shared default would force an edition to restate on two families whenever
    the third differs. Each is independent: declaring one says nothing about
    the others, and an edition declaring none is exactly as it was before these
    keys existed.
    """

    localization_key: str = Field(min_length=1, exclude=True, repr=False)
    legal_refs: Annotated[LegalRefs, MANIFEST_ONLY]
    source_refs: SourceRefs
    # Required by validate_orden_aplicabilidad; kept default-empty so the
    # validator can report a grounded registry failure instead of a parse error.
    orden_aplicabilidad: Annotated[tuple[LegalRefId, ...], MANIFEST_ONLY] = ()
    casilla_source_refs: Annotated[SourceRefs | None, MANIFEST_ONLY] = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    binding_source_refs: Annotated[SourceRefs | None, MANIFEST_ONLY] = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    formula_source_refs: Annotated[SourceRefs | None, MANIFEST_ONLY] = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    parameters: Annotated[tuple[ParameterDefinition, ...], SCHEMA_FAMILY] = ()
    casillas: Annotated[tuple[CasillaDefinition, ...], SCHEMA_FAMILY] = ()
    formulas: Annotated[tuple[FormulaDefinition, ...], SCHEMA_FAMILY] = ()
    bindings: Annotated[tuple[BindingDefinition, ...], SCHEMA_FAMILY] = ()
    projection_endpoints: Annotated[tuple[ProjectionEndpointDeclaration, ...], SCHEMA_FAMILY] = ()
    export_layouts: Annotated[tuple[ExportLayoutDefinition, ...], SCHEMA_FAMILY] = ()
    extraction_profiles: Annotated[tuple[ExtractionProfileDefinition, ...], SCHEMA_FAMILY] = ()
    live_cross_references: Annotated[tuple[LiveCrossReferenceDecision, ...], SCHEMA_FAMILY] = ()
    workbook_parity_refs: Annotated[tuple[WorkbookParityReference, ...], SCHEMA_FAMILY] = ()
    verification_expectations: Annotated[tuple[VerificationExpectationDefinition, ...], SCHEMA_FAMILY] = ()
    application_links: Annotated[tuple[_ApplicationLinkDefinition, ...], SCHEMA_FAMILY] = ()
    deadline_windows: Annotated[tuple[_DeadlineWindowDefinition, ...], SCHEMA_FAMILY] = ()
    filing_schedules: Annotated[tuple[_ModeloScheduleDefinition, ...], SCHEMA_FAMILY] = ()
    constructs: Annotated[tuple[_ConstructDefinition, ...], SCHEMA_FAMILY] = ()
    dependency_classifications: Annotated[tuple[_DependencyClassificationDefinition, ...], SCHEMA_FAMILY] = ()
    applicability: Annotated[tuple[_ApplicabilityRuleDefinition, ...], SCHEMA_FAMILY] = ()
    completeness_manifest: CalculationCompletenessManifest | None = None
    verification_predicates: Annotated[tuple[VerificationPredicateDefinition, ...], SCHEMA_FAMILY] = ()
    continuidad_validation: ContinuidadValidationModeField = ContinuidadValidationMode.ADVISORY
    casilla_continuidad_evolutions: Annotated[tuple[CasillaContinuidadEvolutionDefinition, ...], CHAIN_FAMILY] = ()
    identifier_evolutions: Annotated[tuple[IdentifierEvolution, ...], CHAIN_FAMILY] = ()
    authority_grade: Annotated[RegistryAuthorityGradeField | None, MANIFEST_ONLY] = None
    family_dispositions: Annotated[Mapping[str, SchemaFamilyDispositionDeclaration], MANIFEST_ONLY, FROZEN_MAPPING] = (
        Field(default_factory=dict, validate_default=True)
    )
    engineered_by: Annotated[str | None, GOVERNANCE_STAMP] = None
    review_status: Annotated[RevisionReviewStatusField, GOVERNANCE_STAMP] = RevisionReviewStatus.PENDING_REVIEW
    reviewed_by: Annotated[str | None, GOVERNANCE_STAMP] = None
    reviewed_at: Annotated[date | None, GOVERNANCE_STAMP] = None
    reviewed_against: Annotated[RevisionId | None, GOVERNANCE_STAMP] = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )

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
        return resolve_modelo_localization((self.localization_key,), locale=locale)

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

    @model_validator(mode="after")
    def _validate_review_scope(self) -> ModeloRevision:
        """Bind a delta edition's review claim to the predecessor it was reviewed against."""
        validate_review_scope(
            revision_id=self.id,
            review_status=self.review_status,
            predecessor_id=self.predecessor.revision_id if isinstance(self.predecessor, DeclaredPredecessor) else None,
            reviewed_against=self.reviewed_against,
        )
        return self


REVISION_GOVERNANCE_FIELDS: frozenset[str] = governance_stamp_fields(ModeloRevision)
"""The :class:`ModeloRevision` fields that make up the declared governance stamp.

Derived from the :data:`GOVERNANCE_STAMP` marker on the field declarations rather
than hand-listed, and the sole input to the loader's placement refusal. See
:mod:`..schema_governance` for why the stamp must be readable in the manifest
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

Gated against the collection-shaped fields derived from the model annotations.
"""

REVISION_MANIFEST_ONLY_FIELDS: frozenset[str] = manifest_only_fields(ModeloRevision)
"""Every :class:`ModeloRevision` field that may be declared only in ``revision.toml``.

A superset of :data:`REVISION_GOVERNANCE_FIELDS` by construction, since
:class:`GovernanceStampMarker` is a :class:`ManifestOnlyMarker`. Beyond the
governance stamp it carries the legally load-bearing scalars ``legal_refs``,
``orden_aplicabilidad`` and ``valid_to``, which share the stamp's readability
hazard and raise its stakes, ``casilla_source_refs``, ``binding_source_refs``
and ``formula_source_refs``, which ground rows in
every fragment of the edition, and ``authority_grade``, which is a claim about how
far the whole revision's authority reaches and so belongs in the one file a
reviewer opens; :mod:`..schema_governance` records how a deep
fragment can otherwise supply a revision's legal grounding while
``revision.toml`` reads as though it did not.
"""


class ModeloDefinition(RegistryModel):
    """Declare a modelo and its complete collection of revision authorities."""

    id: ModeloId
    title_localization_key: str = Field(min_length=1, exclude=True, repr=False)
    official_name_localization_key: str = Field(min_length=1, exclude=True, repr=False)
    tax_domain: Annotated[TaxDomain, BeforeValidator(lambda v: TaxDomain(v) if isinstance(v, str) else v)]
    cadence: ModeloCadenceField
    jurisdiction: Literal["ES-AEAT"]
    calculation_class: CalculationClassField = CalculationClass.FILING
    output_sensitivity: SensitivityClassField = SensitivityClass.FINANCIAL
    capabilities: Annotated[frozenset[ModeloFilingCapability], BeforeValidator(frozenset)] = frozenset()
    legal_refs: LegalRefs
    source_refs: SourceRefs
    revisions: Annotated[Mapping[RevisionId, ModeloRevision], FROZEN_MAPPING]

    def get_title(self, locale: str) -> str:
        """Resolve the Modelo title from the shared catalogue."""
        return require_modelo_localization((self.title_localization_key,), locale=locale)

    def get_official_name(self, locale: str) -> str:
        """Resolve the official Modelo name from the shared catalogue."""
        return require_modelo_localization((self.official_name_localization_key,), locale=locale)

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
        validate_revision_predecessors(self.id, self.revisions)
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


class SupportedFilingYearsCatalogue(TemporalSupportEnvelope):
    """The registry's sole declaration of the filing years the product supports.

    Authored as bounds rather than an enumeration, because the two ends of the
    span do not carry the same force. ``floor`` is a hard gate: nothing resolves
    below it, and a request below it is outside what the product claims rather
    than a coverage gap somebody should close. ``horizon`` is the last year the
    corpus carries authored coverage for, and is deliberately not a gate -- a
    year above it remains answerable by carrying the newest declared revision
    forward, which a list of years has no way to say. ``hard_ceiling`` closes
    that open end where the product must stop somewhere, and stays absent where
    it need not.

    The span is contiguous by construction. A product that supports 2022 and
    2024 but not 2023 is not a state the law produces; the enumerated form could
    express it only by accident, and nothing ever did.

    :attr:`years` still enumerates the span, derived now rather than authored,
    so a consumer asking which years are supported keeps asking the same way. It
    is a plain property rather than a computed field on purpose: the published
    artifact is re-validated against this model on every read, and a serialised
    derivation would be refused there as an unexpected member.
    """

    def admits_filing_year(self, filing_year: int) -> bool:
        """Return whether a filing year is inside the product's hard gates.

        Above :attr:`horizon` is admitted while no ``hard_ceiling`` is declared:
        the newest revision carries forward, so the year is answerable even
        though no revision names it. Below :attr:`floor` is never admitted.
        """
        return self.admits_coordinate(filing_year)


class SociedadesAnnualManualCoverageStatus(StrEnum):
    """The independently auditable availability state of one annual manual."""

    AVAILABLE = "available"
    UNACQUIRED = "unacquired"
    UNPUBLISHED = "unpublished"


SociedadesAnnualManualCoverageStatusField = Annotated[
    SociedadesAnnualManualCoverageStatus,
    BeforeValidator(coerce_enum_member(SociedadesAnnualManualCoverageStatus)),
]
"""Registry token hydrated into a Sociedades annual-manual coverage status."""


class SociedadesAnnualManualCoverageDisposition(RegistryModel):
    """One exact-year outcome for the annual Sociedades manual corpus.

    This is documentary availability only. It is intentionally separate from
    Modelo 200 revision selection and filing capability.
    """

    year: int = Field(ge=2000, le=2099)
    status: SociedadesAnnualManualCoverageStatusField
    source_ref: SourceRefId | None = None
    official_locator: RegistryExternalLink
    observed_at: date
    acquisition_condition_key: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _validate_disposition(self) -> SociedadesAnnualManualCoverageDisposition:
        if self.status is SociedadesAnnualManualCoverageStatus.AVAILABLE:
            if self.source_ref is None:
                raise RegistryValidationError("available Sociedades manual coverage requires source_ref")
            if self.acquisition_condition_key is not None:
                raise RegistryValidationError(
                    "available Sociedades manual coverage must not declare acquisition_condition_key",
                )
        elif self.status is SociedadesAnnualManualCoverageStatus.UNACQUIRED:
            if self.source_ref is not None:
                raise RegistryValidationError("unacquired Sociedades manual coverage must not declare source_ref")
            if self.acquisition_condition_key is None:
                raise RegistryValidationError(
                    "unacquired Sociedades manual coverage requires acquisition_condition_key",
                )
        else:
            if self.source_ref is not None:
                raise RegistryValidationError("unpublished Sociedades manual coverage must not declare source_ref")
            if self.acquisition_condition_key is None:
                raise RegistryValidationError(
                    "unpublished Sociedades manual coverage requires acquisition_condition_key",
                )
        return self


class SociedadesAnnualManualCoverageCatalogue(RegistryModel):
    """One declarative coverage ledger for annual Sociedades manuals."""

    dispositions: tuple[SociedadesAnnualManualCoverageDisposition, ...] = Field(min_length=1)

    @field_validator("dispositions")
    @classmethod
    def _years_are_unique_and_ordered(
        cls,
        value: tuple[SociedadesAnnualManualCoverageDisposition, ...],
    ) -> tuple[SociedadesAnnualManualCoverageDisposition, ...]:
        years = tuple(disposition.year for disposition in value)
        if tuple(sorted(set(years))) != years:
            raise RegistryValidationError(
                "Sociedades annual manual coverage years must be unique and in ascending order",
            )
        return value


class RegistryCatalogues(RegistryModel):
    """Collect the registry-wide legal, source, fact, and support catalogues."""

    legal: Annotated[Mapping[LegalRefId, LegalReference], FROZEN_MAPPING]
    sources: Annotated[Mapping[SourceRefId, SourceReference], FROZEN_MAPPING]
    facts: GovernedFactCatalogue = Field(default_factory=GovernedFactCatalogue)
    convenio: ConvenioAuthority = Field(default_factory=ConvenioAuthority.empty)
    supplementary_ordenes: Annotated[Mapping[Modelo, M303AnnualOrdenAuthority], FROZEN_MAPPING] = Field(
        default_factory=dict[Modelo, M303AnnualOrdenAuthority],
        validate_default=True,
    )
    supported_filing_years: SupportedFilingYearsCatalogue | None = None
    sociedades_annual_manual_coverage: SociedadesAnnualManualCoverageCatalogue | None = None


class RegistrySnapshot(RegistryModel):
    """Represent the resolved immutable authority for one modelo filing coordinate."""

    modelo: ModeloDefinition
    revision: ModeloRevision
    filing_period: Period | None = None
    filing_year: FilingYear
    # Accepts normal period codes and declared event-period names; upstream
    # PeriodSelector + ModeloScheduleDefinition constrain the token set.
    period: RegistrySelectorPeriodCode
    legal: Mapping[LegalRefId, LegalReference]
    sources: Mapping[SourceRefId, SourceReference]
    extraction_profiles: Mapping[ExtractionProfileId, ExtractionProfileDefinition]
    live_cross_references: Mapping[CrossReferenceId, LiveCrossReferenceDecision]
    workbook_parity_refs: Mapping[WorkbookParityRefId, WorkbookParityReference]
    verification_expectations: Mapping[VerificationExpectationId, VerificationExpectationDefinition]
    application_links: Mapping[ApplicationLinkId, _ApplicationLinkDefinition]
    deadline_windows: Mapping[DeadlineWindowId, _DeadlineWindowDefinition]
    filing_schedules: Mapping[str, _ModeloScheduleDefinition]
    constructs: Mapping[ConstructId, _ConstructDefinition]
    dependency_classifications: Mapping[DependencyClassificationId, _DependencyClassificationDefinition]
    convenio: ConvenioAuthority = Field(default_factory=ConvenioAuthority.empty)
    supplementary_ordenes: Mapping[Modelo, M303AnnualOrdenAuthority] = Field(
        default_factory=dict[Modelo, M303AnnualOrdenAuthority],
    )

    @property
    def snapshot_ref(self) -> RegistrySnapshotRef:
        """Return this validated snapshot's canonical persisted coordinate."""
        return RegistrySnapshotRef(
            modelo=self.modelo.id,
            revision_id=self.revision.id,
            modelo_year=self.filing_year,
            period=self.period,
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
