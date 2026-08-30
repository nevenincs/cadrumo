"""Territorial-regime region-scoped deductibility selection (region-Renta D1/D4).

These tests pin the region layer added to the Renta expense-deductibility surface:
the optional ``residence_ccaa`` axis on
:class:`~domain.renta.RentaDeductibilityContext` (D1) and the
:func:`~domain.renta.select_deductibility_profile` fail-closed selection (D4).
General expense deductibility is state base-imponible law and does not vary by
comunidad, so the override layer
(:func:`~domain.renta.resolve_region_category_profiles`) is provisioned empty;
the selection mechanism is exercised here with a SYNTHETIC override profile to
prove the wiring and the fail-closed refusal, never a real territorial-regime
figure.

See Also:
    :class:`~domain.contribuyente.CCAA`
        Closed ordinary-residence comunidad enum used as the selector key.
    :class:`~domain.categories.CategoryProfile`
        Deductibility profile selected from state law or a regional override.
    :func:`~application.aggregation._renta_ledger.aggregate_renta_ledger_expenses`
        Application aggregation caller that forwards the region axis into Renta.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core.i18n import Translatable as tr
from ....tests.aeat_literal_fixtures import RENTA_DEDUCIBILIDAD_CITATION_URL_FIXTURE
from ...categories import (
    CategoryCitation,
    CategoryCitationSource,
    CategoryProfile,
    ProportionalityKind,
    ProportionalityRule,
    SpendingCategory,
    parse_http_url,
)
from ...contribuyente.ccaa import CCAA
from .. import (
    RentaDeductibilityContext,
    resolve_region_category_profiles,
    select_deductibility_profile,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_CATEGORY = SpendingCategory.MATERIAL_OFICINA


def _citation() -> CategoryCitation:
    return CategoryCitation(
        source=CategoryCitationSource.MANUAL_RENTA,
        reference="Manual practico Renta 2025",
        locator="test",
        url=parse_http_url(RENTA_DEDUCIBILIDAD_CITATION_URL_FIXTURE),
        quote=tr("Texto de prueba para una regla de deducibilidad."),
        valid_from=date(2025, 1, 1),
        valid_to=date(2025, 12, 31),
    )


def _profile(kind: ProportionalityKind, *, fixed_pct: str | None = None) -> CategoryProfile:
    rule = ProportionalityRule(
        kind=kind,
        fixed_pct=Decimal(fixed_pct) if fixed_pct is not None else None,
        citations=(_citation(),),
        notes=tr("Regla de prueba para la seleccion territorial."),
    )
    return CategoryProfile(
        category=_CATEGORY,
        display_label=tr(f"Perfil de prueba {kind.value}"),
        proportionality=rule,
    )


_STATE_PROFILE = _profile(ProportionalityKind.FULL_DEDUCTIBLE)
_OVERRIDE_PROFILE = _profile(ProportionalityKind.FIXED_PERCENTAGE, fixed_pct="0.50")


def _context(residence_ccaa: CCAA | None) -> RentaDeductibilityContext:
    return RentaDeductibilityContext(profile_year=2025, residence_ccaa=residence_ccaa)


def test_residence_ccaa_defaults_to_none_and_accepts_a_member() -> None:
    """The D1 axis is optional (default ``None``) and accepts a CCAA member."""
    assert RentaDeductibilityContext(profile_year=2025).residence_ccaa is None
    assert _context(CCAA.CANARIAS).residence_ccaa is CCAA.CANARIAS


def test_override_layer_is_provisioned_but_empty() -> None:
    """No SpendingCategory warrants a per-comunidad expense override today (D2-C)."""
    assert dict(resolve_region_category_profiles(2024)) == {}
    assert dict(resolve_region_category_profiles(2025)) == {}


def test_no_override_returns_state_profile_regardless_of_region() -> None:
    """General expense deductibility is state law: no override -> state profile."""
    for residence in (None, CCAA.MADRID, CCAA.CANARIAS):
        selected = select_deductibility_profile(
            state_profile=_STATE_PROFILE,
            region_override_profiles={},
            context=_context(residence),
        )
        assert selected is _STATE_PROFILE


def test_override_with_undeclared_region_fails_closed() -> None:
    """D4: an override exists for the category but ``residence_ccaa`` is None -> None."""
    selected = select_deductibility_profile(
        state_profile=_STATE_PROFILE,
        region_override_profiles={CCAA.CANARIAS: _OVERRIDE_PROFILE},
        context=_context(None),
    )
    assert selected is None


def test_override_selected_when_residence_matches() -> None:
    """A declared residence with an override for that comunidad selects the override."""
    selected = select_deductibility_profile(
        state_profile=_STATE_PROFILE,
        region_override_profiles={CCAA.CANARIAS: _OVERRIDE_PROFILE},
        context=_context(CCAA.CANARIAS),
    )
    assert selected is _OVERRIDE_PROFILE


def test_override_for_other_region_falls_through_to_state() -> None:
    """A residence outside the overridden comunidad gets state law, not the override."""
    selected = select_deductibility_profile(
        state_profile=_STATE_PROFILE,
        region_override_profiles={CCAA.CANARIAS: _OVERRIDE_PROFILE},
        context=_context(CCAA.MADRID),
    )
    assert selected is _STATE_PROFILE
