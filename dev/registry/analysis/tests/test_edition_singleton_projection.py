"""The edition-singleton projection reads a real hydrated modelo."""

from __future__ import annotations

import pytest

from ...compiler.loader import load_modelo_directory, load_shared_catalogues
from ..casilla_lineage_seed_paths import MODELOS_ROOT, REGISTRY_ROOT
from ..edition_singleton_audit import LegalWindow, editions_in_support, singleton_findings

pytestmark = [pytest.mark.integration, pytest.mark.hex_domain]


def test_real_modelo_projects_into_comparable_editions() -> None:
    catalogues = load_shared_catalogues(REGISTRY_ROOT)
    support = catalogues.require_supported_filing_years()
    candidates = sorted(path for path in MODELOS_ROOT.iterdir() if len(list((path / "revisions").glob("*"))) > 1)
    assert candidates
    views = editions_in_support(load_modelo_directory(candidates[0]), catalogues, support)
    assert views
    assert all(view.declarations for view in views)
    assert all(
        all(
            isinstance(window, LegalWindow) for declaration in view.declarations for window in declaration.legal_windows
        )
        for view in views
    )


def test_a_removal_declared_by_a_split_year_edition_cites_where_the_casilla_leaves_the_form() -> None:
    catalogues = load_shared_catalogues(REGISTRY_ROOT)
    support = catalogues.require_supported_filing_years()
    views = editions_in_support(load_modelo_directory(MODELOS_ROOT / "303"), catalogues, support)
    carriers = [
        (view.track, declaration)
        for view in views
        for declaration in view.declarations
        if declaration.family == "casillas" and declaration.declaration_id == "recargo.super-reducido"
    ]
    assert len({track for track, _ in carriers}) > 1, "the working figure no longer spans a split year"
    assert all(declaration.removed_by_next_edition for _, declaration in carriers)
    assert not [
        finding for finding in singleton_findings("303", views) if finding.declaration_id == "recargo.super-reducido"
    ]
