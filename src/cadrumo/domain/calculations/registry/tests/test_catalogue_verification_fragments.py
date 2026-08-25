"""Real-corpus verification for subsection and non-article legal references."""

from __future__ import annotations

from pathlib import Path

import pytest

from .....core import normalise_corpus_text, resolve_anchored_extracted_unit
from .....core.resources import bundled_path
from ..legal import verify_legal_catalogue
from ._catalogue_verification_support import _catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ANNUAL_ORDER_FRAGMENT_IDS = (
    "orden-hfp-1359-2023:instruccion-2-2-a",
    "orden-hfp-1359-2023:instruccion-2-2-b",
    "orden-hfp-1359-2023:instruccion-2-3-b-3",
    "orden-hfp-1359-2023:anexo-ii-instruccion-2-3-incompatibilidades",
    "orden-hfp-1359-2023:anexo-ii-instruccion-2-3-b-1",
    "orden-hfp-1359-2023:anexo-ii-instruccion-2-3-b-2",
    "orden-hfp-1359-2023:anexo-ii-instruccion-2-3-b-4",
    "orden-hac-1347-2024:instruccion-2-2-a",
    "orden-hac-1347-2024:instruccion-2-2-b",
    "orden-hac-1347-2024:instruccion-2-3-b-3",
    "orden-hac-1347-2024:anexo-ii-instruccion-2-3-incompatibilidades",
    "orden-hac-1347-2024:anexo-ii-instruccion-2-3-b-1",
    "orden-hac-1347-2024:anexo-ii-instruccion-2-3-b-2",
    "orden-hac-1347-2024:anexo-ii-instruccion-2-3-b-4",
    "orden-hac-1347-2024:anexo-i-instruccion-2-1",
    "orden-hac-1347-2024:anexo-i-instruccion-2-2",
    "orden-hac-1347-2024:anexo-i-instruccion-2-3",
    "orden-hac-1347-2024:anexo-i-instruccion-3",
    "orden-hac-1425-2025:instruccion-2-2-a",
    "orden-hac-1425-2025:instruccion-2-2-b",
    "orden-hac-1425-2025:instruccion-2-3-b-3",
    "orden-hac-1425-2025:anexo-ii-instruccion-2-3-incompatibilidades",
)

_DIRECT_FRAGMENT_REFS = {
    "orden-2000-11-20:apartado-primero": "#primero",
    "orden-hfp-1359-2023:da-5": "#da-quinta",
    "orden-hfp-1359-2023:da-6": "#da-sexta",
    "orden-hfp-1359-2023:da-1": "#da-primera",
    "orden-hac-1347-2024:da-1": "#da-primera",
    "orden-hac-1425-2025:da-1": "#da-primera",
    "ley-35-2006:da-6": "#da-sexta-beneficios-fiscales-especiales",
    "ley-35-2006:da-50": "#da-quincuagesima-deduccion-por-obras",
    "ley-35-2006:dt-38": "#dt-trigesima-octava-reduccion-aplicable",
    "ley-35-2006:da-48": "#da-cuadragesima-octava-deduccion-aplicable",
    "resolucion-dgt-2013-12-17-modelo-145:amendment": "#apartado-unico",
    "orden-hac-132-2026:art-unico": "#articulo-unico",
    "orden-hfp-528-2023:art-unico": "#articulo-unico",
    "orden-hac-3625-2003:apartado-3": "#tercero",
    "ley-37-1992:art-9-bis": "#articulo-9-bis-acuerdo-de-ventas-de-bienes-en-consigna",
    "ley-37-1992:art-18": "#articulo-18-concepto-de-importacion-de-bienes",
}


def _resolved_text(corpus_ref: str) -> str:
    path_text, _, anchor = corpus_ref.partition("#")
    sidecar = Path(str(bundled_path(path_text)) + ".extracted.json")
    return resolve_anchored_extracted_unit(sidecar, anchor=anchor, include_title=True)


def test_annual_order_instruction_refs_resolve_only_atomic_derived_units() -> None:
    catalogues = _catalogues()
    references = {ref_id: catalogues.legal[ref_id] for ref_id in _ANNUAL_ORDER_FRAGMENT_IDS}

    verify_legal_catalogue(references, source_root=bundled_path())
    for ref_id, reference in references.items():
        text = normalise_corpus_text(_resolved_text(reference.corpus_ref))
        assert reference.required_text, ref_id
        assert all(normalise_corpus_text(item) in text for item in reference.required_text), ref_id


def test_existing_atomic_provisions_use_unambiguous_structural_anchors() -> None:
    catalogues = _catalogues()
    references = {ref_id: catalogues.legal[ref_id] for ref_id in _DIRECT_FRAGMENT_REFS}

    for ref_id, expected_anchor in _DIRECT_FRAGMENT_REFS.items():
        assert references[ref_id].corpus_ref.endswith(expected_anchor), ref_id
    verify_legal_catalogue(references, source_root=bundled_path())
