"""Build-time contract for the one Modelo 303/4T -> Modelo 390/0A handoff."""

from __future__ import annotations

import pytest

from .....core import BindingSourceKind, CasillaId
from .....core.resources import resources
from .....domain.modelos import M390_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY_CASILLA_IDS
from .._bindings import (
    m303_regimen_simplificado_annual_summary_requirement,
    validate_m303_regimen_simplificado_annual_summary_revision,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_RETIRED_RELATION_ID = "modelo-390-rel-303-cuota-devengada-simplificado"
_RETIRED_BINDING_ID = "modelo-390-prev-303-cuota-devengada-simplificado"


def _revision():
    """Return the live 2022-grounded annual Modelo 390 revision."""
    return resources().modelos.authority.snapshot("390", filing_year=2025, period="0A").revision


def test_live_m390_revision_declares_one_exact_ten_endpoint_handoff() -> None:
    """The compiled registry retains all ten official endpoints and no scalar bridge."""
    revision = _revision()
    requirement = m303_regimen_simplificado_annual_summary_requirement(revision)

    assert requirement is not None
    assert requirement.source_modelo == "303"
    assert requirement.source_period == "4T"
    assert requirement.source_casilla_ids == ("51", "53", "52", "54", "55", "56", "57", "58")
    assert tuple(requirement.binding_ids_by_summary_casilla_id) == tuple(
        sorted(M390_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY_CASILLA_IDS)
    )
    assert len(requirement.binding_ids_by_summary_casilla_id) == 10

    casillas = {casilla.id: casilla for casilla in revision.casillas}
    for number, casilla_id in enumerate(M390_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY_CASILLA_IDS, start=74):
        assert casillas[casilla_id].number == str(number)
        assert casillas[casilla_id].binding == requirement.binding_ids_by_summary_casilla_id[casilla_id]
    assert all(
        binding.source is not BindingSourceKind.RELATION_PREFILL or binding.id != _RETIRED_BINDING_ID
        for binding in revision.bindings
    )
    assert _RETIRED_RELATION_ID not in {relation.id for relation in revision.relations}


def test_build_gate_refuses_one_missing_or_miswired_handoff_endpoint() -> None:
    """A future partial map cannot compile and silently zero a 390 endpoint."""
    revision = _revision()
    target_casilla_id: CasillaId = M390_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY_CASILLA_IDS[-1]
    target_binding_id = next(
        binding.id
        for binding in revision.bindings
        if binding.source is BindingSourceKind.M303_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY
        and binding.selector.summary_casilla_id == target_casilla_id
    )
    partial_revision = revision.model_copy(
        update={"bindings": tuple(binding for binding in revision.bindings if binding.id != target_binding_id)},
    )

    failures = validate_m303_regimen_simplificado_annual_summary_revision(partial_revision)

    assert failures
    assert target_casilla_id in "\n".join(failures)
