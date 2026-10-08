"""Applicability projection for annual prorrata regularizacion.

See Also:
    :func:`~application.calculations._prorrata_regularizacion.derive_prorrata_applicability`
        Pure fail-closed-to-visible projection exercised by this test module.
    :class:`~application.calculations._prorrata_regularizacion.ProrrataApplicabilityProjection`
        Result type carrying the boolean applicability decision and evidence
        kinds asserted here.
    :class:`~application.calculations._prorrata_regularizacion.ProrrataDeclaredVolumeLedgerRollup`
        Ledger-side volume carrier used for projected sin-derecho evidence.
    :class:`~domain.prorrata_register.ProrrataRegisterEntry`
        Register entry input proving active taxpayer prorrata state.
    :class:`~core.ProrrataRegisterRegime`
        Closed taxpayer-state axis distinguishing general, especial, and no
        prorrata applicability.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.prorrata_register import ProrrataRegisterRegime
from ....domain.prorrata_register.register import ProrrataRegisterEntry
from ..prorrata_regularizacion import (
    ProrrataDeclaredVolumeLedgerRollup,
    build_prorrata_declared_volume_advisory,
    derive_prorrata_applicability,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]


def _entry(regime: ProrrataRegisterRegime) -> ProrrataRegisterEntry:
    return ProrrataRegisterEntry(
        ejercicio=2026,
        regime=regime,
        especial_transition=None,
        source_registry_snapshot_refs=(),
    )


def test_prorrata_applies_when_register_holds_active_general_entry() -> None:
    projection = derive_prorrata_applicability(
        register_entries=(_entry(ProrrataRegisterRegime.from_registry("general")),)
    )

    assert projection.applies is True
    assert projection.register_active is True
    assert projection.evidence_kinds == ("register_active",)


def test_prorrata_applies_when_register_holds_active_especial_entry() -> None:
    projection = derive_prorrata_applicability(
        register_entries=(_entry(ProrrataRegisterRegime.from_registry("especial")),)
    )

    assert projection.applies is True
    assert projection.evidence_kinds == ("register_active",)


def test_prorrata_applies_from_declared_sin_derecho_volume_without_register_entry() -> None:
    projection = derive_prorrata_applicability(
        declared_volume_total=Decimal("100000.00"),
        declared_volume_con_derecho=Decimal("80000.00"),
    )

    assert projection.applies is True
    assert projection.register_active is False
    assert projection.declared_volume_sin_derecho == Decimal("20000.00")
    assert projection.evidence_kinds == ("declared_sin_derecho_volume",)


def test_prorrata_applies_from_ledger_projected_sin_derecho_volume() -> None:
    rollup = ProrrataDeclaredVolumeLedgerRollup(
        declared_volume_total=Decimal("100000.00"),
        declared_volume_con_derecho=Decimal("100000.00"),
        declared_volume_sin_derecho=Decimal("0.00"),
        ledger_volume_total=Decimal("120000.00"),
        ledger_volume_con_derecho=Decimal("90000.00"),
        ledger_volume_sin_derecho=Decimal("30000.00"),
    )

    projection = derive_prorrata_applicability(ledger_rollup=rollup)

    assert projection.applies is True
    assert projection.ledger_volume_sin_derecho == Decimal("30000.00")
    assert projection.evidence_kinds == ("ledger_sin_derecho_volume",)


def test_prorrata_does_not_apply_for_ninguna_and_full_declared_right_to_deduct() -> None:
    projection = derive_prorrata_applicability(
        register_entries=(_entry(ProrrataRegisterRegime.from_registry("ninguna")),),
        declared_volume_total=Decimal("100000.00"),
        declared_volume_con_derecho=Decimal("100000.00"),
    )

    assert projection.applies is False
    assert projection.register_active is False
    assert projection.declared_volume_sin_derecho == Decimal("0.00")
    assert projection.evidence_kinds == ()


def test_declared_volume_inputs_must_travel_together() -> None:
    with pytest.raises(ValueError, match="declared_volume_total and declared_volume_con_derecho"):
        derive_prorrata_applicability(declared_volume_total=Decimal("100000.00"))


@pytest.mark.parametrize(
    ("declared", "unknown", "reason"),
    [
        (Decimal("250"), (), None),
        (Decimal("300"), (), "prorrata_volume_divergence"),
        (Decimal("300"), ("unclassified",), "prorrata_volume_check_unavailable"),
        (None, (), "prorrata_volume_declaration_missing"),
    ],
)
def test_volume_advisory_distinguishes_disagreement_from_unknown_or_absent_facts(
    declared: Decimal | None, unknown: tuple[str, ...], reason: str | None
) -> None:
    rollup = ProrrataDeclaredVolumeLedgerRollup(
        declared_volume_total=declared,
        declared_volume_con_derecho=Decimal("200"),
        declared_volume_sin_derecho=declared - Decimal("200") if declared is not None else None,
        ledger_volume_total=Decimal("250"),
        ledger_volume_con_derecho=Decimal("200"),
        ledger_volume_sin_derecho=Decimal("50"),
        included_ledger_ids=("sale", "exempt"),
        unclassified_ledger_ids=unknown,
    )
    diagnostic = build_prorrata_declared_volume_advisory(rollup, ejercicio=2026)
    assert (diagnostic.reason if diagnostic else None) == reason
