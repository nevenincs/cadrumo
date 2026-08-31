"""Strict Pydantic records for the concept-oriented Terminology Handbook.

The schema implements the TBX / ISO 30042 three-tier model -- a
:class:`ConceptRecord` owns one :class:`LanguageSection` per output
language, and each language section owns one or more
:class:`TermSection`. SKOS relation vocabulary is borrowed at the
concept level (``broader`` / ``related`` authored shallowly;
``narrower`` derived at compile time, never double-authored) and SKOS
label vocabulary at the term level (``term_status`` from
``prefLabel`` / ``altLabel``; ``hidden_search_forms`` from
``hiddenLabel``).

Every model is strict, frozen, and forbids extra fields
(:data:`~cadrumo.core.STRICT_FROZEN_CONFIG`). The four-language
axis reuses the canonical
:class:`~cadrumo.core.external_constants.OutputLanguage`; the
Handbook-local closed axes (:class:`~dev.docs.terminology_handbook._enums.ConceptDomain`,
:class:`~cadrumo.core.ConceptLifecycle`,
:class:`~dev.docs.terminology_handbook._enums.TermStatus`) live beside this schema.

The ``narrower`` field is intentionally NOT settable from a fragment:
authoring it raises. The loader computes it as the inverse of every
fragment's ``broader`` after the full concept set is parsed
(see :func:`~dev.docs.terminology_handbook._loader.load_terminology_handbook`), which
is why :class:`ConceptRecord` keeps it as a plain field defaulting to
the empty tuple rather than rejecting it outright at the single-record
boundary.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

from cadrumo.application.corpus_search._terminology import CONCEPT_ID_MAX_LENGTH, CONCEPT_ID_MIN_LENGTH, CONCEPT_ID_PATTERN
from cadrumo.core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from cadrumo.core.concept_lifecycle import ConceptLifecycle
from cadrumo.core.external_constants import OutputLanguage

from ._enums import ConceptDomain, TermStatus
from .errors import TerminologyValidationError

__all__ = [
    "ConceptRecord",
    "LanguageSection",
    "LanguageSource",
    "SeedProvenance",
    "TermSection",
]

# Spanish-stem concept identifier: kebab-case, immutable, never reused. The
# shape is imported from the shipped product reader
# (cadrumo.application.corpus_search) rather than redeclared, so this
# authoring-side schema and the lean product-side reader can never drift on
# what a malformed concept_id looks like.
_ConceptId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=CONCEPT_ID_MIN_LENGTH,
        max_length=CONCEPT_ID_MAX_LENGTH,
        pattern=CONCEPT_ID_PATTERN,
    ),
]
# Typed reference into a source entity, e.g. ``modelo:303`` or
# ``iva-category:domestic_general``. Casilla references are deliberately not
# accepted as scalar domain refs; a future casilla link must carry structured
# ``modelo_id`` and ``casilla_id`` fields instead of another combined notation.
_DomainRef = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=2,
        max_length=128,
        pattern=r"^[a-z][a-z0-9.-]*:[A-Za-z0-9:._-]+$",
    ),
]
# Legal catalogue id, e.g. ``ley-37-1992:art-104``; resolution against the
# catalogue is the sibling validation step's concern, not this field's shape.
_LegalRef = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=2,
        max_length=128,
        pattern=r"^[a-z0-9][a-z0-9.-]*:[a-z0-9][A-Za-z0-9.-]*$",
    ),
]
_ShortDescription = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=240),
]
_Definition = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=2000),
]
_ScopeNote = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=1000),
]
_Citation = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=512),
]
_Label = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=160),
]
_SearchForm = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=160),
]
_Attribution = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=512),
]
_FreeShort = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]


def _coerce_str_enum(enum_type: type[StrEnum], value: object) -> object:
    """Coerce a raw TOML string into ``enum_type`` for a ``before`` validator."""
    if isinstance(value, enum_type):
        return value
    if isinstance(value, str):
        return enum_type(value)
    return value


class PartOfSpeech(StrEnum):
    """Closed grammatical category for a term (the TBX ``partOfSpeech``)."""

    NOUN = "noun"
    VERB = "verb"
    ADJECTIVE = "adjective"
    ADVERB = "adverb"
    PHRASE = "phrase"
    ABBREVIATION = "abbreviation"


class GrammaticalGender(StrEnum):
    """Closed grammatical gender (the TBX ``grammaticalGender``).

    Required by Spanish and Catalan term rendering; English and
    Hungarian terms leave it unset.
    """

    MASCULINE = "masculine"
    FEMININE = "feminine"
    COMMON = "common"


class SeedProvenance(BaseModel):
    """Attribution for a concept seeded from an external Tier-A source.

    Stamped on every value imported from IATE / UBTERM / EuroVoc so the
    shipped Handbook carries the licence-required attribution. Absent on
    concepts authored from scratch.
    """

    model_config = _STRICT_FROZEN

    source: _FreeShort
    attribution: _Attribution
    source_entry_id: _FreeShort | None = None


class TermSection(BaseModel):
    """One term inside a language section (the TBX term tier).

    ``label`` is the surface form; ``term_status`` is the SKOS
    normative status; ``hidden_search_forms`` are unaccented or
    misspelt variants that match in search but never render (the SKOS
    ``hiddenLabel``).
    """

    model_config = _STRICT_FROZEN

    label: _Label
    term_status: TermStatus
    part_of_speech: PartOfSpeech | None = None
    grammatical_gender: GrammaticalGender | None = None
    hidden_search_forms: tuple[_SearchForm, ...] = Field(default=())

    @field_validator("term_status", mode="before")
    @classmethod
    def _parse_term_status(cls, value: object) -> object:
        return _coerce_str_enum(TermStatus, value)

    @field_validator("part_of_speech", mode="before")
    @classmethod
    def _parse_part_of_speech(cls, value: object) -> object:
        return None if value is None else _coerce_str_enum(PartOfSpeech, value)

    @field_validator("grammatical_gender", mode="before")
    @classmethod
    def _parse_gender(cls, value: object) -> object:
        return None if value is None else _coerce_str_enum(GrammaticalGender, value)

    @model_validator(mode="after")
    def _validate_search_forms(self) -> Self:
        forms = self.hidden_search_forms
        if len(set(forms)) != len(forms):
            raise TerminologyValidationError(f"term {self.label!r}: duplicate hidden_search_forms")
        if self.label in forms:
            raise TerminologyValidationError(f"term {self.label!r}: label must not repeat in hidden_search_forms")
        return self


class LanguageSource(BaseModel):
    """Source citation grounding a language section's definition."""

    model_config = _STRICT_FROZEN

    citation: _Citation
    authority: _FreeShort | None = None


