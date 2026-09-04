"""The scoring arm: turning an emission into counts the key itself authorises.

The harness could record ``matched``, ``wrong`` and ``fabricated`` long before
anything could COMPUTE them -- :class:`~dev.ingest_harness._result.Scored` took all three
as caller-supplied integers, so the one failure mode the campaign exists to
measure had a place to be written down and no code that produced it. This module
is the missing half, and it is deliberately the only place a verdict is decided.

**Every slot comes from the corpus, never from an example.** The scorable slots
are :attr:`~dev.ingest_harness._key.CorpusDocument.scorable_fields` and the traps are
:attr:`~dev.ingest_harness._key.CorpusDocument.fabrication_trap_fields`, both derived
from the document's own authored truth. Nothing here enumerates a field name, so
a corpus that adds a field is scored on it without this module changing.

**Fabrication is not a wrong answer, and the counts never pool.** A value emitted
into a ``null``-truth slot answers a question the document does not ask, and a
model that invents plausibly outscores one that abstains the moment those two are
averaged together. :class:`FieldVerdict` keeps them distinct all the way to the
report, and :meth:`FieldScoring.as_scored` carries ``fabricated`` across into
:class:`~dev.ingest_harness._result.Scored` without ever folding it into the numerator or
the denominator.

**An emitted field the key does not declare is neither.** The key makes no claim
about it -- it is not authored truth and it is not a trap -- so counting it as
fabrication would assert an absence the corpus never stated. Those land in
:attr:`FieldScoring.undeclared` and are reported beside the counts, never inside
them.

**Verdicts carry field NAMES, never emitted values.** Knowing WHICH slot was
fabricated is the whole diagnostic; carrying the invented value would put model
output describing a document into every report and log the harness writes, and
the harness must stay safe to point at evidence that is not this public corpus.

Comparison is derived from the truth value's own shape rather than from a
field-name table, and it is STRICT:

* A truth string that parses as a finite decimal is compared with
  :func:`~dev.ingest_harness._result.amounts_match` at the document's own
  ``tolerance_cents``. An emitted value that does not parse the same way is
  ``WRONG`` rather than coerced -- so ``"766,30"`` against a truth of ``"766.30"``
  scores wrong. That is a form divergence, not a reading failure, and it is
  counted here as a miss on purpose: the field-form contract pins form
  separately, so a post-contract run is comparable like-for-like. It does mean
  this scorer UNDERSTATES a model that reads correctly and formats differently.
* Any other truth string compares whitespace-normalised and case-sensitively.
* A boolean compares to a boolean, never to ``1``.
* A mapping or sequence compares structurally, applying these same leaf rules
  recursively, and is one slot -- the key declares it as one field.

See Also:
    :func:`~dev.ingest_harness._result.build_result_row`
        Consumes :meth:`FieldScoring.as_scored` and stamps the document's caveats.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any, Final, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ._caveats import normalise_whitespace
from ._key import CorpusDocument
from ._result import HarnessRefusalError, Scored, amounts_match

__all__ = [
    "ABSTENTION_SENTINELS",
    "FieldOutcome",
    "FieldScoring",
    "FieldVerdict",
    "score_emission",
]

_STRICT = ConfigDict(frozen=True, strict=True, extra="forbid")

ABSTENTION_SENTINELS: Final = frozenset({"", "null", "none", "n/a", "na", "-", "--", "unknown"})
"""Emitted spellings that mean "I did not find this", not "the value is this".

