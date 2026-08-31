"""Live source-mesh enrollment for ``prorrata_regularizacion``.

This test exercises the application mesh path, not the resolver in isolation:
the mesh materialises current-year registry values, calls the real
``ProrrataRegularizacionSourceResolver``, and merges its binding output.

See Also:
    :class:`~application.aggregation.CalculationSourceResolution`
        Source-mesh result envelope whose owned sources, binding values, and
        diagnostics are asserted by this enrollment gate.
    :func:`~application.modelo._calculation_actions._resolve_bucket_source_mesh`
        Calculate-path mesh entry point that enrolls the prorrata resolver.
    :class:`~application.calculations._prorrata_regularizacion.ProrrataRegularizacionSourceResolver`
        Live resolver promoted from resolver-only proof into the application
        mesh by this slice.
    :mod:`~application.calculations.tests.test_prorrata_regularizacion_source_resolver`
        Resolver-isolation tests for the same ``prorrata_regularizacion`` source.
        The enrollment policy governing the promotion.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from ....adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from ....core.aggregation import BindingSourceKind
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period
from ....core.prorrata_register import ProrrataProvisionalProvenance, ProrrataRegisterRegime
from ....core.resources.bundled_data import bundled_path
from ....core.result_disposition import ResultDisposition
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.iva_compensation.filed_derivation import M303_COMPENSATION_RESULTADO_CASILLA
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ....domain.prorrata_register.register import ProrrataRegister, ProrrataRegisterEntry
from ....tests.registry_observations import registry_grounded_modelo_observation
from ....tests.secure_sql import isolated_runtime_profile
from ...calculations.observations_repository import CalculationObservationRepository, ResultDispositionProjection
from ..calculation_actions import _resolve_bucket_source_mesh

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ORACLE_PATH = Path(
    bundled_path("corpus", "manual_oracles", "modelo-303-2025-prorrata-general-regularizacion.json"),
)
_BUCKET_ID = "88888888-8888-4888-8888-888888888888"
_FILING_YEAR = 2025
_PRIOR_YEAR = _FILING_YEAR - 1
_PERIOD = Period.from_year_and_code(_FILING_YEAR, "4T")
_M303_CODE = ModeloCode("303")
_CREATED_AT = datetime(2026, 1, 20, 9, 0, tzinfo=UTC)
_M303_BINDING_ID = "modelo-303-prorrata-regularizacion-casilla-44"
_M390_BINDING_ID = "modelo-390-prorrata-regularizacion-anual"

_SOPORTADO_INTERIORES_ID: CasillaId = validated_casilla_id("iva.soportado.interiores", surface="test casilla id")
_CUOTA_DEDUCIBLE_TOTAL_ID: CasillaId = validated_casilla_id(
    "iva.cuota-deducible-total",
    surface="test casilla id",
)
_VOLUMEN_CON_DERECHO_ID: CasillaId = validated_casilla_id(
    "iva.prorrata-volumen-con-derecho",
    surface="test casilla id",
)
_VOLUMEN_TOTAL_ID: CasillaId = validated_casilla_id("iva.prorrata-volumen-total", surface="test casilla id")
_PORCENTAJE_ID: CasillaId = validated_casilla_id("iva.prorrata-porcentaje", surface="test casilla id")
_CASILLA_44_ID: CasillaId = validated_casilla_id("44", surface="test casilla id")

# AEAT Manual practico IVA 2025, Capitulo 5 prorrata general example: the
# regularizacion compares the provisional percentage applied to the first three
# quarters' input IVA subtotal against the definitive annual percentage.
_FIRST_THREE_QUARTERS_INPUT_IVA = Decimal("1280.00")
_MANUAL_PROVISIONAL_PERCENTAGE = Decimal("73")
# The same example's current-year 'n' operations (locales 25.000 EUR con derecho,
# viviendas 20.000 EUR exentas, annual total 45.000 EUR) and its "Exceso de
# deduccion: 217,60" carried into casilla 44 as a lower deduction. Scenario
# givens and a resolver-produced value, so they are named constants quoting
# `corpus/manuals/iva/2025/source.pdf#Pag.137-138` rather than entries in the
# payload's `expected_by_casilla_id`, which is reserved for casillas the registry
# engine computes and a verification expectation reconciles.
_MANUAL_CURRENT_YEAR_CON_DERECHO = Decimal("25000.00")
_MANUAL_CURRENT_YEAR_TOTAL = Decimal("45000.00")
_MANUAL_CASILLA_44_REGULARIZACION = Decimal("-217.60")


def _oracle_payload() -> dict[str, Any]:
    return json.loads(_ORACLE_PATH.read_text(encoding="utf-8"))


def _oracle_expected(casilla_id: CasillaId) -> Decimal:
    raw = _oracle_payload()["expected_by_casilla_id"][str(casilla_id)]
    return Decimal(str(raw))


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
                regime=ProrrataRegisterRegime.GENERAL,
                especial_transition=None,
                provisional_percentage=_MANUAL_PROVISIONAL_PERCENTAGE,
                provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
                source_observation_ref=f"303:{_PRIOR_YEAR}:4T",
            ),
        ),
    )


def _save_current_year_source_observations(repository: CalculationObservationRepository) -> None:
    source_values_by_period = {
        "1T": {_CUOTA_DEDUCIBLE_TOTAL_ID: Decimal("400.00")},
        "2T": {_CUOTA_DEDUCIBLE_TOTAL_ID: Decimal("420.00")},
        "3T": {_CUOTA_DEDUCIBLE_TOTAL_ID: Decimal("460.00")},
        "4T": {
            _VOLUMEN_CON_DERECHO_ID: _MANUAL_CURRENT_YEAR_CON_DERECHO,
            _VOLUMEN_TOTAL_ID: _MANUAL_CURRENT_YEAR_TOTAL,
            _PORCENTAJE_ID: _oracle_expected(_PORCENTAJE_ID),
        },
    }
    for period, casilla_values in source_values_by_period.items():
        snapshot = bundled_authority().snapshot("303", filing_year=_FILING_YEAR, period=period)
        filing_values = {**casilla_values, M303_COMPENSATION_RESULTADO_CASILLA: Decimal("0.00")}
        repository.save(
            repository.prepare_observation_envelope(
                registry_grounded_modelo_observation(
                    modelo="303",
                    filing_year=_FILING_YEAR,
                    period=period,
                    casilla_values=filing_values,
                ),
                source_kind="app_filing",
                captured_at=_CREATED_AT,
                stamped_revision_id=snapshot.revision.id,
                result_disposition=ResultDispositionProjection(
                    disposition=ResultDisposition.NEGATIVA,
                    provenance_kind="app_filing",
                    provenance_locator=f"test-local-filing:{_FILING_YEAR}:{period}",
                ),
                normalize_m303_carry=True,
            )
        )


def test_source_mesh_resolves_prorrata_regularizacion_binding(tmp_path: Path) -> None:
    """The live mesh invokes prorrata without requiring unrelated carry bindings."""
    snapshot = bundled_authority().snapshot("303", filing_year=_FILING_YEAR, period="4T")
    assert snapshot.filing_period is not None
    work_unit = _work_unit(revision_id=snapshot.revision.id)

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        ProrrataRegisterRepository(bucket_id=_BUCKET_ID).save(_register_with_carried_prior())

        resolution = _resolve_bucket_source_mesh(
            snapshot,
            work_unit,
            transaction_repository=None,
            invoice_repository=None,
            foreign_asset_observations=(),
            foreign_asset_row_observations=(),
            casilla_inputs={
                _SOPORTADO_INTERIORES_ID: _FIRST_THREE_QUARTERS_INPUT_IVA,
                _VOLUMEN_CON_DERECHO_ID: _MANUAL_CURRENT_YEAR_CON_DERECHO,
                _VOLUMEN_TOTAL_ID: _MANUAL_CURRENT_YEAR_TOTAL,
            },
            filing_period_date=snapshot.filing_period.end_date,
        )

    prorrata_diagnostics = tuple(
        diagnostic
        for diagnostic in resolution.diagnostics
        if diagnostic.binding_source is BindingSourceKind.PRORRATA_REGULARIZACION
    )
    assert BindingSourceKind.PRORRATA_REGULARIZACION in resolution.owned_sources
    assert resolution.binding_values[_M303_BINDING_ID] == _MANUAL_CASILLA_44_REGULARIZACION
    assert resolution.bound_inputs_by_casilla_id[_CASILLA_44_ID] == _MANUAL_CASILLA_44_REGULARIZACION
    assert _M303_BINDING_ID not in resolution.unresolved_binding_ids
    assert prorrata_diagnostics == ()
    assert "prorrata-register:2025:carried_prior_definitiva:303:2024:4T" in {
        row.source_ref for row in resolution.provenance
    }


def test_source_mesh_resolves_m390_prorrata_binding_from_m303_source_periods(
    tmp_path: Path,
) -> None:
    """The M390 binding consumes stamped Modelo 303 source-period observations."""
    period = Period.from_year_and_code(_FILING_YEAR, "0A")
    snapshot = bundled_authority().snapshot("390", filing_year=_FILING_YEAR, period="0A")
    assert snapshot.filing_period is not None
    work_unit = _work_unit(revision_id=snapshot.revision.id, modelo=ModeloCode("390"), period=period)

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        ProrrataRegisterRepository(bucket_id=_BUCKET_ID).save(_register_with_carried_prior())
        _save_current_year_source_observations(CalculationObservationRepository(objects=profile.repository))

        resolution = _resolve_bucket_source_mesh(
            snapshot,
            work_unit,
            transaction_repository=None,
            invoice_repository=None,
            foreign_asset_observations=(),
            foreign_asset_row_observations=(),
            filing_period_date=snapshot.filing_period.end_date,
        )

    prorrata_diagnostics = tuple(
        diagnostic
        for diagnostic in resolution.diagnostics
        if diagnostic.binding_source is BindingSourceKind.PRORRATA_REGULARIZACION
    )
    assert BindingSourceKind.PRORRATA_REGULARIZACION in resolution.owned_sources
    assert resolution.binding_values[_M390_BINDING_ID] == _MANUAL_CASILLA_44_REGULARIZACION
    assert _M390_BINDING_ID not in resolution.unresolved_binding_ids
    assert prorrata_diagnostics == ()
