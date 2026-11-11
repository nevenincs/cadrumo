"""The edition-singleton projection reads a real hydrated modelo."""

from __future__ import annotations

import pytest

from ...compiler.loader import load_modelo_directory, load_shared_catalogues
from ..casilla_lineage_seed_paths import MODELOS_ROOT, REGISTRY_ROOT
from ..edition_singleton_audit import LegalWindow, editions_in_support

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
