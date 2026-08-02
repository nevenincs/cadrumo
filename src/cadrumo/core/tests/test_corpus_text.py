"""Behaviour and import-boundary tests for corpus-text normalisation."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from .. import CorpusAnchorResolutionError, normalise_corpus_text, resolve_anchored_extracted_unit
from ..corpus_text import normalise_corpus_text as normalise_corpus_text_owner

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REPO_ROOT = Path(__file__).resolve().parents[4]
_NORMATIVES = _REPO_ROOT / "src" / "cadrumo" / "_data" / "corpus" / "normatives" / "html"


def test_core_facade_reexports_the_corpus_text_owner() -> None:
    """All consumers share the exact stdlib-only normaliser object."""
    assert normalise_corpus_text is normalise_corpus_text_owner


def test_core_facade_normaliser_imports_without_configuration_or_domain_loading() -> None:
    """Build tooling can use the facade without loading settings or registry code."""
    probe = (
        "import sys\n"
        "from cadrumo.core import normalise_corpus_text\n"
        "assert normalise_corpus_text('<p>Café&nbsp;2026</p>') == 'cafe 2026'\n"
        "assert 'cadrumo.core.config' not in sys.modules\n"
        "assert not any(name.startswith('cadrumo.domain') for name in sys.modules)\n"
    )
    completed = subprocess.run(  # noqa: S603 - fixed interpreter and inline probe exercise the import boundary.
        [sys.executable, "-c", probe],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


def test_math_notation_less_than_does_not_swallow_prose() -> None:
    corpus = "Reducción aplicable cuando el importe es < 500 euros y el plazo es < 3 años."

    normalised = normalise_corpus_text(corpus)

    assert "< 500 euros" in normalised
    assert "< 3 anos" in normalised
    assert "reduccion aplicable" in normalised


def test_well_formed_html_tags_are_stripped() -> None:
    corpus = "<p>escala autonómica</p> aplicable a <strong>base liquidable</strong>"

    normalised = normalise_corpus_text(corpus)

    assert "<p>" not in normalised
    assert "</p>" not in normalised
    assert "<strong>" not in normalised
    assert "escala autonomica" in normalised
    assert "base liquidable" in normalised


def test_html_entities_are_decoded_before_stripping() -> None:
    corpus = "escala auton&oacute;mica &amp; base liquidable general"

    normalised = normalise_corpus_text(corpus)

    assert "escala autonomica" in normalised
    assert "&" in normalised
    assert "base liquidable general" in normalised


def test_nfkd_nbsp_and_whitespace_normalisation_preserve_citation_grammar() -> None:
    corpus = "  Año\xa02025\n\npor\tatribución  "

    assert normalise_corpus_text(corpus) == "ano 2025 por atribucion"


def test_unbalanced_open_angle_at_end_of_input_is_preserved() -> None:
    corpus = "Importe inferior a <"

    normalised = normalise_corpus_text(corpus)

    assert "importe inferior a" in normalised


def test_single_article_sidecar_safely_resolves_a_subsection_fragment() -> None:
    """A one-unit article excerpt cannot select unrelated text for a sub-anchor."""
    sidecar = _NORMATIVES / "ley-58-2003-art-27.html.extracted.json"

    text = resolve_anchored_extracted_unit(sidecar, anchor="a27-2")

    assert "porcentaje igual al 1 por ciento" in text


def test_multi_unit_sidecar_refuses_a_missing_anchor() -> None:
    """A missing anchor may not widen to every article in a consolidated law."""
    sidecar = _NORMATIVES / "ley-37-1992.html.extracted.json"

    with pytest.raises(CorpusAnchorResolutionError, match="missing"):
        resolve_anchored_extracted_unit(sidecar, anchor="not-a-real-anchor")


def test_multi_unit_sidecar_refuses_a_duplicate_anchor(tmp_path: Path) -> None:
    """Duplicated provenance anchors are not resolved by arbitrary unit order."""
    source = _NORMATIVES / "ley-37-1992.html.extracted.json"
    copied = tmp_path / source.name
    payload = json.loads(source.read_text(encoding="utf-8"))
    first_unit = next(unit for unit in payload["units"] if unit["anchor"] == "#a1")
    payload["units"].append(first_unit)
    copied.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(CorpusAnchorResolutionError, match="duplicated"):
        resolve_anchored_extracted_unit(copied, anchor="a1")


def test_multi_unit_sidecar_can_resolve_a_unique_structural_heading() -> None:
    """Legacy BOE document anchors select their one matching article heading."""
    sidecar = _NORMATIVES / "orden-hfp-1359-2023.html.extracted.json"

    text = resolve_anchored_extracted_unit(sidecar, anchor="articulo-4")

    assert "De conformidad con los artículos" in text


def test_multi_unit_sidecar_can_resolve_a_spelled_out_disposicion_heading() -> None:
    """A legacy unit title can ground a fully spelled corpus provision anchor."""
    sidecar = _NORMATIVES / "orden-hfp-1359-2023.html.extracted.json"

    text = resolve_anchored_extracted_unit(
        sidecar,
        anchor="disposicion-adicional-quinta",
        include_title=True,
    )

    assert normalise_corpus_text("Reducción en 2024 del rendimiento neto") in normalise_corpus_text(text)


def test_descriptive_article_anchor_does_not_collapse_to_its_base_article() -> None:
    """A suffixed article title is not an ambiguous request for its base number."""
    sidecar = _NORMATIVES / "ley-37-1992.html.extracted.json"

    text = resolve_anchored_extracted_unit(
        sidecar,
        anchor="articulo-9-bis-acuerdo-de-ventas-de-bienes-en-consigna",
        include_title=True,
    )

    assert normalise_corpus_text("Artículo 9 bis. Acuerdo de ventas de bienes en consigna") in normalise_corpus_text(text)


def test_multi_unit_sidecar_keeps_articulo_unico_distinct_from_articulo_1() -> None:
    """An ordinal provision title must not collapse to a numeric article."""
    sidecar = _NORMATIVES / "orden-hfp-312-2023.html.extracted.json"

    text = resolve_anchored_extracted_unit(sidecar, anchor="articulo-unico")

    assert "Se introducen las siguientes modificaciones" in text


def test_legal_verification_can_include_the_selected_unit_title() -> None:
    """Required legal text may deliberately name the provision heading."""
    sidecar = _NORMATIVES / "orden-hfp-312-2023.html.extracted.json"

    text = resolve_anchored_extracted_unit(sidecar, anchor="articulo-unico", include_title=True)

    assert normalise_corpus_text("Artículo único. Modificación de la Orden HFP/227/2017") in normalise_corpus_text(text)


def test_multi_unit_sidecar_resolves_an_unanchored_ordinal_apartado() -> None:
    """A reviewed subsection may select its unique ordinal heading without widening."""
    sidecar = _NORMATIVES / "orden-hac-3625-2003-art-3.html.extracted.json"

    text = resolve_anchored_extracted_unit(sidecar, anchor="apartado-3")

    assert "veinte primeros días" in text
    assert "treinta primeros días" in text


def test_multi_unit_sidecar_resolves_an_unanchored_ordinal_provision() -> None:
    """A bare ordinal anchor selects the one matching BOE provision title."""
    sidecar = _NORMATIVES / "boe-a-2011-208-modelo-145.html.extracted.json"

    text = resolve_anchored_extracted_unit(sidecar, anchor="primero")

    assert "Se aprueba el modelo 145" in text
    assert "un ejemplar para la empresa" in text


def test_multi_unit_sidecar_resolves_the_exact_roman_numeral_annex() -> None:
    """An annex I request cannot widen to annexes II through VI."""
    sidecar = _NORMATIVES / "orden-eha-3435-2007.html.extracted.json"

    text = resolve_anchored_extracted_unit(sidecar, anchor="anexo-i")

    assert "Ref. BOE-A-2018-17997" in text


def test_structural_heading_selects_one_unmarked_provision_unit() -> None:
    """A unique official provision title grounds an unanchored legacy unit."""
    sidecar = _NORMATIVES / "orden-hfp-1359-2023.html.extracted.json"

    text = resolve_anchored_extracted_unit(
        sidecar,
        anchor="disposicion-adicional-quinta",
    )

    assert normalise_corpus_text("término municipal de Lorca") in normalise_corpus_text(text)
    assert normalise_corpus_text("rendimiento neto de módulos de 2024") in normalise_corpus_text(text)
