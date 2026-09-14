"""M303 export arrivals read Bienes de inversión from the target bucket only."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.period import Period
from ....core.prorrata_register import ProrrataRegisterRegime
from ....domain.bienes_inversion.register import BienesInversionIvaRegister, BienInversionIvaRecord
from ....domain.bienes_inversion.vocabulary import BienInversionKind
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.prorrata_register.register import ProrrataRegister, ProrrataRegisterEntry
from ...aggregation.iva_ledger import IvaLedgerAggregation
from ..export import _resolve_m303_export_arrivals

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _record(identifier: str, *, initial_percentage: Decimal) -> BienInversionIvaRecord:
    return BienInversionIvaRecord(
        identifier=identifier,
        description=f"Bien de inversion {identifier}",
        acquisition_year=2024,
        cuota_soportada=Decimal("5000.00"),
        prorrata_inicial_pct=initial_percentage,
        kind=BienInversionKind.MUEBLE,
        acquisition_ledger_id=f"ledger:{identifier}",
    )


def test_m303_export_arrivals_use_the_work_unit_bound_bienes_register() -> None:
    """Primary evidence cannot bleed into the secondary M303 export arrival."""
    period = Period.from_year_and_code(2026, "4T")
    prorrata_register = ProrrataRegister(
        entries=(
            ProrrataRegisterEntry(
                ejercicio=2026,
                regime=ProrrataRegisterRegime.GENERAL,
                especial_transition=None,
                definitive_percentage=Decimal("60"),
                definitive_volume_con_derecho=Decimal("600.00"),
                definitive_volume_sin_derecho=Decimal("400.00"),
                source_registry_snapshot_refs=(
                    bundled_authority().snapshot("303", filing_year=2026, period="4T").snapshot_ref,
                ),
            ),
        ),
    )
    primary_register = BienesInversionIvaRegister(
        records=(_record("primary-bien", initial_percentage=Decimal("95")),),
    )
    secondary_register = BienesInversionIvaRegister(
        records=(_record("secondary-bien", initial_percentage=Decimal("80")),),
    )
    contributions, resolved_register, regularisation, _bienes_parameters = _resolve_m303_export_arrivals(
        period=period,
        prorrata_register=prorrata_register,
        iva_aggregation=IvaLedgerAggregation(period=period),
        bienes_register=secondary_register,
    )

    assert contributions == ()
    assert tuple(record.identifier for record in resolved_register.records) == ("secondary-bien",)
    assert tuple(row.identifier for row in regularisation.rows) == ("secondary-bien",)
    assert regularisation.pending_percentage_count == 0
    assert tuple(record.identifier for record in primary_register.records) == ("primary-bien",)
