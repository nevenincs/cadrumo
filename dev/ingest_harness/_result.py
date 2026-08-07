"""What a measured result IS, and the shapes it is not allowed to take.

Three failures in this campaign came from a number's shape rather than from its
value, so each is made structurally unrepresentable here rather than warned
about:

**A figure with no model tier.** A result quoted without the tier that produced
it is as unfalsifiable as one quoted without the key hash, because the design
target is a small on-host model and a figure from a frontier model says nothing
about it. :attr:`ResultRow.model_tier` is required, and the tier is a closed set
whose members state whether the row is baseline-eligible at all.

**An accuracy over documents with no authored truth.** 81 corpus documents carry
``ground_truth == {}``. A report once read "0-1 of 8 recovered" over such
documents: the product emitted 0-1 fields, nothing was *recovered*, and there was
no denominator in existence. So a scored outcome and an emitted-only outcome are
different TYPES here. :class:`EmittedOnly` has no accuracy to read, and
:func:`build_result_row` refuses to attach a scored outcome to a document that
authored no truth -- the two cannot be confused because the confusing shape does
not exist.

**A number that passed through float.** Amounts are decimal literal strings and
tolerances are in whole cents, so comparison is exact-decimal or it is wrong.
:func:`amounts_match` takes ``Decimal`` and the harness prints a sanity line
proving the comparison path never touches binary floating point.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Final, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ._caveats import caveats_for_document
from ._key import CorpusDocument

__all__ = [
    "EmittedOnly",
    "EngineRoute",
    "HarnessRefusalError",
    "ModelTier",
    "PipelineStage",
    "ResultRow",
    "Scored",
    "amounts_match",
    "build_result_row",
]

_STRICT = ConfigDict(frozen=True, strict=True, extra="forbid")


class HarnessRefusalError(RuntimeError):
    """The harness refuses to record or report a result in an unquotable shape."""


class ModelTier(StrEnum):
    """What CLASS of model produced a figure, and whether it can be a baseline.

    Named by the role the tier plays in the decision rather than by vendor or
    parameter count, because the question a reader actually has is "does this
    number bound the product, or describe it?". A vendor-named tier would need
    that translation performed from memory every time it was read.
    """

    ON_HOST_SMALL = "on_host_small"
    """The 2B-4B on-host class the product actually ships. Baseline-eligible."""

    CLOUD_DESIGN_PROXY = "cloud_design_proxy"
    """A Haiku-class cloud model standing in for the design target. Baseline-eligible."""

    UPPER_REFERENCE = "upper_reference"
    """A frontier model. Bounds the pipeline from ABOVE and is NEVER a baseline.

    A figure at this tier answers "is the pipeline design capable of this?", not
    "is the shipped product this good?". Recording it as a baseline would set an
    acceptance floor no shipped configuration can meet.
    """

    @property
    def is_baseline_eligible(self) -> bool:
        """Whether a figure at this tier may set or test an acceptance floor."""
        return self is not ModelTier.UPPER_REFERENCE


class EngineRoute(StrEnum):
    """Where the inference physically ran.

    A cloud-measured figure and an on-host figure are not interchangeable: the
    governing record is explicit that a cloud-measured stage characterises the
    pipeline DESIGN and says nothing about what the shipped local model recovers.
    """

    GATED_CLOUD = "gated_cloud"
    """The sanctioned cloud engine. Admissible because the corpus is public."""

    LOCAL_ON_HOST = "local_on_host"
    """A local model on this machine. The only route that measures shipped floors."""

    DETERMINISTIC = "deterministic"
    """No model at all -- a parser or text-layer extraction. No tier judgement applies."""


class PipelineStage(StrEnum):
    """Which seam of the pipeline the row measures."""

    S1_TRANSCRIPTION = "s1_transcription"
    S2_EXTRACTION = "s2_extraction"
    S3_GROUNDING = "s3_grounding"
    S4_CLASSIFICATION = "s4_classification"
    TABULAR_MAPPING = "tabular_mapping"
    END_TO_END = "end_to_end"


class Scored(BaseModel):
    """An outcome measured against authored truth.

    Fabrication is counted apart from a miss on purpose. A field the document
    does not have, emitted anyway, is not a wrong answer to a question -- it is
    an answer to a question nobody asked, and averaging it into an accuracy hides
    the one failure mode the grounding seam exists to make impossible.
    """

    model_config = _STRICT

    scorable_field_count: int = Field(gt=0)
    matched: int = Field(ge=0)
    wrong: int = Field(ge=0)
    fabricated: int = Field(ge=0)

    @model_validator(mode="after")
    def _totals_are_coherent(self) -> Self:
        if self.matched + self.wrong > self.scorable_field_count:
            raise ValueError(
                f"matched ({self.matched}) + wrong ({self.wrong}) exceeds the scorable field "
                f"count ({self.scorable_field_count})",
            )
        return self

    @property
    def accuracy(self) -> Decimal:
        """Matched over the authored-truth denominator, as an exact ratio."""
        return Decimal(self.matched) / Decimal(self.scorable_field_count)

    @property
    def missed(self) -> int:
        """Authored fields neither matched nor answered wrongly."""
        return self.scorable_field_count - self.matched - self.wrong


class EmittedOnly(BaseModel):
    """An outcome over a document that authored no truth.

    Carries a count of what the product produced and, deliberately, NO accuracy
    and no denominator. There is nothing to divide by, and the absence is the
    point: a reader cannot quote a rate from this type because it does not have
    one to quote.
    """

    model_config = _STRICT

    emitted_field_count: int = Field(ge=0)

    @property
    def why_unscored(self) -> str:
        """The sentence a report prints instead of a percentage."""
        return (
            "no authored truth for this document, so accuracy is UNDEFINED rather than zero; "
            f"the product emitted {self.emitted_field_count} field(s) and none of them was verified"
        )


class ResultRow(BaseModel):
    """One measured result, in the only shape the harness will report.

    Build these through :func:`build_result_row` rather than directly: that
    function derives the caveats from the document and enforces the pairing
    between a document's truth and the outcome type, neither of which a
    hand-built row would carry.
    """

    model_config = _STRICT

    doc_id: str = Field(min_length=1)
    key_sha256: str = Field(min_length=64, max_length=64)
    stage: PipelineStage
    engine_route: EngineRoute
    model_identity: str = Field(min_length=1)
    model_revision: str = Field(min_length=1)
    model_tier: ModelTier
    outcome: Scored | EmittedOnly
    caveats: tuple[str, ...] = ()

    @property
    def is_baseline_eligible(self) -> bool:
        """Whether this row may inform an acceptance floor."""
        return self.model_tier.is_baseline_eligible


def build_result_row(
    *,
    document: CorpusDocument,
    key_sha256: str,
    stage: PipelineStage,
    engine_route: EngineRoute,
    model_identity: str,
    model_revision: str,
    model_tier: ModelTier,
    outcome: Scored | EmittedOnly,
) -> ResultRow:
    """Build a row, stamping its caveats and refusing an incoherent pairing.

    Raises:
        HarnessRefusalError: When a scored outcome is claimed over a document that
            authored no truth, when a scored outcome's denominator disagrees with
            the document's own authored-field count, or when an emitted-only
            outcome is used for a document that DOES carry truth (which would
            discard a real denominator and under-report the measurement).
    """
    authored = len(document.scorable_fields)
    if isinstance(outcome, Scored):
        if not document.has_authored_truth:
            raise HarnessRefusalError(
                f"{document.doc_id}: refused a scored outcome over a document with no authored truth. "
                "An accuracy here would have no denominator; use EmittedOnly, which cannot be quoted "
                "as a rate.",
            )
        if outcome.scorable_field_count != authored:
            raise HarnessRefusalError(
                f"{document.doc_id}: scored denominator {outcome.scorable_field_count} does not match "
                f"the document's {authored} non-null authored field(s). A denominator that is not the "
                "key's own is a figure about a set nobody can reconstruct.",
            )
    elif document.has_authored_truth:
        raise HarnessRefusalError(
            f"{document.doc_id}: refused an emitted-only outcome over a document that authored "
            f"{authored} field(s). Truth exists here, so the result is scorable and reporting a bare "
            "emitted count would discard it.",
        )

    return ResultRow(
        doc_id=document.doc_id,
        key_sha256=key_sha256,
        stage=stage,
        engine_route=engine_route,
        model_identity=model_identity,
        model_revision=model_revision,
        model_tier=model_tier,
        outcome=outcome,
        caveats=caveats_for_document(document),
    )


#: Printed by the runner so a reader can see that comparison never widens to
#: binary floating point. ``0.1 + 0.2 == 0.3`` is False in float and True in
#: Decimal; the harness asserts the Decimal answer at report time.
FLOAT_SANITY_PROBE: Final = (Decimal("0.1"), Decimal("0.2"), Decimal("0.3"))


def amounts_match(printed: Decimal, truth: Decimal, *, tolerance_cents: int) -> bool:
    """Compare two amounts in exact decimal, within a whole-cent tolerance.

    Both operands are ``Decimal`` by signature, so a float cannot enter the
    comparison without a type error at the call site. The tolerance is the key's
    own ``scoring_hints.tolerance_cents`` rather than a harness default, because
    tolerance is a property of the document's rounding convention.
    """
    return abs(printed - truth) <= Decimal(tolerance_cents) / Decimal(100)
