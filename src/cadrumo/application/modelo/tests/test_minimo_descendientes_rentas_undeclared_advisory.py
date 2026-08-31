"""A descendant claiming the mínimo with no rentas figure on record.

Art. 58.1 and Art. 61 norma 2ª both read an ABSENT rentas figure as
non-excluding, and that default is correct: treating absence as exclusion would
zero the allowance for every young child, who has no rentas to declare. It is
pinned elsewhere and is not under test here.

The asymmetry it leaves is. A descendant who genuinely earns above the ceiling
but whose figure was never entered still contributes a full tranche, and until
this advisory nothing said so. The sibling undeclared-advisory cannot cover it:
that one fires only when the aggregate is ZERO and returns the moment any
descendiente fact exists, because its subject is a filer who declared no
children. A declared descendant with an absent figure is a non-zero CLAIM, so
the two guards never overlap.

Both directions are proved, and the silent direction is the one that decides
whether this advisory is worth shipping. An advisory that also fires when the
figure IS present is a blanket advisory, and an operator who learns to ignore
one is worse off than an operator who never saw it. The sharpest case is a
declared ZERO: it looks like emptiness but is an answer, and it must be silent.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core.casilla_id import CasillaId
from ....core.modelo import Modelo
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.contribuyente.descendant import DescendantInfo
from ....domain.contribuyente.descendant_facts import descendant_facts_from_list
from ....domain.user_profile.values import UserProfileFact
from ....tests.profile_capsule import set_active_test_profile_facts
from ...aggregation import CalculationSourceDiagnostic
from .._minimo_descendientes_advisory import collect_minimo_descendientes_rentas_undeclared_diagnostics
from ._advisory_bucket_fixture import _bucket  # noqa: F401
from ._advisory_bucket_fixture import operator_text as _operator_text

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_BUCKET_ID = "7b7b7b7b-7b7b-4b7b-8b7b-7b7b7b7b7b7b"
_FILING_YEAR = 2024
_ESTATAL_CASILLA: CasillaId = "0513"

#: Any non-zero aggregate: the advisory's precondition is that a mínimo is being
#: claimed, not any particular amount.
_CLAIMED = {_ESTATAL_CASILLA: Decimal("2400")}
_NOTHING_CLAIMED = {_ESTATAL_CASILLA: Decimal("0")}


@pytest.fixture
def bucket_id() -> str:
    return _BUCKET_ID


def _revision() -> ModeloRevision:
    return bundled_authority().snapshot("100", filing_year=_FILING_YEAR, period="0A").revision


def _write(*descendants: DescendantInfo) -> None:
    facts = tuple(UserProfileFact(path=p, value=v) for p, v in descendant_facts_from_list(list(descendants)))
    set_active_test_profile_facts(facts)


def _collect(casilla_values: dict[CasillaId, Decimal] | None = None) -> tuple[CalculationSourceDiagnostic, ...]:
    return collect_minimo_descendientes_rentas_undeclared_diagnostics(
        _revision(),
        _CLAIMED if casilla_values is None else casilla_values,
        modelo=Modelo.M100.value,
        bucket_id=_BUCKET_ID,
    )


def _contributing_child(
    *,
    convive_con_contribuyente: bool = True,
    rentas_anuales_euros: Decimal | None = None,
) -> DescendantInfo:
    """A cohabiting 10-year-old: contributes on the non-income conditions alone."""
    return DescendantInfo(
        birth_date=date(_FILING_YEAR - 10, 5, 1),
        convive_con_contribuyente=convive_con_contribuyente,
        rentas_anuales_euros=rentas_anuales_euros,
    )


# ---------------------------------------------------------------------------
# Fires: a declared descendant claiming with no figure on record.
# ---------------------------------------------------------------------------


def test_fires_for_a_contributing_descendant_with_no_rentas_figure() -> None:
    _write(_contributing_child())
    diagnostics = _collect()
    assert len(diagnostics) == 1
    diagnostic = diagnostics[0]
    assert diagnostic.source_kind == "minimo_descendientes_rentas_undeclared"
    assert diagnostic.casilla_id == _ESTATAL_CASILLA


def test_the_advisory_asserts_both_provisions_its_message_states() -> None:
    """The message names two clauses; the typed grounding must name both, not the casilla's coarser ref.

    Art. 58.1 and Art. 61 norma 2ª are declared on ``asserted_legal_refs``, the
    advisory-asserted path -- not ``legal_refs``, which would read the coarser
    whole-article refs off the casilla the advisory addresses.
    """
    _write(_contributing_child())
    diagnostic = _collect()[0]
    assert diagnostic.asserted_legal_refs == ("ley-35-2006:art-58-1", "ley-35-2006:art-61-norma-2")
    assert diagnostic.legal_refs == ()


def test_the_advisory_names_the_descendant_and_the_way_to_answer() -> None:
    """An advisory an operator cannot act on is noise."""
    _write(_contributing_child())
    message = _operator_text(_collect()[0])
    assert "renta_family.descendiente.0" in message
    assert "RENTAS=" in message
    assert "RENTAS=0" in message, "the message must say a zero is a valid answer, or it reads as unanswerable"


def test_names_only_the_descendants_actually_missing_a_figure() -> None:
    """A mixed household flags the gap and not its siblings."""
    _write(
        _contributing_child(rentas_anuales_euros=Decimal("500")),
        _contributing_child(),
    )
    message = _collect()[0].message
    assert "renta_family.descendiente.1" in message
    assert "renta_family.descendiente.0" not in message


# ---------------------------------------------------------------------------
# Silent: the half that decides whether this is worth shipping.
# ---------------------------------------------------------------------------


def test_silent_when_the_figure_is_present() -> None:
    _write(_contributing_child(rentas_anuales_euros=Decimal("9500")))
    assert _collect() == ()


def test_silent_when_the_figure_is_present_and_zero() -> None:
    """A declared zero is an ANSWER, not an absence.

    The sharpest case in this file. Zero is what an operator enters for the
    ordinary child with no income, so an advisory that treats it as missing
    would fire on nearly every household with children -- exactly the blanket
    advisory that trains operators to ignore the channel.
    """
    _write(_contributing_child(rentas_anuales_euros=Decimal("0")))
    assert _collect() == ()


def test_a_declared_zero_survives_the_round_trip_as_an_answer() -> None:
    """The silence above must come from a real stored zero, not from a lost fact.

    If persistence dropped a zero the way it drops empty optionals, the test
    above would pass for the wrong reason -- the advisory would be silent
    because the descendant vanished, not because zero was recorded. This pins
    the distinction the whole advisory rests on.
    """
    from ....domain.contribuyente.descendant_facts import descendant_list_from_facts

    stored = dict(descendant_facts_from_list([_contributing_child(rentas_anuales_euros=Decimal("0"))]))
    assert "renta_family.descendiente.0.rentas_anuales" in stored
    assert descendant_list_from_facts(stored)[0].rentas_anuales_euros == Decimal("0")

    absent = dict(descendant_facts_from_list([_contributing_child()]))
    assert "renta_family.descendiente.0.rentas_anuales" not in absent
    assert descendant_list_from_facts(absent)[0].rentas_anuales_euros is None


def test_silent_when_nothing_is_being_claimed() -> None:
    """A zero aggregate means no tranche is at stake, so an absent figure is moot."""
    _write(_contributing_child())
    assert _collect(_NOTHING_CLAIMED) == ()


def test_silent_for_a_descendant_that_could_not_contribute_anyway() -> None:
    """Narrowness: a non-cohabiting child's figure changes no outcome.

    Art. 58.1 requires cohabitation, so this descendant carries no mínimo with
    or without a rentas figure. Flagging it would be noise.
    """
    _write(_contributing_child(convive_con_contribuyente=False))
    assert _collect() == ()


def test_silent_for_an_over_25_child_without_discapacidad() -> None:
    """The other non-income limb, same reasoning."""
    _write(DescendantInfo(birth_date=date(_FILING_YEAR - 30, 5, 1)))
    assert _collect() == ()


def test_silent_for_a_profile_with_no_descendientes_at_all() -> None:
    """That state belongs to the sibling undeclared-advisory, not this one."""
    assert _collect() == ()


def test_silent_for_another_modelo() -> None:
    diagnostics = collect_minimo_descendientes_rentas_undeclared_diagnostics(
        _revision(),
        _CLAIMED,
        modelo="303",
        bucket_id=_BUCKET_ID,
    )
    assert diagnostics == ()


def test_a_large_household_still_raises_a_valid_advisory() -> None:
    """Household size must not decide whether the advisory can be raised at all.

    The diagnostic message is length-bounded by contract, and naming every
    descendant is the only unbounded part of it. An unbounded list overflowed
    that bound during development and turned the advisory into a hard
    ValidationError -- at precisely the moment it had something to say, and for
    the filer with the most children at stake. The message names a few and
    counts the rest.
    """
    _write(*[_contributing_child() for _ in range(12)])
    diagnostics = _collect()
    assert len(diagnostics) == 1
    message = diagnostics[0].message
    assert len(message) <= 512
    assert "and 9 more" in message, "the remainder must be counted, not dropped"


# ---------------------------------------------------------------------------
# The two guards do not overlap.
# ---------------------------------------------------------------------------


def test_this_covers_the_state_the_sibling_undeclared_advisory_returns_early_on() -> None:
    """The finding this test exists to close, pinned as a relation between the two.

    The sibling fires only on a ZERO aggregate with no descendiente facts, and
    returns empty once any descendiente fact exists. That early return reasons
    about a declared zero -- a filer with no children is not a silent gap -- and
    does not hold for a declared descendant whose figure is merely absent. This
    asserts the sibling is indeed silent on that state and that this collector
    is not, so a future edit cannot quietly make both silent.
    """
    from .._minimo_descendientes_advisory import collect_minimo_descendientes_undeclared_diagnostics

    _write(_contributing_child())
    sibling = collect_minimo_descendientes_undeclared_diagnostics(
        _revision(),
        _CLAIMED,
        modelo=Modelo.M100.value,
        bucket_id=_BUCKET_ID,
    )
    assert sibling == (), "sibling unexpectedly covers this state; the overlap claim needs re-checking"
    assert len(_collect()) == 1
