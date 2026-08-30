"""Shipped maternidad advisory copy must never reach the diagnostic truncator.

``CalculationSourceDiagnostic.message`` truncates rather than refuses, so an
over-long advisory can no longer block a filing. That defence is deliberately not
a licence: a message that reaches the truncator has already lost words an
operator was meant to read.

These are the authoring-time half of the pair. They assert HEADROOM against the
real cap at the worst case a taxpayer can produce, so shipped copy fails here
while it is being written rather than silently eliding in front of an operator.
The type-level half — that truncation is total, visible, and word-clean for any
input — belongs with the type and stays in the aggregation suite.

Worst case is the largest household expressible, not a large one: the bounded
name list keeps growing with the digits of its "and N more" remainder long after
the names themselves stop being added.

Lives beside the advisories rather than beside the cap. The subject under test is
``_calculate_input``'s private message builders, so the narrowest owning package
is this one; the cap comes from the aggregation facade, which is where the
constraint is declared.

The elision marker is READ OFF the type rather than imported. Its constant has
moved home once already, and a test that pins the import path fails on the next
move for a reason that has nothing to do with advisory copy. Asking the truncator
what it appends cannot go stale.
"""

from __future__ import annotations

import pytest

from ....core.casilla_id import validated_casilla_id
from ...aggregation import DIAGNOSTIC_MESSAGE_MAX_LENGTH, CalculationSourceDiagnostic

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: Characters a taxpayer-scaled message must keep free at its worst case.
#:
#: Not zero. A message that merely fits today re-crashes on the next clause
#: someone adds, which is how this defect arrived: the interpolated term was
#: bounded correctly and the fixed prose was never measured.
_REQUIRED_HEADROOM = 40

#: The worst case is a LATE-QUALIFYING subset of a large household, not a large
#: household in which everyone qualifies.
#:
#: This convention previously built ids ``"0"..."999999"`` and took the whole run
#: as the worst case, which understated the real one. The bounded name list
#: renders the first three ids and then counts the rest, so its length grows on
#: two independent axes: the DIGITS of those three ids, and the digits of the
#: "and N more" remainder. An all-qualifying household maximises only the second
#: -- it names ids 0, 1 and 2, which are one digit each. Starting the qualifying
#: run partway into a larger household buys six-digit ids AND a six-digit
#: remainder at once.
#:
#: Measured against the live renderer: the old all-qualifying convention yielded
#: 101 characters of names, these values yield 116. The gate was understating
#: headroom by fifteen characters, in the safe-looking direction, inside the
#: instrument built to measure it. Do not simplify this back to ``range(count)``.
_WORST_FIRST_ID = 100_000
_WORST_QUALIFYING = 900_000


def _elision_marker() -> str:
    """Return the suffix the truncator appends, read off the live type.

    Feeds it one enormous unbroken word, which has no word boundary to cut on and
    so truncates to exactly the cap. Stripping the filler leaves precisely the
    marker, whatever it currently is and wherever its constant now lives.
    """
    probe = CalculationSourceDiagnostic(
        reason="source_issue",
        source_kind="probe",
        message="z" * (DIAGNOSTIC_MESSAGE_MAX_LENGTH * 2),
    )
    marker = probe.message.lstrip("z")
    assert marker, "the truncator appended no marker, so the elision assertions below prove nothing"
    return marker


class TestTaxpayerScaledMessagesKeepAuthoringHeadroom:
    """Copy that only just fits is copy that breaks on its next edit."""

    @staticmethod
    def _ids() -> tuple[str, ...]:
        """Return the worst-case id run: late-qualifying inside a larger household."""
        return tuple(str(index) for index in range(_WORST_FIRST_ID, _WORST_FIRST_ID + _WORST_QUALIFYING))

    def test_the_withheld_advisory_keeps_headroom_at_its_worst_case(self) -> None:
        """Worst case is an ENORMOUS household, not a large one.

        The bounded name list still grows with the digits of its "and N more"
        remainder, so the true worst case sits at the largest household
        expressible rather than at fifty -- and, per ``_WORST_FIRST_ID``, at a
        qualifying run that starts partway into it rather than at zero.
        """
        from .._calculate_input import _maternidad_meses_withheld_advisory

        advisory = _maternidad_meses_withheld_advisory(self._ids(), validated_casilla_id("0611"))

        assert advisory is not None
        headroom = DIAGNOSTIC_MESSAGE_MAX_LENGTH - len(advisory.message)
        assert headroom >= _REQUIRED_HEADROOM, (
            f"withheld advisory has {headroom} chars of headroom; shorten the fixed prose "
            "or move detail onto the notice context before adding another clause"
        )

    def test_the_ambiguous_relacion_advisory_keeps_headroom_at_its_worst_case(self) -> None:
        from .._calculate_input import _maternidad_ambiguous_relacion_advisory

        advisory = _maternidad_ambiguous_relacion_advisory(
            frozenset(self._ids()),
            validated_casilla_id("0611"),
        )

        assert advisory is not None
        headroom = DIAGNOSTIC_MESSAGE_MAX_LENGTH - len(advisory.message)
        assert headroom >= _REQUIRED_HEADROOM, (
            f"ambiguous-relación advisory has {headroom} chars of headroom; shorten the fixed "
            "prose or move detail onto the notice context before adding another clause"
        )

    def test_neither_advisory_reaches_the_truncator(self) -> None:
        """The floor must stay unreached in shipped copy.

        If either of these ever ends in the elision marker, the type saved the
        filing and the operator still lost words — which is the state the
        headroom assertions above exist to prevent reaching.
        """
        from .._calculate_input import (
            _maternidad_ambiguous_relacion_advisory,
            _maternidad_meses_withheld_advisory,
        )

        casilla = validated_casilla_id("0611")
        withheld = _maternidad_meses_withheld_advisory(self._ids(), casilla)
        ambiguous = _maternidad_ambiguous_relacion_advisory(frozenset(self._ids()), casilla)
        marker = _elision_marker()

        assert withheld is not None
        assert ambiguous is not None
        assert not withheld.message.endswith(marker)
        assert not ambiguous.message.endswith(marker)
