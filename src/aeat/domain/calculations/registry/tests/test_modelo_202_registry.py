"""Tests for committed Modelo 202 registry foundation."""

from __future__ import annotations

from functools import lru_cache

import pytest

from .....core.resources import bundled_path
from .. import RegistryValidator, build_snapshot, load_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@lru_cache(maxsize=1)
def _load_modelo_202():
    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    modelo = next(modelo for modelo in modelos if modelo.id == "202")
    return modelo, catalogues


def test_committed_modelo_202_validates_against_catalogues() -> None:
    modelo, catalogues = _load_modelo_202()

    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)

    assert set(modelo.revisions) == {"2019-2022", "2023-2024", "2025-y-siguientes"}


def test_committed_modelo_202_marks_2025_only_b2_rate_bands_as_intentional_singletons() -> None:
    modelo, _catalogues = _load_modelo_202()
    revision = modelo.revisions["2025-y-siguientes"]
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas}

    for casilla_id in ("61", "62", "64", "65"):
        casilla = casillas_by_id[casilla_id]
        assert casilla.semantic_role_cardinality == "intentional_singleton"
        assert casilla.semantic_role_cardinality_reason is not None
        assert "2025-only" in casilla.semantic_role_cardinality_reason


def test_committed_modelo_202_static_cross_reference_and_construct_are_declared() -> None:
    modelo, catalogues = _load_modelo_202()
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2026,
        period="2P",
    )
    decision = snapshot.live_cross_references["modelo-202-static-documentation"]
    construct = snapshot.constructs["modelo-202-foundation"]

    assert decision.surface == "static_official_documentation"
    assert decision.requires_authentication is False
    assert decision.synthetic_data_allowed is False
    assert "presentation" in decision.forbidden_actions
    assert "modelo-202-portal" in construct.application_links
    assert set(construct.live_cross_references) == {"modelo-202-static-documentation"}
    assert set(construct.workbook_parity_refs) == {"modelo-202-dr-xlsx-2025"}
    assert "modelo-202-2025-y-siguientes-cuota-base-ejercicio-anterior" in construct.bindings
    assert "modelo-202-2025-y-siguientes-dep-200-cuota-base" in construct.dependency_classifications
    assert "modelo-202-2025-y-siguientes-rel-cuota-base-1p" in construct.relations
    assert "modelo-202-2025-y-siguientes-rel-cuota-base-2p-3p" in construct.relations


def test_committed_modelo_202_cuota_base_relation_periods_and_year_offsets_are_declared() -> None:
    modelo, _catalogues = _load_modelo_202()
    revision = modelo.revisions["2025-y-siguientes"]
    relations = {relation.id: relation for relation in revision.relations}

    one_p = relations["modelo-202-2025-y-siguientes-rel-cuota-base-1p"]
    assert one_p.source_modelo == "200"
    assert one_p.source_casilla_id == "DP200014B:00592"
    assert one_p.target_binding == "modelo-202-2025-y-siguientes-cuota-base-ejercicio-anterior"
    assert one_p.source_revision_selector.filing_year_delta == -2
    assert one_p.period_alignment.filing_year_delta == -2
    assert one_p.source_periods == ("0A",)
    assert one_p.target_periods == ("1P",)

    two_p_three_p = relations["modelo-202-2025-y-siguientes-rel-cuota-base-2p-3p"]
    assert two_p_three_p.source_modelo == "200"
    assert two_p_three_p.source_casilla_id == "DP200014B:00592"
    assert two_p_three_p.target_binding == "modelo-202-2025-y-siguientes-cuota-base-ejercicio-anterior"
    assert two_p_three_p.source_revision_selector.filing_year_delta == -1
    assert two_p_three_p.period_alignment.filing_year_delta == -1
    assert two_p_three_p.source_periods == ("0A",)
    assert two_p_three_p.target_periods == ("2P", "3P")
