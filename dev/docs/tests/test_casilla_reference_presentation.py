"""Presentation contracts for the generated casilla reference pages.

The pages are where a search result lands, and there is no per-casilla prose to
land on, so they carry two obligations the anchor-parity gate does not cover:

- **One language, never a substitute.** A page built under one
  ``CADRUMO_DOCS_LANGUAGE`` renders ONLY that language's schema localizations. A
  string the build language does not author is OMITTED, never filled from
  Spanish or from another locale - a substituted string reads as though the
  reader's language were covered when it is not.
- **The substance is compiled from the schema.** What a filer needs is how the
  box gets filled: entered, calculated from named other boxes, or filled from a
  named source. Those come from ``input_kind``, the ``formula`` expression and
  the ``binding`` source taxonomy, and must reach the page - with the registry's
  own identifiers demoted, and legal refs linked rather than printed raw.

Records and compiled facts are constructed here rather than projected, so each
contract is driven by values this module supplies: the assertions then read the
renderer's behaviour, never a catalogue's current contents.
"""

from __future__ import annotations

import re
from typing import Any

import pytest

from cadrumo.core.modelo import Modelo
from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaConstraints

from ..._paths import REPO_ROOT
from .._locale_chrome import DocsChromeError, docs_chrome
from ..casilla_reference import (
    EMPTY_SCHEMA,
    CasillaFacts,
    CompiledSchema,
    ModeloOverview,
    _display_language,
    _handbook_definitions,
    _legal_provision_display,
    display_locale_keys,
    render_casilla_reference,
)
from ..legal_reference import legal_reference_target, load_legal_provisions
from ..terminology._casilla_anchor import casilla_page_anchor
from ..terminology._search_record import CasillaSearchRecord

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_REPO_ROOT = REPO_ROOT

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
    fields: dict[str, Any] = {
        "descriptions": dict(_LABELS),
        "modelo": Modelo.M130,
        "casilla_id": "03",
        "localized_help": dict(_HELP),
        "data_type": "money",
        "input_kind": InputKind.COMPUTED,
        "required": True,
        "formula_id": "modelo-130-rendimiento-neto",
        "number": "03",
        "section": ("actividades_economicas",),
        "semantic_role": "irpf_rendimiento_neto",
        "legal_refs": ("ley-37-1992:art-92",),
        "source_refs": ("aeat-dr-130-2025",),
        "source_revisions": ("2025",),
    }
    fields.update(overrides)
    return CasillaSearchRecord(**fields)  # type: ignore[arg-type]


def _schema(
    facts: dict[tuple[str, str], CasillaFacts] | None = None,
    overview: ModeloOverview | None = None,
) -> CompiledSchema:
    return CompiledSchema(
        casillas=facts or {},
        modelos={Modelo.M130.value: overview} if overview is not None else {},
    )


def _render(
    records: tuple[CasillaSearchRecord, ...],
    language: OutputLanguage,
    schema: CompiledSchema = EMPTY_SCHEMA,
) -> str:
    result = render_casilla_reference(_REPO_ROOT, records=records, language=language, schema=schema)
    assert len(result.pages) == 1
    return result.pages[0].rst


# ── One language, never a substitute ─────────────────────────────────────────


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


def test_catalogue_line_wrapping_cannot_break_raw_html_cards_or_index() -> None:
    """Authored multiline labels stay intact while generated HTML stays one line."""
    record = _record(
        descriptions={OutputLanguage.ES: "Etiqueta con\n  salto de línea"},
        localized_help={OutputLanguage.ES.value: "Ayuda con\n  salto de línea"},
    )

    rst = _render((record,), OutputLanguage.ES)

    assert "Etiqueta con salto de línea" in rst
    assert "Ayuda con salto de línea" in rst
    assert "Etiqueta con\n" not in rst
    assert "Ayuda con\n" not in rst


@pytest.mark.parametrize("language", [OutputLanguage.EN, OutputLanguage.CA, OutputLanguage.HU])
def test_absent_locale_omits_the_string_rather_than_substituting(language: OutputLanguage) -> None:
    """A language with no authored string gets none - Spanish is not a fallback."""
    spanish_only = _record(
        descriptions={OutputLanguage.ES: _LABELS[OutputLanguage.ES]},
        localized_help={OutputLanguage.ES.value: _HELP[OutputLanguage.ES.value]},
    )
    rst = _render((spanish_only,), language)
    assert _LABELS[OutputLanguage.ES] not in rst
    assert _HELP[OutputLanguage.ES.value] not in rst
    assert "casilla-card__title" not in rst
    assert "casilla-card__help" not in rst
    # The entry still exists and is still addressable, just unlabelled.
    assert f'id="{casilla_page_anchor(spanish_only.modelo, spanish_only.casilla_id)}"' in rst


