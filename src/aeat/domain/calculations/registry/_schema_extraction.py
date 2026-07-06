"""Extraction-profile schema contracts for registry revisions."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import Field, field_validator, model_validator

from ._errors import RegistryValidationError
from ._ids import CasillaId, ExtractionProfileId
from ._schema_base import LegalRefs, RegistryModel, SourceRefs
from ._schema_scalars import DecimalValue


class BboxAnchorSpec(RegistryModel):
    r"""Spatial anchor configuration for the ``bbox_anchored`` extraction strategy."""

    box_number_pattern: str
    value_offset: Literal["left_of_number", "above_number", "right_of_number"]
    anchor_x_min: float | None = None
    anchor_x_max: float | None = None
    value_x_max: float | None = None
    column_anchor: str | None = None


class ExtractionTargetDefinition(RegistryModel):
    """Per-target descriptor for a registry extraction profile."""

    casilla_id: CasillaId
    match_strategy: Literal["numeric_casilla", "named_label", "bbox_anchored"]
    value_kind: Literal["amount", "text", "enum"]
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
    surface: Literal["borrador_pdf", "declaracion_pdf", "justificante_pdf", "export_record", "official_workbook"]
    artefact_kind: str
    accepted_artefact_kinds: tuple[
        Literal["submitted_file", "declaration_pdf", "justificante_pdf", "official_workbook"],
        ...,
    ] = Field(min_length=1)
    parser: str
    target_casillas: tuple[ExtractionTargetDefinition, ...] = Field(min_length=1)
    confidence: Literal["strict", "review_required"]
    provisional_pending_specimen: bool = False
    corpus_round_trip_verified: bool = False
    verification_source: (
        Literal[
            "real_aeat_corpus_pdf",
            "synthetic_from_aeat_published_text",
            "historical_suppression",
            "not_applicable",
        ]
        | None
    ) = None
    min_coverage: DecimalValue = Field(ge=Decimal("0"), le=Decimal("1"))
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
