"""Recorded observations that bound the pipeline from above without being baselines.

A reference point is a figure someone measured, kept because it answers "is the
pipeline design capable of this at all?". It is deliberately NOT a
:class:`~dev.ingest_harness._result.ResultRow`: it was not produced by this harness
against this key's denominators, so giving it the same type would let it flow
into a baseline calculation that must never see it.

The distinction is enforced by shape rather than by convention. A reference point
has no accuracy property, its denominator is recorded as the reporter stated it
alongside the key's own count for the same document, and it carries its caveats
as a required non-empty field.
"""

from __future__ import annotations

from typing import Final, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ._caveats import caveats_for_document
from ._key import CorpusKey
from ._result import EngineRoute, ModelTier, PipelineStage

__all__ = [
    "SONNET_4_6_REC_DOM_IMG_008",
    "ReferencePoint",
    "reference_points_with_key_context",
]

_STRICT = ConfigDict(frozen=True, strict=True, extra="forbid")


class ReferencePoint(BaseModel):
    """One recorded upper-bound observation, with the conditions that qualify it.

    Attributes:
        reported_matched: Fields the reporter counted as correct.
        reported_denominator: The denominator the reporter used. Recorded as
            stated, and compared against the key's own authored-field count for
            the same document, because a denominator that is not the key's is a
            figure over a set a later reader cannot reconstruct.
        caveats: Required and non-empty. A reference point whose conditions are
            not stated is indistinguishable from a baseline, which is precisely
            the confusion this type exists to prevent.
    """

    model_config = _STRICT

    label: str = Field(min_length=1)
    doc_id: str = Field(min_length=1)
    stage: PipelineStage
    engine_route: EngineRoute
    model_identity: str = Field(min_length=1)
    model_revision: str = Field(min_length=1)
    model_tier: ModelTier
    reported_matched: int = Field(ge=0)
    reported_denominator: int = Field(gt=0)
    fabricated: int = Field(ge=0)
    elapsed_seconds: float = Field(gt=0)
    caveats: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _must_not_be_baseline_eligible(self) -> Self:
        """A reference point is an upper bound by definition.

        Recording one at a baseline-eligible tier would silently promote it into
        the set that sets acceptance floors -- so the type refuses the tier
        rather than trusting every future caller to pick correctly.
        """
        if self.model_tier.is_baseline_eligible:
            raise ValueError(
                f"{self.label}: a reference point must be recorded at a non-baseline tier; "
                f"{self.model_tier.value} is baseline-eligible and would set an acceptance floor "
                "no shipped configuration can meet",
            )
        if self.reported_matched > self.reported_denominator:
            raise ValueError(f"{self.label}: matched exceeds the reported denominator")
        return self


SONNET_4_6_REC_DOM_IMG_008: Final = ReferencePoint(
    label="claude-sonnet-4-6 / REC-DOM-IMG-008",
    doc_id="REC-DOM-IMG-008",
    stage=PipelineStage.S1_TRANSCRIPTION,
    engine_route=EngineRoute.GATED_CLOUD,
    model_identity="claude-sonnet-4-6",
    model_revision="unrecorded-at-measurement-time",
    model_tier=ModelTier.UPPER_REFERENCE,
    reported_matched=7,
    reported_denominator=8,
    fabricated=0,
    elapsed_seconds=4.4,
    caveats=(
        "UPPER REFERENCE POINT, NOT A BASELINE. A frontier-tier model bounds the pipeline design "
        "from above; the shipping baseline is re-established at the design target (the on-host 2B-4B "
        "class and its Haiku-class cloud proxy).",
        "CONFOUNDED BY A PROMPT/GROUNDING MISMATCH. Measured BEFORE the field-form contract landed, "
        "so the single miss is a printed-percent form mismatch that penalised instruction-compliance "
        "rather than reading. The figure understates the model on reading and cannot be compared "
        "like-for-like against post-contract runs.",
        "DENOMINATOR IS NOT THE KEY'S. The reported 8 fields are a probe-selected subset; the pinned "
        "key authors 20 non-null fields for this document (and 5 null-truth fabrication traps). The "
        "subset is not defined by the corpus, so '7 of 8' cannot be reconstructed from the key and "
        "must never be restated as a key-denominated accuracy.",
        "MODEL REVISION WAS NOT RECORDED at measurement time, so this observation cannot be "
        "reproduced against a pinned model build.",
    ),
)
"""The first recorded reference point: a frontier read of one Spanish photograph.

Kept because it establishes that the staged design can recover this document's
figures with zero fabrication, which is a fact about the PIPELINE. It says
nothing about the shipped on-host model, and three separate conditions in its
caveats are needed before the number means anything at all.
"""


def reference_points_with_key_context(key: CorpusKey) -> tuple[tuple[ReferencePoint, tuple[str, ...]], ...]:
    """Pair each reference point with the caveats its document's own properties add.

    The recorded caveats state the conditions of the measurement; the key adds
    the conditions of the document -- above all the Spanish optimism bias, which
    applies to this observation because the document is a Spanish photograph and
    every Spanish rendered document in the corpus is synthetic.
    """
    return tuple((point, caveats_for_document(key.document(point.doc_id))) for point in (SONNET_4_6_REC_DOM_IMG_008,))