def test_unlabelled_entry_keeps_its_number_and_its_grounding() -> None:
    """An entry with no label in this language is not dropped from the page."""
    spanish_only = _record(descriptions={OutputLanguage.ES: _LABELS[OutputLanguage.ES]}, localized_help={})
    rst = _render((spanish_only,), OutputLanguage.HU)
    assert '<span class="casilla-card__number">03</span>' in rst
    # The citation renders as instrument plus provision so siblings can group,
    # so assert both parts rather than the joined string.
    assert "Ley 37/1992" in rst
    assert "art. 92" in rst


def test_default_language_is_the_shared_build_signal() -> None:
    """The renderer's default language is the one build-language authority."""
    import os

    from ..build import docs_build_language

    assert _display_language() == docs_build_language(os.environ)


def test_handbook_definitions_are_read_per_language_and_never_shared() -> None:
    """Each language reads its own curated definitions, with no cross-fill.

    Structural only: a modelo present in two languages must not carry the same
    string in both (that would be one language's prose serving another), and the
    per-language maps are independently derived rather than one copied map.
    """
    per_language = {language: _handbook_definitions(language) for language in OutputLanguage}
    spanish = per_language[OutputLanguage.ES]
    assert spanish, "no approved modelo concept authored a Spanish definition"
    for language, definitions in per_language.items():
        if language is OutputLanguage.ES:
            continue
        shared = {key for key in definitions if definitions[key] == spanish.get(key)}
        assert not shared, f"{language.value} reuses the Spanish definition for {sorted(shared)}"


# ── The substance: how the box gets filled ───────────────────────────────────


def _resolves(key: str, language: OutputLanguage) -> bool:
    try:
        docs_chrome(key, language)
    except DocsChromeError:
        return False
    return True


def test_a_missing_display_string_refuses_rather_than_rendering_a_fallback() -> None:
    """An unauthored key is a build failure, never a humanised key fragment.

    The refusal is the shared resolver's, not a second one this surface owns:
    all three generated surfaces fail the same way on the same fault.
    """
    with pytest.raises(DocsChromeError):
        docs_chrome("docs.casilla.chrome.no_such_string", OutputLanguage.ES)


def test_display_keys_are_registered_so_the_scaffold_keeps_them() -> None:
    """The locale scaffold prunes keys its scan cannot see; these are registered.

    The AST key scan walks ``src/cadrumo`` only, so every key this dev-side
    surface consumes would be pruned as stale on the next scaffold run unless it
    is registered. Registration is what makes the catalogue the durable home.
    """
    from ...locales._fstring_registry import get_registered_keys

    assert set(display_locale_keys()) <= get_registered_keys()


def test_computed_casilla_names_the_boxes_it_derives_from() -> None:
    """A derivation renders as linked box numbers, never as the formula id."""
    target = _record()
    inputs = (
        _record(casilla_id="01", number="01", input_kind=InputKind.MANUAL, formula_id=None),
        _record(casilla_id="02", number="02", input_kind=InputKind.MANUAL, formula_id=None),
    )
    schema = _schema({(Modelo.M130.value, "03"): CasillaFacts(formula_inputs=("01", "02"))})
    rst = _render((*inputs, target), OutputLanguage.EN, schema)

    assert "casilla-fill--computed" in rst
    for casilla_id in ("01", "02"):
        anchor = casilla_page_anchor(Modelo.M130, casilla_id)
        assert f'href="#{anchor}" title="{casilla_id}">{casilla_id}</a>' in rst
    assert (
        f" {docs_chrome('docs.casilla.chrome.list_and', OutputLanguage.EN)} "
        in rst.partition("casilla-derives-from")[2]
    )
    assert "modelo-130-rendimiento-neto" not in rst.partition("casilla-card__internals")[0]


