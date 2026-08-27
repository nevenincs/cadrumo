"""Registry source grounding for annual enrolled capital-market summary modelos."""

from __future__ import annotations

import pytest

from .....core.resources import bundled_path
from .....tests.aeat_literal_fixtures import PROCEDIMIENTOINI_PATH_PREFIX_FIXTURE
from .._validate import RegistryValidator
from ._registry_schema_support import _committed_modelo, _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.mark.parametrize(
    ("modelo_id", "procedure_code"),
    [
        ("187", "GI07"),
        ("188", "GI08"),
        ("194", "GI13"),
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
        f"corpus/aeat_official/instructions/modelo_{modelo_id}/files/modelo-{modelo_id}-procedure.html"
    )
    assert (bundled_path() / procedure.corpus_path).is_file()
    assert procedure.source_url.endswith(f"{PROCEDIMIENTOINI_PATH_PREFIX_FIXTURE}{procedure_code}.shtml")
    assert layout.evidence_tier == "layout_authority"
    assert layout.authority == "boe"
    assert layout.kind == "form_spec"

    # Every declared revision, not one pinned id: the ids are re-authored per
    # orden (187 is 2022-y-siguientes, 188 is 2023-y-siguientes, 194 carries
    # three), so pinning one both rots and narrows what this asserts.
    for revision in modelo.revisions.values():
        for formula in revision.formulas:
            for citation in formula.source_citations:
                assert citation.source_ref == procedure_ref
                assert catalogues.sources[citation.source_ref].evidence_tier == "official_source_guidance"


def test_deenrolled_modelo_198_has_no_registry_sources() -> None:
    modelos, catalogues = _committed_registry_tree()

    assert all(modelo.id != "198" for modelo in modelos)
    assert "aeat-modelo-198-procedure" not in catalogues.sources
    assert "boe-modelo-198-form-layout" not in catalogues.sources


@pytest.mark.parametrize(
    (
        "modelo_id",
        "procedure_code",
        "annex_ref",
        "formula_specs",
        "closure_casillas",
    ),
    [
        (
            "117",
            "GH03",
            "orden-eha-3435-2007:anexo-i",
            {
                "modelo-117-total-liquidacion": ("09", "add", ("03", "06", "08")),
                "modelo-117-resultado-ingresar": ("11", "subtract", ("09", "10")),
            },
            ("03", "06", "08", "09", "10", "11"),
        ),
        (
            "126",
            "GH06",
            "orden-eha-3435-2007:anexo-iv",
            {
                "modelo-126-total-liquidacion": ("10", "add", ("02", "06")),
                "modelo-126-resultado-ingresar": ("12", "subtract", ("10", "11")),
            },
            ("02", "06", "10", "11", "12"),
        ),
        (
            "128",
            "GH07",
            "orden-eha-3435-2007:anexo-v",
            {
                "modelo-128-resultado-ingresar": ("07", "subtract", ("03", "06")),
            },
            ("03", "06", "07"),
        ),
    ],
)
def test_current_retention_autoliquidaciones_use_current_grounded_sources(
    modelo_id: str,
    procedure_code: str,
    annex_ref: str,
    formula_specs: dict[str, tuple[str, str, tuple[str, ...]]],
    closure_casillas: tuple[str, ...],
) -> None:
    modelo, catalogues = _committed_modelo(modelo_id)
    procedure_ref = f"aeat-modelo-{modelo_id}-procedure"
    text_ref = f"boe-modelo-{modelo_id}-form-text"
    layout_ref = f"boe-modelo-{modelo_id}-form-layout"
    stale_prefix = f"enrolled-modelo-{modelo_id}-"

    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)

    procedure = catalogues.sources[procedure_ref]
    text = catalogues.sources[text_ref]
    layout = catalogues.sources[layout_ref]
    legal = catalogues.legal[annex_ref]

    assert procedure_ref in modelo.source_refs
    assert text_ref in modelo.source_refs
    assert layout_ref in modelo.source_refs
    assert not any(source_ref.startswith(stale_prefix) for source_ref in modelo.source_refs)
    assert procedure.evidence_tier == "official_source_guidance"
    assert procedure.authority == "aeat"
    assert procedure.kind == "instructions"
    assert procedure.corpus_path == (
        f"corpus/aeat_official/instructions/modelo_{modelo_id}/files/modelo-{modelo_id}-procedure.html"
    )
    assert (bundled_path() / procedure.corpus_path).is_file()
    assert procedure.source_url.endswith(f"{PROCEDIMIENTOINI_PATH_PREFIX_FIXTURE}{procedure_code}.shtml")
    assert text.evidence_tier == "official_source_guidance"
    assert text.authority == "boe"
    assert text.kind == "form_spec"
    assert (bundled_path() / text.corpus_path).is_file()
    assert layout.evidence_tier == "layout_authority"
    assert layout.authority == "boe"
    assert layout.kind == "form_spec"
    assert "BOE-A-2007-20485" in layout.source_url
    assert legal.document_id == "BOE-A-2007-20485"

    revision = modelo.revisions["2019-y-siguientes"]
    assert annex_ref in revision.orden_aplicabilidad
    assert annex_ref in revision.legal_refs
    assert "orden-eha-3435-2007:anexo-ii" not in revision.legal_refs
    assert not any(source_ref.startswith(stale_prefix) for source_ref in _revision_source_refs(revision))

    formulas = {formula.id: formula for formula in revision.formulas}
    assert set(formula_specs) == set(formulas)
    source_text = (bundled_path() / text.corpus_path).read_text(encoding="utf-8")
    for formula_id, (target, op, operands) in formula_specs.items():
        formula = formulas[formula_id]
        assert formula.target_casilla_id == target
        assert formula.expression.op == op
        assert tuple(arg.casilla_id for arg in formula.expression.args) == operands
        assert text_ref in formula.source_refs
        assert procedure_ref not in formula.source_refs
        assert tuple(citation.source_ref for citation in formula.source_citations) == (text_ref,)
        for citation in formula.source_citations:
            assert all(required_text in source_text for required_text in citation.required_text)

    assert revision.completeness_manifest is not None
    manifest = revision.completeness_manifest
    assert manifest.source_ref == layout_ref
    assert annex_ref in manifest.legal_refs
    assert text_ref in manifest.source_refs
    assert tuple(casilla.casilla_id for casilla in manifest.casillas) == closure_casillas


def _revision_source_refs(revision: object) -> tuple[str, ...]:
    source_refs: list[str] = [*getattr(revision, "source_refs", ())]
    for collection_name in (
        "casillas",
        "formulas",
        "workbook_parity_refs",
        "application_links",
        "deadline_windows",
    ):
        for item in getattr(revision, collection_name, ()):
            source_refs.extend(getattr(item, "source_refs", ()))
            if collection_name == "formulas":
                source_refs.extend(citation.source_ref for citation in getattr(item, "source_citations", ()))
    return tuple(source_refs)
