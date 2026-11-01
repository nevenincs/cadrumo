"""Modelo 322's scenario supplies envelope evidence exactly where the selected edition's layout declares one."""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.temporal import select_revision

from ..conformance.registry_schema_support import committed_modelo
from ..edition_export_scenarios import edition_export_scenarios

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_envelope_evidence_follows_the_selected_editions_layout() -> None:
    """Identity and election are supplied iff the edition's layout declares a filing envelope."""
    modelo, catalogues = committed_modelo("322")
    scenarios = edition_export_scenarios("322")
    assert scenarios
    declaring: list[str] = []
    for revision_id, scenario in scenarios.items():
        revision = select_revision(
            modelo,
            filing_year=scenario.period.filing_year,
            period=scenario.period.registry_token,
            support=catalogues.supported_filing_years,
        )
        assert str(revision.id) == revision_id
        declares = any(layout.filing_envelope is not None for layout in revision.export_layouts)
        assert (scenario.product_software_identity_factory is not None) is declares, revision_id
        assert (scenario.prior_domiciliation_election is not None) is declares, revision_id
        if declares:
            declaring.append(revision_id)
    assert declaring
