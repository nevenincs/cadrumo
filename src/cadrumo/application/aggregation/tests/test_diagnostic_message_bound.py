"""A non-blocking advisory must never become a blocking failure.

`CalculationSourceDiagnostic.message` was capped by a refusing constraint, so a
message that outgrew the cap raised, `calculate` exited with a raw validation
error, and the filing stopped — at exactly the moment the advisory had something
to say. The severity is inverted: the diagnostic exists to avoid silence, and the
cap turned it into an obstruction.

Bounding each interpolated term was necessary and provably not sufficient. The
messages are fixed prose plus terms sized by data the taxpayer controls, and a
bounded list still crossed the cap once the prose grew. Two defences are needed
and they answer different failures:

* the type truncates, so the blocking failure is impossible by construction;
* headroom assertions on the taxpayer-scaled messages fail at authoring time, so
  truncation is never actually reached in shipped copy.

The second is what keeps the first from being a licence. A message that reaches
the truncator has already lost words an operator was meant to read.
"""

from __future__ import annotations

import pytest

from ....core import validated_casilla_id
from .._source_mesh import (
    DIAGNOSTIC_MESSAGE_ELISION,
    DIAGNOSTIC_MESSAGE_MAX_LENGTH,
    CalculationSourceDiagnostic,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: Characters a taxpayer-scaled message must keep free at its worst case.
#:
#: Not zero. A message that merely fits today re-crashes on the next clause
#: someone adds, which is how this defect arrived: the interpolated term was
#: bounded correctly and the fixed prose was never measured.
_REQUIRED_HEADROOM = 40


def _diagnostic(message: str) -> CalculationSourceDiagnostic:
    return CalculationSourceDiagnostic(reason="source_issue", source_kind="probe", message=message)


class TestTheTypeIsTotal:
    """No input produces a refusal, because a refusal blocks a filing."""

    @pytest.mark.parametrize("length", [1, 100, 511, 512, 513, 5_000, 100_000])
    def test_a_message_of_any_length_constructs(self, length: int) -> None:
        diagnostic = _diagnostic("x" * length)

        assert len(diagnostic.message) <= DIAGNOSTIC_MESSAGE_MAX_LENGTH

    def test_a_message_within_the_cap_is_untouched(self) -> None:
        """Truncation must not touch the overwhelming majority of advisories."""
        message = "a short advisory that says what went wrong and how to fix it"

        assert _diagnostic(message).message == message

    def test_an_exactly_capped_message_is_untouched(self) -> None:
        """The boundary is inclusive; 512 is allowed, not truncated."""
        message = "y" * DIAGNOSTIC_MESSAGE_MAX_LENGTH

        assert _diagnostic(message).message == message


class TestTruncationIsVisibleAndClean:
    """A shortened advisory must not read as a terse one."""

    def test_an_over_long_message_is_marked_as_elided(self) -> None:
        assert _diagnostic("word " * 300).message.endswith(DIAGNOSTIC_MESSAGE_ELISION)

    def test_truncation_does_not_cut_mid_word(self) -> None:
        """Cut on a word boundary, so the last word read is a whole word."""
        message = " ".join(f"word{index:03d}" for index in range(200))

        truncated = _diagnostic(message).message

        body = truncated[: -len(DIAGNOSTIC_MESSAGE_ELISION)]
        assert not body.endswith(" ")
        assert body.split()[-1] in message.split()

    def test_a_single_enormous_word_still_truncates_rather_than_raising(self) -> None:
        """No word boundary to cut on, and the type must stay total anyway.

        The mid-word guard is a preference; totality is the requirement, so the
        preference yields when they conflict.
        """
        diagnostic = _diagnostic("z" * 2_000)

        assert len(diagnostic.message) == DIAGNOSTIC_MESSAGE_MAX_LENGTH
        assert diagnostic.message.endswith(DIAGNOSTIC_MESSAGE_ELISION)

    def test_truncation_is_idempotent(self) -> None:
        """Re-validating a truncated message must not shorten it again.

        These records round-trip through persistence, so a validator that ate
        six more characters per load would erode a message over its lifetime.
        """
        once = _diagnostic("word " * 300).message
        twice = _diagnostic(once).message

        assert twice == once


class TestTaxpayerScaledMessagesKeepAuthoringHeadroom:
    """The early warning, on exactly the messages whose length is not fixed.

    The discriminator is not "the message interpolates something" — most
    interpolated terms are bounded by the calendar or by registry content and
    cannot grow. It is "sized by data the taxpayer controls". Only those can be
    pushed toward the cap by a filer's own household.
    """

    @staticmethod
    def _ids(count: int) -> tuple[str, ...]:
        return tuple(str(index) for index in range(count))

    def test_the_withheld_advisory_keeps_headroom_at_its_worst_case(self) -> None:
        """Worst case is an ENORMOUS household, not a large one.

        The bounded name list still grows with the digits of its "and N more"
        remainder, so the true worst case sits at the largest household
        expressible rather than at fifty.
        """
        from ...modelo._calculate_input import _maternidad_meses_withheld_advisory

        advisory = _maternidad_meses_withheld_advisory(self._ids(1_000_000), validated_casilla_id("0611"))

        assert advisory is not None
        headroom = DIAGNOSTIC_MESSAGE_MAX_LENGTH - len(advisory.message)
        assert headroom >= _REQUIRED_HEADROOM, (
            f"withheld advisory has {headroom} chars of headroom; shorten the fixed prose "
            "or move detail onto the notice context before adding another clause"
        )

    def test_the_ambiguous_relacion_advisory_keeps_headroom_at_its_worst_case(self) -> None:
        from ...modelo._calculate_input import _maternidad_ambiguous_relacion_advisory

        advisory = _maternidad_ambiguous_relacion_advisory(
            frozenset(self._ids(1_000_000)),
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
        from ...modelo._calculate_input import (
            _maternidad_ambiguous_relacion_advisory,
            _maternidad_meses_withheld_advisory,
        )

        casilla = validated_casilla_id("0611")
        withheld = _maternidad_meses_withheld_advisory(self._ids(1_000_000), casilla)
        ambiguous = _maternidad_ambiguous_relacion_advisory(frozenset(self._ids(1_000_000)), casilla)

        assert withheld is not None
        assert ambiguous is not None
        assert not withheld.message.endswith(DIAGNOSTIC_MESSAGE_ELISION)
        assert not ambiguous.message.endswith(DIAGNOSTIC_MESSAGE_ELISION)
