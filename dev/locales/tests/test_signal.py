"""Contracts for the actionable locale translation backlog."""

from __future__ import annotations

import pytest

from .._signal import (
    _domain_summaries,
    _dynamic_key_families,
    _headline,
    _human_translation_text,
    _parallel_localization_inventory,
    _source_inventory,
    _spellcheck_catalogues,
    _translation_matrix,
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
        [{"kind": "naked_presentation_text"}],
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
    assert {finding["field"] for finding in findings} == {"name_ca", "name_hu"}


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

    _parallel_localization_inventory(tmp_path, spelling_values=values)

    assert values["ca"]["parallel:src/cadrumo/_data/labels.toml:label_ca"] == "Declaració tributària"
    plural_values = {key: value for key, value in values["ca"].items() if "docs/locales/ca/LC_MESSAGES/guide.po" in key}
    assert plural_values == {
        "parallel:docs/locales/ca/LC_MESSAGES/guide.po:One return\x04Many returns:plural[0]": "Una declaració",
        "parallel:docs/locales/ca/LC_MESSAGES/guide.po:One return\x04Many returns:plural[1]": "Moltes declaracions",
    }


def test_spellcheck_fails_closed_when_pinned_dictionaries_are_absent(tmp_path) -> None:
    spelling, inventory, findings = _spellcheck_catalogues(
        {"cli.title"},
        {"ca": {"cli.title": "Declaració tributària"}},
        tmp_path,
    )

    assert spelling == {}
    assert inventory["spelling_tool_failures"] == 1
    assert findings[0]["kind"] == "spelling_tool_unavailable"