A model asked for a field it cannot see answers with a blank or a placeholder far
more often than it omits the key. Treating those as emitted values would score an
abstention as a fabrication on every trap slot, which would invert the exact
measurement this module exists to produce -- the abstaining model would look like
the worst offender.
"""


class FieldVerdict(StrEnum):
    """What happened at one declared slot.

    Five outcomes, not three, because "did not answer" and "answered wrongly" are
    different behaviours at a scorable slot, and "answered" and "stayed silent"
    are different behaviours at a trap.
    """

    MATCHED = "matched"
    """A scorable slot, answered, and the answer agrees with the key."""

    WRONG = "wrong"
    """A scorable slot, answered, and the answer disagrees with the key."""

    MISSED = "missed"
    """A scorable slot the emission left unanswered. Truth existed and was not found."""

    FABRICATED = "fabricated"
    """A ``null``-truth slot answered anyway. The hard error, never a miss."""

    CORRECTLY_ABSTAINED = "correctly_abstained"
    """A ``null``-truth slot left unanswered. The behaviour the trap rewards."""


class FieldOutcome(BaseModel):
    """One slot's verdict, named by field.

    Carries no emitted value: see the module docstring. The field name plus the
    verdict is what a reader needs to act, and it is all this type will hold.
    """

    model_config = _STRICT

    field_name: str = Field(min_length=1)
    verdict: FieldVerdict


class FieldScoring(BaseModel):
    """Every declared slot's verdict for one document, plus what fell outside them.

    Built only by :func:`score_emission`. The counters are properties derived
    from the verdicts rather than stored alongside them, so a count cannot
    disagree with the outcomes it summarises.
    """

    model_config = _STRICT

    doc_id: str = Field(min_length=1)
    outcomes: tuple[FieldOutcome, ...]
    undeclared: tuple[str, ...] = ()
    """Emitted field names the key declares neither as truth nor as a trap.

    Reported beside the counts and never inside them: the key asserts nothing
    about these slots, so calling one a fabrication would invent an absence.
    """

    @model_validator(mode="after")
    def _slots_are_declared_once(self) -> Self:
        """Refuse a double verdict on one slot.

        Two verdicts for one field would make every counter below ambiguous, and
        the ambiguity would show up as a total that quietly exceeds the key's own
        field count.
        """
        names = [outcome.field_name for outcome in self.outcomes]
        if len(names) != len(set(names)):
            duplicated = sorted({name for name in names if names.count(name) > 1})
            raise ValueError(f"{self.doc_id}: fields scored more than once: {duplicated}")
        return self

    def _count(self, verdict: FieldVerdict) -> int:
        return sum(1 for outcome in self.outcomes if outcome.verdict is verdict)

    @property
    def matched(self) -> int:
        """Scorable slots answered correctly."""
        return self._count(FieldVerdict.MATCHED)

    @property
    def wrong(self) -> int:
        """Scorable slots answered incorrectly."""
        return self._count(FieldVerdict.WRONG)

    @property
    def missed(self) -> int:
        """Scorable slots left unanswered."""
        return self._count(FieldVerdict.MISSED)

    @property
    def fabricated(self) -> int:
        """Trap slots answered anyway. The hard error."""
        return self._count(FieldVerdict.FABRICATED)

    @property
    def correctly_abstained(self) -> int:
        """Trap slots left unanswered."""
        return self._count(FieldVerdict.CORRECTLY_ABSTAINED)

    @property
    def scorable_field_count(self) -> int:
        """The key's own denominator: slots carrying non-null truth."""
        return self.matched + self.wrong + self.missed

    @property
    def trap_slot_count(self) -> int:
        """Slots the key declares the document LACKS."""
        return self.fabricated + self.correctly_abstained

    def fabricated_fields(self) -> tuple[str, ...]:
        """The names of every fabricated slot, for the report to enumerate.

        A count alone tells a reader that invention happened; the names tell them
        where to look, which is the difference between a number and a finding.
        """
        return tuple(outcome.field_name for outcome in self.outcomes if outcome.verdict is FieldVerdict.FABRICATED)

    def as_scored(self) -> Scored:
        """Project to the reportable outcome, keeping fabrication separate.

        Raises:
            HarnessRefusalError: When the document declared no scorable slot.
                :class:`~dev.ingest_harness._result.Scored` requires a positive
                denominator, and an accuracy over nothing is undefined rather
                than zero -- the caller wants
                :class:`~dev.ingest_harness._result.EmittedOnly`.
        """
        if self.scorable_field_count == 0:
            raise HarnessRefusalError(
                f"{self.doc_id}: cannot project a scored outcome; the key authors no non-null truth "
                "for this document, so there is no denominator. Use EmittedOnly, which carries no rate.",
            )
        return Scored(
            scorable_field_count=self.scorable_field_count,
            matched=self.matched,
            wrong=self.wrong,
            fabricated=self.fabricated,
        )


def _is_abstention(value: Any) -> bool:
    """Whether an emitted value means "not found" rather than a value."""
    if value is None:
        return True
    if isinstance(value, str):
        return normalise_whitespace(value).casefold() in ABSTENTION_SENTINELS
    return False


