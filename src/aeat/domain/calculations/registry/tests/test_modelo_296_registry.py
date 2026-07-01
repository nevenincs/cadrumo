"""Modelo 296 registry source grounding."""

from __future__ import annotations

import pytest

from .....core.resources import bundled_path
from .. import RegistryValidator
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_modelo_296_guidance_and_layout_sources_are_separated() -> None:
    modelo, catalogues = _committed_modelo("296")
    procedure = catalogues.sources["aeat-modelo-296-procedure"]
    layout = catalogues.sources["boe-modelo-296-form-layout"]

    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)
    assert procedure.evidence_tier == "official_source_guidance"
    assert procedure.authority == "aeat"
    assert procedure.kind == "instructions"
    assert (bundled_path() / procedure.corpus_path).is_file()
    assert layout.evidence_tier == "layout_authority"
    assert layout.authority == "boe"
    assert layout.kind == "form_spec"
    for formula in modelo.revisions["2024-y-siguientes"].formulas:
        for citation in formula.source_citations:
            assert catalogues.sources[citation.source_ref].evidence_tier == "official_source_guidance"
