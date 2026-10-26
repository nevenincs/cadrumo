"""M303 export arrivals read Bienes de inversión from the target bucket only."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation

from ....core.period import Period
from ....core.prorrata_register import ProrrataRegisterRegime
from ....domain.bienes_inversion.register import BienesInversionIvaRegister, BienInversionIvaRecord
from ....domain.bienes_inversion.regularizacion_parameters import (
    BienesInversionParameterResolutionError,
    resolve_bienes_inversion_regularizacion_parameters,
)
from ....domain.bienes_inversion.vocabulary import BienInversionKind
from ....domain.calculations.registry.tests.published_authority import published_snapshot
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
        kind=BienInversionKind.from_registry("mueble"),
        acquisition_ledger_id=f"ledger:{identifier}",
    )


def test_m303_export_arrivals_use_the_work_unit_bound_bienes_register(*, operation: PinnedAuthorityOperation) -> None:
    """Primary evidence cannot bleed into the secondary M303 export arrival."""
    period = Period.from_year_and_code(2026, "4T")
    prorrata_register = ProrrataRegister(
        entries=(
            ProrrataRegisterEntry(
                ejercicio=2026,
                regime=ProrrataRegisterRegime.from_registry("general"),
                especial_transition=None,
                definitive_percentage=Decimal("60"),
                definitive_volume_con_derecho=Decimal("600.00"),
                definitive_volume_sin_derecho=Decimal("400.00"),
                source_registry_snapshot_refs=(published_snapshot("303", filing_year=2026, period="4T").snapshot_ref,),
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
        operation=operation,
    )

    assert contributions == ()
    assert tuple(record.identifier for record in resolved_register.records) == ("secondary-bien",)
    assert tuple(row.identifier for row in regularisation.rows) == ("secondary-bien",)
    assert regularisation.pending_percentage_count == 0
    assert tuple(record.identifier for record in primary_register.records) == ("primary-bien",)


@pytest.mark.parametrize(
    ("filing_year", "period_token", "revision_id", "resolved_on"),
    [
        (2024, "1T", "2024-hasta-08-y-2t", date(2024, 3, 31)),
        (2024, "08", "2024-hasta-08-y-2t", date(2024, 8, 31)),
        (2024, "3T", "2024-desde-09-y-3t", date(2024, 9, 30)),
        (2025, "1T", "2025", date(2025, 3, 31)),
        (2026, "01", "2026-hasta-01-y-1t", date(2026, 1, 31)),
        (2026, "1T", "2026-hasta-01-y-1t", date(2026, 3, 31)),
        (2026, "02", "2026-y-siguientes", date(2026, 2, 28)),
        (2026, "03", "2026-y-siguientes", date(2026, 3, 31)),
        (2026, "2T", "2026-y-siguientes", date(2026, 6, 30)),
        (2026, "4T", "2026-y-siguientes", date(2026, 12, 31)),
        (2026, "12", "2026-y-siguientes", date(2026, 12, 31)),
    ],
)
def test_m303_export_parameter_lookup_uses_the_selected_filing_period_end(
    *,
    operation: PinnedAuthorityOperation,
    filing_year: int,
    period_token: str,
    revision_id: str,
    resolved_on: date,
) -> None:
    """A real empty-register arrival must resolve its selected revision's figures."""
    period = Period.from_year_and_code(filing_year, period_token)
    snapshot = operation.snapshot("303", filing_year=filing_year, period=period_token)
    assert snapshot.revision.id == revision_id
    register = BienesInversionIvaRegister(records=())

    contributions, returned_register, regularisation, parameters = _resolve_m303_export_arrivals(
        period=period,
        prorrata_register=ProrrataRegister(entries=()),
        iva_aggregation=IvaLedgerAggregation(period=period),
        bienes_register=register,
        operation=operation,
    )

    assert contributions == ()
    assert returned_register == register
    assert regularisation.rows == ()
    assert regularisation.pending_percentage_count == 0
    assert regularisation.regularizacion_year == filing_year
    assert regularisation.parameters_provenance == parameters.provenance
    assert parameters.provenance.modelo_id == "303"
    assert parameters.provenance.revision_id == revision_id
    assert parameters.provenance.resolved_on == resolved_on == period.end_date
    declared_ids = {parameter.id for parameter in snapshot.revision.parameters if "bien-inversion-" in parameter.id}
    assert len(declared_ids) == 5
    assert set(parameters.provenance.parameter_ids) == declared_ids


def test_m303_early_revision_still_refuses_a_year_end_parameter_date(
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """Period-correct admission must not weaken the underlying revision-window gate."""
    snapshot = operation.snapshot("303", filing_year=2026, period="1T")
    assert snapshot.revision.id == "2026-hasta-01-y-1t"

    with pytest.raises(BienesInversionParameterResolutionError, match="date lies outside the revision's window"):
        resolve_bienes_inversion_regularizacion_parameters(
            snapshot.revision,
            modelo_id="303",
            filing_period_date=date(2026, 12, 31),
        )