def _as_finite_decimal(value: str) -> Decimal | None:
    """Parse a decimal string, rejecting the non-finite spellings ``Decimal`` accepts.

    ``Decimal("NaN")`` and ``Decimal("Infinity")`` both succeed, and neither is an
    amount. A field whose truth is the literal text "NaN" must compare as text.
    """
    try:
        parsed = Decimal(value.strip())
    except (InvalidOperation, ValueError, ArithmeticError):
        return None
    return parsed if parsed.is_finite() else None


def _values_agree(truth: Any, emitted: Any, *, tolerance_cents: int) -> bool:
    """Compare one leaf or composite, dispatching on the TRUTH's shape.

    The truth decides the comparison because the truth is the authority; letting
    the emitted value choose would let a model pick the rule it passes.
    """
    if isinstance(truth, bool):
        return isinstance(emitted, bool) and truth == emitted
    if isinstance(truth, str):
        truth_amount = _as_finite_decimal(truth)
        if truth_amount is not None:
            if isinstance(emitted, bool) or not isinstance(emitted, str | int | Decimal):
                return False
            emitted_amount = _as_finite_decimal(str(emitted))
            if emitted_amount is None:
                return False
            return amounts_match(emitted_amount, truth_amount, tolerance_cents=tolerance_cents)
        return isinstance(emitted, str) and normalise_whitespace(truth) == normalise_whitespace(emitted)
    if isinstance(truth, Mapping):
        if not isinstance(emitted, Mapping) or set(truth) != set(emitted):
            return False
        return all(
            _values_agree(value, emitted[name], tolerance_cents=tolerance_cents) for name, value in truth.items()
        )
    if isinstance(truth, Sequence):
        if isinstance(emitted, str) or not isinstance(emitted, Sequence) or len(truth) != len(emitted):
            return False
        return all(
            _values_agree(item, other, tolerance_cents=tolerance_cents)
            for item, other in zip(truth, emitted, strict=True)
        )
    return truth == emitted


def score_emission(*, document: CorpusDocument, emitted: Mapping[str, Any]) -> FieldScoring:
    """Score one emission against one document's authored truth.

    The emission is whatever the product produced for this document -- a mapping
    of field name to value. An absent key and an abstention sentinel are both
    "not answered"; see :data:`ABSTENTION_SENTINELS` for why the second is not a
    fabrication.

    Args:
        document: The corpus document, carrying the slots and the tolerance.
        emitted: Field name to emitted value, as the product produced it.

    Returns:
        :class:`FieldScoring`: A verdict for every slot the key declares, plus
        the emitted names it declares nothing about.

    Raises:
        HarnessRefusalError: When the document authors no truth at all. There is
            nothing to score against, and every slot would be undeclared, so a
            verdict set would be an empty measurement wearing a result's shape.
    """
    if not document.has_authored_truth:
        raise HarnessRefusalError(
            f"{document.doc_id}: refused to score an emission against a document with no authored truth. "
            "The key declares neither a scorable slot nor a trap here, so every verdict would be vacuous; "
            "report an EmittedOnly outcome, which carries no rate.",
        )

    outcomes: list[FieldOutcome] = []
    for name in document.scorable_fields:
        if name not in emitted or _is_abstention(emitted[name]):
            verdict = FieldVerdict.MISSED
        elif _values_agree(document.ground_truth[name], emitted[name], tolerance_cents=document.tolerance_cents):
            verdict = FieldVerdict.MATCHED
        else:
            verdict = FieldVerdict.WRONG
        outcomes.append(FieldOutcome(field_name=name, verdict=verdict))

    for name in document.fabrication_trap_fields:
        answered = name in emitted and not _is_abstention(emitted[name])
        outcomes.append(
            FieldOutcome(
                field_name=name,
                verdict=FieldVerdict.FABRICATED if answered else FieldVerdict.CORRECTLY_ABSTAINED,
            ),
        )

    declared = set(document.ground_truth)
    undeclared = tuple(sorted(name for name in emitted if name not in declared and not _is_abstention(emitted[name])))
    return FieldScoring(doc_id=document.doc_id, outcomes=tuple(outcomes), undeclared=undeclared)
