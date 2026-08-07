"""Presentation contracts for the generated casilla reference pages.

The pages are where a search result lands, so they carry two obligations the
anchor-parity gate does not cover:

- **One language per page.** The projection carries every supported language's
  label and help; a page built under one ``CADRUMO_DOCS_LANGUAGE`` must render
  ONLY that language, falling back to the Spanish invariant marked ``lang="es"``
  where a locale authored nothing. Rendering all four at once made every entry a
  four-language dump.
- **Meaning outranks machine vocabulary.** The registry's own identifiers
  (casilla id, semantic role, binding/formula ids, source refs, revisions) stay
  on the page for an operator but are demoted into the collapsed disclosure, and
  every legal ref renders as a named link into the generated legal reference
  rather than a raw catalogue token.

Records are constructed here rather than projected so each contract is driven by
values this module supplies: the assertions then read the renderer's behaviour,
never a locale catalogue's current contents.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from cadrumo.core import Modelo
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.domain.calculations.registry import InputKind

from ..casilla_reference import _display_language, _legal_provision_display, render_casilla_reference
from ..legal_reference import legal_reference_target, load_legal_provisions
from ..terminology._casilla_anchor import casilla_page_anchor
from ..terminology._search_record import CasillaSearchRecord

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_REPO_ROOT = Path(__file__).resolve().parents[3]

#: Per-language marker strings this module authors onto one record, so a leak of
#: any non-build language is detectable by exact substring.
_LABELS = {
    OutputLanguage.ES: "Etiqueta castellana de prueba",
    OutputLanguage.EN: "English test label",
    OutputLanguage.CA: "Etiqueta catalana de prova",
    OutputLanguage.HU: "Magyar tesztcimke",
}
_HELP = {
    OutputLanguage.ES.value: "Ayuda castellana de prueba",
    OutputLanguage.EN.value: "English test help",
    OutputLanguage.CA.value: "Ajuda catalana de prova",
    OutputLanguage.HU.value: "Magyar tesztsugo",
}


def _record(**overrides: object) -> CasillaSearchRecord:
    """One fully populated casilla record with every language authored."""
    fields: dict[str, object] = {
        "descriptions": dict(_LABELS),
        "modelo": Modelo.M390,
        "casilla_id": "iva.anual.soportado.interiores",
        "localized_help": dict(_HELP),
        "data_type": "money",
        "input_kind": InputKind.BOUND,
        "required": True,
        "binding": "modelo-390-iva-soportado-interiores",
        "number": "0630",
        "segmento": "T1",
        "section": ("iva", "anual", "deducible"),
        "semantic_role": "iva_cuota_soportada_interiores",
        "legal_refs": ("ley-37-1992:art-92",),
        "source_refs": ("aeat-dr-390-2025",),
        "source_revisions": ("2010-y-siguientes",),
    }
    fields.update(overrides)
    return CasillaSearchRecord(**fields)  # type: ignore[arg-type]


def _render(records: tuple[CasillaSearchRecord, ...], language: OutputLanguage) -> str:
    result = render_casilla_reference(_REPO_ROOT, records=records, language=language)
    assert len(result.pages) == 1
    return result.pages[0].rst


@pytest.mark.parametrize("language", list(OutputLanguage))
def test_page_renders_only_the_build_language(language: OutputLanguage) -> None:
    """A page carries the build language's label and help, and no other's."""
    rst = _render((_record(),), language)
    assert _LABELS[language] in rst
    assert _HELP[language.value] in rst
    for other in OutputLanguage:
        if other is language:
            continue
        assert _LABELS[other] not in rst
        assert _HELP[other.value] not in rst


@pytest.mark.parametrize("language", [OutputLanguage.EN, OutputLanguage.CA, OutputLanguage.HU])
def test_absent_locale_falls_back_to_spanish_and_declares_it(language: OutputLanguage) -> None:
    """A language with no authored string shows Spanish, marked ``lang="es"``."""
    spanish_only = _record(
        descriptions={OutputLanguage.ES: _LABELS[OutputLanguage.ES]},
        localized_help={OutputLanguage.ES.value: _HELP[OutputLanguage.ES.value]},
    )
    rst = _render((spanish_only,), language)
    assert f'casilla-card__title" lang="es">{_LABELS[OutputLanguage.ES]}' in rst
    assert f'casilla-card__help" lang="es">{_HELP[OutputLanguage.ES.value]}' in rst


def test_authored_locale_is_never_marked_as_a_fallback() -> None:
    """A language that DID author the string carries no ``lang`` override."""
    rst = _render((_record(),), OutputLanguage.CA)
    assert f'casilla-card__title">{_LABELS[OutputLanguage.CA]}' in rst
    assert 'lang="es"' not in rst


def test_default_language_is_the_shared_build_signal() -> None:
    """The renderer's default language is the one build-language authority."""
    import os

    from ..build import docs_build_language

    assert _display_language() == docs_build_language(os.environ)


