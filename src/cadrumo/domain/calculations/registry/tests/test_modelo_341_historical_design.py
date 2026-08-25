"""Historical AEAT record-design evidence for Modelo 341.

This is an acquisition proof only. It deliberately does not make the design
an authority for the revision's existing export layout until that layout has
been compared against the historical geometry.
"""

from __future__ import annotations

from datetime import date

import pytest

from .....core.hashing import hash_file
from .....core.resources import bundled_path
from ..record_design import extract_record_design
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SOURCE_REF = "aeat-dr-341-2005-2015"


def test_modelo_341_historical_design_is_hash_pinned_but_not_yet_joined() -> None:
    """Keep the exact AEAT evidence without silently backdating the writer."""
    modelo, catalogues = _committed_modelo("341")
    source = catalogues.sources[_SOURCE_REF]
    path = bundled_path() / source.corpus_path
    revision = modelo.revisions["2000-y-siguientes"]

    assert source.evidence_tier == "layout_authority"
    assert source.authority == "aeat"
    assert source.kind == "record_design"
    assert source.record_design_epoch == "2005"
    assert (source.applies_from, source.applies_to) == (date(2005, 2, 1), date(2015, 12, 31))
    assert source.source_url.endswith("/ant_300_399/archivos/dr341_2005.pdf")
    assert hash_file(path) == (source.sha256, source.bytes)

    extraction = extract_record_design(path)
    assert [(sheet.total_positions, len(sheet.fields)) for sheet in extraction.accept_partial()] == [(619, 20)]
    assert _SOURCE_REF not in {reference for layout in revision.export_layouts for reference in layout.source_refs}
