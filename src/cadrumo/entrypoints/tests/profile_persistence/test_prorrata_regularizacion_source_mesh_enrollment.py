"""Live source-mesh enrollment for ``prorrata_regularizacion``.

These tests exercise the application mesh path, not the resolver in isolation:
the mesh materialises current-year registry values, calls the real
``ProrrataRegularizacionSourceResolver``, and merges its binding output. The
annual regularisation box belongs to the year's last liquidation only, reads
the earlier liquidations from their filed observations, and the Modelo 390
annual field restates the filed settlement box.

See Also:
    :class:`~application.aggregation.CalculationSourceResolution`
        Source-mesh result envelope whose owned sources, binding values, and
        diagnostics are asserted by this enrollment gate.
    :func:`~application.modelo.calculation_source_mesh_actions.resolve_bucket_source_mesh`
        Calculate-path mesh entry point that enrolls the prorrata resolver.
    :class:`~application.calculations._prorrata_regularizacion.ProrrataRegularizacionSourceResolver`
        Live resolver promoted from resolver-only proof into the application
        mesh by this slice.
    :mod:`~application.calculations.tests.test_prorrata_regularizacion_source_resolver`
        Resolver-isolation tests for the same ``prorrata_regularizacion`` source.
        The enrollment policy governing the promotion.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.tests.taxpayer_persona_support import seed_modelo_ready_profile

from ....adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from ....adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from ....adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from ....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ....application.aggregation.source_mesh import CalculationSourceResolution
from ....application.calculations.observations_repository import ResultDispositionProjection
from ....application.modelo.calculation_source_mesh_actions import resolve_bucket_source_mesh
from ....core.aggregation import BindingSourceKind
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.i18n.render import tr as render_tr
from ....core.period import Period
from ....core.prorrata_register import ProrrataProvisionalProvenance, ProrrataRegisterRegime
from ....core.result_disposition import ResultDisposition
from ....domain.calculations.registry.iva_compensation_annual_partition_bindings import (
    M303_COMPENSATION_RESULTADO_CASILLA,
)
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope, manual_editions_printing
from ....domain.calculations.registry.tests.registry_observations import registry_grounded_modelo_observation
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ....domain.prorrata_register.register import ProrrataRegister, ProrrataRegisterEntry
from .file_flow_test_support import calculation_ports_for_test

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BUCKET_ID = "88888888-8888-4888-8888-888888888888"
#: The newest AEAT manual edition printing the worked prorrata example the expected figures below are taken from.
_FILING_YEAR = manual_editions_printing("iva", "Exceso de deducción: 217,60")[-1]
_PRIOR_YEAR = _FILING_YEAR - 1
_PERIOD = Period.from_year_and_code(_FILING_YEAR, "4T")
_UNRESOLVED_KEY = "application.calculations.prorrata_regularizacion.unresolved"
_M303_CODE = ModeloCode("303")
_CREATED_AT = datetime(filing_year_envelope().horizon, 1, 20, 9, 0, tzinfo=UTC)
_M303_BINDING_ID = "modelo-303-prorrata-regularizacion-casilla-44"
_M390_BINDING_ID = "modelo-390-prorrata-regularizacion-anual"

_VOLUMEN_CON_DERECHO_ID: CasillaId = validated_casilla_id(
    "iva.prorrata-volumen-con-derecho",
    surface="test casilla id",
)
_VOLUMEN_TOTAL_ID: CasillaId = validated_casilla_id("iva.prorrata-volumen-total", surface="test casilla id")
_PORCENTAJE_ID: CasillaId = validated_casilla_id("iva.prorrata-porcentaje", surface="test casilla id")
_CASILLA_44_ID: CasillaId = validated_casilla_id("44", surface="test casilla id")

# AEAT Manual practico IVA 2025, Capitulo 5 prorrata general example
# (`corpus/manuals/iva/2025/source.pdf#Pag.137-138`): provisional 73 %, the
# year's operations (locales 25.000 EUR con derecho, viviendas 20.000 EUR
# exentas, total 45.000 EUR) give a definitive 56 %, and the fourth quarter
# regularises the first three quarters with "Exceso de deduccion: 217,60".
_MANUAL_PROVISIONAL_PERCENTAGE = Decimal("73")
_MANUAL_CURRENT_YEAR_CON_DERECHO = Decimal("25000.00")
_MANUAL_CURRENT_YEAR_TOTAL = Decimal("45000.00")
_MANUAL_DEFINITIVE_PERCENTAGE = Decimal("56")
_MANUAL_CASILLA_44_REGULARIZACION = Decimal("-217.60")


def _work_unit(
    *,
    revision_id: str,
    modelo: ModeloCode = _M303_CODE,
    period: Period = _PERIOD,
) -> WorkUnit:
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo=modelo,
            filing_year=_FILING_YEAR,
            period=period,
            revision_id=revision_id,
        ),
        bucket_id=_BUCKET_ID,
        modelo=modelo,
        filing_year=_FILING_YEAR,
        period=period,
        revision_id=revision_id,
        name=f"{modelo}-{_FILING_YEAR}-{period.registry_token}",
        created_at=_CREATED_AT,
        updated_at=_CREATED_AT,
    )


def _register_with_carried_prior() -> ProrrataRegister:
    return ProrrataRegister(
        entries=(
            ProrrataRegisterEntry(
                ejercicio=_FILING_YEAR,
                regime=ProrrataRegisterRegime.from_registry("general"),
                especial_transition=None,
                provisional_percentage=_MANUAL_PROVISIONAL_PERCENTAGE,
                provisional_provenance=ProrrataProvisionalProvenance.from_registry("carried_prior_definitiva"),
                source_observation_ref=f"303:{_PRIOR_YEAR}:4T",
                source_registry_snapshot_refs=(
                    published_authority_operation().snapshot("303", filing_year=_PRIOR_YEAR, period="4T").snapshot_ref,
                ),
            ),
        ),
    )


def _save_filed_settlement_observation(repository: CalculationObservationRepository) -> None:
    """Persist the filed fourth-quarter liquidation carrying the manual's casilla 44."""
    snapshot = published_authority_operation().snapshot("303", filing_year=_FILING_YEAR, period="4T")
    repository.save(
        repository.prepare_observation_envelope(
            registry_grounded_modelo_observation(
                modelo="303",
                filing_year=_FILING_YEAR,
                period="4T",
                casilla_values={
                    _VOLUMEN_CON_DERECHO_ID: _MANUAL_CURRENT_YEAR_CON_DERECHO,
                    _VOLUMEN_TOTAL_ID: _MANUAL_CURRENT_YEAR_TOTAL,
                    _PORCENTAJE_ID: _MANUAL_DEFINITIVE_PERCENTAGE,
                    _CASILLA_44_ID: _MANUAL_CASILLA_44_REGULARIZACION,
                    M303_COMPENSATION_RESULTADO_CASILLA: Decimal("0.00"),
                },
            ),
            source_kind="app_filing",
            captured_at=_CREATED_AT,
            stamped_revision_id=snapshot.revision.id,
            result_disposition=ResultDispositionProjection(
                disposition=ResultDisposition.NEGATIVA,
                provenance_kind="app_filing",
                provenance_locator=f"test-local-filing:{_FILING_YEAR}:4T",
            ),
        )
    )


