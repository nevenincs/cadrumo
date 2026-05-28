"""Real-behavior tests for _actions module-level IVA-regime enum surface.

S168 asserts that ``_IVA_LEDGER_EXEMPT_REGIMES`` uses ``IVARegime`` enum
members rather than raw strings, so the frozenset membership check is typed
at the schema boundary and cannot silently drift from the canonical enum.
"""

from __future__ import annotations

import pytest

from ...domain.deadlines import IVARegime
from ._actions import _IVA_LEDGER_EXEMPT_REGIMES

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def test_iva_ledger_exempt_regimes_contains_enum_members() -> None:
    """Every element of _IVA_LEDGER_EXEMPT_REGIMES must be an IVARegime member.

    A bare string like ``"SIMPLIFICADO"`` would pass a membership test but
    would bypass the typed surface: IVARegime values compared via StrEnum
    equality will match, but the frozenset must be authored with enum members
    so static analysis and future mypy strict checks can verify the boundary.
    """
    for member in _IVA_LEDGER_EXEMPT_REGIMES:
        assert isinstance(member, IVARegime), (
            f"_IVA_LEDGER_EXEMPT_REGIMES contains a bare string {member!r}; "
            f"expected an IVARegime enum member"
        )


def test_iva_ledger_exempt_regimes_includes_simplificado() -> None:
    """SIMPLIFICADO must be in the exempt set — removing it would silently break ledger bypass."""
    assert IVARegime.SIMPLIFICADO in _IVA_LEDGER_EXEMPT_REGIMES


def test_iva_ledger_exempt_regimes_excludes_general() -> None:
    """GENERAL must not be in the exempt set — it is subject to ledger preflight."""
    assert IVARegime.GENERAL not in _IVA_LEDGER_EXEMPT_REGIMES


def test_iva_regime_enum_covers_all_wizard_choice_values() -> None:
    """All IVARegime members must appear in the wizard's IVA-regime choice list.

    This cross-cuts the wizard ``_IVA_REGIME_CHOICE_VALUES`` derivation (S167)
    against the canonical enum so neither can drift independently.
    """
    from ..wizard._commands import _IVA_REGIME_CHOICE_VALUES

    enum_values = {m.value for m in IVARegime}
    choice_set = set(_IVA_REGIME_CHOICE_VALUES)
    assert enum_values == choice_set, (
        f"Wizard choice values {choice_set!r} do not match IVARegime members {enum_values!r}. "
        "Update _iva_regime_choice_values() or IVARegime."
    )
