"""Live source-mesh enrollment for ``bienes_inversion_regularizacion``.

This test exercises the application mesh path, not the advisory projection in
isolation: the mesh materialises current-year registry prorrata values, calls
the real bienes-inversión resolver, and binds Modelo 303 casilla 43.

See Also:
    :class:`~application.aggregation.CalculationSourceResolution`
        Source-mesh result envelope whose owned sources, binding values, and
        diagnostics are asserted by this enrollment gate.
    :func:`~application.modelo._calculation_actions._resolve_bucket_source_mesh`
        Calculate-path mesh entry point that enrolls the bienes-inversión
        resolver.
    :mod:`~application.calculations._bienes_inversion_regularizacion`
        Projection and live resolver for the capital-goods IVA regularización
        source kind.
    :mod:`~application.modelo._bienes_inversion_advisory`
        Earlier advisory wiring that kept casilla 43 visible before hard
        source-mesh promotion.
        The M303 live enrollment policy.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.bienes_inversion import BienesInversionIvaRegisterRepository
from ....core.aggregation import BindingSourceKind
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period
from ....domain.bienes_inversion.register import BienInversionIvaRecord, BienInversionKind
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ....tests.secure_sql import isolated_runtime_profile
from .._calculation_actions import _resolve_bucket_source_mesh

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "77777777-7777-4777-8777-777777777777"
_FILING_YEAR = 2024
_PERIOD = Period.from_year_and_code(_FILING_YEAR, "4T")
_CREATED_AT = datetime(2025, 1, 20, 9, 0, tzinfo=UTC)
_BINDING_ID = "modelo-303-bienes-inversion-regularizacion-casilla-43"
_CASILLA_43_ID: CasillaId = validated_casilla_id("43", surface="test casilla id")
_VOLUMEN_CON_DERECHO_ID: CasillaId = validated_casilla_id(
    "iva.prorrata-volumen-con-derecho",
    surface="test casilla id",
)
_VOLUMEN_TOTAL_ID: CasillaId = validated_casilla_id("iva.prorrata-volumen-total", surface="test casilla id")


def _work_unit(*, revision_id: str) -> WorkUnit:
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo=ModeloCode("303"),
            filing_year=_FILING_YEAR,
            period=_PERIOD,
            revision_id=revision_id,
        ),
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode("303"),
        filing_year=_FILING_YEAR,
        period=_PERIOD,
        revision_id=revision_id,
        name=f"303-{_FILING_YEAR}-{_PERIOD.registry_token}",
        created_at=_CREATED_AT,
        updated_at=_CREATED_AT,
    )


def _record() -> BienInversionIvaRecord:
    return BienInversionIvaRecord(
        identifier="bi-2022-maquina",
        description="Maquina afecta a la actividad",
        acquisition_year=2022,
        cuota_soportada=Decimal("5000.00"),
        prorrata_inicial_pct=Decimal("80"),
        kind=BienInversionKind.MUEBLE,
        acquisition_ledger_id="ledger-bi-2022-maquina",
    )


def test_source_mesh_resolves_bienes_inversion_regularizacion_binding(tmp_path: Path) -> None:
    """The live mesh projects the register value into Modelo 303 casilla 43."""
    snapshot = bundled_authority().snapshot("303", filing_year=_FILING_YEAR, period="4T")
    assert snapshot.filing_period is not None
    work_unit = _work_unit(revision_id=snapshot.revision.id)

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        BienesInversionIvaRegisterRepository(objects=profile.repository).add(_record())

        resolution = _resolve_bucket_source_mesh(
            snapshot,
            work_unit,
            transaction_repository=None,
            invoice_repository=None,
            foreign_asset_observations=(),
            foreign_asset_row_observations=(),
            casilla_inputs={
                _VOLUMEN_CON_DERECHO_ID: Decimal("60000.00"),
                _VOLUMEN_TOTAL_ID: Decimal("100000.00"),
            },
            filing_period_date=snapshot.filing_period.end_date,
        )

    bienes_diagnostics = tuple(
        diagnostic
        for diagnostic in resolution.diagnostics
        if diagnostic.binding_source is BindingSourceKind.BIENES_INVERSION_REGULARIZACION
    )
    assert BindingSourceKind.BIENES_INVERSION_REGULARIZACION in resolution.owned_sources
    assert resolution.binding_values[_BINDING_ID] == Decimal("200.00")
    assert resolution.bound_inputs_by_casilla_id[_CASILLA_43_ID] == Decimal("200.00")
    assert _BINDING_ID not in resolution.unresolved_binding_ids
    assert bienes_diagnostics == ()
