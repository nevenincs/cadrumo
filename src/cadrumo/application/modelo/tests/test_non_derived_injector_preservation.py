"""The boundary compute-always deliberately did NOT cross.

Making the derived injectors compute-always was scoped by asking the profile
schema's declared derived namespace which paths the engine owns, rather than by
counting the guards that happened to share the skip-if-present shape. Three
injector families share that shape and are NOT declared derived, so they keep
deferring to a stored fact:

* the Art. 82 matrimonio-sobrevenido facts,
* the M303 state-attribution ratio,
* the Madrid nacimiento/adopción pair (DL 1/2010) -- which is a different
  shape again and is pinned separately below.

Nothing tested that boundary. Flipping any of them to compute-always is the
exact mistake the scoping avoided, and no test failed. These assertions pin it,
so the line between what changed and what deliberately did not is a gate rather
than a paragraph in a commit message.

Every assertion is paired with a positive control computing the SAME injector
over the same profile WITHOUT the seed. Without that, "the stored value
survived" is equally satisfied by an injector that writes nothing at all, and
the test would pass against a function that had been gutted.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from .._profile_binding import (
    _AUTONOMIC_DEDUCCION_ELIGIBLE_COUNT_KEY,
    _UNIDAD_FAMILIAR_OTROS_MIEMBROS_BASE_KEY,
    _inject_derived_autonomic_deduccion_facts,
    _inject_derived_marriage_facts,
    _inject_derived_state_attribution_facts,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MARRIAGE_FULL_YEAR = "renta_taxpayer.marriage_full_year"
_STATE_ATTRIBUTION = "tax_residence.state_attribution_ratio"
_MADRID_YEAR = 2025

#: Values no branch of these injectors can produce. The marriage flag is 0 or 1,
#: the attribution ratio is 1 or 0, and the Madrid count is a non-negative
#: prorrateo share of the declared descendants -- of which these profiles
#: declare none. A survivor equal to one of these therefore cannot be the
#: computation coincidentally agreeing with the seed.
_UNREACHABLE_FLAG = Decimal("7")
_UNREACHABLE_RATIO = Decimal("0.5")
_UNREACHABLE_COUNT = Decimal("42")


def _married_profile() -> dict[str, Any]:
    return {"renta_taxpayer.marriage_date": date(2024, 6, 1)}


def _common_regime_profile() -> dict[str, Any]:
    return {"tax_residence.jurisdiction_scope": "common_regime"}


# ---------------------------------------------------------------------------
# Family 1: the Art. 82 matrimonio-sobrevenido facts.
# ---------------------------------------------------------------------------


def test_marriage_facts_preserve_a_stored_value() -> None:
    seeded: dict[str, Any] = {**_married_profile(), _MARRIAGE_FULL_YEAR: _UNREACHABLE_FLAG}
    _inject_derived_marriage_facts(seeded, 2024)

    assert seeded[_MARRIAGE_FULL_YEAR] == _UNREACHABLE_FLAG

    # Positive control: the injector really does write this key when it is
    # absent, and writes something DIFFERENT, so the survival above is
    # deference rather than the injector doing nothing.
    computed: dict[str, Any] = _married_profile()
    _inject_derived_marriage_facts(computed, 2024)
    assert _MARRIAGE_FULL_YEAR in computed
    assert computed[_MARRIAGE_FULL_YEAR] != _UNREACHABLE_FLAG


# ---------------------------------------------------------------------------
# Family 2: the M303 state-attribution ratio.
# ---------------------------------------------------------------------------


def test_state_attribution_ratio_preserves_a_stored_value() -> None:
    seeded: dict[str, Any] = {**_common_regime_profile(), _STATE_ATTRIBUTION: _UNREACHABLE_RATIO}
    _inject_derived_state_attribution_facts(seeded)

    assert seeded[_STATE_ATTRIBUTION] == _UNREACHABLE_RATIO

    computed: dict[str, Any] = _common_regime_profile()
    _inject_derived_state_attribution_facts(computed)
    assert _STATE_ATTRIBUTION in computed
    assert computed[_STATE_ATTRIBUTION] != _UNREACHABLE_RATIO


# ---------------------------------------------------------------------------
# Family 3: the Madrid nacimiento/adopción pair -- a DIFFERENT shape.
#
# Not skip-if-present. It unconditionally ``setdefault``s a neutral zero so the
# casilla-1039 formula resolves for every filer, then OVERWRITES the count for a
# determinable Madrid unit with eligible descendants. So a stored value survives
# in one direction and is replaced in the other, and flattening it into the same
# preservation assertion as the two families above would pin behaviour it does
# not have.
# ---------------------------------------------------------------------------


def test_madrid_count_preserves_a_stored_value_for_a_non_madrid_filer() -> None:
    """Outside Madrid the injector only defaults, so a stored value survives."""
    seeded: dict[str, Any] = {
        "tax_residence.ccaa": "cataluna",
        _AUTONOMIC_DEDUCCION_ELIGIBLE_COUNT_KEY: _UNREACHABLE_COUNT,
    }
    _inject_derived_autonomic_deduccion_facts(seeded, _MADRID_YEAR)

    assert seeded[_AUTONOMIC_DEDUCCION_ELIGIBLE_COUNT_KEY] == _UNREACHABLE_COUNT
    # The neutral default still lands on the sibling key it does own.
    assert seeded[_UNIDAD_FAMILIAR_OTROS_MIEMBROS_BASE_KEY] == Decimal("0")


def test_madrid_count_is_overwritten_for_a_determinable_madrid_unit() -> None:
    """Inside Madrid, determinable, with an eligible descendant, the count wins.

    The override direction of the same injector. Pinned so the preservation
    assertion above cannot be read as "this key is never computed".
    """
    seeded: dict[str, Any] = {
        "tax_residence.ccaa": "madrid",
        "renta_taxpayer.marital_status": "1",
        "filing_export.declaration_type": "1",
        "renta_family.descendiente.0.birth_date": f"{_MADRID_YEAR}-03-01",
        "renta_family.descendiente.0.convivencia": "true",
        _AUTONOMIC_DEDUCCION_ELIGIBLE_COUNT_KEY: _UNREACHABLE_COUNT,
    }
    _inject_derived_autonomic_deduccion_facts(seeded, _MADRID_YEAR)

    resolved = seeded[_AUTONOMIC_DEDUCCION_ELIGIBLE_COUNT_KEY]
    assert isinstance(resolved, Decimal)
    assert resolved != _UNREACHABLE_COUNT, "a determinable Madrid unit must overwrite the stored count"
    assert resolved > 0


def test_unidad_familiar_base_preserves_a_stored_value() -> None:
    """The sibling Madrid key is default-only and never overwritten."""
    seeded: dict[str, Any] = {
        "tax_residence.ccaa": "madrid",
        "renta_taxpayer.marital_status": "1",
        "filing_export.declaration_type": "1",
        _UNIDAD_FAMILIAR_OTROS_MIEMBROS_BASE_KEY: _UNREACHABLE_COUNT,
    }
    _inject_derived_autonomic_deduccion_facts(seeded, _MADRID_YEAR)

    assert seeded[_UNIDAD_FAMILIAR_OTROS_MIEMBROS_BASE_KEY] == _UNREACHABLE_COUNT


# ---------------------------------------------------------------------------
# The scoping decision itself: none of these paths is declared derived.
# ---------------------------------------------------------------------------


def test_none_of_the_preserved_paths_is_declared_derived() -> None:
    """The namespace is why these three families were left alone.

    If a future change declared one of these paths derived, its injector would
    have to become compute-always in the same change -- otherwise the write
    door would refuse the path while the injector still deferred to whatever
    was already stored there. This asserts the premise the tests above rest on
    rather than leaving it implicit.
    """
    from ....domain.user_profile import derived_selector_for_path, load_user_profile_schema

    schema = load_user_profile_schema()
    for path in (
        _MARRIAGE_FULL_YEAR,
        "renta_taxpayer.marriage_month_start",
        "renta_taxpayer.marriage_month_end",
        _STATE_ATTRIBUTION,
        _AUTONOMIC_DEDUCCION_ELIGIBLE_COUNT_KEY,
        _UNIDAD_FAMILIAR_OTROS_MIEMBROS_BASE_KEY,
    ):
        assert derived_selector_for_path(path, schema.derived_selectors) is None, path
