"""Build-time contract for the one Modelo 303/4T -> Modelo 390/0A handoff."""

from __future__ import annotations

from typing import get_args

import pytest

from .....core.aggregation import BindingSourceKind
from .....core.casilla_id import CasillaId
from .....core.filing_projection_ref import FilingProjectionRef
from ..authority import bundled_indexed_authority
from ..m303_regimen_simplificado_annual_summary_bindings import (
    m303_regimen_simplificado_annual_summary_requirement,
    validate_m303_regimen_simplificado_annual_summary_revision,
)
from .published_authority import published_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_RETIRED_RELATION_ID = "modelo-390-rel-303-cuota-devengada-simplificado"
_RETIRED_BINDING_ID = "modelo-390-prev-303-cuota-devengada-simplificado"


def _revision():
    """Return the live 2022-grounded annual Modelo 390 revision."""
    return published_snapshot("390", filing_year=2025, period="0A").revision


def test_live_m390_revision_declares_one_exact_ten_endpoint_handoff() -> None:
    """The compiled registry retains all ten official endpoints and no scalar bridge."""
    revision = _revision()
    requirement = m303_regimen_simplificado_annual_summary_requirement(revision)

    assert requirement is not None
    assert requirement.source_modelo == "303"
    assert requirement.source_period == "4T"
    assert requirement.source_casilla_ids == ("51", "53", "52", "54", "55", "56", "57", "58")
    assert tuple(requirement.binding_ids_by_summary_casilla_id)
    assert len(requirement.binding_ids_by_summary_casilla_id) == 10

    casillas = {casilla.id: casilla for casilla in revision.casillas}
    for number, casilla_id in enumerate(requirement.binding_ids_by_summary_casilla_id, start=74):
        assert casillas[casilla_id].number == str(number)
        assert casillas[casilla_id].binding == requirement.binding_ids_by_summary_casilla_id[casilla_id]
    bindings_by_id = {binding.id: binding for binding in revision.bindings}
    assert {
        bindings_by_id[binding_id].source for binding_id in requirement.binding_ids_by_summary_casilla_id.values()
    } == {BindingSourceKind.M303_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY}

    # Future M390 repeated-row reference families are not an
    # alternate owner for these existing scalar casillas: the ten boxes arrive
    # only through the typed M303/4T handoff above, so none of those reference
    # variants may carry a CasillaId payload capable of selecting 74--83.
    projection_models = get_args(get_args(FilingProjectionRef)[0])
    m390_projection_models = tuple(
        model_type
        for model_type in projection_models
        if get_args(model_type.model_fields["projection_kind"].annotation)[0].startswith("m390_")
    )
    assert m390_projection_models
    assert all("casilla_id" not in model_type.model_fields for model_type in m390_projection_models)
    assert all(
        binding.source is not BindingSourceKind.RELATION_PREFILL or binding.id != _RETIRED_BINDING_ID
        for binding in revision.bindings
    )
    assert _RETIRED_RELATION_ID not in {binding.id for binding in revision.bindings}


def test_build_gate_refuses_one_missing_or_miswired_handoff_endpoint() -> None:
    """A future partial map cannot compile and silently zero a 390 endpoint."""
    revision = _revision()
    requirement = m303_regimen_simplificado_annual_summary_requirement(revision)
    assert requirement is not None
    target_casilla_id: CasillaId = tuple(requirement.binding_ids_by_summary_casilla_id)[-1]
    target_binding_id = next(
        binding.id
        for binding in revision.bindings
        if binding.source is BindingSourceKind.M303_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY
        and binding.provider.summary_casilla_id == target_casilla_id
    )
    partial_revision = revision.model_copy(
        update={"bindings": tuple(binding for binding in revision.bindings if binding.id != target_binding_id)},
    )

    failures = validate_m303_regimen_simplificado_annual_summary_revision(partial_revision)

    target_number = next(casilla.number for casilla in revision.casillas if casilla.id == target_casilla_id)
    assert failures
    assert repr(target_number) in "\n".join(failures)


@pytest.mark.parametrize("filing_year", (2022, 2023, 2024, 2025, 2026))
def test_each_edition_declares_the_boxes_the_official_form_prints(filing_year: int) -> None:
    """Read from the AEAT Modelo 390 and Modelo 303 record designs, not from the declaration."""
    with bundled_indexed_authority().operation() as operation:
        revision = operation.revision_for_context("390", filing_year=filing_year, period="0A")
        source = operation.revision_for_context("303", filing_year=filing_year, period="4T")
    requirement = m303_regimen_simplificado_annual_summary_requirement(revision)

    assert requirement is not None
    assert requirement.source_period == "4T"
    assert requirement.source_casilla_ids == ("51", "53", "52", "54", "55", "56", "57", "58")
    assert {casilla.id for casilla in source.casillas} >= set(requirement.source_casilla_ids)
    numbers = {casilla.id: casilla.number for casilla in revision.casillas}
    assert sorted(int(numbers[casilla_id]) for casilla_id in requirement.binding_ids_by_summary_casilla_id) == list(
        range(74, 84)
    )
    assert not validate_m303_regimen_simplificado_annual_summary_revision(revision)


def test_build_gate_refuses_an_endpoint_outside_the_summary_section() -> None:
    revision = _revision()
    requirement = m303_regimen_simplificado_annual_summary_requirement(revision)
    assert requirement is not None
    target_casilla_id: CasillaId = tuple(requirement.binding_ids_by_summary_casilla_id)[0]
    moved = revision.model_copy(
        update={
            "casillas": tuple(
                casilla.model_copy(update={"section": ("iva", "anual", "resultado")})
                if casilla.id == target_casilla_id
                else casilla
                for casilla in revision.casillas
            )
        }
    )

    assert any(
        "more than one form section" in failure
        for failure in validate_m303_regimen_simplificado_annual_summary_revision(moved)
    )
