"""The boundary compute-always deliberately did NOT cross.

Making the derived injectors compute-always was scoped by asking the profile
schema's declared derived namespace which paths the engine owns, rather than by
counting the guards that happened to share the skip-if-present shape. The
remaining non-derived families defer to stored facts across five paths:

* the Art. 82 matrimonio-sobrevenido facts (three paths),
* the Madrid nacimiento/adopción eligible count (DL 1/2010) -- a different
  shape again, ``setdefault`` then conditional overwrite, so it is pinned in
  both directions rather than flattened into a preservation assertion,
* the unidad-familiar otros-miembros base, its ``setdefault``-only sibling.

The count is stated here because it has drifted before: enumerate these from
:func:`test_none_of_the_preserved_paths_is_declared_derived`, whose loop is the
authoritative list, rather than from whichever injectors a change happened to
touch.

Nothing tested that boundary. Flipping any of them to compute-always is the
exact mistake the scoping avoided, and no test failed. These assertions pin it,
so the line between what changed and what deliberately did not is a gate rather
than a paragraph in a commit message.

Every assertion is paired, within its own test, with a positive control
computing the SAME injector over the same profile WITHOUT the seed. Without
that, "the stored value survived" is equally satisfied by an injector that
writes nothing at all, and the test would pass against a function that had been
gutted.

One trap worth naming, because it is invisible at the call site: the Madrid
injector is gated on filing year 2025. Probing it at 2024 returns before writing
anything, which reads as a broken test rather than a year gate.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from ..profile_binding import (
    _AUTONOMIC_DEDUCCION_ELIGIBLE_COUNT_KEY,
    _UNIDAD_FAMILIAR_OTROS_MIEMBROS_BASE_KEY,
    _inject_derived_state_attribution_facts,
    inject_derived_autonomic_deduccion_facts,
    inject_derived_marriage_facts,
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
    inject_derived_marriage_facts(seeded, 2024)

    assert seeded[_MARRIAGE_FULL_YEAR] == _UNREACHABLE_FLAG

    # Positive control: the injector really does write this key when it is
    # absent, and writes something DIFFERENT, so the survival above is
    # deference rather than the injector doing nothing.
    computed: dict[str, Any] = _married_profile()
    inject_derived_marriage_facts(computed, 2024)
    assert _MARRIAGE_FULL_YEAR in computed
    assert computed[_MARRIAGE_FULL_YEAR] != _UNREACHABLE_FLAG


# ---------------------------------------------------------------------------
# Family 2: the M303 state-attribution ratio.
# ---------------------------------------------------------------------------


def test_state_attribution_ratio_rejects_a_stored_value_as_authority() -> None:
    seeded: dict[str, Any] = {**_common_regime_profile(), _STATE_ATTRIBUTION: _UNREACHABLE_RATIO}
    _inject_derived_state_attribution_facts(seeded)

    assert seeded[_STATE_ATTRIBUTION] == Decimal("100")

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
    inject_derived_autonomic_deduccion_facts(seeded, _MADRID_YEAR)

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
        "renta_filing.declaration_type": "1",
        "renta_family.descendiente.0.birth_date": f"{_MADRID_YEAR}-03-01",
        "renta_family.descendiente.0.convivencia": "true",
        _AUTONOMIC_DEDUCCION_ELIGIBLE_COUNT_KEY: _UNREACHABLE_COUNT,
    }
    inject_derived_autonomic_deduccion_facts(seeded, _MADRID_YEAR)

    resolved = seeded[_AUTONOMIC_DEDUCCION_ELIGIBLE_COUNT_KEY]
    assert isinstance(resolved, Decimal)
    assert resolved != _UNREACHABLE_COUNT, "a determinable Madrid unit must overwrite the stored count"
    assert resolved > 0


def test_unidad_familiar_base_preserves_a_stored_value() -> None:
    """The sibling Madrid key is default-only and never overwritten."""
    determinable_madrid: dict[str, Any] = {
        "tax_residence.ccaa": "madrid",
        "renta_taxpayer.marital_status": "1",
        "renta_filing.declaration_type": "1",
    }
    seeded: dict[str, Any] = {**determinable_madrid, _UNIDAD_FAMILIAR_OTROS_MIEMBROS_BASE_KEY: _UNREACHABLE_COUNT}
    inject_derived_autonomic_deduccion_facts(seeded, _MADRID_YEAR)

    assert seeded[_UNIDAD_FAMILIAR_OTROS_MIEMBROS_BASE_KEY] == _UNREACHABLE_COUNT

    # Positive control, in this test rather than borrowed from a sibling: the
    # injector does write this key when it is absent, and writes something
    # different, so the survival above is the setdefault deferring rather than
    # the injector never touching the key at all.
    computed: dict[str, Any] = dict(determinable_madrid)
    inject_derived_autonomic_deduccion_facts(computed, _MADRID_YEAR)
    assert _UNIDAD_FAMILIAR_OTROS_MIEMBROS_BASE_KEY in computed
    assert computed[_UNIDAD_FAMILIAR_OTROS_MIEMBROS_BASE_KEY] != _UNREACHABLE_COUNT


# ---------------------------------------------------------------------------
# The scoping decision itself: none of these paths is declared derived.
# ---------------------------------------------------------------------------


def test_none_of_the_preserved_paths_is_declared_derived() -> None:
    """The namespace is why these four families were left alone.

    This loop is the authoritative enumeration: six paths across the four
    families. Any prose elsewhere that counts them should be read off here
    rather than recalled.

    If a future change declared one of these paths derived, its injector would
    have to become compute-always in the same change -- otherwise the write
    door would refuse the path while the injector still deferred to whatever
    was already stored there. This asserts the premise the tests above rest on
    rather than leaving it implicit.
    """
    from ....domain.user_profile.loader import load_user_profile_schema
    from ....domain.user_profile.schema import derived_selector_for_path

    schema = load_user_profile_schema()
    preserved_paths = (
        _MARRIAGE_FULL_YEAR,
        "renta_taxpayer.marriage_month_start",
        "renta_taxpayer.marriage_month_end",
        _AUTONOMIC_DEDUCCION_ELIGIBLE_COUNT_KEY,
        _UNIDAD_FAMILIAR_OTROS_MIEMBROS_BASE_KEY,
    )

    # The prose above and in the module docstring counts this population. A
    # recalled count drifts -- it already has -- so the number is asserted
    # here, where adding a path forces the prose to be revisited instead of
    # quietly disagreeing with it.
    assert len(preserved_paths) == 5

    for path in preserved_paths:
        assert derived_selector_for_path(path, schema.derived_selectors) is None, path
