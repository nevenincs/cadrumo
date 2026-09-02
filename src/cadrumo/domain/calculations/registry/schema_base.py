"""Shared base classes and aliases for registry schema models.

The ``SensitivityClassField`` alias coerces registry ``output_sensitivity``
tokens into :class:`SensitivityClass` members before strict schema validation.
``RevisionReviewStatusField`` does the same for the per-revision governance
stamp's ``review_status`` token, and ``RegistryAuthorityGradeField`` for the
per-revision ``authority_grade`` token.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal, get_args, get_origin

from pydantic import BaseModel, BeforeValidator, Field, TypeAdapter, field_validator

from ....core.authority_grade import RegistryAuthorityGrade
from ....core.classification.policies import SensitivityClass
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.revision_review import RevisionReviewStatus
from .errors import RegistryValidationError
from .ids import LegalRefId, SourceRefId

__all__ = [
    "GOVERNANCE_STAMP",
    "MANIFEST_ONLY",
    "REGISTRY_SOURCE_GROUNDING_TIERS",
    "SCHEMA_FAMILY",
    "CalculationClass",
    "DateAxis",
    "EvidenceTier",
    "FormulaOperator",
    "GovernanceStampMarker",
    "LegalRefs",
    "ManifestOnlyMarker",
    "ModeloFilingCapability",
    "RegistryAuthorityGradeField",
    "RegistryModel",
    "RevisionReviewStatusField",
    "SchemaFamilyMarker",
    "SensitivityClassField",
    "SourceCitation",
    "SourceCitationText",
    "SourceRefs",
    "coerce_decimal_tuple",
    "coerce_enum_member",
    "coerce_enum_tuple",
    "collection_shaped_fields",
    "governance_stamp_fields",
    "manifest_only_fields",
    "schema_family_enrollment_failures",
    "schema_family_fields",
]


def _coerce_sensitivity_class(value: object) -> object:
    if isinstance(value, SensitivityClass):
        return value
    if isinstance(value, str):
        return SensitivityClass(value)
    return value


SensitivityClassField = Annotated[SensitivityClass, BeforeValidator(_coerce_sensitivity_class)]


def _coerce_revision_review_status(value: object) -> object:
    if isinstance(value, RevisionReviewStatus):
        return value
    if isinstance(value, str):
        return RevisionReviewStatus(value)
    return value


RevisionReviewStatusField = Annotated[RevisionReviewStatus, BeforeValidator(_coerce_revision_review_status)]
"""Registry ``review_status`` token coerced into a :class:`RevisionReviewStatus` member.

Registry schema models validate under ``strict=True``, which refuses a bare TOML
string for an enum-typed field, so the governance stamp needs this coercion hop
exactly as ``output_sensitivity`` does. An unknown token raises out of the enum
constructor and surfaces as a registry load failure naming the offending value.

Shared with the legal catalogue rows, which reach the same vocabulary.
"""


def _coerce_registry_authority_grade(value: object) -> object:
    if isinstance(value, RegistryAuthorityGrade):
        return value
    if isinstance(value, str):
        return RegistryAuthorityGrade(value)
    return value


RegistryAuthorityGradeField = Annotated[RegistryAuthorityGrade, BeforeValidator(_coerce_registry_authority_grade)]
"""Registry ``authority_grade`` token coerced into a :class:`RegistryAuthorityGrade` member.

The same coercion hop :data:`RevisionReviewStatusField` needs, for the same
reason: registry schema models validate under ``strict=True``, which refuses a
bare TOML string for an enum-typed field. Registry TOML therefore stays
free-form and the loader boundary hydrates the typed member, so an unknown grade
surfaces as a registry load failure naming the offending value rather than
reaching a downstream branch on a string.

