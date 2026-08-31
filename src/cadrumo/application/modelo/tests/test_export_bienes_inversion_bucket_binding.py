"""M303 export arrivals read Bienes de inversión from the target bucket only."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.bienes_inversion import BienesInversionIvaRegisterRepository
from ....core.prorrata_register import ProrrataRegisterRegime
from ....core.period import Period
from ....domain.bienes_inversion import BienInversionIvaRecord, BienInversionKind
from ....domain.prorrata_register import ProrrataRegister, ProrrataRegisterEntry
from ....tests.secure_sql import isolated_two_bucket_runtime
from ...aggregation import IvaLedgerAggregation
from .._export import _resolve_m303_export_arrivals

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


def test_m303_export_arrivals_use_the_work_unit_bound_bienes_register(tmp_path: Path) -> None:
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
            ),
        ),
    )
    with isolated_two_bucket_runtime(tmp_path=tmp_path) as runtime:
        BienesInversionIvaRegisterRepository(objects=runtime.primary.repository).add(
            _record("primary-bien", initial_percentage=Decimal("95")),
        )
        with runtime.switch_to_secondary():
            secondary_repository = BienesInversionIvaRegisterRepository(objects=runtime.secondary.repository)
            secondary_repository.add(_record("secondary-bien", initial_percentage=Decimal("80")))
            secondary_register = secondary_repository.load()

        contributions, resolved_register, regularisation = _resolve_m303_export_arrivals(
            period=period,
            prorrata_register=prorrata_register,
            iva_aggregation=IvaLedgerAggregation(period=period),
            bienes_register=secondary_register,
        )

        primary_register = BienesInversionIvaRegisterRepository(objects=runtime.primary.repository).load()

    assert contributions == ()
    assert tuple(record.identifier for record in resolved_register.records) == ("secondary-bien",)
    assert tuple(row.identifier for row in regularisation.rows) == ("secondary-bien",)
    assert regularisation.pending_percentage_count == 0
    assert tuple(record.identifier for record in primary_register.records) == ("primary-bien",)
