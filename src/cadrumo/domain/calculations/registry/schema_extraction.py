"""Extraction-profile schema contracts for registry revisions.

These :class:`~domain.calculations.registry._schema_base.RegistryModel`
definitions describe how a registry revision maps declaration PDFs, submitted
files, justificantes, and official workbooks into target casillas. The contract
records parser identity, accepted artefact kind, match strategy, confidence,
coverage, legal grounding, source grounding, and the explicit specimen /
round-trip flags that prevent silent provisional extraction.

The schema remains declarative authority only: it does not import parser
adapters, read artefacts, or run extraction. Registry validation checks local
reference closure and evidence sufficiency before
:class:`~domain.calculations.registry.RegistrySnapshot` exposes the profiles to
application and adapter consumers.

See Also:
    :class:`~domain.calculations.registry.ModeloRevision`
        Revision record that owns committed extraction-profile rows.
    :class:`~domain.calculations.registry.RegistrySnapshot`
        Validated filing-context view that exposes extraction profiles by id.
    :func:`~domain.calculations.registry._validate_record_sections.validate_extraction_profile_section`
        Record-section validator that checks casilla, export-field, legal, and
        source closure for each profile.
    :mod:`~domain.calculations.registry._validate_extraction_profiles`
        Artefact-kind, dotted-parser, bbox-anchor, specimen, and round-trip
        validator helpers for these contracts.
    :class:`~domain.calculations.registry.CasillaDefinition`
        Target casilla metadata each extraction target must reference.
    :class:`~domain.calculations.registry.LegalReference`
        Legal evidence rows cited through ``legal_refs``.
    :class:`~domain.calculations.registry.SourceReference`
        Source evidence rows cited through ``source_refs``.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BeforeValidator, Field, field_validator, model_validator

from ....core.casilla_id import CasillaId
from .errors import RegistryValidationError
from .ids import ExtractionProfileId
from .schema_base import LegalRefs, RegistryModel, SourceRefs, coerce_enum_member
from .schema_scalars import DecimalValue


class ExtractionSurface(StrEnum):
    """The artefact an extraction profile reads casilla values out of."""

    BORRADOR_PDF = "borrador_pdf"
    DECLARACION_PDF = "declaracion_pdf"
    JUSTIFICANTE_PDF = "justificante_pdf"
    EXPORT_RECORD = "export_record"
    OFFICIAL_WORKBOOK = "official_workbook"


ExtractionSurfaceField = Annotated[ExtractionSurface, BeforeValidator(coerce_enum_member(ExtractionSurface))]
"""Registry ``surface`` token hydrated into a member."""


class ExtractionArtefactKind(StrEnum):
    """A stored artefact an extraction profile will accept as its input.

    Deliberately NOT the same vocabulary as :class:`ExtractionSurface`, despite the
    overlap: a surface says what the profile was designed to read, an artefact kind says
    what a caller may hand it. ``submitted_file`` is an artefact and never a surface, and
    ``borrador_pdf`` is a surface with no artefact kind of its own.
    """

    SUBMITTED_FILE = "submitted_file"
    DECLARATION_PDF = "declaration_pdf"
    JUSTIFICANTE_PDF = "justificante_pdf"
    OFFICIAL_WORKBOOK = "official_workbook"


ExtractionArtefactKindField = Annotated[
    ExtractionArtefactKind, BeforeValidator(coerce_enum_member(ExtractionArtefactKind))
]
"""Registry ``accepted_artefact_kinds`` token hydrated into a member."""


class ExtractionMatchStrategy(StrEnum):
    """How a target casilla is located on the surface."""

    NUMERIC_CASILLA = "numeric_casilla"
    NAMED_LABEL = "named_label"
    BBOX_ANCHORED = "bbox_anchored"


ExtractionMatchStrategyField = Annotated[
    ExtractionMatchStrategy, BeforeValidator(coerce_enum_member(ExtractionMatchStrategy))
]
"""Registry ``match_strategy`` token hydrated into a member."""


class ExtractionValueKind(StrEnum):
    """What kind of value the extractor expects to read."""

    AMOUNT = "amount"
    TEXT = "text"
    ENUM = "enum"


ExtractionValueKindField = Annotated[ExtractionValueKind, BeforeValidator(coerce_enum_member(ExtractionValueKind))]
"""Registry ``value_kind`` token hydrated into a member."""


class BboxValueOffset(StrEnum):
    """Where the value sits relative to its anchoring box number."""

    LEFT_OF_NUMBER = "left_of_number"
    ABOVE_NUMBER = "above_number"
    RIGHT_OF_NUMBER = "right_of_number"


BboxValueOffsetField = Annotated[BboxValueOffset, BeforeValidator(coerce_enum_member(BboxValueOffset))]
"""Registry ``value_offset`` token hydrated into a member."""


class ExtractionConfidence(StrEnum):
    """How far a profile's output may be trusted without review."""

    STRICT = "strict"
    REVIEW_REQUIRED = "review_required"


ExtractionConfidenceField = Annotated[ExtractionConfidence, BeforeValidator(coerce_enum_member(ExtractionConfidence))]
"""Registry ``confidence`` token hydrated into a member."""


class ExtractionVerificationSource(StrEnum):
    """What evidence backs a profile's extraction accuracy.

    ``NOT_APPLICABLE`` and ``HISTORICAL_SUPPRESSION`` are distinct on purpose: the first
    says verification does not apply, the second says it was deliberately withheld for a
    historical revision. Collapsing them would report a suppression as an absence.
    """

    REAL_AEAT_CORPUS_PDF = "real_aeat_corpus_pdf"
    SYNTHETIC_FROM_AEAT_PUBLISHED_TEXT = "synthetic_from_aeat_published_text"
    HISTORICAL_SUPPRESSION = "historical_suppression"
    NOT_APPLICABLE = "not_applicable"


