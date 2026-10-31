"""Each 303 projection output refuses a row past what the registry declares."""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal

import pytest
from pydantic import ValidationError

from .....core.filing_projection_ref import M303_MESA_FACTS
from .....core.prorrata_register import ProrrataRegisterRegime
from ....filing_evidence import FilingEvidenceReference
from ....iva.regimen_simplificado_rows import (
    ActividadNoAgricolaSimplificado,
    EntradaModuloSimplificado,
    HechoActividadSimplificado,
    RegimenSimplificadoFilingRows,
)
from ....modelos.calculation_revision_m303_evidence import (
    M303Exonerado390ActivityRowEvidence,
    M303RegimenSimplificadoActivityCalculationResult,
    M303RegimenSimplificadoModuleCalculationResult,
)
from ....prorrata_register.register import ProrrataActivityRow
from ..authority import bundled_indexed_authority
from ..form_codes import resolve_form_codes
from ..m303_differentiated_deduction_projection import M303DifferentiatedDeductionRowProjection
from ..m303_prorrata_activity_projection import M303ProrrataActivityRowProjection
from ..m303_regimen_simplificado_projection import M303RegimenSimplificadoRecordProjection

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(autouse=True)
def _pinned_authority() -> Iterator[None]:
    with bundled_indexed_authority().operation():
        yield


def _declared(key: str) -> int:
    return int(resolve_form_codes("form-row-codes").code(key))


def test_a_differentiated_row_past_the_declared_slots_is_refused() -> None:
    with pytest.raises(ValidationError, match="past the form's declared rows"):
        M303DifferentiatedDeductionRowProjection(
            slot=_declared("m303.differentiated.row_slots") + 1,
            sector_id="sector",
            regime=ProrrataRegisterRegime.from_registry("general"),
            percentage=Decimal(50),
            endpoints=(),
        )


def test_a_differentiated_row_short_of_its_endpoints_is_refused() -> None:
    with pytest.raises(ValidationError, match="one endpoint per declared field"):
        M303DifferentiatedDeductionRowProjection(
            slot=1,
            sector_id="sector",
            regime=ProrrataRegisterRegime.from_registry("general"),
            percentage=Decimal(50),
            endpoints=(),
        )


def test_a_prorrata_row_past_the_declared_slots_is_refused() -> None:
    with pytest.raises(ValidationError, match="past the form's declared rows"):
        M303ProrrataActivityRowProjection(slot=_declared("m303.prorrata.activity_slots") + 1, endpoints=())


def test_a_prorrata_row_short_of_its_endpoints_is_refused() -> None:
    with pytest.raises(ValidationError, match="one endpoint per declared field"):
        M303ProrrataActivityRowProjection(slot=1, endpoints=())


def test_a_simplified_regime_record_past_the_declared_pages_is_refused() -> None:
    with pytest.raises(ValidationError, match="past the form's declared pages"):
        M303RegimenSimplificadoRecordProjection(record=_declared("m303.dp30302.records") + 1, fields=())


def test_an_activity_with_more_modules_than_declared_is_refused() -> None:
    module = EntradaModuloSimplificado.model_construct()
    with pytest.raises(ValidationError, match="more modules than the record declares"):
        ActividadNoAgricolaSimplificado.model_validate(
            {"modulos": (module,) * (_declared("m303.orden.modules_per_activity") + 1)}
        )


def test_an_activity_result_with_more_modules_than_declared_is_refused() -> None:
    module = M303RegimenSimplificadoModuleCalculationResult.model_construct()
    with pytest.raises(ValidationError, match="more module results than the record declares"):
        M303RegimenSimplificadoActivityCalculationResult.model_validate(
            {"module_results": (module,) * (_declared("m303.orden.modules_per_activity") + 1)}
        )


def test_more_activities_of_a_kind_than_the_pages_hold_is_refused() -> None:
    activities = tuple(
        ActividadNoAgricolaSimplificado.model_construct(ejercicio=2026, activity_id=f"a{index}", modulos=())
        for index in range(_declared("m303.dp30302.activities_per_kind") + 1)
    )
    with pytest.raises(ValidationError, match="activities of each kind"):
        RegimenSimplificadoFilingRows(ejercicio=2026, activities=activities)


def test_a_prorrata_register_row_past_the_declared_slots_is_refused() -> None:
    with pytest.raises(ValidationError, match="past the form's declared rows"):
        ProrrataActivityRow.model_validate({"slot": _declared("m303.prorrata.activity_slots") + 1})


def test_an_exonerado_row_past_the_declared_slots_is_refused() -> None:
    with pytest.raises(ValidationError, match="past the form's declared rows"):
        M303Exonerado390ActivityRowEvidence.model_validate({"slot": _declared("m303.exonerado_390.activity_slots") + 1})


def test_a_sub_index_the_record_does_not_declare_is_refused() -> None:
    codes = resolve_form_codes("form-row-codes").codes("m303.dp30302.sub_indices")
    with pytest.raises(ValidationError, match="not a row the DP30302 record declares"):
        HechoActividadSimplificado(
            fact=next(iter(M303_MESA_FACTS)),
            sub_index=max(int(code) for code in codes) + 1,
            value="1",
            evidence_reference=FilingEvidenceReference.model_construct(),
        )
