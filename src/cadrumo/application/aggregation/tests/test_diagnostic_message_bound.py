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

This module owns the FIRST defence, which is a property of the type and holds for
any input. The authoring-time headroom assertions are a property of specific
shipped copy, so they live beside the advisories that produce it, in
``application.modelo.tests.test_maternidad_advisory_headroom``. Both halves read
the same cap from this package and the same elision marker from
:mod:`core.prose_elision`, which owns the one clamp the whole tree shares.
"""

from __future__ import annotations

import pytest

from ....core.prose_elision import PROSE_ELISION_MARKER as DIAGNOSTIC_MESSAGE_ELISION
from .._source_mesh import DIAGNOSTIC_MESSAGE_MAX_LENGTH, CalculationSourceDiagnostic

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


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
