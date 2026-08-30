"""Shipped mínimo-descendientes advisory copy must never reach the diagnostic truncator.

``CalculationSourceDiagnostic.message`` truncates rather than refuses, so an
over-long advisory can no longer block a filing. That defence is deliberately not
a licence: a message that reaches the truncator has already lost words an
operator was meant to read, and these advisories are the ones that explain why a
taxpayer's allowance came out at zero.

These are the authoring-time half of the pair, and they are the reason the copy
below is split across ``message`` and ``remedy``. Two of these ten messages were
measured over the cap in production and eight of the ten sat within forty
characters of it at four descendants -- not an extreme tail, an ordinary
household. The fixed remedy prose was competing for room against the interpolated
descendant paths, so the filers with the most children were the ones whose remedy
got cut. Moving the remedy onto its own field is what bought the headroom these
tests now hold.

The type-level half -- that truncation is total, visible, and word-clean for any
input -- belongs with the type and stays in the aggregation suite.

Lives beside the advisories rather than beside the cap. The subject under test is
``_minimo_descendientes_advisory``'s private message builders, so the narrowest
owning package is this one; the cap comes from the aggregation facade, which is
where the constraint is declared.

The elision marker is READ OFF the type rather than imported. Its constant has
moved home once already, and a test that pins the import path fails on the next
move for a reason that has nothing to do with advisory copy. Asking the truncator
what it appends cannot go stale.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

import pytest

from ....core.casilla_id import validated_casilla_id
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.calculations.registry.temporal import select_revision
from ....tests.registry_tree import bundled_registry_tree
from ...aggregation import DIAGNOSTIC_MESSAGE_MAX_LENGTH, CalculationSourceDiagnostic
from .._minimo_descendientes_advisory import (
    _count_desync_advisory,
    _dependencia_assimilated_advisory,
    _dependencia_suppressed_advisory,
    _entry_date_missing_advisory,
    _guarderia_madre_meses_advisory,
    _guarderia_shape_advisory,
    _prorrata_inferred_advisory,
    _rentas_undeclared_advisory,
    _undeclared_advisory,
)

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
#: This distinction is the whole instrument, and getting it wrong understates
#: headroom in the safe-looking direction. The bounded name list renders the
#: first three qualifying descendants by their POSITION in the household and then
#: counts the rest, so its length grows on two independent axes: the DIGITS of
#: those three positions, and the digits of the "and N more" remainder. An
#: all-qualifying household maximises only the second -- it names positions 0, 1
#: and 2, which are one digit each. Starting the qualifying run partway into a
#: larger household buys six-digit positions AND a six-digit remainder at once.
#:
#: Measured against the live renderer: the all-qualifying million convention
#: yields 101 characters of names, the values below yield 116. Fifteen characters
#: of real headroom that a simpler convention would have quietly spent.
_WORST_FIRST_INDEX = 100_000
_WORST_QUALIFYING = 900_000

#: The largest count-vs-rows disagreement worth rendering. ``count_desync``
#: interpolates two integers rather than descendant paths, so its length scales
#: with their digits and not with the name list.
_WORST_COUNT = 1_000_000


def _worst_case_indices() -> list[int]:
    return list(range(_WORST_FIRST_INDEX, _WORST_FIRST_INDEX + _WORST_QUALIFYING))


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


def _headroom_revision() -> ModeloRevision:
    """A real M100 revision, fetched once, for the casilla-derived advisory builders.

    Only the presence of casilla ``0513`` in the revision matters here -- these
    tests measure message length, not grounding -- so any committed M100
    revision serves; the resident registry authority is real rather than a
    hand-built stub.

    Reached through the compiler and the canonical temporal resolver. Measuring
    an advisory's rendered length is not a filing operation, and every rung above
    this one -- the validated authority and its inspection projection alike --
    validates the whole registry first, so either would make a message-length
    test unobtainable for reasons that have nothing to do with messages.
    """
    modelos, _catalogues = bundled_registry_tree()
    modelo = next(candidate for candidate in modelos if candidate.id == "100")
    return select_revision(modelo, filing_year=2024, period="0A")


def _advisory_builders() -> list[tuple[str, Callable[[], CalculationSourceDiagnostic]]]:
    """Every shipped advisory in this module, built at its worst case.

    Enumerated by hand rather than discovered, so that adding an advisory without
    adding it here is a visible omission in this list rather than a silent gap in
    the gate.
    """
    casilla = validated_casilla_id("0513")
    guarderia = validated_casilla_id("0613")
    indices = _worst_case_indices()
    revision = _headroom_revision()
    return [
        ("undeclared", lambda: _undeclared_advisory(revision, casilla)),
        ("prorrata_inferred", lambda: _prorrata_inferred_advisory(revision, indices, casilla)),
        ("rentas_undeclared", lambda: _rentas_undeclared_advisory(revision, indices, casilla)),
        ("entry_date_missing", lambda: _entry_date_missing_advisory(indices, casilla)),
        ("guarderia_shape", lambda: _guarderia_shape_advisory(indices, guarderia)),
        ("guarderia_madre_meses", lambda: _guarderia_madre_meses_advisory(indices, guarderia)),
        ("dependencia_assimilated", lambda: _dependencia_assimilated_advisory(indices, casilla)),
        ("dependencia_suppressed", lambda: _dependencia_suppressed_advisory(indices, casilla)),
        ("count_desync", lambda: _count_desync_advisory(Decimal(_WORST_COUNT), _WORST_COUNT)),
    ]


_CASES = _advisory_builders()
_IDS = [name for name, _ in _CASES]


class TestTaxpayerScaledMessagesKeepAuthoringHeadroom:
    """Copy that only just fits is copy that breaks on its next edit."""

    @pytest.mark.parametrize(("name", "build"), _CASES, ids=_IDS)
    def test_the_advisory_keeps_headroom_at_its_worst_case(
        self,
        name: str,
        build: Callable[[], CalculationSourceDiagnostic],
    ) -> None:
        advisory = build()

        headroom = DIAGNOSTIC_MESSAGE_MAX_LENGTH - len(advisory.message)
        assert headroom >= _REQUIRED_HEADROOM, (
            f"{name} advisory has {headroom} chars of headroom; state the problem in `message` "
            "and move the operator's next step onto `remedy` before adding another clause"
        )

    @pytest.mark.parametrize(("name", "build"), _CASES, ids=_IDS)
    def test_the_advisory_does_not_reach_the_truncator(
        self,
        name: str,
        build: Callable[[], CalculationSourceDiagnostic],
    ) -> None:
        """The floor must stay unreached in shipped copy.

        If one of these ever ends in the elision marker, the type saved the
        filing and the operator still lost words -- which is the state the
        headroom assertions above exist to prevent reaching.
        """
        advisory = build()
        marker = _elision_marker()

        assert not advisory.message.endswith(marker), f"{name} message was elided"
        assert advisory.remedy is None or not advisory.remedy.endswith(marker), f"{name} remedy was elided"


class TestEveryRemedyIsCarriedApartFromTheProblem:
    """The split is the fix, so a regression that re-fuses them must fail here."""

    @pytest.mark.parametrize(("name", "build"), _CASES, ids=_IDS)
    def test_the_advisory_carries_an_operator_next_step(
        self,
        name: str,
        build: Callable[[], CalculationSourceDiagnostic],
    ) -> None:
        """Every one of these ten advisories has something for the operator to do.

        None of them is a bare disclosure: even the two that report a modelling
        limitation rather than a missing fact ask the filer to check a figure
        before filing. A ``None`` remedy here means a next step was dropped, or
        was folded back into the message where it competes for room again.
        """
        advisory = build()

        assert advisory.remedy, f"{name} carries no remedy"

    @pytest.mark.parametrize(("name", "build"), _CASES, ids=_IDS)
    def test_the_message_does_not_restate_the_remedy(
        self,
        name: str,
        build: Callable[[], CalculationSourceDiagnostic],
    ) -> None:
        """A remedy left in both places spends the headroom the split just bought."""
        advisory = build()

        assert advisory.remedy is not None
        assert advisory.remedy not in advisory.message, f"{name} carries its remedy in both fields"