Distinct subject from :data:`RevisionReviewStatusField`: that vocabulary records
who signed a revision off, this one records how far the revision's authority
reaches.
"""


#: A parsed TOML tuple/list, typed at the boundary rather than left with the
#: ``Unknown`` element type an ``isinstance(value, (tuple, list))`` narrow of a
#: bare ``object`` carries -- both coercion hops below iterate a validated,
#: fully-typed ``list[object]`` through this one adapter.
_OBJECT_LIST_ADAPTER: TypeAdapter[list[object]] = TypeAdapter(list[object])


def coerce_enum_member(enum_cls: type) -> Callable[[object], object]:
    """Return a scalar coercion hop for one enum-typed field.

    The generated function is the identical shape as :func:`_coerce_sensitivity_class`
    and its siblings above -- registry schema models validate under
    ``strict=True``, which refuses a bare TOML string for an enum-typed field, so
    the loader boundary hydrates the typed member here. An unknown token still
    raises out of the enum constructor and surfaces as a registry load failure
    naming the offending value.

    Factored out because the ledger binding-selector families (IVA, OSS/IOSS,
    retenciones) need this same coercion for several enum types each; hand-
    duplicating the four-line function per type is the drift risk this project's
    architecture rules warn against, not the discipline they ask for.
    """

    def _coerce(value: object) -> object:
        if isinstance(value, enum_cls):
            return value
        if isinstance(value, str):
            return enum_cls(value)
        return value

    return _coerce


def coerce_enum_tuple(enum_cls: type) -> Callable[[object], object]:
    """Return a ``tuple[enum_cls, ...]`` coercion hop, element-wise.

    Same rationale and mechanism as :func:`coerce_enum_member`, applied to each
    element of an enum-typed tuple field rather than to a scalar field: strict
    mode refuses a bare string for an enum-typed tuple ELEMENT exactly as it
    refuses one for a scalar enum field, so each element is coerced
    independently and an unknown token still raises out of the enum
    constructor unchanged.
    """

    def _coerce(value: object) -> object:
        if not isinstance(value, (tuple, list)):
            return value
        items = _OBJECT_LIST_ADAPTER.validate_python(value)
        return tuple(
            item if isinstance(item, enum_cls) else enum_cls(item) if isinstance(item, str) else item for item in items
        )

    return _coerce


def coerce_decimal_tuple(value: object) -> object:
    """Coerce a ``tuple[Decimal, ...]`` field's elements from TOML string/int tokens.

    TOML has no native ``Decimal`` type; committed registry TOML stores a rate
    tuple as quoted decimal strings (e.g. ``["0.21"]``) to avoid float
    imprecision. Strict mode refuses that bare string for a ``Decimal``-typed
    tuple element exactly as it refuses one for any other strict-typed element,
    so this is the same coercion-hop mechanism as :func:`coerce_enum_tuple`,
    targeting ``Decimal`` instead of an enum. An unparseable token still raises
    out of the ``Decimal`` constructor and surfaces as a registry load failure.
    """
    if not isinstance(value, (tuple, list)):
        return value
    items = _OBJECT_LIST_ADAPTER.validate_python(value)
    return tuple(
        item if isinstance(item, Decimal) else Decimal(item) if isinstance(item, (str, int)) else item for item in items
    )


@dataclass(frozen=True, slots=True)
class ManifestOnlyMarker:
    """``Annotated`` metadata pinning one field to the revision's own manifest.

    A revision compiles from its ``revision.toml`` manifest plus up to several
    hundred per-section fragment files, and the merge takes a scalar from
    whichever file declares it. A field marked here is refused inside a section
    fragment: it is a statement about the WHOLE revision, so it has to be
    readable in the one place a reviewer opens, not merged in from a file
    thousands deep in a fragment tree where the manifest still reads silent on
    it.

    Manifest-only-ness is not derivable from a field's annotation - the marked
    fields are a free-text attribution, a closed enum, a date and two id tuples,
    shapes a dozen unmarked fields on the same model share - so the enrolment
    has to be declared. Declaring it *at the field* rather than in a hand-kept
    list is the point: the list can be forgotten when a field is added, and it
    is the sole input to the loader's placement refusal, so a forgotten entry
    silently reopens the laundering route the refusal exists to close.
    """


MANIFEST_ONLY = ManifestOnlyMarker()
"""The singleton marker attached to every manifest-only field declaration."""


@dataclass(frozen=True, slots=True)
class GovernanceStampMarker(ManifestOnlyMarker):
    """``Annotated`` metadata enrolling one field into the governance stamp.

    Narrower than :class:`ManifestOnlyMarker`, and a subclass of it rather than
    a sibling. Governance provenance and legal grounding are different subjects
    - one is a claim about who built and signed off a revision, the other is the
    law the revision stands on - and only the governance fields belong to the
    stamp vocabulary the conformance tooling reads and writes. What they share
    is the placement guarantee, and expressing that as a type relation rather
    than a second marker on the same fields is what keeps it: a governance field
    added tomorrow cannot be manifest-pinned by memory, because it already is
    one by construction.
    """


GOVERNANCE_STAMP = GovernanceStampMarker()
"""The singleton marker attached to every governance-stamp field declaration."""


@dataclass(frozen=True, slots=True)
class SchemaFamilyMarker:
    """``Annotated`` metadata enrolling one field as a revision schema family.

    A family is one of the revision's declared content collections - its
    casillas, its formulas, its bindings, its export layouts. Coverage asks one
    question of each: is it populated, is it honestly not applicable, or is it
    empty for a reason nobody has recorded. The marker is what makes a field
    subject to that question.

    Unrelated to :class:`ManifestOnlyMarker`, and deliberately not a subclass of
    it. Placement asks WHERE a field may be written; enrolment asks WHETHER a
    field's emptiness is a coverage claim. The two sets barely intersect: the
    manifest-only fields are scalars, and the families are collections. A marker
    hierarchy between them would assert a relationship that does not exist.

    Family-ness IS derivable from the annotation - a family is exactly a
    ``tuple`` of a schema model - which is why the marker carries a completeness
    check rather than standing alone: :func:`schema_family_fields` reads the
    declarations, the check compares that against the shape-derived set, and a
    collection added without the marker reds. Marking alone would catch a rename
    and never an addition; deriving alone would enrol collections nobody meant
    as families. Requiring both is what makes the enrolment exhaustive AND
    deliberate.
    """


SCHEMA_FAMILY = SchemaFamilyMarker()
"""The singleton marker attached to every revision schema-family declaration."""


def manifest_only_fields(model: type[BaseModel]) -> frozenset[str]:
    """Return the names of ``model``'s fields marked :data:`MANIFEST_ONLY`.

    Includes every field marked :data:`GOVERNANCE_STAMP`, since the governance
    marker is a :class:`ManifestOnlyMarker`. Reads the marker back out of
    pydantic's retained ``Annotated`` metadata, so a field carrying either
    marker - including one added by a subclass - enrols itself without any
    second list being edited.
    """
    return frozenset[str](
        name
        for name, field in model.model_fields.items()
        if any(isinstance(meta, ManifestOnlyMarker) for meta in field.metadata)
    )


def schema_family_fields(model: type[BaseModel]) -> frozenset[str]:
    """Return the names of ``model``'s fields marked :data:`SCHEMA_FAMILY`.

    The declared enrolment. :func:`collection_shaped_fields` computes the set
    this one is meant to equal; the gate that compares them is what stops a new
    collection shipping outside coverage.
    """
    return frozenset[str](
        name
        for name, field in model.model_fields.items()
        if any(isinstance(meta, SchemaFamilyMarker) for meta in field.metadata)
    )


def collection_shaped_fields(model: type[BaseModel]) -> frozenset[str]:
    """Return ``model``'s fields annotated as a ``tuple`` of a schema model.

    The shape-derived counterpart to :func:`schema_family_fields`, computed from
    the annotation and nothing else, so it cannot be forgotten when a field is
    added.

    A singleton sub-model and a required value object are deliberately outside
    this set even though both hold schema content. The coverage question is
    about an EMPTY collection, and neither shape can be empty in the sense the
    question means: a singleton is present or absent, and a required value
    object is always present. Folding them in would need a second disposition
    vocabulary for a different question wearing the same words.
    """
    families: set[str] = set()
    for name, field in model.model_fields.items():
        if get_origin(field.annotation) is not tuple:
            continue
        args = get_args(field.annotation)
        element = args[0] if args else None
        if isinstance(element, type) and issubclass(element, BaseModel):
            families.add(name)
    return frozenset(families)


def schema_family_enrollment_failures(model: type[BaseModel]) -> tuple[str, ...]:
    """Return why ``model``'s declared families disagree with its shape-derived ones.

    The completeness rule of the marker mechanism, expressed as a function rather
    than inline in a test so the thing proven to bite is the thing that runs.

    Accumulating rather than raising, and reporting both directions separately,
    because the two failures have opposite fixes: an unmarked collection needs
    the marker, while a marked non-collection needs the marker removed or the
    field's shape reconsidered. A single combined message would leave the author
    to work out which.

    Args:
        model: The schema model whose family enrolment to check.

    Returns:
        One message per disagreement, empty when the enrolment is complete.
    """
    declared = schema_family_fields(model)
    shaped = collection_shaped_fields(model)
    failures = [
        f"field {name!r} is a collection of schema models but is not marked SCHEMA_FAMILY, so its emptiness "
        f"would never be reported as a coverage disposition"
        for name in sorted(shaped - declared)
    ]
    failures.extend(
        f"field {name!r} is marked SCHEMA_FAMILY but is not a collection of schema models, so it has no "
        f"emptiness for a disposition to describe"
        for name in sorted(declared - shaped)
    )
    return tuple(failures)


def governance_stamp_fields(model: type[BaseModel]) -> frozenset[str]:
    """Return the names of ``model``'s fields marked :data:`GOVERNANCE_STAMP`.

    The stamp vocabulary proper, narrower than :func:`manifest_only_fields`: a
    field pinned to the manifest for legal-grounding reasons is not part of the
    provenance claim and must not be written or read as one.
    """
    return frozenset[str](
        name
        for name, field in model.model_fields.items()
        if any(isinstance(meta, GovernanceStampMarker) for meta in field.metadata)
    )


CalculationClass = Literal["filing", "informative", "summary"]
ModeloFilingCapability = Literal["borrador", "renta_ledger_default"]
"""Discriminator for the calculation role of a ModeloDefinition.