def _resolve_m303(tmp_path: Path, period_code: str) -> CalculationSourceResolution:
    snapshot = published_authority_operation().snapshot("303", filing_year=_FILING_YEAR, period=period_code)
    assert snapshot.filing_period is not None
    period = Period.from_year_and_code(_FILING_YEAR, period_code)
    work_unit = _work_unit(revision_id=snapshot.revision.id, period=period)
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        seed_modelo_ready_profile(bucket_id=_BUCKET_ID, at=_CREATED_AT)
        ProrrataRegisterRepository(bucket_id=_BUCKET_ID).save(_register_with_carried_prior())
        with calculation_ports_for_test(bucket_id=work_unit.bucket_id) as calculation_ports:
            return resolve_bucket_source_mesh(
                snapshot,
                work_unit,
                ports=calculation_ports,
                foreign_asset_observations=(),
                foreign_asset_row_observations=(),
                casilla_inputs={
                    _VOLUMEN_CON_DERECHO_ID: _MANUAL_CURRENT_YEAR_CON_DERECHO,
                    _VOLUMEN_TOTAL_ID: _MANUAL_CURRENT_YEAR_TOTAL,
                },
                filing_period_date=snapshot.filing_period.end_date,
            )


def _binding_messages(resolution: CalculationSourceResolution, binding_id: str) -> tuple[str, ...]:
    return tuple(diagnostic.message for diagnostic in resolution.diagnostics if diagnostic.binding_id == binding_id)


