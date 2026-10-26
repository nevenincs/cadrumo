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

from cadrumo.core.prorrata_register import ProrrataProvisionalProvenance, ProrrataRegisterRegime
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority as _indexed_authority_for_test
from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot

from ....domain.calculations.registry.prorrata_register_catalogue import (
    regime_apportions_deduction,
    resolve_prorrata_register_catalogue,
)
from ....domain.prorrata_register.register import (
    ProrrataRegister,
    ProrrataRegisterEntry,
    resolve_provisional_percentage,
)
from ..iva_ledger import _sector_scoped_apportionment

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_EJERCICIO = 2026
_PERCENTAGE = Decimal("64")


def _prior_m303_snapshot_ref():
    return published_snapshot("303", filing_year=2025, period="4T").snapshot_ref


def _register(regime: ProrrataRegisterRegime) -> ProrrataRegister:
    """A real single-entry register carrying a resolvable provisional percentage."""
    return ProrrataRegister(
        entries=(
            ProrrataRegisterEntry(
                ejercicio=_EJERCICIO,
                regime=regime,
                especial_transition=None,
                provisional_percentage=_PERCENTAGE,
                provisional_provenance=ProrrataProvisionalProvenance.from_registry("carried_prior_definitiva"),
                source_observation_ref="303:2025:4T",
                source_registry_snapshot_refs=(_prior_m303_snapshot_ref(),),
            ),
        ),
    )


def _registry_regimes() -> tuple[ProrrataRegisterRegime, ...]:
    """Return the registry-declared regimes in their authoritative order."""
    with _indexed_authority_for_test().operation() as operation:
        catalogue = resolve_prorrata_register_catalogue(authority=operation)
        return tuple(definition.token for definition in catalogue.regimes)


@pytest.mark.parametrize("regime", _registry_regimes())
def test_the_iva_gate_follows_the_shared_predicate_for_every_regime(
    regime: ProrrataRegisterRegime,
) -> None:
    """The IVA apportionment resolves exactly when the regime apportions.

    Parametrised over the whole registry vocabulary rather than the two
    interesting members, so a regime added later is exercised here without
    anyone remembering to add it.
    """
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        apportionment = _sector_scoped_apportionment(
            _register(regime), _EJERCICIO, sector_id=None, operation=_authority_operation_for_test
        )

        assert (apportionment is not None) is regime_apportions_deduction(regime)
        if apportionment is not None:
            assert apportionment.percentage == _PERCENTAGE
            assert apportionment.regime == regime


def test_a_percentage_and_its_provenance_are_resolved_together_or_not_at_all() -> None:
    """Co-presence is what makes the IVA site's extra provenance test a no-op.

    The resolver skips any candidate missing either field, so the result is
    ``(value, value)`` or ``(None, None)`` -- never one without the other. This
    is the invariant under which the IVA gate and the Renta gate ask the same
    question despite testing different numbers of fields.
    """
    entry = ProrrataRegisterEntry(
        ejercicio=_EJERCICIO,
        regime=ProrrataRegisterRegime.from_registry("general"),
        especial_transition=None,
        provisional_percentage=_PERCENTAGE,
        provisional_provenance=ProrrataProvisionalProvenance.from_registry("carried_prior_definitiva"),
        source_observation_ref="303:2025:4T",
        source_registry_snapshot_refs=(_prior_m303_snapshot_ref(),),
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
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        register = ProrrataRegister(
            entries=(
                ProrrataRegisterEntry(
                    ejercicio=_EJERCICIO,
                    regime=ProrrataRegisterRegime.from_registry("general"),
                    especial_transition=None,
                    provisional_percentage=None,
                    provisional_provenance=None,
                    source_registry_snapshot_refs=(),
                ),
            ),
        )

        assert regime_apportions_deduction(ProrrataRegisterRegime.from_registry("general"))
        assert (
            _sector_scoped_apportionment(register, _EJERCICIO, sector_id=None, operation=_authority_operation_for_test)
            is None
        )


def test_an_absent_entry_yields_no_apportionment() -> None:
    """The ``entry is None`` half of the gate, which both ledgers also share."""
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        assert (
            _sector_scoped_apportionment(
                ProrrataRegister(entries=()), _EJERCICIO, sector_id=None, operation=_authority_operation_for_test
            )
            is None
        )