- ``filing``: The modelo computes and submits filing-grade amounts.
  Most modelos fall into this class.
- ``informative``: The modelo collects and reports data but does not
  compute filing-grade amounts. Revisions must have empty ``formulas``
  and empty ``relations``; every casilla must be ``manual`` or
  ``informational``. Modelo 232 is the canonical example.
- ``summary``: The modelo aggregates other modelos (e.g. 390 over 303)
  and may declare cross-model relations but is not a filing modelo.
"""


DesignAuthority = Literal["authoritative", "provenance_only"]
"""Whether a bundled record design is a machine-readable authority or provenance.

``authoritative`` is the default and the case for every design a revision may
cite as an export-layout authority. ``provenance_only`` marks a design the
corpus keeps as evidence but which the registry must never treat as a layout
map: the raw BOE ordenes that carry a modelo's design as an annex and so refuse
to parse from wire position 1, and a superseded draft AEAT published alongside a
definitive edition. The distinction has to be declared rather than inferred --
parse failure alone cannot tell "this is provenance" from "this design is
broken", and neither can the absence of a record_design_epoch, which also covers
designs whose selection window is merely not assigned yet.
"""

DateAxis = Literal["filing_period", "devengo_date", "transaction_date", "invoice_date", "submission_date"]
class EvidenceTier(StrEnum):
    """What kind of authority grounds a registry entity."""

    LEGAL_AUTHORITY = "legal_authority"
    """The law itself: a BOE provision or the orden that approves a design."""

    OFFICIAL_SOURCE_GUIDANCE = "official_source_guidance"
    """AEAT-published guidance, instructions or a form specification."""

    EXECUTABLE_PARITY_EVIDENCE = "executable_parity_evidence"
    """An artefact that can be executed and compared, such as a safe calculator."""

    LAYOUT_AUTHORITY = "layout_authority"
    """A published record design fixing field offsets, widths and order."""


EvidenceTierField = Annotated[EvidenceTier, BeforeValidator(coerce_enum_member(EvidenceTier))]
"""Registry ``evidence_tier`` token hydrated into a member.

