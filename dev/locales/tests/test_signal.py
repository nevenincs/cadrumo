"""Contracts for the actionable locale translation backlog."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from .._signal import (
    _documentation_source_inventory,
    _domain_summaries,
    _dynamic_key_families,
    _embedded_document_language_prose,
    _filtered_translation_text,
    _headline,
    _human_translation_text,
    _parallel_localization_inventory,
    _platform_identity_terms,
    _source_inventory,
    _spellcheck_catalogues,
    _translation_invariant_echo_reason,
    _translation_matrix,
    _visible_document_prose,
)
from ..manager import LocaleManager

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_translation_matrix_counts_keys_and_locale_cells_without_overlap() -> None:
    required = {"cli.save", "modelo.title"}
    leaves = {
        "en": {"cli.save": "Save", "modelo.title": "modelo.title"},
        "es": {"cli.save": "Guardar"},
    }

    matrix = _translation_matrix(required, leaves)

    assert matrix["cells"] == {
        "required": 4,
        "defined": 3,
        "ready": 2,
        "missing": 1,
        "needs_value": 1,
        "needs_repair": 0,
        "needs_review": 0,
    }
    backlog = matrix["backlog"]
    assert [(item["key"], item["locale"], item["state"]) for item in backlog] == [
        ("modelo.title", "en", "needs_value"),
        ("modelo.title", "es", "missing"),
    ]


def test_translation_matrix_flags_long_target_text_effectively_identical_to_spanish() -> None:
    spanish = "Importe total de la deducción tributaria aplicable en esta autoliquidación anual."
    matrix = _translation_matrix(
        {"modelo.help"},
        {"es": {"modelo.help": spanish}, "en": {"modelo.help": spanish}},
    )

    assert matrix["cells"]["needs_review"] == 1
    assert matrix["backlog"] == [
        {
            "domain": "modelo",
            "key": "modelo.help",
            "locale": "en",
            "state": "needs_review",
            "reason": "translation_too_similar",
            "next_action": "review_translation",
        }
    ]


def test_translation_matrix_flags_unaccented_tax_prose() -> None:
    matrix = _translation_matrix(
        {"modelo.help"},
        {
            "es": {"modelo.help": "Descripción oficial de la casilla tributaria."},
            "ca": {"modelo.help": "Consulteu la descripcio oficial de la casella tributària."},
        },
        {("ca", "modelo.help"): ("descripcio",)},
    )

    assert matrix["cells"]["needs_review"] == 1
    assert matrix["backlog"][0]["reason"] == "translation_spelling_unknown"
    assert matrix["backlog"][0]["unknown_words"] == ["descripcio"]


def test_translation_matrix_refuses_dropped_expansion_and_casilla_tokens() -> None:
    matrix = _translation_matrix(
        {"modelo.help"},
        {
            "es": {"modelo.help": "Importe %{amount} procedente de [00230] cuando [a=c1+c2]."},
            "ca": {"modelo.help": "Import procedent de la casella."},
            "en": {"modelo.help": "Amount %{amount} from [00230] when [a=c1+c2]."},
        },
    )

    assert matrix["cells"]["needs_repair"] == 1
    assert matrix["backlog"] == [
        {
            "domain": "modelo",
            "key": "modelo.help",
            "locale": "ca",
            "state": "needs_repair",
            "reason": "translation_placeholder_mismatch",
            "next_action": "repair_translation",
        }
    ]


def test_spelling_prose_excludes_long_casilla_and_formula_references() -> None:
    assert _human_translation_text("Import de [00230] quan [base_total=casella1+casella2].") == "import de quan ."


def test_spelling_filter_excludes_transport_syntax_but_keeps_visible_labels() -> None:
    tick = chr(96)
    value = (
        "Open https://example.test/docs/guide.md or docs/locales/hu/index.po; "
        "[Guide](https://example.test/guide) :ref:"
        + tick
        + "Visible guide <how-to/quickstart>"
        + tick
        + " {term}"
        + tick
        + "modelo 100"
        + tick
        + " "
        + tick
        + "internal_token"
        + tick
        + " %{amount} base_total=c1+c2 2025."
    )

    filtered, excluded = _filtered_translation_text(value)

    assert filtered == "open or guide visible guide ."
    assert excluded == 10


def test_spelling_filter_keeps_plain_prose_and_removes_file_extensions() -> None:
    filtered, excluded = _filtered_translation_text("Olvassa el a guide.md fájlt, majd folytassa.")

    assert filtered == "olvassa el a fájlt majd folytassa."
    assert excluded == 1


def test_spellcheck_reports_structural_exclusions_by_surface_and_locale(tmp_path, monkeypatch) -> None:
    from .. import _signal as signal_module

    tick = chr(96)

    class _Dictionary:
        def lookup(self, _word: str) -> bool:
            return True

    monkeypatch.setattr(
        signal_module,
        "load_dictionaries",
        lambda _repository: {locale: _Dictionary() for locale in signal_module._LOCALES},
    )
    spelling, inventory, findings = _spellcheck_catalogues(
        {"runtime.value"},
        {"ca": {"runtime.value": "2025 + 2026"}},
        tmp_path,
        additional_values={
            "ca": {
                "parallel:src/cadrumo/_data/labels.toml:label_ca": "Lásd docs/guide.po https://example.test",
                "parallel:docs/locales/ca/LC_MESSAGES/guide.po:message": "[Guide](https://example.test)",
            },
            "en": {
                "parallel:docs/cli/guide.rst:line[1]": "{term}" + tick + "modelo 100" + tick + " --dry-run",
            },
        },
    )

    assert spelling == {}
    assert findings == []
    assert inventory["excluded_structural_tokens"] == 6
    assert inventory["excluded_structural_tokens_by_surface_locale"] == {
        "docs_po/ca": 1,
        "docs_po/en": 0,
        "docs_po/es": 0,
        "docs_po/hu": 0,
        "generated_docs/ca": 0,
        "generated_docs/en": 2,
        "generated_docs/es": 0,
        "generated_docs/hu": 0,
        "runtime/ca": 1,
        "runtime/en": 0,
        "runtime/es": 0,
        "runtime/hu": 0,
        "toml/ca": 2,
        "toml/en": 0,
        "toml/es": 0,
        "toml/hu": 0,
    }


def test_spellcheck_reconciles_enrolled_cells_with_prose_and_structural_cells(tmp_path, monkeypatch) -> None:
    from .. import _signal as signal_module

    class _Dictionary:
        def lookup(self, _word: str) -> bool:
            return True

    monkeypatch.setattr(
        signal_module,
        "load_dictionaries",
        lambda _repository: {locale: _Dictionary() for locale in signal_module._LOCALES},
    )
    _spelling, inventory, _findings = _spellcheck_catalogues(
        {"runtime.prose", "runtime.syntax"},
        {
            "ca": {
                "runtime.prose": "Visible prose",
                "runtime.syntax": "2025 --dry-run",
            },
            "en": {"runtime.prose": "Visible prose"},
        },
        tmp_path,
    )

    assert inventory["spelling_cells_by_locale"] == {"ca": 2, "en": 1}
    assert inventory["spellchecked_cells"] == sum(inventory["spelling_cells_by_locale"].values()) == 3
    assert inventory["spelling_prose_cells_by_locale"] == {"ca": 1, "en": 1}
    assert inventory["spelling_structural_only_cells_by_locale"] == {"ca": 1}
    assert (
        inventory["spelling_prose_cells"] + inventory["spelling_structural_only_cells"]
        == inventory["spellchecked_cells"]
    )


def test_spellcheck_returns_actionable_finding_for_each_unknown_parallel_cell(tmp_path, monkeypatch) -> None:
    from .. import _signal as signal_module

    class _Dictionary:
        def lookup(self, word: str) -> bool:
            return word.casefold() == "known"

    monkeypatch.setattr(
        signal_module,
        "load_dictionaries",
        lambda _repository: {locale: _Dictionary() for locale in signal_module._LOCALES},
    )
    spelling, inventory, findings = _spellcheck_catalogues(
        set(),
        {},
        tmp_path,
        additional_values={"es": {"parallel:docs/locales/es/LC_MESSAGES/guide.po:message": "known typo"}},
    )

    assert spelling == {("es", "parallel:docs/locales/es/LC_MESSAGES/guide.po:message"): ("typo",)}
    assert inventory["spelling_unknown_cells"] == 1
    assert findings == [
        {
            "classification": "blocking",
            "kind": "translation_spelling_unknown",
            "domain": "docs",
            "locale": "es",
            "location": "docs/locales/es/LC_MESSAGES/guide.po:message",
            "unknown_words": ["typo"],
            "next_action": "correct the localized prose in its authoritative data source",
        }
    ]


def test_spellcheck_routes_lang_annotated_embedded_prose_to_declared_dictionary(tmp_path, monkeypatch) -> None:
    from .. import _signal as signal_module

    class _Dictionary:
        def __init__(self, known: set[str]) -> None:
            self.known = known

        def lookup(self, word: str) -> bool:
            return word.casefold() in self.known

    monkeypatch.setattr(
        signal_module,
        "load_dictionaries",
        lambda _repository: {
            "ca": _Dictionary(set()),
            "en": _Dictionary({"published"}),
            "es": _Dictionary({"known"}),
            "hu": _Dictionary(set()),
        },
    )
    spelling, _inventory, _findings = _spellcheck_catalogues(
        set(),
        {},
        tmp_path,
        additional_values={
            "en": {
                "parallel:docs/_generated/legal/guide.rst:line[5]": (
                    'Published <blockquote lang="es">known typo</blockquote>'
                )
            }
        },
    )

    assert spelling == {("en", "parallel:docs/_generated/legal/guide.rst:line[5]"): ("typo",)}


def test_domain_summary_enumerates_every_domain_and_unassigned_inventory() -> None:
    required = {"cli.save", "modelo.title", "tui.home.title"}
    leaves = {
        "en": {"cli.save": "Save"},
        "es": {"cli.save": "Guardar", "modelo.title": "Modelo"},
    }
    matrix = _translation_matrix(required, leaves)

    domains = _domain_summaries(
        required,
        matrix,
        leaves,
        [{"classification": "blocking", "kind": "naked_presentation_text"}],
    )

    assert {row["domain"] for row in domains} == {"cli", "modelo", "tui", "unassigned"}
    unassigned = next(row for row in domains if row["domain"] == "unassigned")
    assert unassigned["state"] == "inventory_open"
    assert unassigned["inventory_violations"] == 1
    modelo = next(row for row in domains if row["domain"] == "modelo")
    assert modelo["keys_to_translate"] == 1
    assert modelo["to_translate_by_locale"] == {"en": 1, "es": 0}


def test_headline_distinguishes_exact_and_known_backlogs() -> None:
    locales = [
        {"locale": "ca", "to_translate": 3},
        {"locale": "en", "to_translate": 1},
    ]
    exact = {
        "exact": True,
        "cells_to_translate": 4,
        "unique_keys_to_translate": 3,
        "known_cells_to_translate": 4,
        "known_unique_keys_to_translate": 3,
    }
    open_inventory = {**exact, "exact": False, "cells_to_translate": None, "unique_keys_to_translate": None}

    assert _headline(exact, locales, ("cli", "ca", 3), 0).startswith("Translate 4 locale cells for 3 unique keys")
    assert _headline(open_inventory, locales, ("cli", "ca", 3), 2).startswith(
        "Translation total is not yet knowable: canonicalize 2 inventory violations"
    )


def test_source_inventory_reports_literal_key_set_reduction(tmp_path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "surface.py").write_text(
        "from cadrumo.core.i18n.render import tr\n"
        "def render():\n    tr('cli.save')\n    tr('cli.save')\n    tr('cli.cancel')\n",
        encoding="utf-8",
    )
    locales = tmp_path / "locales"
    locales.mkdir()
    manager = LocaleManager(source, locales)

    inventory, findings = _source_inventory(manager)

    assert findings == []
    assert inventory["literal_tr_calls"] == 3
    assert inventory["literal_tr_keys_unique"] == 2
    assert inventory["literal_tr_reuse_occurrences"] == 1
    assert inventory["literal_tr_keys_reused"] == 1


def test_source_inventory_reports_dot_key_uniqueness_and_semantic_duplicate_findings(tmp_path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "surface.py").write_text(
        "from cadrumo.core.i18n.render import tr\n"
        "def render(name):\n"
        "    tr('cli.save')\n"
        "    tr('cli.save', name=name)\n"
        "    tr('cli.cancel')\n"
        "    tr(f'cli.dynamic.{name}')\n",
        encoding="utf-8",
    )
    locales = tmp_path / "locales"
    locales.mkdir()

    inventory, findings = _source_inventory(
        LocaleManager(source, locales),
        dynamic_resolved_keys=("cli.dynamic.one", "cli.save"),
    )

    assert inventory["raw_localization_key_occurrences"] == 5
    assert inventory["dynamic_resolved_key_occurrences"] == 2
    assert inventory["unique_dot_keys"] == 3
    assert inventory["duplicate_key_occurrence_delta"] == 2
    conflicts = [finding for finding in findings if finding["kind"] == "conflicting_duplicate_translation_key"]
    assert len(conflicts) == inventory["conflicting_duplicate_declarations"] == 1
    assert conflicts[0]["key"] == "cli.save"
    assert [declaration["placeholders"] for declaration in conflicts[0]["declarations"]] == [[], ["name"], []]


def test_source_inventory_ignores_non_translation_tr_alias(tmp_path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "surface.py").write_text(
        "from cadrumo.core.i18n.translatable import Translatable as tr\nROLE = tr('cuota diferencial')\n",
        encoding="utf-8",
    )
    locales = tmp_path / "locales"
    locales.mkdir()

    inventory, findings = _source_inventory(LocaleManager(source, locales))

    assert findings == []
    assert inventory["tr_calls"] == 0


def test_dynamic_key_families_use_registered_concrete_values() -> None:
    finite, unresolved = _dynamic_key_families(
        ("wizard.setup.*", "wizard.setup.flags.*", "profile.keys.*"),
        registered_keys=(
            "wizard.setup.flags.export",
            "wizard.setup.residence",
            "unrelated.key",
        ),
    )

    assert finite == {
        "wizard.setup.*": (
            "wizard.setup.flags.export",
            "wizard.setup.residence",
        ),
        "wizard.setup.flags.*": ("wizard.setup.flags.export",),
    }
    assert unresolved == ("profile.keys.*",)


def test_finite_dynamic_values_and_concrete_catalogue_keys_remain_required(tmp_path, monkeypatch) -> None:
    from .. import _signal as signal_module

    source = tmp_path / "source"
    source.mkdir()
    locales = tmp_path / "locales"
    locales.mkdir()
    (locales / "en.yml").write_text(
        "wizard:\n  setup:\n    status:\n      ready: Ready\n      stale: Legacy\n",
        encoding="utf-8",
    )
    manager = LocaleManager(source, locales)
    monkeypatch.setattr(manager, "get_codebase_keys", lambda: set())
    monkeypatch.setattr(manager, "get_codebase_namespaces", lambda: {"profile.keys.*", "wizard.setup.*"})
    monkeypatch.setattr(
        signal_module,
        "_dynamic_key_families",
        lambda markers: ({"wizard.setup.*": ("wizard.setup.status.ready",)}, ("profile.keys.*",)),
    )

    payload = signal_module.locale_signal(manager, repository=tmp_path)

    assert "wizard.setup.status.ready" in payload["details"]["required_keys"]
    assert "wizard.setup.status.stale" in payload["details"]["required_keys"]
    assert payload["summary"]["catalogue_only"] == {"keys": 0, "cells": 0}
    assert payload["summary"]["inventory"]["finite_key_families"] == 1
    assert payload["summary"]["inventory"]["unbounded_key_families"] == 1
    assert [
        finding["key_prefix"] for finding in payload["details"]["findings"] if finding["kind"] == "unbounded_key_family"
    ] == ["profile.keys.*"]


def test_parallel_toml_inventory_reports_missing_cells_not_authored_values(tmp_path) -> None:
    concepts = tmp_path / "src" / "cadrumo" / "_data" / "terminology" / "concepts"
    concepts.mkdir(parents=True)
    (concepts / "term.toml").write_text(
        "[language.es]\nshort_description='Concepto fiscal'\n"
        "[language.en]\nshort_description='Tax concept'\n"
        "[language.ca]\nshort_description='Concepte fiscal'\n"
        "[language.hu]\nshort_description='Adózási fogalom'\n",
        encoding="utf-8",
    )
    registry = tmp_path / "src" / "cadrumo" / "_data" / "registry"
    registry.mkdir(parents=True)
    (registry / "scope.toml").write_text("name_es='Renta'\nname_en='Income tax'\n", encoding="utf-8")

    inventory, findings = _parallel_localization_inventory(tmp_path)

    assert inventory["parallel_localization_declarations"] == 2
    assert {finding["field"] for finding in findings if "field" in finding} == {"name_ca", "name_hu"}


def test_parallel_inventory_enrols_toml_and_every_po_plural_form_for_spelling(tmp_path) -> None:
    data = tmp_path / "src" / "cadrumo" / "_data"
    data.mkdir(parents=True)
    (data / "labels.toml").write_text("label_ca='Declaració tributària'\n", encoding="utf-8")
    docs = tmp_path / "docs" / "locales" / "ca" / "LC_MESSAGES"
    docs.mkdir(parents=True)
    (docs / "guide.po").write_text(
        'msgid ""\nmsgstr ""\n"Language: ca\\n"\n"Plural-Forms: nplurals=2; plural=(n != 1);\\n"\n\n'
        'msgid "One return"\nmsgid_plural "Many returns"\n'
        'msgstr[0] "Una declaració"\nmsgstr[1] "Moltes declaracions"\n',
        encoding="utf-8",
    )
    values: dict[str, dict[str, str]] = {}

    inventory, _findings = _parallel_localization_inventory(tmp_path, spelling_values=values)

    assert values["ca"]["parallel:src/cadrumo/_data/labels.toml:label_ca"] == "Declaració tributària"
    plural_values = {key: value for key, value in values["ca"].items() if "docs/locales/ca/LC_MESSAGES/guide.po" in key}
    assert plural_values == {
        "parallel:docs/locales/ca/LC_MESSAGES/guide.po:One return\x04Many returns:plural[0]": "Una declaració",
        "parallel:docs/locales/ca/LC_MESSAGES/guide.po:One return\x04Many returns:plural[1]": "Moltes declaracions",
    }
    assert inventory["docs_catalogues_compiled"] == 1
    assert inventory["docs_catalogues_compiled_ca"] == 1


def test_generated_user_doc_adapter_reads_visible_prose_not_option_or_literal_syntax(tmp_path) -> None:
    page = tmp_path / "command.rst"
    page.write_text(
        "Filing command\n==============\n\nReview the prepared return.\n\n"
        "--source\n   Select the source record.\n\n``raw_internal_token``\n",
        encoding="utf-8",
    )

    prose = _visible_document_prose(page)

    rendered = {text for _line, text in prose}
    assert "Filing command" in rendered
    assert "Review the prepared return." in rendered
    assert "Select the source record." in rendered
    assert all("--source" not in text for text in rendered)
    assert all("raw_internal_token" not in text for text in rendered)


def test_generated_user_doc_adapter_enrols_explicit_embedded_language(tmp_path) -> None:
    page = tmp_path / "legal.rst"
    page.write_text(
        "Legal reference\n===============\n\n"
        ".. raw:: html\n\n"
        '   <blockquote lang="es"><p>Administracion Tributaria</p></blockquote>\n',
        encoding="utf-8",
    )

    assert _embedded_document_language_prose(page) == ((6, "es", "administracion tributaria"),)


def _write_docs_source_cache(docs, page: str, source_text: str, pot_text: str) -> None:
    source = docs / page
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(source_text, encoding="utf-8")
    templates = docs / "locales" / "pot"
    template = templates / Path(page).with_suffix(".pot")
    template.parent.mkdir(parents=True, exist_ok=True)
    template.write_text(pot_text, encoding="utf-8")
    (templates / ".source-manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "sources": {page: hashlib.sha256(source.read_bytes()).hexdigest()},
            }
        ),
        encoding="utf-8",
    )


def test_documentation_inventory_extracts_live_source_and_enrols_english_for_spelling(tmp_path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    _write_docs_source_cache(
        docs,
        "guide.md",
        "# Filing guide\n\nReview the current return.\n",
        'msgid ""\nmsgstr ""\n\nmsgid "Filing guide"\nmsgstr ""\n\nmsgid "Review the current return."\nmsgstr ""\n',
    )
    catalogue_messages = {
        ("guide.po", "Filing guide"): {"ca": True, "es": True, "hu": True},
        ("guide.po", "Review the current return."): {"ca": True, "es": True, "hu": True},
    }
    values: dict[str, dict[str, str]] = {}

    inventory, findings = _documentation_source_inventory(
        tmp_path,
        catalogue_messages,
        spelling_values=values,
    )

    assert findings == []
    assert {
        key: inventory[key]
        for key in (
            "docs_source_pages",
            "docs_source_messages",
            "docs_catalogue_files_expected",
            "docs_catalogue_files_read",
            "docs_source_drift_pages",
            "docs_source_messages_missing",
            "docs_catalogue_messages_stale",
            "docs_extraction_failures",
            "docs_orphan_catalogue_files",
            "docs_orphan_source_templates",
            "docs_generated_english_only_pages",
        )
    } == {
        "docs_source_pages": 1,
        "docs_source_messages": 2,
        "docs_catalogue_files_expected": 3,
        "docs_catalogue_files_read": 3,
        "docs_source_drift_pages": 0,
        "docs_source_messages_missing": 0,
        "docs_catalogue_messages_stale": 0,
        "docs_extraction_failures": 0,
        "docs_orphan_catalogue_files": 0,
        "docs_orphan_source_templates": 0,
        "docs_generated_english_only_pages": 0,
    }
    assert values["en"] == {
        "parallel:docs/guide.md:Filing guide": "Filing guide",
        "parallel:docs/guide.md:Review the current return.": "Review the current return.",
    }


def test_documentation_inventory_enumerates_source_to_catalogue_drift(tmp_path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    _write_docs_source_cache(
        docs,
        "guide.md",
        "# Current source\n",
        'msgid ""\nmsgstr ""\n\nmsgid "Current source"\nmsgstr ""\n',
    )
    inventory, findings = _documentation_source_inventory(
        tmp_path,
        {("guide.po", "Old source"): {"ca": True, "es": True, "hu": True}},
    )

    assert inventory["docs_source_drift_pages"] == 1
    assert inventory["docs_source_messages_missing"] == 3
    assert inventory["docs_catalogue_messages_stale"] == 3
    assert len(findings) == 3
    assert {finding["kind"] for finding in findings} == {"docs_source_catalogue_drift"}
    assert all(finding["missing_message_ids"] == ["Current source"] for finding in findings)
    assert all(finding["stale_message_ids"] == ["Old source"] for finding in findings)


def test_documentation_inventory_separates_source_echo_and_near_echo(tmp_path) -> None:
    docs = tmp_path / "docs"
    _write_docs_source_cache(
        docs,
        "guide.md",
        "# Filing guide\n\nReview the current return.\n\nOne return.\n",
        'msgid ""\nmsgstr ""\n\n'
        'msgid "Filing guide"\nmsgstr ""\n\n'
        'msgid "Review the current return."\nmsgstr ""\n\n'
        'msgid "One return"\nmsgid_plural "Many returns"\nmsgstr[0] ""\nmsgstr[1] ""\n',
    )
    catalogue_messages = {
        ("guide.po", "Filing guide"): {"ca": True, "es": True, "hu": True},
        ("guide.po", "Review the current return."): {"ca": True, "es": True, "hu": True},
        ("guide.po", "One return\x04Many returns"): {"ca": True, "es": True, "hu": True},
    }
    catalogue_translations = {
        ("guide.po", "Review the current return."): {
            "ca": ("Review the current returns.",),
            "es": (" Review   THE current return! ",),
        },
        ("guide.po", "One return\x04Many returns"): {
            "ca": ("One return", "Many returns"),
        },
    }

    inventory, findings = _documentation_source_inventory(
        tmp_path,
        catalogue_messages,
        catalogue_files={(locale, "guide.po") for locale in ("ca", "es", "hu")},
        catalogue_translations=catalogue_translations,
    )

    assert inventory["docs_translation_comparisons"] == 4
    assert inventory["docs_translation_source_echo"] == 3
    assert inventory["docs_translation_source_echo_ratio"] == 0.75
    assert inventory["docs_translation_near_echo"] == 1
    assert inventory["docs_translation_near_echo_ratio"] == 0.25
    assert inventory["docs_translation_source_echo_ca"] == 2
    assert inventory["docs_translation_source_echo_es"] == 1
    assert inventory["docs_translation_near_echo_ca"] == 1
    assert len(inventory["docs_translation_source_echo_samples"]) == 3
    assert len(inventory["docs_translation_near_echo_samples"]) == 1
    exact = [finding for finding in findings if finding["kind"] == "docs_translation_source_echo"]
    near = [finding for finding in findings if finding["kind"] == "docs_translation_near_echo"]
    assert len(exact) == 3
    assert len(near) == 1
    assert all(finding["classification"] == "blocking" for finding in exact)
    assert near[0]["classification"] == "advisory"
    assert near[0]["ratio"] >= 0.9


def test_documentation_inventory_classifies_only_provable_invariant_echoes(tmp_path, monkeypatch) -> None:
    from .. import _signal as signal_module

    class _Dictionary:
        def lookup(self, word: str) -> bool:
            return word.casefold() == "manual"

    monkeypatch.setattr(
        signal_module,
        "load_dictionaries",
        lambda _repository: {locale: _Dictionary() for locale in signal_module._LOCALES},
    )
    docs = tmp_path / "docs"
    messages = (
        "Download",
        "Review the current return",
        "`--help`",
        "Modelo 303",
        "PDF",
        "Cadrumo",
        "Manual",
    )
    pot = 'msgid ""\nmsgstr ""\n\n' + "\n".join(f'msgid "{message}"\nmsgstr ""\n' for message in messages)
    _write_docs_source_cache(docs, "guide.md", "# Echo classification\n", pot)
    catalogue_messages = {("guide.po", message): {"ca": True, "es": True, "hu": True} for message in messages}
    catalogue_translations = {
        ("guide.po", "Download"): {"ca": ("Download",)},
        ("guide.po", "Review the current return"): {"es": ("Review the current return",)},
        ("guide.po", "`--help`"): {"ca": ("`--help`",)},
        ("guide.po", "Modelo 303"): {"es": ("Modelo 303",)},
        ("guide.po", "PDF"): {"es": ("PDF",)},
        ("guide.po", "Cadrumo"): {"ca": ("Cadrumo",)},
        ("guide.po", "Manual"): {"ca": ("Manual",)},
    }

    inventory, findings = _documentation_source_inventory(
        tmp_path,
        catalogue_messages,
        catalogue_files={(locale, "guide.po") for locale in ("ca", "es", "hu")},
        catalogue_translations=catalogue_translations,
    )

    assert inventory["docs_translation_comparisons"] == 7
    assert inventory["docs_translation_source_echo"] == 2
    assert inventory["docs_translation_invariant_echo"] == 5
    assert inventory["docs_translation_invariant_echo_ca"] == 3
    assert inventory["docs_translation_invariant_echo_es"] == 2
    assert inventory["docs_translation_invariant_echo_hu"] == 0
    for reason in (
        "inline_code",
        "modelo_form",
        "platform_format",
        "canonical_product_identity",
        "target_dictionary_shared_term",
    ):
        assert inventory[f"docs_translation_invariant_echo_reason_{reason}"] == 1
    blocking = [finding for finding in findings if finding["kind"] == "docs_translation_source_echo"]
    invariant = [finding for finding in findings if finding["kind"] == "docs_translation_invariant_echo"]
    assert {finding["source"] for finding in blocking} == {"Download", "Review the current return"}
    assert all(finding["classification"] == "blocking" for finding in blocking)
    assert {finding["reason"] for finding in invariant} == {
        "inline_code",
        "modelo_form",
        "platform_format",
        "canonical_product_identity",
        "target_dictionary_shared_term",
    }
    assert all(finding["classification"] == "advisory" for finding in invariant)


def test_translation_echo_invariants_use_identity_syntax_and_language_evidence() -> None:
    class _Dictionary:
        def __init__(self, words: set[str] | None = None, *, accept_all: bool = False) -> None:
            self.words = words or set()
            self.accept_all = accept_all

        def lookup(self, word: str) -> bool:
            return self.accept_all or word.casefold() in self.words

    target = _Dictionary(accept_all=True)
    english = _Dictionary({"download", "the", "current", "return"})

    assert (
        _translation_invariant_echo_reason(
            "Cadrumo vX.Y.Z",
            "es",
            dictionary=target,
            source_dictionary=english,
        )
        == "canonical_product_identity"
    )
    assert (
        _translation_invariant_echo_reason(
            "vX.Y.Z",
            "es",
            dictionary=target,
            source_dictionary=english,
        )
        is None
    )
    assert (
        _translation_invariant_echo_reason(
            "Windows (x86-64)",
            "es",
            dictionary=target,
            source_dictionary=english,
        )
        == "platform_format"
    )
    assert (
        _translation_invariant_echo_reason(
            "Régimen de atribución de rentas (socios)",
            "es",
            dictionary=target,
            source_dictionary=english,
        )
        == "target_dictionary_shared_term"
    )
    assert (
        _translation_invariant_echo_reason(
            "Download the current return",
            "es",
            dictionary=target,
            source_dictionary=english,
        )
        is None
    )


def test_platform_identity_terms_follow_the_download_descriptor(tmp_path) -> None:
    descriptor = tmp_path / "docs" / "_data" / "download_channels.toml"
    descriptor.parent.mkdir(parents=True)
    descriptor.write_text(
        '[[channel]]\nplatform = "macOS (Apple silicon), Linux (x86-64 and arm64)"\n\n'
        '[[channel]]\nplatform = "Windows (x86-64)"\n',
        encoding="utf-8",
    )

    terms = _platform_identity_terms(tmp_path)

    assert {"macos", "linux", "windows"}.issubset(terms)
    assert "any" not in terms
    assert "any platform with python 3 13+" not in terms


def test_documentation_inventory_fails_closed_when_source_manifest_is_absent(tmp_path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text("# Filing guide\n", encoding="utf-8")

    inventory, findings = _documentation_source_inventory(tmp_path, {})

    assert inventory["docs_source_pages"] == 1
    assert inventory["docs_extraction_failures"] == 1
    extraction = [finding for finding in findings if finding["kind"] == "docs_source_extraction_failure"]
    assert len(extraction) == 1
    assert extraction[0]["classification"] == "blocking"
    assert extraction[0]["domain"] == "docs"
    assert extraction[0]["error_type"] == "FileNotFoundError"
    assert sum(finding["kind"] == "docs_catalogue_missing" for finding in findings) == 3


def test_spellcheck_fails_closed_when_pinned_dictionaries_are_absent(tmp_path) -> None:
    spelling, inventory, findings = _spellcheck_catalogues(
        {"cli.title"},
        {"ca": {"cli.title": "Declaració tributària"}},
        tmp_path,
    )

    assert spelling == {}
    assert inventory["spelling_tool_failures"] == 1
    assert findings[0]["kind"] == "spelling_tool_unavailable"
