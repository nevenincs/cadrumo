"""Regression test: build_overview_calendar and build_overview_explain agree.

Asserts that for the same profile, the ``ApplicabilityVerdict`` derived
by :func:`build_overview_calendar` (which calls
:func:`derive_modelo_applicability` internally for each obligation in
the schedule) matches the verdict returned by
:func:`build_overview_explain` for every modelo the deadline engine
produces an obligation for.

The test pins the CURRENT agreement state. A future regression where
one surface diverges from the other will be caught immediately.

Design:
- Uses ``show_suppressed=True`` so the calendar captures ALL modelos —
  both applicable (``entries``) and filtered (``suppressed_entries``).
- Calls ``build_overview_explain`` for each captured modelo and compares
  verdicts.
- Tests the core persona set (autónomo, sociedad limitada, landlord,
  attribution entity) to cover all four :class:`ApplicabilityVerdict`
  branches across the rule table.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

import pytest

from ....domain.calculations.registry.applicability import ApplicabilityVerdict
from ....domain.contribuyente.entity_type import EntityType
from ....domain.deadlines.models import IrpfEstimationRegime, IrpfIncomeCategory, IVARegime, TaxpayerProfile
from ..calendar import build_overview_calendar
from ..calendar_models import OverviewCalendarRange
from ..explain import build_overview_explain

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CALENDAR_RANGE = OverviewCalendarRange(
    from_date=date(2026, 1, 1),
    to_date=date(2026, 12, 31),
)
_TODAY = date(2026, 4, 1)


def _autonomo() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="X1234567L",
        entity_type=EntityType.NATURAL_PERSON,
        irpf_income_categories=frozenset({IrpfIncomeCategory.ACTIVIDAD_ECONOMICA}),
        irpf_estimation_regime=IrpfEstimationRegime.DIRECTA_NORMAL,
        iva_regime=IVARegime.GENERAL,
    )


def _sociedad_limitada() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="B12345674",
        entity_type=EntityType.LEGAL_ENTITY,
        irpf_income_categories=frozenset(),
        iva_regime=IVARegime.GENERAL,
    )


def _landlord() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="X9876543K",
        entity_type=EntityType.NATURAL_PERSON,
        irpf_income_categories=frozenset({IrpfIncomeCategory.CAPITAL_INMOBILIARIO}),
        iva_regime=IVARegime.GENERAL,
    )


def _attribution_entity() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="E12345674",
        entity_type=EntityType.ATTRIBUTION_ENTITY,
        irpf_income_categories=frozenset(),
        iva_regime=IVARegime.GENERAL,
    )


def _collect_verdicts_from_calendar(profile: TaxpayerProfile) -> dict[str, ApplicabilityVerdict]:
    """Build a calendar with suppressed entries and collect verdict per modelo.

    Returns {modelo: verdict} for all modelos the engine produced at
    least one obligation for, merging applicable and suppressed entries.
    When the same modelo appears in both active and suppressed (impossible
    by construction but guarded), the applicable verdict wins.
    """
    cal = build_overview_calendar(
        profile,
        _CALENDAR_RANGE,
        today=_TODAY,
        show_suppressed=True,
    )
    verdicts: dict[str, ApplicabilityVerdict] = {}
    for entry in cal.suppressed_entries:
        verdicts[entry.modelo] = entry.verdict
    # Applicable entries overwrite any suppressed entry for the same modelo
    for entry in cal.entries:
        verdicts[entry.modelo] = ApplicabilityVerdict.APPLICABLE
    return verdicts


def _collect_verdicts_from_explain(
    profile: TaxpayerProfile,
    modelos: set[str],
) -> dict[str, ApplicabilityVerdict]:
    """Call build_overview_explain for each modelo and collect the verdict."""
    verdicts: dict[str, ApplicabilityVerdict] = {}
    for modelo in modelos:
        explain = build_overview_explain(profile, modelo=modelo, year=2026)
        verdicts[modelo] = explain.verdict
    return verdicts


@pytest.mark.parametrize(
    "profile_factory",
    [
        _autonomo,
        _sociedad_limitada,
        _landlord,
        _attribution_entity,
    ],
    ids=["autonomo", "sociedad_limitada", "landlord", "attribution_entity"],
)
def test_calendar_and_explain_agree_on_applicability_verdict(
    profile_factory: Callable[[], TaxpayerProfile],
) -> None:
    """Calendar and explain surfaces agree on the verdict for every modelo.

    For every modelo the deadline engine produces an obligation for (in
    any verdict state), the applicability verdict returned by the calendar
    path must be identical to the verdict returned by the explain path.

    This pins the agreement state as of the contract landing commit. A
    regression in either surface will be caught by this test.
    """
    profile = profile_factory()
    calendar_verdicts = _collect_verdicts_from_calendar(profile)

    assert calendar_verdicts, (
        f"No obligations produced for profile {profile.entity_type}; "
        "either the registry has no deadline windows or the calendar range "
        "covers no registered modelos. Check _CALENDAR_RANGE and registry data."
    )

    explain_verdicts = _collect_verdicts_from_explain(profile, set(calendar_verdicts))

    mismatches: list[str] = []
    for modelo in sorted(calendar_verdicts):
        cal_verdict = calendar_verdicts[modelo]
        exp_verdict = explain_verdicts.get(modelo)
        if exp_verdict is None:
            mismatches.append(f"  {modelo}: calendar={cal_verdict.value!r} explain=MISSING")
        elif cal_verdict is not exp_verdict:
            mismatches.append(f"  {modelo}: calendar={cal_verdict.value!r} explain={exp_verdict.value!r}")

    if mismatches:
        formatted = "\n".join(mismatches)
        pytest.fail(
            f"calendar and explain disagree on applicability verdict for profile {profile.entity_type}:\n{formatted}",
        )


def test_derive_modelo_applicability_is_the_shared_implementation() -> None:
    """Both surfaces call the same derive_modelo_applicability function.

    Structural pin: the function imported via the explain module and the
    function imported via the calendar module are identity-equal. This
    ensures both surfaces use the same rule table and there is no
    divergence path through a separate implementation.
    """
    from inspect import getclosurevars

    from .. import calendar as calendar_module

    calendar_fn = calendar_module._derive_modelo_applicability
    explain_fn = getclosurevars(build_overview_explain).globals["derive_modelo_applicability"]

    assert calendar_fn is explain_fn, (
        "calendar and explain modules import different derive_modelo_applicability "
        "objects — they may use separate rule tables and produce divergent verdicts"
    )