Registry schema models validate strictly, which refuses a bare TOML string for an
enum-typed field, so the token is coerced at the boundary.
"""

#: The tiers that ground a registry entity on AEAT-published MATERIAL, as distinct
#: from the law itself and from executable parity artefacts. Three section validators
#: require exactly this pair through ``require_any_source_tier``. Derived from the
#: vocabulary above rather than restated, so a tier added there cannot leave this
#: narrowing silently measuring the old set.
REGISTRY_SOURCE_GROUNDING_TIERS: tuple[EvidenceTier, ...] = (
    EvidenceTier.OFFICIAL_SOURCE_GUIDANCE,
    EvidenceTier.LAYOUT_AUTHORITY,
)

class CorpusTier(StrEnum):
    """How much of a legal instrument the bundled corpus artefact carries."""

    FULL_CONSOLIDATED = "full_consolidated"
    """The whole consolidated instrument, not a provision-suffixed extract."""

    PROVISION_EXCERPT = "provision_excerpt"
    """A single provision lifted from the instrument."""


CorpusTierField = Annotated[CorpusTier, BeforeValidator(coerce_enum_member(CorpusTier))]
"""Registry ``corpus_tier`` token hydrated into a member.

Registry schema models validate strictly, which refuses a bare TOML string for an
enum-typed field, so the token is coerced at the boundary.
"""

class PublishingAuthority(StrEnum):
    """Who published the instrument or artefact a registry row cites."""

    BOE = "boe"
    """The Boletin Oficial del Estado, where Spanish law is promulgated."""

    AEAT = "aeat"
    """The Agencia Estatal de Administracion Tributaria."""

    EU = "eu"
    """A European Union instrument."""

    AUTONOMOUS_COMMUNITY = "autonomous_community"
    """An autonomous community exercising its own competence."""

    OTHER = "other"
    """A publisher outside the four named above, recorded rather than assumed."""


PublishingAuthorityField = Annotated[
    PublishingAuthority, BeforeValidator(coerce_enum_member(PublishingAuthority))
]
"""Registry ``authority`` token hydrated into a member.

