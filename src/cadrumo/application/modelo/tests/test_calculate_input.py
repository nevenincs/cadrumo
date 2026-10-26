"""Inward tests for calculate-input advisory bounds.

Profile, secure-storage, and live registry integration for the input boundary
lives in the outer persistence test with the same name. These tests exercise the
application-owned advisory policy without importing concrete persistence support.
"""

from __future__ import annotations

import pytest

from cadrumo.core.casilla_id import validated_casilla_id

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class TestMaternidadAdvisoryLengthIsBoundedByHouseholdSize:
    """Both maternidad advisories interpolate one entry per descendant.

    That makes their length DYNAMIC, which is what distinguishes this from the
    cotizaciones-ceiling crash: that message was a fixed string measured once
    and trimmed. These grow, so measuring one is measuring nothing. Past a
    household size the message overruns the diagnostic cap, the model refuses,
    and `calculate` exits with a raw validation error reaching the operator --
    a NON-blocking advisory stopping the filing outright, at exactly the moment
    it had something to say.

    Every case here is constructed ABOVE the count at which the unbounded form
    crossed the cap, never at one index, because a single-index construction is
    what let both of these ship.
    """

    #: The pydantic cap on ``CalculationSourceDiagnostic.message``.
    CAP = 512

    #: Comfortably past both observed crossings (13 withheld, 25 ambiguous),
    #: so a later message edit that lengthens the fixed prose is still covered.
    MANY = 60

    @staticmethod
    def _ids(count: int) -> tuple[str, ...]:
        return tuple(str(index) for index in range(count))

    def test_withheld_advisory_stays_within_the_cap_at_many_descendants(self) -> None:
        from ..calculate_input import _maternidad_meses_withheld_advisory

        advisory = _maternidad_meses_withheld_advisory(self._ids(self.MANY), validated_casilla_id("0611"))

        assert advisory is not None
        assert len(advisory.message) <= self.CAP

    def test_ambiguous_relacion_advisory_stays_within_the_cap_at_many_descendants(self) -> None:
        from ..calculate_input import _maternidad_ambiguous_relacion_advisory

        advisory = _maternidad_ambiguous_relacion_advisory(
            frozenset(self._ids(self.MANY)),
            validated_casilla_id("0611"),
        )

        assert advisory is not None
        assert len(advisory.message) <= self.CAP

    def test_both_advisories_hold_at_the_observed_crossing_points(self) -> None:
        """Pinned at the counts the review measured: 13 withheld, 25 ambiguous.

        Kept alongside the larger case so a regression that merely RAISES the
        threshold rather than removing it is still caught here.
        """
        from ..calculate_input import _maternidad_ambiguous_relacion_advisory, _maternidad_meses_withheld_advisory

        casilla = validated_casilla_id("0611")
        for count in (13, 25, 26):
            withheld = _maternidad_meses_withheld_advisory(self._ids(count), casilla)
            ambiguous = _maternidad_ambiguous_relacion_advisory(frozenset(self._ids(count)), casilla)
            assert withheld is not None
            assert ambiguous is not None
            assert len(withheld.message) <= self.CAP, f"withheld overran at {count}"
            assert len(ambiguous.message) <= self.CAP, f"ambiguous overran at {count}"

    def test_the_unbounded_form_would_have_overrun(self) -> None:
        """Positive control: the bound is doing work, not decorating a short message.

        Reconstructs what an unbounded join of the same ids costs and asserts it
        exceeds the cap. Without this, every assertion above would pass equally
        well against a message that never approached the limit, and the tests
        would prove nothing about the defence.
        """
        from ..calculate_input import _bounded_descendant_ids, _maternidad_meses_withheld_advisory

        ids = self._ids(self.MANY)
        advisory = _maternidad_meses_withheld_advisory(ids, validated_casilla_id("0611"))
        assert advisory is not None

        bounded_term = _bounded_descendant_ids(ids)
        unbounded_term = ", ".join(ids)
        would_be = len(advisory.message) - len(bounded_term) + len(unbounded_term)

        assert would_be > self.CAP, "the control does not reach the cap, so the bound proves nothing"

    def test_the_bound_still_names_descendants_and_counts_the_rest(self) -> None:
        """Bounding must keep the advisory ACTIONABLE, not reduce it to a count.

        An operator needs at least one index to act on, and needs to know the
        list was truncated rather than complete -- otherwise a household of
        sixty reads as a household of three.
        """
        from ..calculate_input import _bounded_descendant_ids

        rendered = _bounded_descendant_ids(self._ids(self.MANY))

        assert rendered.startswith("0, 1, 2")
        assert rendered.endswith(f"and {self.MANY - 3} more")

    def test_a_small_household_is_named_in_full_with_no_remainder_clause(self) -> None:
        """The bound must not degrade the ordinary case it was added to protect."""
        from ..calculate_input import _bounded_descendant_ids

        assert _bounded_descendant_ids(("0", "1")) == "0, 1"