def test_settlement_liquidation_without_filed_earlier_quarters_stays_unresolved(tmp_path: Path) -> None:
    """The fourth quarter cannot regularise quarters that have no filed liquidation."""
    resolution = _resolve_m303(tmp_path, "4T")

    assert BindingSourceKind.PRORRATA_REGULARIZACION in resolution.owned_sources
    assert _M303_BINDING_ID in resolution.unresolved_binding_ids
    assert _M303_BINDING_ID not in resolution.binding_values
    assert _CASILLA_44_ID not in resolution.bound_inputs_by_casilla_id
    expected = render_tr(f"{_UNRESOLVED_KEY}.source_periods_missing", periods="1T, 2T, 3T")
    assert expected in _binding_messages(resolution, _M303_BINDING_ID)


def test_non_settlement_liquidation_carries_a_structural_zero(tmp_path: Path) -> None:
    """Casilla 44 belongs to the last liquidation; the third quarter declares a proven zero."""
    resolution = _resolve_m303(tmp_path, "3T")

    assert resolution.binding_values[_M303_BINDING_ID] == Decimal("0.00")
    assert resolution.bound_inputs_by_casilla_id[_CASILLA_44_ID] == Decimal("0.00")
    assert _M303_BINDING_ID not in resolution.unresolved_binding_ids
    assert f"303:{_FILING_YEAR}:3T:prorrata-regularizacion-settlement-only" in {
        row.source_ref for row in resolution.provenance
    }


def test_source_mesh_m390_restates_the_filed_settlement_casilla_44(tmp_path: Path) -> None:
    """The Modelo 390 annual field restates the filed fourth-quarter regularisation."""
    period = Period.from_year_and_code(_FILING_YEAR, "0A")
    snapshot = published_authority_operation().snapshot("390", filing_year=_FILING_YEAR, period="0A")
    assert snapshot.filing_period is not None
    work_unit = _work_unit(revision_id=snapshot.revision.id, modelo=ModeloCode("390"), period=period)

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        seed_modelo_ready_profile(bucket_id=_BUCKET_ID, at=_CREATED_AT)
        ProrrataRegisterRepository(bucket_id=_BUCKET_ID).save(_register_with_carried_prior())
        _save_filed_settlement_observation(CalculationObservationRepository(objects=profile.repository))
        with calculation_ports_for_test(bucket_id=work_unit.bucket_id) as calculation_ports:
            resolution = resolve_bucket_source_mesh(
                snapshot,
                work_unit,
                ports=calculation_ports,
                foreign_asset_observations=(),
                foreign_asset_row_observations=(),
                filing_period_date=snapshot.filing_period.end_date,
            )

    assert BindingSourceKind.PRORRATA_REGULARIZACION in resolution.owned_sources
    assert resolution.binding_values[_M390_BINDING_ID] == _MANUAL_CASILLA_44_REGULARIZACION
    assert _M390_BINDING_ID not in resolution.unresolved_binding_ids
    assert _binding_messages(resolution, _M390_BINDING_ID) == ()
    assert f"303:{_FILING_YEAR}:4T:44" in {row.source_ref for row in resolution.provenance}