class LanguageSection(BaseModel):
    """One language section of a concept (the TBX language tier).

    ``short_description`` is first-class and required -- the tooltip /
    card text, never inferred from the first paragraph of ``definition``
    (the documented gettext failure mode). ``definition``, ``source``,
    and ``scope_note`` are optional at the single-record boundary; the
    completeness rule for approved concepts (an ``es`` grounded
    definition with a source citation) is enforced by the sibling
    validation step, not here.
    """

    model_config = _STRICT_FROZEN

    language: OutputLanguage
    short_description: _ShortDescription
    definition: _Definition | None = None
    scope_note: _ScopeNote | None = None
    source: LanguageSource | None = None
    terms: tuple[TermSection, ...] = Field(default=())

    @field_validator("language", mode="before")
    @classmethod
    def _parse_language(cls, value: object) -> object:
        return _coerce_str_enum(OutputLanguage, value)

    @model_validator(mode="after")
    def _validate_terms(self) -> Self:
        labels = tuple(term.label for term in self.terms)
        if len(set(labels)) != len(labels):
            duplicates = sorted({label for label in labels if labels.count(label) > 1})
            raise TerminologyValidationError(f"language {self.language.value!r}: duplicate term labels {duplicates!r}")
        preferred = [term for term in self.terms if term.term_status is TermStatus.PREFERRED]
        if len(preferred) > 1:
            raise TerminologyValidationError(
                f"language {self.language.value!r}: at most one preferred term, found {len(preferred)}",
            )
        return self