def test_bound_casilla_names_the_source_that_fills_it() -> None:
    """A bound casilla answers "filled from what", not merely "bound"."""
    record = _record(input_kind=InputKind.BOUND, formula_id=None, binding="modelo-130-ingresos")
    facts = CasillaFacts(binding_sources=(BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION.value,))
    rst = _render((record,), OutputLanguage.EN, _schema({(Modelo.M130.value, "03"): facts}))

    assert "casilla-fill--bound" in rst
    assert (
        docs_chrome(
            f"docs.casilla.binding_source.{BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION.value}", OutputLanguage.EN
        )
        in rst
    )


def test_alternate_binding_sources_are_offered_as_alternatives() -> None:
    """Alternate bindings read as another way the same box may be filled."""
    record = _record(input_kind=InputKind.BOUND, formula_id=None, binding="modelo-130-ingresos")
    facts = CasillaFacts(
        binding_sources=(
            BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION.value,
            BindingSourceKind.PREVIOUS_FILING.value,
        ),
    )
    rst = _render((record,), OutputLanguage.EN, _schema({(Modelo.M130.value, "03"): facts}))
    assert (
        docs_chrome(f"docs.casilla.binding_source.{BindingSourceKind.PREVIOUS_FILING.value}", OutputLanguage.EN) in rst
    )
    assert docs_chrome("docs.casilla.chrome.alternative_join", OutputLanguage.EN) in rst


@pytest.mark.parametrize(
    ("input_kind", "marker"),
    [
        (InputKind.MANUAL, "casilla-fill--manual"),
        (InputKind.INFORMATIONAL, "casilla-fill--informational"),
    ],
)
def test_every_casilla_states_how_it_is_filled(input_kind: InputKind, marker: str) -> None:
    """The fill explanation is unconditional; no casilla is silent about it."""
    rst = _render((_record(input_kind=input_kind, formula_id=None),), OutputLanguage.EN)
    assert marker in rst


def test_constraints_render_as_what_a_filer_may_enter() -> None:
    """Authored value constraints become a readable range, not a schema dump."""
    constraints = CasillaConstraints(
        sign="non_negative",
        min_value=0,
        max_value=100,
        legal_refs=("ley-37-1992:art-92",),
        source_refs=("aeat-dr-130-2025",),
    )
    facts = CasillaFacts(constraints=constraints)
    rst = _render((_record(),), OutputLanguage.EN, _schema({(Modelo.M130.value, "03"): facts}))
    assert docs_chrome("docs.casilla.value_range.between", OutputLanguage.EN, min=0, max=100) in rst


def test_printed_box_number_wins_over_the_record_design_number() -> None:
    """The badge shows the box a reader sees; the record-design value is demoted."""
    record = _record(casilla_id="iva.anual.total", number="iva.anual.total")
    facts = CasillaFacts(form_number="64")
    rst = _render((record,), OutputLanguage.EN, _schema({(Modelo.M130.value, "iva.anual.total"): facts}))

    above, _, below = rst.partition('<details class="casilla-card__internals">')
    assert '<span class="casilla-card__number">64</span>' in above
    assert docs_chrome("docs.casilla.chrome.record_design_number", OutputLanguage.EN) in below
    assert "iva.anual.total" not in above


# ── Modelo identity ──────────────────────────────────────────────────────────


def _overview(**overrides: object) -> ModeloOverview:
    fields: dict[str, object] = {
        "title": "IRPF pago fraccionado",
        "official_name": "Modelo 130. Pago fraccionado.",
        "definition": None,
        "tax_domain": "irpf",
        "cadence": "quarterly",
        "legal_refs": ("ley-37-1992:art-92",),
    }
    fields.update(overrides)
    return ModeloOverview(**fields)  # type: ignore[arg-type]


def test_modelo_page_leads_with_the_curated_definition_when_one_exists() -> None:
    """An approved Handbook definition is the modelo's opening statement."""
    definition = "Curated statement of what this modelo is."
    rst = _render((_record(),), OutputLanguage.EN, _schema(overview=_overview(definition=definition)))
    assert f'<p class="modelo-overview__definition">{definition}</p>' in rst
    assert "Modelo 130. Pago fraccionado." in rst


def test_modelo_page_without_a_definition_still_characterises_the_modelo() -> None:
    """No curated prose means compiled facts, never a fabricated description."""
    rst = _render((_record(),), OutputLanguage.EN, _schema(overview=_overview()))
    assert "modelo-overview__definition" not in rst
    assert "IRPF" in rst
    assert docs_chrome("docs.casilla.cadence.quarterly", OutputLanguage.EN) in rst
    assert docs_chrome("docs.casilla.chrome.casilla_count", OutputLanguage.EN, casillas=1, sections=1) in rst
    assert f"1 {docs_chrome('docs.casilla.input_kind_count.computed', OutputLanguage.EN)}" in rst