def test_legal_refs_link_into_the_generated_legal_reference() -> None:
    """Each ref renders as a named link resolving to the legal generator's target."""
    record = _record()
    result = render_casilla_reference(_REPO_ROOT, records=(record,), language=OutputLanguage.EN)
    rst = result.pages[0].rst

    provisions = {provision.legal_id: provision for provision in load_legal_provisions(_REPO_ROOT)}
    provision = provisions["ley-37-1992:art-92"]
    site_target = legal_reference_target(
        provision.document_id,
        provision.legal_id,
        article=provision.article,
        section=provision.section,
        corpus_ref=provision.corpus_ref,
        permalink=provision.permalink,
    )
    expected = "../" + site_target.removeprefix("_generated/")
    assert f'href="{expected}"' in rst
    assert result.legal_links == 1
    # The raw catalogue token survives as the link's title, never as the text.
    assert 'title="ley-37-1992:art-92"' in rst
    assert ">ley-37-1992:art-92<" not in rst


def test_unresolvable_ref_still_renders_and_is_not_counted_as_a_link() -> None:
    """D6: grounding is never dropped, but an unlinkable ref is not a link."""
    record = _record(legal_refs=("ley-37-1992:art-92", "no-such-norm-1-2000:art-1"))
    result = render_casilla_reference(_REPO_ROOT, records=(record,), language=OutputLanguage.EN)
    rst = result.pages[0].rst
    anchor = casilla_page_anchor(record.modelo, record.casilla_id)

    assert "no-such-norm-1-2000:art-1" in rst
    assert result.legal_links == 1
    assert result.pages[0].rendered_legal_refs[anchor] == record.legal_refs


@pytest.mark.parametrize(
    ("legal_id", "expected"),
    [
        ("ley-37-1992:art-92", "Ley 37/1992, art. 92"),
        ("rd-1624-1992:art-71", "Real Decreto 1624/1992, art. 71"),
        ("orden-eha-3111-2009:art-1", "Orden EHA/3111/2009, art. 1"),
        ("real-decreto-ley-4-2024:art-1", "Real Decreto-ley 4/2024, art. 1"),
    ],
)
def test_provision_display_reads_the_official_instrument_name(legal_id: str, expected: str) -> None:
    """A catalogue id renders as the instrument's official Spanish name plus article."""
    provisions = {provision.legal_id: provision for provision in load_legal_provisions(_REPO_ROOT)}
    assert _legal_provision_display(legal_id, provisions[legal_id]) == expected


def test_machine_identifiers_are_confined_to_the_disclosure() -> None:
    """Registry vocabulary stays on the page, below the fold of a ``<details>``."""
    record = _record(formula_id="modelo-390-total-cuota-devengada")
    rst = _render((record,), OutputLanguage.EN)
    disclosure = rst.partition('<details class="casilla-card__internals">')
    assert disclosure[1], "the registry-identifier disclosure is missing"
    above, below = disclosure[0], disclosure[2]

    for identifier in (
        str(record.casilla_id),
        str(record.semantic_role),
        str(record.binding),
        str(record.formula_id),
        record.source_refs[0],
        record.source_revisions[0],
    ):
        assert identifier in below
        assert identifier not in above


def test_card_leads_with_the_number_and_the_filing_facts() -> None:
    """The head is the official number and label; the chips are filer-facing."""
    rst = _render((_record(),), OutputLanguage.EN)
    head = rst.partition('<details class="casilla-card__internals">')[0]
    assert '<span class="casilla-card__number">0630</span>' in head
    assert "casilla-fact--bound" in head
    assert "casilla-fact--required" in head
    assert "Segmento T1" in head


def test_sections_carry_jump_targets_matching_the_page_nav() -> None:
    """Every section in the jump list resolves to an anchor emitted on the page."""
    records = (
        _record(),
        _record(casilla_id="decl.ejercicio", number="ejercicio", section=("declarante",)),
    )
    rst = _render(records, OutputLanguage.EN)
    linked = set(re.findall(r'href="#(section-[a-z0-9-]+)"', rst))
    emitted = set(re.findall(r'casilla-section-anchor" id="(section-[a-z0-9-]+)"', rst))
    assert linked
    assert linked == emitted


def test_colliding_section_anchors_are_a_build_failure() -> None:
    """Two section paths folding to one jump target are refused, never merged."""
    from ..casilla_reference import CasillaReferenceError, _section_anchor

    underscored = ("iva", "anual_deducible")
    hyphenated = ("iva", "anual-deducible")
    assert _section_anchor(underscored) == _section_anchor(hyphenated)

    records = (
        _record(section=underscored),
        _record(casilla_id="decl.ejercicio", number="ejercicio", section=hyphenated),
    )
    with pytest.raises(CasillaReferenceError):
        _render(records, OutputLanguage.EN)