class ConceptRecord(BaseModel):
    """The compiled Terminology Handbook concept (the TBX concept tier).

    ``concept_id`` is the immutable Spanish stem; ``broader`` / ``related``
    are authored shallow SKOS relations and ``narrower`` is DERIVED by the
    loader from the inverse of every concept's ``broader`` -- authoring
    ``narrower`` in a fragment is rejected so the inverse is never
    double-booked. ``replaced_by`` is mandatory when ``lifecycle`` is
    ``RETIRED`` (the tombstone contract), optional when ``DEPRECATED`` (an
    in-use concept may name a recommended successor), and forbidden on a
    ``DRAFT`` or ``APPROVED`` concept (a live, non-discouraged concept has
    no successor). The successor's existence, non-retired target, and
    acyclicity are handbook-level gates, not per-record invariants.
    """

    model_config = _STRICT_FROZEN

    concept_id: _ConceptId
    domain: ConceptDomain
    lifecycle: ConceptLifecycle
    domain_refs: tuple[_DomainRef, ...] = Field(default=())
    legal_refs: tuple[_LegalRef, ...] = Field(default=())
    broader: tuple[_ConceptId, ...] = Field(default=())
    related: tuple[_ConceptId, ...] = Field(default=())
    narrower: tuple[_ConceptId, ...] = Field(default=())
    replaced_by: _ConceptId | None = None
    seed_provenance: SeedProvenance | None = None
    created_at: date
    updated_at: date
    languages: tuple[LanguageSection, ...] = Field(min_length=1)

    @field_validator("domain", mode="before")
    @classmethod
    def _parse_domain(cls, value: object) -> object:
        return _coerce_str_enum(ConceptDomain, value)

    @field_validator("lifecycle", mode="before")
    @classmethod
    def _parse_lifecycle(cls, value: object) -> object:
        return _coerce_str_enum(ConceptLifecycle, value)

    @field_validator("domain_refs")
    @classmethod
    def _reject_scalar_casilla_refs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        casilla_refs = tuple(ref for ref in value if ref.startswith("casilla:"))
        if casilla_refs:
            raise TerminologyValidationError(
                "concept domain_refs must not use scalar casilla references; "
                f"use a structured modelo_id/casilla_id surface instead: {casilla_refs!r}",
            )
        return value

    @model_validator(mode="after")
    def _validate_concept(self) -> Self:
        if self.concept_id in self.broader:
            raise TerminologyValidationError(f"concept {self.concept_id!r}: broader must not reference itself")
        if self.concept_id in self.related:
            raise TerminologyValidationError(f"concept {self.concept_id!r}: related must not reference itself")
        for axis_name, axis in (("broader", self.broader), ("related", self.related)):
            if len(set(axis)) != len(axis):
                raise TerminologyValidationError(f"concept {self.concept_id!r}: duplicate {axis_name} entries")
        if self.lifecycle is ConceptLifecycle.RETIRED and self.replaced_by is None:
            raise TerminologyValidationError(f"concept {self.concept_id!r}: retired concept requires replaced_by")
        if self.lifecycle in (ConceptLifecycle.DRAFT, ConceptLifecycle.APPROVED) and self.replaced_by is not None:
            raise TerminologyValidationError(
                f"concept {self.concept_id!r}: replaced_by is only valid on a deprecated or retired concept",
            )
        if self.replaced_by == self.concept_id:
            raise TerminologyValidationError(f"concept {self.concept_id!r}: replaced_by must not reference itself")
        languages = tuple(section.language for section in self.languages)
        if len(set(languages)) != len(languages):
            duplicates = sorted({lang.value for lang in languages if languages.count(lang) > 1})
            raise TerminologyValidationError(f"concept {self.concept_id!r}: duplicate language sections {duplicates!r}")
        return self

    @property
    def language_codes(self) -> tuple[OutputLanguage, ...]:
        """Output languages this concept declares a section for."""
        return tuple(section.language for section in self.languages)

    def section(self, language: OutputLanguage) -> LanguageSection:
        """Return the :class:`LanguageSection` for ``language``."""
        for section in self.languages:
            if section.language is language:
                return section
        raise TerminologyValidationError(f"concept {self.concept_id!r}: no {language.value!r} language section")
