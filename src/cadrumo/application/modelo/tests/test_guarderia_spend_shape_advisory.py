"""The Art. 81.2 shape advisory: a declared figure that counts nothing, disclosed.

There is one state in which a taxpayer declares real guardería spend, sees it
stored, and receives nothing for it: the child turns three during the period and
the figure on record is a single annual total that cannot be apportioned.

The zero comes from the UPPER edge of the window, not from the birthday. The
birthday is not a boundary here — Capítulo 18's "gastos incurridos con
posterioridad al cumplimiento de dicha edad" GRANTS the months after it and
withdraws none of the months before, which the manual settles with a child who
"en septiembre cumple 3 años" and is granted "6 meses completos (de enero a
junio)", every one of them before the birthday. What the application cannot
derive is where the window ENDS: the statute closes it at the month before the
second cycle of infant education may begin, and each región determines that.
So a yearly figure carries no month information the increment could use, and
the only basis derivable from a birth date alone — the under-three months — is
NARROWER than the increment's own window, so using it would prorate against a
basis the spend it pairs with does not share.

The zero is correct — splitting the total would be inventing the split. What
would not be correct is silence. The whole reason zero is defensible here is that
the operator is told, and told the one thing that fixes it: the month-by-month
detail their childcare centre already certified. That is not a workaround for a
rule this application declines to compute; the eligible months genuinely ARE the
ones the centre determined, because the centre files the informative return that
reports them.

Both directions are covered. An advisory that also fired for households it does
not describe would be a blanket advisory, and an operator who learns to ignore
one is worse off than one who never saw it.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core import CasillaId, Modelo
from ....core.resources import resources
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from ....domain.contribuyente import (
    DescendantInfo,
    GuarderiaMonthSpend,
    descendant_facts_from_list,
    parse_guarderia_mensual,
)
from ....domain.user_profile.values import UserProfileFact
from ....tests.profile_capsule import set_active_test_profile_facts
from ...aggregation import CalculationSourceDiagnostic
from .._calculation_diagnostics import collect_bucket_aggregation_advisory_diagnostics
from .._minimo_descendientes_advisory import collect_guarderia_spend_shape_diagnostics
from ._advisory_bucket_fixture import _bucket  # noqa: F401
from ._advisory_bucket_fixture import operator_text as _operator_text

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_BUCKET_ID = "6b6b6b6b-6b6b-4b6b-8b6b-6b6b6b6b6b6b"
_FILING_YEAR = 2024
_GUARDERIA_CASILLA: CasillaId = "0613"
_ANNUAL_PERIOD = "0A"
_KIND = "guarderia_spend_needs_monthly_detail"

#: A child who turns three DURING the filing year: the extension's own period.
_TURNS_THREE = date(_FILING_YEAR - 3, 4, 15)
#: A child under three for the whole period: the ordinary limb, no shape problem.
_UNDER_THREE = date(_FILING_YEAR - 2, 6, 1)
#: A child already past the extension: no spend counts either way.
_PAST_THREE = date(_FILING_YEAR - 5, 4, 15)


@pytest.fixture
def bucket_id() -> str:
    return _BUCKET_ID


def _revision() -> ModeloRevision:
    return resources().modelos.authority.snapshot("100", filing_year=_FILING_YEAR, period=_ANNUAL_PERIOD).revision


def _write(*descendants: DescendantInfo) -> None:
    facts = [UserProfileFact(path=p, value=v) for p, v in descendant_facts_from_list(list(descendants))]
    set_active_test_profile_facts(tuple(facts))


def _collect() -> tuple[CalculationSourceDiagnostic, ...]:
    return collect_guarderia_spend_shape_diagnostics(
        _revision(),
        {_GUARDERIA_CASILLA: Decimal("0")},
        modelo=Modelo.M100.value,
        bucket_id=_BUCKET_ID,
    )


def _monthly(raw: str) -> tuple[GuarderiaMonthSpend, ...]:
    return parse_guarderia_mensual(raw, field="probe")


# ---------------------------------------------------------------------------
# Fires: the one state where a declared figure counts nothing by shape alone.
# ---------------------------------------------------------------------------


def test_fires_for_an_annual_only_figure_in_the_turning_three_period() -> None:
    _write(DescendantInfo(birth_date=_TURNS_THREE, gastos_guarderia_euros=2400))

    diagnostics = _collect()

    assert len(diagnostics) == 1
    assert diagnostics[0].source_kind == _KIND
    assert diagnostics[0].casilla_id == _GUARDERIA_CASILLA


def test_the_message_names_the_descendant_the_key_and_the_certificate() -> None:
    """The zero is only defensible if the operator can act on the message.

    It has to say which child, which key states the months, and — the part that
    makes this actionable rather than a rule quiz — that the eligible months are
    the ones on the certificate they already hold, because those are what the
    centre determined and reported.
    """
    _write(DescendantInfo(birth_date=_TURNS_THREE, gastos_guarderia_euros=2400))

    message = _operator_text(_collect()[0])

    assert "renta_family.descendiente.0" in message
    assert "GASTOS_GUARDERIA_MENSUAL" in message
    assert "certificate" in message


def test_it_reaches_the_operator_through_the_coordinator() -> None:
    """A collector nothing calls protects nobody.

    This drives the coordinator rather than the collector, so removing the
    wiring line fails here — which is what the direct cases above cannot catch.
    """
    _write(DescendantInfo(birth_date=_TURNS_THREE, gastos_guarderia_euros=2400))

    diagnostics = collect_bucket_aggregation_advisory_diagnostics(
        _revision(),
        {_GUARDERIA_CASILLA: Decimal("0")},
        modelo=Modelo.M100.value,
        bucket_id=_BUCKET_ID,
        period_token=_ANNUAL_PERIOD,
        filing_year=_FILING_YEAR,
    )

    assert _KIND in {d.source_kind for d in diagnostics}


# ---------------------------------------------------------------------------
# Silent: every household the advisory does not describe.
# ---------------------------------------------------------------------------


def test_silent_when_the_monthly_detail_is_already_on_record() -> None:
    """The shape is already the one that works; there is nothing to correct.

    The second-cycle month is declared too, so this asserts the SHAPE advisory's
    silence rather than an empty channel. Without it the sibling advisory fires --
    correctly, because a turning-three window with no declared month is withheld --
    and an unqualified ``== ()`` here would then be asserting that no guardería
    advisory of any kind exists, which is a different and weaker claim.
    """
    _write(
        DescendantInfo(
            birth_date=_TURNS_THREE,
            gastos_guarderia_mensuales=_monthly("5-8:210"),
            segundo_ciclo_infantil_inicio_mes=9,
        ),
    )

    assert _collect() == ()


def test_silent_for_a_child_under_three_for_the_whole_period() -> None:
    """No birthday to apportion across, so an annual total is sufficient."""
    _write(DescendantInfo(birth_date=_UNDER_THREE, gastos_guarderia_euros=2400))

    assert _collect() == ()


def test_silent_for_a_child_past_the_extension() -> None:
    """Nothing counts for them in any shape, so no shape would help."""
    _write(DescendantInfo(birth_date=_PAST_THREE, gastos_guarderia_euros=2400))

    assert _collect() == ()


def test_silent_when_no_guarderia_spend_was_declared_at_all() -> None:
    """The advisory is about a figure that counts nothing, not an absent one.

    This is the majority household. Firing here would make the message ordinary
    noise, which is how an advisory stops being read.
    """
    _write(DescendantInfo(birth_date=_TURNS_THREE))

    assert _collect() == ()


def test_silent_for_a_non_cohabiting_child() -> None:
    """Cohabitation gates the whole limb, so no shape change would grant anything."""
    _write(
        DescendantInfo(
            birth_date=_TURNS_THREE,
            convive_con_contribuyente=False,
            gastos_guarderia_euros=2400,
        ),
    )

    assert _collect() == ()


def test_silent_for_another_modelo() -> None:
    """Only Modelo 100 declares the Art. 81.2 increase."""
    _write(DescendantInfo(birth_date=_TURNS_THREE, gastos_guarderia_euros=2400))

    assert (
        collect_guarderia_spend_shape_diagnostics(
            _revision(),
            {_GUARDERIA_CASILLA: Decimal("0")},
            modelo=Modelo.M303.value,
            bucket_id=_BUCKET_ID,
        )
        == ()
    )


def test_it_names_every_affected_child_in_a_mixed_household() -> None:
    """Per-child, not per-profile: one child's correct shape must not mask another's."""
    _write(
        DescendantInfo(birth_date=_UNDER_THREE, gastos_guarderia_euros=600),
        DescendantInfo(birth_date=_TURNS_THREE, gastos_guarderia_euros=2400),
    )

    message = _collect()[0].message

    assert "renta_family.descendiente.1" in message
    assert "renta_family.descendiente.0" not in message


# ---------------------------------------------------------------------------
# The second-cycle ceiling's two disclosures, which share this collector.
# ---------------------------------------------------------------------------


def test_the_undeclared_second_cycle_month_reaches_the_operator() -> None:
    """A withheld turning-three window must be visible, not merely correct.

    The window is refused when the month is undeclared, which is the safe
    direction — but a refusal the operator cannot see is indistinguishable from
    the child simply not qualifying. This is the assertion that makes the refusal
    recoverable rather than silent, and it is the one the domain predicate alone
    does not give: a predicate nothing emits reaches nobody.
    """
    _write(DescendantInfo(birth_date=_TURNS_THREE, gastos_guarderia_mensuales=_monthly("5-8:210")))

    kinds = {diagnostic.source_kind for diagnostic in _collect()}

    assert "guarderia_segundo_ciclo_month_undeclared" in kinds


def test_the_month_advisory_is_silent_once_the_month_is_declared() -> None:
    """Declared, there is nothing to ask for and the channel stays quiet."""
    _write(
        DescendantInfo(
            birth_date=_TURNS_THREE,
            gastos_guarderia_mensuales=_monthly("5-8:210"),
            segundo_ciclo_infantil_inicio_mes=9,
        ),
    )

    kinds = {diagnostic.source_kind for diagnostic in _collect()}

    assert "guarderia_segundo_ciclo_month_undeclared" not in kinds


def test_the_month_advisory_is_silent_for_a_child_who_never_turns_three() -> None:
    """No ceiling applies outside the turning-three período, so no month is wanted.

    Pins the advisory against the noise failure: a guardería question asked on
    every filing is what teaches operators to stop reading the channel.
    """
    _write(DescendantInfo(birth_date=_UNDER_THREE, gastos_guarderia_mensuales=_monthly("5-8:210")))

    kinds = {diagnostic.source_kind for diagnostic in _collect()}

    assert "guarderia_segundo_ciclo_month_undeclared" not in kinds
