"""The IVA and Renta ledgers gate a prorrata percentage on the same question.

Prorrata decides what fraction of input IVA is deductible. The two ledgers ask
independently whether a register entry yields a usable percentage, so if their
gates ever diverged the same taxpayer's deduction would differ by which ledger
asked. Both now route the regime half through
:func:`~core.regime_apportions_deduction`; these tests bind the behaviour that
makes routing them together correct.

The IVA site additionally tests ``resolution.provenance is None`` where Renta
does not. That reads like a second, stricter rule, and is not one: the domain
resolver only ever emits percentage and provenance together, so the extra test
narrows a type at a construction site and can never change the answer. The
co-presence test below is what keeps that true -- if it ever broke, the two
ledgers really would diverge, and silently.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.prorrata_register import (
    ProrrataProvisionalProvenance,
    ProrrataRegisterRegime,
    regime_apportions_deduction,
)
from ....domain.prorrata_register import (
    ProrrataRegister,
    ProrrataRegisterEntry,
    resolve_provisional_percentage,
)
from .._iva_ledger import _sector_scoped_apportionment

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_EJERCICIO = 2026
_PERCENTAGE = Decimal("64")


def _register(regime: ProrrataRegisterRegime) -> ProrrataRegister:
    """A real single-entry register carrying a resolvable provisional percentage."""
    return ProrrataRegister(
        entries=(
            ProrrataRegisterEntry(
                ejercicio=_EJERCICIO,
                regime=regime,
                especial_transition=None,
                provisional_percentage=_PERCENTAGE,
                provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
                source_observation_ref="303:2025:4T",
            ),
        ),
    )


@pytest.mark.parametrize("regime", list(ProrrataRegisterRegime))
def test_the_iva_gate_follows_the_shared_predicate_for_every_regime(
    regime: ProrrataRegisterRegime,
) -> None:
    """The IVA apportionment resolves exactly when the regime apportions.

    Parametrised over the whole enum rather than the two interesting members, so
    a regime added later is exercised here without anyone remembering to add it.
    """
    apportionment = _sector_scoped_apportionment(_register(regime), _EJERCICIO, sector_id=None)

    assert (apportionment is not None) is regime_apportions_deduction(regime)
    if apportionment is not None:
        assert apportionment.percentage == _PERCENTAGE
        assert apportionment.regime is regime


def test_a_percentage_and_its_provenance_are_resolved_together_or_not_at_all() -> None:
    """Co-presence is what makes the IVA site's extra provenance test a no-op.

    The resolver skips any candidate missing either field, so the result is
    ``(value, value)`` or ``(None, None)`` -- never one without the other. This
    is the invariant under which the IVA gate and the Renta gate ask the same
    question despite testing different numbers of fields.
    """
    entry = ProrrataRegisterEntry(
        ejercicio=_EJERCICIO,
        regime=ProrrataRegisterRegime.GENERAL,
        especial_transition=None,
        provisional_percentage=_PERCENTAGE,
        provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
        source_observation_ref="303:2025:4T",
    )
    resolved = resolve_provisional_percentage((entry,))
    assert (resolved.percentage is None) is (resolved.provenance is None)

    without_percentage = entry.model_copy(update={"provisional_percentage": None})
    unresolved = resolve_provisional_percentage((without_percentage,))
    assert unresolved.percentage is None
    assert unresolved.provenance is None


def test_an_entry_recording_a_regime_but_no_percentage_yields_no_apportionment() -> None:
    """An apportioning regime is necessary but not sufficient.

    The regime gate is only the first half; a register entry that records
    ``GENERAL`` without a provisional percentage still resolves to nothing, and
    no percentage is fabricated to fill the gap.
    """
    register = ProrrataRegister(
        entries=(
            ProrrataRegisterEntry(
                ejercicio=_EJERCICIO,
                regime=ProrrataRegisterRegime.GENERAL,
                especial_transition=None,
                provisional_percentage=None,
                provisional_provenance=None,
            ),
        ),
    )

    assert regime_apportions_deduction(ProrrataRegisterRegime.GENERAL)
    assert _sector_scoped_apportionment(register, _EJERCICIO, sector_id=None) is None


def test_an_absent_entry_yields_no_apportionment() -> None:
    """The ``entry is None`` half of the gate, which both ledgers also share."""
    assert _sector_scoped_apportionment(ProrrataRegister(entries=()), _EJERCICIO, sector_id=None) is None