def test_modelo_page_survives_an_unresolved_overview() -> None:
    """A modelo the schema could not compile still renders its casillas."""
    rst = _render((_record(),), OutputLanguage.EN)
    assert "Modelo 130" in rst
    assert "modelo-overview__name" not in rst
    assert '<span class="casilla-card__number">03</span>' in rst


# ── Legal grounding ──────────────────────────────────────────────────────────


def test_legal_refs_link_into_the_generated_legal_reference() -> None:
    """Each ref renders as a named link resolving to the legal generator's target."""
    result = render_casilla_reference(
        _REPO_ROOT,
        records=(_record(),),
        language=OutputLanguage.EN,
        schema=EMPTY_SCHEMA,
    )
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
    result = render_casilla_reference(
        _REPO_ROOT,
        records=(record,),
        language=OutputLanguage.EN,
        schema=EMPTY_SCHEMA,
    )
    rst = result.pages[0].rst
    anchor = casilla_page_anchor(record.modelo, record.casilla_id)

    assert "no-such-norm-1-2000:art-1" in rst
    assert result.legal_links == 1
    assert result.pages[0].rendered_legal_refs[anchor] == record.legal_refs


@pytest.mark.parametrize(
    ("legal_id", "instrument", "provision"),
    [
        ("ley-37-1992:art-92", "Ley 37/1992", "art. 92"),
        ("rd-1624-1992:art-71", "Real Decreto 1624/1992", "art. 71"),
        ("orden-eha-3111-2009:art-1", "Orden EHA/3111/2009", "art. 1"),
        ("real-decreto-ley-4-2024:art-1", "Real Decreto-ley 4/2024", "art. 1"),
    ],
)
def test_provision_display_reads_the_official_instrument_name(
    legal_id: str,
    instrument: str,
    provision: str,
) -> None:
    """A catalogue id splits into the official Spanish instrument name and its article.

    The split is what lets sibling provisions of one norm group under a single
    citation instead of repeating the instrument once per article. The instrument
    name is identical in every build language: BOE publishes "Ley 37/1992" under
    that name, so translating it would cite a norm that does not exist.
    """
    provisions = {record.legal_id: record for record in load_legal_provisions(_REPO_ROOT)}
    for language in OutputLanguage:
        assert _legal_provision_display(legal_id, provisions[legal_id], language) == (instrument, provision)


# ── Structure ────────────────────────────────────────────────────────────────


def test_machine_identifiers_are_confined_to_the_disclosure() -> None:
    """Registry vocabulary stays on the page, below the fold of a ``<details>``."""
    record = _record(binding=None)
    rst = _render((record,), OutputLanguage.EN)
    disclosure = rst.partition('<details class="casilla-card__internals">')
    assert disclosure[1], "the registry-identifier disclosure is missing"
    above, below = disclosure[0], disclosure[2]

    for identifier in (str(record.semantic_role), str(record.formula_id), record.source_refs[0]):
        assert identifier in below
        assert identifier not in above


def test_sections_carry_jump_targets_matching_the_page_nav() -> None:
    """Every section in the jump list resolves to an anchor emitted on the page."""
    records = (
        _record(),
        _record(casilla_id="09", number="09", section=("resultado_final",)),
    )
    rst = _render(records, OutputLanguage.EN)
    linked = set(re.findall(r'href="#(section-[a-z0-9-]+)"', rst))
    emitted = set(re.findall(r'casilla-section-anchor" id="(section-[a-z0-9-]+)"', rst))
    assert linked
    assert linked == emitted


def test_colliding_section_anchors_are_a_build_failure() -> None:
    """Two section paths folding to one jump target are refused, never merged."""
    from ..casilla_reference import CasillaReferenceError, _section_anchor

    underscored = ("irpf", "resultado_final")
    hyphenated = ("irpf", "resultado-final")
    assert _section_anchor(underscored) == _section_anchor(hyphenated)

    records = (
        _record(section=underscored),
        _record(casilla_id="09", number="09", section=hyphenated),
    )
    with pytest.raises(CasillaReferenceError):
        _render(records, OutputLanguage.EN)
