"""Producer-export check for the canonical M303 simplified-regime scope."""

from __future__ import annotations

from datetime import date as _prov_date
from decimal import Decimal

import pytest

from cadrumo.adapters.persistence.profile.tests._export_test_support import _general_m303_filing_evidence, _profile
from cadrumo.application.aggregation.iva_ledger import (
    IvaLedgerAggregation,
)
from cadrumo.application.aggregation.m303_arrivals import (
    resolve_m303_prorrata_transition_arrival,
    resolve_m303_supplier_regime_arrival,
)
from cadrumo.application.filing.producer_snapshot import resolve_m303_filing_facts
from cadrumo.application.modelo.m303_regimen_simplificado_scope import m303_regimen_simplificado_scope_for_profile
from cadrumo.core.period import Period
from cadrumo.domain.bienes_inversion.register import BienesInversionIvaRegister, RegistroRegularizacionResult
from cadrumo.domain.bienes_inversion.regularizacion_parameters import (
    BienesInversionParameterProvenance,
    BienesInversionRegularizacionParameters,
)
from cadrumo.domain.calculations.registry.schema_base import ThresholdComparison
from cadrumo.domain.deadlines.models import M303RegimeComposition
from cadrumo.domain.prorrata_register.register import ProrrataRegister

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


#: Provenance stamped onto directly-constructed projections in this module. A
#: result must name the registry declaration its figures came from; these tests
#: build results by hand rather than by projection, so they state it explicitly.
_PROVENANCE = BienesInversionParameterProvenance(
    modelo_id="303",
    revision_id="2025",
    parameter_ids=(
        "m303-bien-inversion-ventana-anos-mueble",
        "m303-bien-inversion-ventana-anos-inmueble",
        "m303-bien-inversion-divisor-mueble",
        "m303-bien-inversion-divisor-inmueble",
        "m303-bien-inversion-regularizacion-umbral-puntos",
    ),
    resolved_on=_prov_date(2025, 6, 1),
)


#: The resolved bundle the regularisation result above was produced under. The
#: oracle compares the result's carried provenance against this, so the two must
#: name the same declaration.
_PARAMS = BienesInversionRegularizacionParameters(
    ventana_anos_mueble=4,
    ventana_anos_inmueble=9,
    divisor_mueble=Decimal("5"),
    divisor_inmueble=Decimal("10"),
    umbral_puntos=Decimal("10"),
    umbral_comparison=ThresholdComparison.EXCLUSIVE,
    provenance=_PROVENANCE,
)


def _params_for(year: int) -> BienesInversionRegularizacionParameters:
    """The bundle, resolved for ``year``.

    The projection refuses a bundle resolved for a different filing year, so the
    fixture must follow the period rather than pin a year of its own.
    """
    return _PARAMS.model_copy(
        update={"provenance": _PARAMS.provenance.model_copy(update={"resolved_on": _prov_date(year, 12, 31)})}
    )


def _general_m303_filing_facts():
    period = Period.from_year_and_code(2026, "1T")
    prorrata_register = ProrrataRegister()
    return resolve_m303_filing_facts(
        evidence=_general_m303_filing_evidence(period),
        supplier_regime=resolve_m303_supplier_regime_arrival(
            period=period,
            iva_aggregation=IvaLedgerAggregation(period=period),
        ),
        prorrata_transition=resolve_m303_prorrata_transition_arrival(
            period=period,
            prorrata_register=prorrata_register,
        ),
        prorrata_register=prorrata_register,
        differentiated_contributions=(),
        bienes_register=BienesInversionIvaRegister(),
        regularisation_result=RegistroRegularizacionResult(
            regularizacion_year=period.filing_year,
            rows=(),
            proposed_casilla_43=Decimal("0"),
            computed_count=0,
            pending_percentage_count=0,
            sector_contributions=(),
            parameters_provenance=_params_for(period.filing_year).provenance,
        ),
        bienes_parameters=_params_for(period.filing_year),
    )


def test_export_scope_mapper_rejects_general_evidence_for_a_simplified_profile() -> None:
    """General evidence cannot be exported under a simplified profile composition."""
    filing_facts = _general_m303_filing_facts()
    workflow_profile = _profile()
    assert workflow_profile.iva is not None
    simplified_profile = workflow_profile.model_copy(
        update={
            "iva": workflow_profile.iva.model_copy(
                update={"regime_composition": M303RegimeComposition._from_registry("simplified")}
            )
        }
    )

    expected_scope = m303_regimen_simplificado_scope_for_profile(simplified_profile)
    assert filing_facts.regimen_simplificado.scope_decision != expected_scope