ExtractionVerificationSourceField = Annotated[
    ExtractionVerificationSource,
    BeforeValidator(coerce_enum_member(ExtractionVerificationSource)),
]
"""Registry ``verification_source`` token hydrated into a member."""


class BboxAnchorSpec(RegistryModel):
    r"""Spatial anchor configuration for the ``bbox_anchored`` extraction strategy."""

    box_number_pattern: str
    value_offset: BboxValueOffsetField
    anchor_x_min: float | None = None
    anchor_x_max: float | None = None
    value_x_max: float | None = None
    column_anchor: str | None = None

    @model_validator(mode="after")
    def _anchor_x_range_is_not_inverted(self) -> BboxAnchorSpec:
        if self.anchor_x_min is not None and self.anchor_x_max is not None and self.anchor_x_min > self.anchor_x_max:
            raise RegistryValidationError("bbox anchor_x_min must not exceed anchor_x_max")
        return self


class ExtractionTargetDefinition(RegistryModel):
    """Per-target descriptor for a registry extraction profile.

    ``value_kind`` is a PARSE DIRECTIVE, not a declaration of the target's type.
    It answers only "how is the captured token turned into a value?", and the
    parser branches on it exactly one way: ``amount`` gets Spanish-decimal
    parsing, the blank-box guard and the word-level positional pass, while
    everything else carries the raw token through unchanged.

    ``enum`` is therefore a documentation refinement of ``text`` and makes no
    enforceable claim about the value space. Nothing in this schema declares
    the permitted members of any target's enumeration, so there is no set to
    validate against and no consumer that would consult one. A reader meeting
    ``value_kind = "enum"`` should read "expected to be one of a closed set,
    and nothing checks that", not "constrained".

    The consequence is that ``value_kind`` and ``data_type`` answer different
    questions and cannot be compared for coherence. A target declaring ``enum``
    over a casilla whose ``data_type`` is ``text`` or ``integer`` is not
    incoherent -- the first says how to read the printed token, the second says
    what the casilla holds. Under this reading such targets are documentation
    rather than defects, which is why none of them is "corrected" to ``text``.

    Measured 2026-07-28 by walking every profile on every revision through the
    authority, eight targets declare ``enum`` and all eight sit over ``text`` or
    ``integer``. Four are on the ``declaracion_pdf`` surface and are the ones
    this ruling was raised against (Modelo 036 ``decl.event-kind``, Modelo 232
    ``decl.tipo-ejercicio`` in both revisions, Modelo 840
    ``decl.tipo-declaracion``). The other four are ``export_record`` targets on
    Modelo 180, and they are if anything a stronger case for the same reading:
    no consumer reads ``value_kind`` on that surface at all.

    Making ``enum`` load-bearing later is a real option, but it requires
    declaring the value space first -- a member list per target, grounded in
    AEAT's published values -- because a constraint no one can enumerate cannot
    be enforced. Until then the parser must treat ``enum`` and ``text``
    identically, which is pinned by
    ``adapters.inbound.declaracion.tests.test_extraction_value_kind_contract``.
    """

    casilla_id: CasillaId
    match_strategy: ExtractionMatchStrategyField
    value_kind: ExtractionValueKindField
    label_pattern: str | None = None
    bbox_anchor: BboxAnchorSpec | None = None

    @model_validator(mode="after")
    def _field_strategy_consistency(self) -> ExtractionTargetDefinition:
        if self.match_strategy == "named_label" and not self.label_pattern:
            raise RegistryValidationError("named_label extraction targets require label_pattern")
        if self.match_strategy == "numeric_casilla" and self.label_pattern is not None:
            raise RegistryValidationError("numeric_casilla extraction targets must not define label_pattern")
        if self.match_strategy == "bbox_anchored" and self.bbox_anchor is None:
            raise RegistryValidationError("bbox_anchored extraction targets require bbox_anchor")
        if self.match_strategy != "bbox_anchored" and self.bbox_anchor is not None:
            raise RegistryValidationError("bbox_anchor must be None for non-bbox_anchored strategies")
        return self


class ExtractionProfileDefinition(RegistryModel):
    """Registry extraction profile for declaration/borrador/workbook artefacts."""

    id: ExtractionProfileId
    surface: ExtractionSurfaceField
    artefact_kind: str
    accepted_artefact_kinds: tuple[ExtractionArtefactKindField, ...] = Field(min_length=1)
    parser: str
    target_casillas: tuple[ExtractionTargetDefinition, ...] = Field(min_length=1)
    confidence: ExtractionConfidenceField
    provisional_pending_specimen: bool = False
    corpus_round_trip_verified: bool = False
    verification_source: ExtractionVerificationSourceField | None = None
    min_coverage: DecimalValue = Field(gt=Decimal("0"), le=Decimal("1"))
    failure_semantics: Literal["fail_hard"]
    legal_refs: LegalRefs
    source_refs: SourceRefs

    @field_validator("accepted_artefact_kinds")
    @classmethod
    def _accepted_artefact_kinds_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError("extraction profile accepted_artefact_kinds entries must be unique")
        return value

    @field_validator("target_casillas")
    @classmethod
    def _target_casillas_unique(
        cls,
        value: tuple[ExtractionTargetDefinition, ...],
    ) -> tuple[ExtractionTargetDefinition, ...]:
        casilla_ids = [target.casilla_id for target in value]
        if len(set(casilla_ids)) != len(casilla_ids):
            raise RegistryValidationError("extraction profile target_casillas casilla_id entries must be unique")
        return value


__all__ = ["BboxAnchorSpec", "ExtractionProfileDefinition", "ExtractionTargetDefinition"]
