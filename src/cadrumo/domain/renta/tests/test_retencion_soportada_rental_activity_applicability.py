"""Whether an urban rental carried on as an activity is declared, read from the declared activities' IAE group.

The rental is activity income, but so is every other activity, so the activity
category alone cannot say whether one exists. RIRPF art. 100 makes the rental's
withholding an activity's; the lessor declares the rental under group 861 of the
IAE tariffs (RDLeg 1175/1990). Each expectation below is derived from that rule,
not from a run.
"""

from __future__ import annotations

import pytest

from ....core.retencion_soportada import RetencionSoportadaClase
from ..retencion_soportada_applicability import (
    RetencionSoportadaApplicability,
    arrendamiento_actividad_applicability,
    retencion_soportada_applicability,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_RENTAL_ACTIVITY = RetencionSoportadaClase.ARRENDAMIENTO_INMUEBLE_URBANO_ACTIVIDAD
_ACTIVITY_INCOME = frozenset({"actividad_economica"})


@pytest.mark.parametrize(
    ("epigraphs", "expected"),
    [
        # Group 861 with or without its epigraph digit, surrounding blanks trimmed.
        (("861.1",), RetencionSoportadaApplicability.DECLARED),
        (("861",), RetencionSoportadaApplicability.DECLARED),
        ((" 861.2 ",), RetencionSoportadaApplicability.DECLARED),
        # One rental among other activities is enough.
        (("844", "861.1"), RetencionSoportadaApplicability.DECLARED),
        # An 861 among unreadable epigraphs still needs the payer evidence.
        (("861", None), RetencionSoportadaApplicability.DECLARED),
        # Another group starting with 8, and the rural rental group 862, are not 861.
        (("841",), RetencionSoportadaApplicability.DECLARED_ABSENT),
        (("862",), RetencionSoportadaApplicability.DECLARED_ABSENT),
        (("751.2", "844"), RetencionSoportadaApplicability.DECLARED_ABSENT),
        # No prefix match: neither a shorter nor a longer group reads as 861.
        (("86",), RetencionSoportadaApplicability.UNKNOWN),
        (("8611",), RetencionSoportadaApplicability.UNKNOWN),
        (("861.12",), RetencionSoportadaApplicability.UNKNOWN),
        # An activity without an epigraph, or with one that does not parse, is unknown.
        ((None,), RetencionSoportadaApplicability.UNKNOWN),
        (("844", "otros"), RetencionSoportadaApplicability.UNKNOWN),
        # No declared activity says nothing either way.
        ((), RetencionSoportadaApplicability.UNKNOWN),
        (None, RetencionSoportadaApplicability.UNKNOWN),
    ],
)
def test_the_rental_activity_is_read_from_the_exact_iae_group(
    epigraphs: tuple[str | None, ...] | None,
    expected: RetencionSoportadaApplicability,
) -> None:
    assert arrendamiento_actividad_applicability(epigraphs) is expected


def test_a_profile_declaring_no_activity_income_proves_the_rental_activity_absent() -> None:
    assert (
        retencion_soportada_applicability(_RENTAL_ACTIVITY, frozenset({"trabajo"}), ("861",))
        is RetencionSoportadaApplicability.DECLARED_ABSENT
    )


def test_declared_activity_income_is_refined_by_the_activities_groups() -> None:
    assert (
        retencion_soportada_applicability(_RENTAL_ACTIVITY, _ACTIVITY_INCOME, ("861.1",))
        is RetencionSoportadaApplicability.DECLARED
    )
    assert (
        retencion_soportada_applicability(_RENTAL_ACTIVITY, _ACTIVITY_INCOME, ("844",))
        is RetencionSoportadaApplicability.DECLARED_ABSENT
    )
    assert (
        retencion_soportada_applicability(_RENTAL_ACTIVITY, _ACTIVITY_INCOME, None)
        is RetencionSoportadaApplicability.UNKNOWN
    )


def test_an_undeclared_category_set_stays_unknown_whatever_the_activities_say() -> None:
    assert (
        retencion_soportada_applicability(_RENTAL_ACTIVITY, None, ("844",)) is RetencionSoportadaApplicability.UNKNOWN
    )


def test_the_other_activity_class_does_not_read_the_epigraphs() -> None:
    assert (
        retencion_soportada_applicability(RetencionSoportadaClase.ACTIVIDAD_ECONOMICA, _ACTIVITY_INCOME, ("861",))
        is RetencionSoportadaApplicability.DECLARED
    )
    assert (
        retencion_soportada_applicability(RetencionSoportadaClase.ACTIVIDAD_ECONOMICA, _ACTIVITY_INCOME, None)
        is RetencionSoportadaApplicability.DECLARED
    )
