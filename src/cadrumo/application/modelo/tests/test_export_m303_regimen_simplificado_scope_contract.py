"""Producer-export check for the canonical M303 simplified-regime scope."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.period import Period
from ....domain.bienes_inversion import BienesInversionIvaRegister, RegistroRegularizacionResult
from ....domain.deadlines.models import M303RegimeComposition
from ....domain.prorrata_register import ProrrataRegister
from ...aggregation import (
    IvaLedgerAggregation,
    resolve_m303_prorrata_transition_arrival,
    resolve_m303_supplier_regime_arrival,
)
from ...filing import FilingProducerSnapshotError, resolve_m303_filing_facts
from .._export import _require_m303_regimen_simplificado_scope_matches_profile
from ._export_test_support import _general_m303_filing_evidence, _profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


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
        ),
    )


def test_export_refuses_m303_filing_scope_that_disagrees_with_the_canonical_profile_mapper() -> None:
    """General evidence cannot be exported under a simplified or mixed profile composition."""
    filing_facts = _general_m303_filing_facts()
    workflow_profile = _profile()
    assert workflow_profile.iva is not None
    simplified_profile = workflow_profile.model_copy(
        update={"iva": workflow_profile.iva.model_copy(update={"regime_composition": M303RegimeComposition.SIMPLIFIED})}
    )

    with pytest.raises(FilingProducerSnapshotError, match="canonical IVA profile composition"):
        _require_m303_regimen_simplificado_scope_matches_profile(
            filing_facts=filing_facts,
            workflow_profile=simplified_profile,
        )
