"""Candidate verification for the Modelo 190 pension-indicator scope."""

from __future__ import annotations

import pytest

from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.core.period import Period
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.governed_fact_scope import CandidateFactAuthority
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.modelos.perceptor_clave_scope import (
    PerceptorClaveScope,
    resolve_perceptor_clave_scope,
    rows_missing_scoped_casilla,
)

from ..compiler.authority import AuthoringCandidateInspection, inspect_authoring_candidate

pytestmark = [pytest.mark.integration, pytest.mark.hex_domain]

_JUBILACION = validated_casilla_id("perc.prestacion-jubilacion")


@pytest.fixture(scope="module")
def candidate() -> AuthoringCandidateInspection:
    return inspect_authoring_candidate(bundled_path("registry", "aeat"), bundled_path())


def test_pension_indicators_are_required_for_b01_not_professional_g_rows(
    candidate: AuthoringCandidateInspection,
) -> None:
    """The candidate preserves B.01 completeness without imposing it on G.01/G.02."""
    assert candidate.publication_valid, candidate.findings
    support = candidate.components.catalogues.require_supported_filing_years()
    authority = CandidateFactAuthority(candidate.components.catalogues.facts, support)
    revision = next(modelo for modelo in candidate.components.modelos if modelo.id == "190").revisions[
        "2025-y-siguientes"
    ]
    # The revision that introduces the pension indicators opens its own open-ended span;
    # every supported exercise inside that span must carry the same clave scope.
    covered_years = tuple(year for year in support.years if year >= revision.valid_from.year)
    assert covered_years
    for filing_year in covered_years:
        _assert_pension_scope(
            resolve_perceptor_clave_scope(period=Period.from_year_and_code(filing_year, "0A"), authority=authority),
            revision,
        )


def _assert_pension_scope(scope: PerceptorClaveScope, revision: ModeloRevision) -> None:
    value_binding = next(
        binding.id for binding in revision.bindings if binding.id == "modelo-190-perceptor-row-prestacion-jubilacion"
    )
    rows = {
        scope.row_clave_binding: {"professional-01": "G", "professional-02": "G", "pension": "B"},
        scope.row_subclave_binding: {"professional-01": "01", "professional-02": "02", "pension": "01"},
        value_binding: {},
    }

    assert not scope.admits(_JUBILACION, "G", "01")
    assert not scope.admits(_JUBILACION, "G", "02")
    assert scope.admits(_JUBILACION, "B", "01")
    assert rows_missing_scoped_casilla(
        scope,
        casilla_id=_JUBILACION,
        value_binding=value_binding,
        row_binding_values=rows,
    ) == ("pension",)
