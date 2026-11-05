"""Contracts for the actionable locale translation backlog."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest

from ..manager import LocaleManager
from ..signal_discovery import dynamic_key_families
from ..signal_document_prose import visible_document_prose
from ..signal_domain_summary import domain_summaries, headline
from ..signal_parallel_inventory import parallel_localization_inventory
from ..signal_policy import LOCALES
from ..signal_source_inventory import collect_source_inventory
from ..signal_spelling import spellcheck_catalogues
from ..signal_tokens import filtered_translation_text, human_translation_text
from ..signal_translation_matrix import translation_matrix
from .signal_support import (
    signal_list,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _mapping(value: object) -> Mapping[str, object]:
    """Narrow one report payload mapping for assertions over dynamic fields."""
    if not isinstance(value, Mapping):
        raise AssertionError("expected a mapping payload")
    result: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise AssertionError("expected string mapping keys")
        result[key] = item
    return result


def test_translation_matrix_counts_keys_and_locale_cells_without_overlap() -> None:
    required = {"cli.save", "modelo.title"}
    leaves = {
        "en": {"cli.save": "Save", "modelo.title": "modelo.title"},
        "es": {"cli.save": "Guardar"},
    }

    matrix = translation_matrix(required, leaves)

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
    matrix = translation_matrix(
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
    matrix = translation_matrix(
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
    matrix = translation_matrix(
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
    assert human_translation_text("Import de [00230] quan [base_total=casella1+casella2].") == "import de quan ."


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

    filtered, excluded = filtered_translation_text(value)

    assert filtered == "Open or Guide Visible guide ."
    assert excluded == 10


def test_spelling_filter_keeps_plain_prose_and_removes_file_extensions() -> None:
    filtered, excluded = filtered_translation_text("Olvassa el a guide.md fájlt, majd folytassa.")

    assert filtered == "Olvassa el a fájlt majd folytassa."
    assert excluded == 1


def test_spellcheck_reports_structural_exclusions_by_surface_and_locale(tmp_path, monkeypatch) -> None:
    from .. import signal_spelling as spelling_module

    tick = chr(96)

    class _Dictionary:
        def lookup(self, _word: str) -> bool:
            return True

    monkeypatch.setattr(
        spelling_module,
        "load_dictionaries",
        lambda _repository: {locale: _Dictionary() for locale in LOCALES},
    )
    spelling, inventory, findings = spellcheck_catalogues(
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
    from .. import signal_spelling as spelling_module

    class _Dictionary:
        def lookup(self, _word: str) -> bool:
            return True

    monkeypatch.setattr(
        spelling_module,
        "load_dictionaries",
        lambda _repository: {locale: _Dictionary() for locale in LOCALES},
    )
    _spelling, inventory, _findings = spellcheck_catalogues(
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
    from .. import signal_spelling as spelling_module

    class _Dictionary:
        def lookup(self, word: str) -> bool:
            return word.casefold() == "known"

    monkeypatch.setattr(
        spelling_module,
        "load_dictionaries",
        lambda _repository: {locale: _Dictionary() for locale in LOCALES},
    )
    spelling, inventory, findings = spellcheck_catalogues(
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
    from .. import signal_spelling as spelling_module

    class _Dictionary:
        def __init__(self, known: set[str]) -> None:
            self.known = known

        def lookup(self, word: str) -> bool:
            return word.casefold() in self.known

    monkeypatch.setattr(
        spelling_module,
        "load_dictionaries",
        lambda _repository: {
            "ca": _Dictionary(set()),
            "en": _Dictionary({"published"}),
            "es": _Dictionary({"known"}),
            "hu": _Dictionary(set()),
        },
    )
    spelling, _inventory, _findings = spellcheck_catalogues(
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
    matrix = translation_matrix(required, leaves)

    domains = domain_summaries(
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

    assert headline(exact, locales, ("cli", "ca", 3), 0).startswith("Translate 4 locale cells for 3 unique keys")
    assert headline(open_inventory, locales, ("cli", "ca", 3), 2).startswith(
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

    inventory, findings = collect_source_inventory(manager)

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

    inventory, findings = collect_source_inventory(
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
    declarations = [_mapping(declaration) for declaration in signal_list(conflicts[0]["declarations"])]
    assert [declaration["placeholders"] for declaration in declarations] == [[], ["name"], []]


def test_source_inventory_ignores_non_translation_tr_alias(tmp_path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "surface.py").write_text(
        "from cadrumo.core.i18n.translatable import Translatable as tr\nROLE = tr('cuota diferencial')\n",
        encoding="utf-8",
    )
    locales = tmp_path / "locales"
    locales.mkdir()

    inventory, findings = collect_source_inventory(LocaleManager(source, locales))

    assert findings == []
    assert inventory["tr_calls"] == 0


def test_dynamic_key_families_use_registered_concrete_values() -> None:
    finite, unresolved = dynamic_key_families(
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
    from .. import signal as signal_module
    from .. import signal_discovery as discovery_module

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
        discovery_module,
        "dynamic_key_families",
        lambda markers: ({"wizard.setup.*": ("wizard.setup.status.ready",)}, ("profile.keys.*",)),
    )

    payload = signal_module.locale_signal(manager, repository=tmp_path)

    assert "wizard.setup.status.ready" in payload["details"]["required_keys"]
    assert "wizard.setup.status.stale" in payload["details"]["required_keys"]
    assert payload["summary"]["catalogue_only"] == {"keys": 0, "cells": 0}
    inventory_summary = _mapping(payload["summary"]["inventory"])
    assert inventory_summary["finite_key_families"] == 1
    assert inventory_summary["unbounded_key_families"] == 1
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

    inventory, findings = parallel_localization_inventory(tmp_path)

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

    inventory, _findings = parallel_localization_inventory(tmp_path, spelling_values=values)

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

    prose = visible_document_prose(page)

    rendered = {text for _line, text in prose}
    assert "Filing command" in rendered
    assert "Review the prepared return." in rendered
    assert "Select the source record." in rendered
    assert all("--source" not in text for text in rendered)
    assert all("raw_internal_token" not in text for text in rendered)


def test_generated_cli_docs_exempt_only_exact_executable_command_headings(tmp_path) -> None:
    page = tmp_path / "docs" / "cli" / "commands.rst"
    page.parent.mkdir(parents=True)
    command = "aeat app diagnostics errors"
    unknown_path = "aeat app diagnostics definitely-unknown"
    command_with_option = "aeat app diagnostics errors --format"
    page.write_text(
        f"{command}\n{'=' * len(command)}\n\n"
        "Check this adjacent misspeling.\n\n"
        f"{unknown_path}\n{'-' * len(unknown_path)}\n\n"
        f"{command_with_option}\n{'-' * len(command_with_option)}\n\n"
        "Run aeat app diagnostics errors for the report.\n",
        encoding="utf-8",
    )

    prose = visible_document_prose(page)

    assert prose == (
        (4, "Check this adjacent misspeling."),
        (7, unknown_path),
        (10, command_with_option),
        (12, "Run aeat app diagnostics errors for the report."),
    )


def test_generated_casilla_inventory_excludes_only_exact_registry_section_heading(tmp_path) -> None:
    page = tmp_path / "docs" / "_generated" / "casillas" / "130.rst"
    page.parent.mkdir(parents=True)
    page.write_text(
        "Casilla reference\n=================\n\n"
        "Model reference navigation.\n\n"
        '.. cadrumo-casilla-section-identifier: ["did", "devolucion_banco_bank_name"]\n\n'
        "Did › Devolucion banco bank name\n" + "-" * len("Did › Devolucion banco bank name") + "\n\n"
        "Review this misspeling carefully.\n",
        encoding="utf-8",
    )

    prose = visible_document_prose(page)

    assert prose == (
        (2, "Casilla reference"),
        (4, "Model reference navigation."),
        (11, "Review this misspeling carefully."),
    )


def test_generated_casilla_marker_validates_first_heading_parsed_as_subtitle(tmp_path) -> None:
    page = tmp_path / "docs" / "_generated" / "casillas" / "038.rst"
    page.parent.mkdir(parents=True)
    heading = "Declarante"
    page.write_text(
        "Casilla reference\n=================\n\n"
        '.. cadrumo-casilla-section-identifier: ["declarante"]\n\n'
        f"{heading}\n{'-' * len(heading)}\n\n"
        "Nearby misspeling stays visible.\n",
        encoding="utf-8",
    )

    prose = visible_document_prose(page)

    assert prose == ((2, "Casilla reference"), (9, "Nearby misspeling stays visible."))


@pytest.mark.parametrize(
    "page_path, marker, separator, heading",
    [
        (
            "docs/_generated/casillas/130.rst",
            '.. cadrumo-casilla-section-identifier ["did"]',
            "\n\n",
            "Did",
        ),
        (
            "docs/_generated/casillas/130.rst",
            '.. cadrumo-casilla-section-identifier: ["other"]',
            "\n\n",
            "Expected wrong heading",
        ),
        (
            "docs/_generated/casillas/130.rst",
            '.. cadrumo-casilla-section-identifier: ["did"]',
            "\nIntervening prose\n\n",
            "Did",
        ),
        (
            "docs/_generated/other.rst",
            '.. cadrumo-casilla-section-identifier: ["did"]',
            "\n\n",
            "Did",
        ),
    ],
)
def test_casilla_section_marker_fails_closed_when_stale_or_out_of_scope(
    tmp_path: Path,
    page_path: str,
    marker: str,
    separator: str,
    heading: str,
) -> None:
    page = tmp_path / page_path
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        "Casilla reference\n=================\n\n" + marker + separator + heading + "\n" + "-" * len(heading) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="casilla section"):
        visible_document_prose(page)
