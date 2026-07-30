"""Shared base classes and aliases for registry schema models.

The ``SensitivityClassField`` alias coerces registry ``output_sensitivity``
tokens into :class:`SensitivityClass` members before strict schema validation.
``RevisionReviewStatusField`` does the same for the per-revision governance
stamp's ``review_status`` token.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field, field_validator

from ....core import STRICT_FROZEN_CONFIG, RevisionReviewStatus
from ....core.classification import SensitivityClass
from ._errors import RegistryValidationError
from ._ids import LegalRefId, SourceRefId

__all__ = [
    "GOVERNANCE_STAMP",
    "MANIFEST_ONLY",
    "CalculationClass",
    "ContinuidadId",
    "DateAxis",
    "EvidenceTier",
    "FormulaOperator",
    "GovernanceStampMarker",
    "LegalRefs",
    "ManifestOnlyMarker",
    "ModeloFilingCapability",
    "RegistryModel",
    "ReviewStatus",
    "RevisionReviewStatusField",
    "SensitivityClassField",
    "SourceCitation",
    "SourceCitationText",
    "SourceRefs",
    "governance_stamp_fields",
    "manifest_only_fields",
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

Distinct from :data:`ReviewStatus` below, which is the legal catalogue's own
single-valued review vocabulary and governs a different subject.
"""


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


def manifest_only_fields(model: type[BaseModel]) -> frozenset[str]:
    """Return the names of ``model``'s fields marked :data:`MANIFEST_ONLY`.

    Includes every field marked :data:`GOVERNANCE_STAMP`, since the governance
    marker is a :class:`ManifestOnlyMarker`. Reads the marker back out of
    pydantic's retained ``Annotated`` metadata, so a field carrying either
    marker - including one added by a subclass - enrols itself without any
    second list being edited.
    """
    return frozenset(
        name
        for name, field in model.model_fields.items()
        if any(isinstance(meta, ManifestOnlyMarker) for meta in field.metadata)
    )


def governance_stamp_fields(model: type[BaseModel]) -> frozenset[str]:
    """Return the names of ``model``'s fields marked :data:`GOVERNANCE_STAMP`.

    The stamp vocabulary proper, narrower than :func:`manifest_only_fields`: a
    field pinned to the manifest for legal-grounding reasons is not part of the
    provenance claim and must not be written or read as one.
    """
    return frozenset(
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

ReviewStatus = Literal["reviewed"]
"""The legal catalogue's single-valued human review-stamp vocabulary.

Distinct from :data:`RevisionReviewStatusField` above, which coerces the
registry's per-revision governance-stamp token and governs a different
subject.
"""

DateAxis = Literal["filing_period", "devengo_date", "transaction_date", "invoice_date", "submission_date"]
EvidenceTier = Literal[
    "legal_authority",
    "official_source_guidance",
    "executable_parity_evidence",
    "layout_authority",
]
LegalRefs = Annotated[tuple[LegalRefId, ...], Field(min_length=1)]
SourceRefs = Annotated[tuple[SourceRefId, ...], Field(min_length=1)]
SourceCitationText = Annotated[tuple[str, ...], Field(min_length=1)]
ContinuidadId = Annotated[
    str,
    Field(
        min_length=1,
        max_length=128,
        pattern=r"^[a-z0-9][a-z0-9._:-]*[a-z0-9]$|^[a-z0-9]$",
    ),
]
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
    "m303_resolve_modulos_iva_cuota_devengada",
    "m303_resolve_modulos_iva_cuota_minima_pct",
]


class RegistryModel(BaseModel):
    """Strict frozen base for registry schema objects."""

    model_config = STRICT_FROZEN_CONFIG


class SourceCitation(RegistryModel):
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