Registry schema models validate strictly, which refuses a bare TOML string for an
enum-typed field, so the token is coerced at the boundary.
"""

LegalRefs = Annotated[tuple[LegalRefId, ...], Field(min_length=1)]
SourceRefs = Annotated[tuple[SourceRefId, ...], Field(min_length=1)]
SourceCitationText = Annotated[tuple[str, ...], Field(min_length=1)]
FormulaOperator = Literal[
    "add",
    "subtract",
    "multiply",
    "divide",
    "percent",
    "less_than",
    "less_equal",
    "greater_than",
    "greater_equal",
    "equal",
    "sum",
    "min",
    "max",
    "clamp",
    "negate",
    "copy",
    "if_then_else",
    "lookup_parameter",
    "lookup_bracket",
    "lookup_bracket_by_ccaa",
    "m100_resolve_renta_inmobiliaria_imputada",
    "irnr_resolve_tipo_gravamen",
    "m210_resolve_base_imponible",
    "lookup_parameter_by_entity_type",
    "lookup_bracket_by_entity_type",
    "previous_period_value",
    "previous_period_sum",
    "cross_model_sum",
    "age_at_year_end",
    "m131_resolve_modulos_previo",
    "m131_resolve_modulos_minoracion_empleo",
    "m131_resolve_modulos_indice_exceso",
    "m131_resolve_modulos_indices_generales",
    "m131_resolve_modulos_pequena_dimension_ignorado_flag",
    "m131_resolve_modulos_temporada_inicio_conflicto_flag",
    "m100_resolve_eo_agraria_indices_correctores",
]


class RegistryModel(BaseModel):
    """Strict frozen base for registry schema objects."""

    model_config = STRICT_FROZEN_CONFIG


class SourceCitation(RegistryModel):
    """A source reference paired with the exact text required to ground it."""

    source_ref: SourceRefId
    required_text: SourceCitationText

    @field_validator("required_text")
    @classmethod
    def _required_text_non_empty(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not item.strip() for item in value):
            raise RegistryValidationError("source citation required_text entries must be non-empty")
        if len(set(value)) != len(value):
            raise RegistryValidationError("source citation required_text entries must be unique")
        return value
