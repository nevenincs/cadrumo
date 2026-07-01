"""Registry source grounding for annual enrolled capital-market summary modelos."""

from __future__ import annotations

import pytest

from .....core.resources import bundled_path
from .. import RegistryValidator
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.mark.parametrize(
    ("modelo_id", "procedure_code"),
    [
        ("187", "GI07"),
        ("188", "GI08"),
        ("194", "GI13"),
        ("198", "GI17"),
    ],
)
def test_capital_mobiliario_summary_guidance_and_layout_sources_are_separated(
    modelo_id: str,
    procedure_code: str,
) -> None:
    modelo, catalogues = _committed_modelo(modelo_id)
    procedure_ref = f"aeat-modelo-{modelo_id}-procedure"
    layout_ref = f"boe-modelo-{modelo_id}-form-layout"

    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)

    procedure = catalogues.sources[procedure_ref]
    layout = catalogues.sources[layout_ref]

    assert procedure_ref in modelo.source_refs
    assert layout_ref in modelo.source_refs
    assert procedure.evidence_tier == "official_source_guidance"
    assert procedure.authority == "aeat"
    assert procedure.kind == "instructions"
    assert procedure.corpus_path == (
        f"corpus/aeat_official/instructions/modelo_{modelo_id}/files/"
        f"modelo-{modelo_id}-procedure.html"
    )
    assert (bundled_path() / procedure.corpus_path).is_file()
    assert procedure.source_url.endswith(f"/Sede/procedimientoini/{procedure_code}.shtml")
    assert layout.evidence_tier == "layout_authority"
    assert layout.authority == "boe"
    assert layout.kind == "form_spec"

    revision = modelo.revisions["2019-y-siguientes"]
    for formula in revision.formulas:
        for citation in formula.source_citations:
            assert citation.source_ref == procedure_ref
            assert catalogues.sources[citation.source_ref].evidence_tier == "official_source_guidance"
