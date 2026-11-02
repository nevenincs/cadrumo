"""Locale signal checks for user documentation adapters."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import pytest

from ..manager import LocaleManager
from ..signal_discovery import signal_catalogue_coverage
from ..signal_document_prose import embedded_document_language_prose
from ..signal_documentation_inventory import documentation_source_inventory, inventory_generated_document_file
from ..signal_echo_classification import load_platform_identity_terms, translation_invariant_echo_reason
from ..signal_parallel_inventory import parallel_localization_inventory
from ..signal_policy import LOCALES
from ..signal_report import signal_catalogue_only_cells
from ..signal_spelling import spellcheck_catalogues
from ..signal_tokens import filtered_translation_text, human_translation_text
from ..signal_translation_matrix import translation_matrix
from ._signal_support import (
    _list,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_generated_user_doc_adapter_enrols_explicit_embedded_language(tmp_path) -> None:
    page = tmp_path / "legal.rst"
    page.write_text(
        "Legal reference\n===============\n\n"
        ".. raw:: html\n\n"
        '   <blockquote lang="es"><p>Administracion Tributaria</p></blockquote>\n',
        encoding="utf-8",
    )

    assert embedded_document_language_prose(page) == ((6, "es", "Administracion Tributaria"),)


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

    inventory, findings = documentation_source_inventory(
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
    inventory, findings = documentation_source_inventory(
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

    inventory, findings = documentation_source_inventory(
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
    assert len(_list(inventory["docs_translation_source_echo_samples"])) == 3
    assert len(_list(inventory["docs_translation_near_echo_samples"])) == 1
    exact = [finding for finding in findings if finding["kind"] == "docs_translation_source_echo"]
    near = [finding for finding in findings if finding["kind"] == "docs_translation_near_echo"]
    assert len(exact) == 3
    assert len(near) == 1
    assert all(finding["classification"] == "blocking" for finding in exact)
    assert near[0]["classification"] == "advisory"
    ratio = near[0]["ratio"]
    assert isinstance(ratio, (int, float))
    assert ratio >= 0.9


def test_documentation_inventory_classifies_only_provable_invariant_echoes(tmp_path, monkeypatch) -> None:
    from .. import signal_documentation_echo as echo_module

    class _Dictionary:
        def lookup(self, word: str) -> bool:
            return word.casefold() == "manual"

    monkeypatch.setattr(
        echo_module,
        "load_dictionaries",
        lambda _repository: {locale: _Dictionary() for locale in LOCALES},
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

    inventory, findings = documentation_source_inventory(
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
        translation_invariant_echo_reason(
            "Cadrumo vX.Y.Z",
            "es",
            dictionary=target,
            source_dictionary=english,
        )
        == "canonical_product_identity"
    )
    assert (
        translation_invariant_echo_reason(
            "vX.Y.Z",
            "es",
            dictionary=target,
            source_dictionary=english,
        )
        is None
    )
    assert (
        translation_invariant_echo_reason(
            "Windows (x86-64)",
            "es",
            dictionary=target,
            source_dictionary=english,
        )
        == "platform_format"
    )
    assert (
        translation_invariant_echo_reason(
            "Régimen de atribución de rentas (socios)",
            "es",
            dictionary=target,
            source_dictionary=english,
        )
        == "target_dictionary_shared_term"
    )
    assert (
        translation_invariant_echo_reason(
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

    terms = load_platform_identity_terms(tmp_path)

    assert {"macos", "linux", "windows"}.issubset(terms)
    assert "any" not in terms
    assert "any platform with python 3 13+" not in terms


@pytest.mark.parametrize("source", ("!", "●", "↓", "▹ ▿", "…", "`/`", "`?`"))
def test_literal_symbols_are_invariant_without_language_dictionaries(source: str) -> None:
    assert translation_invariant_echo_reason(source, "hu", dictionary=None) == "symbol_only"


@pytest.mark.parametrize("source", ("`Enter`", "`Esc`", "`i`"))
def test_keyboard_and_alphabetic_marks_require_existing_literal_code_contract(source: str) -> None:
    assert translation_invariant_echo_reason(source, "ca", dictionary=None) == "inline_code"


@pytest.mark.parametrize("source", ("Enter", "Esc", "Space", "i", "", " ", "Review the return!"))
def test_symbol_invariance_does_not_exempt_unmarked_words_or_prose(source: str) -> None:
    assert translation_invariant_echo_reason(source, "es", dictionary=None) is None


def test_symbol_classification_preserves_blocking_prose_and_missing_translations(tmp_path, monkeypatch) -> None:
    from .. import signal_documentation_echo as echo_module

    monkeypatch.setattr(echo_module, "load_dictionaries", lambda _repository: {})
    docs = tmp_path / "docs"
    messages = ("●", "`Enter`", "Review the current return!", "Fill in the box")
    pot = 'msgid ""\nmsgstr ""\n\n' + "\n".join(f'msgid "{message}"\nmsgstr ""\n' for message in messages)
    _write_docs_source_cache(docs, "guide.md", "# Filing guide\n", pot)
    catalogue_messages = {("guide.po", message): {"es": True} for message in messages if message != "Fill in the box"}
    catalogue_translations = {
        ("guide.po", message): {"es": (message,)} for message in messages if message != "Fill in the box"
    }

    inventory, findings = documentation_source_inventory(
        tmp_path,
        catalogue_messages,
        catalogue_files={("es", "guide.po")},
        catalogue_translations=catalogue_translations,
    )

    assert inventory["docs_translation_source_echo"] == 1
    assert inventory["docs_translation_invariant_echo"] == 2
    blocking = [finding for finding in findings if finding["kind"] == "docs_translation_source_echo"]
    assert [finding["source"] for finding in blocking] == ["Review the current return!"]
    missing = [finding for finding in findings if finding["kind"] == "docs_source_catalogue_drift"]
    assert any(finding["missing_message_ids"] == ["Fill in the box"] for finding in missing)


def test_documentation_inventory_fails_closed_when_source_manifest_is_absent(tmp_path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text("# Filing guide\n", encoding="utf-8")

    inventory, findings = documentation_source_inventory(tmp_path, {})

    assert inventory["docs_source_pages"] == 1
    assert inventory["docs_extraction_failures"] == 1
    extraction = [finding for finding in findings if finding["kind"] == "docs_source_extraction_failure"]
    assert len(extraction) == 1
    assert extraction[0]["classification"] == "blocking"
    assert extraction[0]["domain"] == "docs"
    assert extraction[0]["error_type"] == "FileNotFoundError"
    assert sum(finding["kind"] == "docs_catalogue_missing" for finding in findings) == 3


def test_spellcheck_fails_closed_when_pinned_dictionaries_are_absent(tmp_path) -> None:
    spelling, inventory, findings = spellcheck_catalogues(
        {"cli.title"},
        {"ca": {"cli.title": "Declaració tributària"}},
        tmp_path,
    )

    assert spelling == {}
    assert inventory["spelling_tool_failures"] == 1
    assert findings[0]["kind"] == "spelling_tool_unavailable"


def test_identifier_signal_pattern_terminates_on_adversarial_underscore_runs() -> None:
    """The snake_case arm must not backtrack exponentially on a near-miss run.

    ``_filtered_translation_text`` runs the identifier pattern over arbitrary
    translator-supplied prose, and Spanish, Catalan and Galician prose is full
    of non-ASCII letters. Such a letter is a word character the ASCII-only
    identifier body cannot consume, so a long underscore-separated run ending
    in one forces the pattern to prove no split matches. With an ambiguous
    "body or separator" spelling that proof doubles in cost per segment: the
    input below takes minutes, against microseconds once the split is unique.
    """
    adversarial = "A_" + "0_" * 30 + "é"

    started = time.perf_counter()
    filtered, _ = filtered_translation_text(adversarial)
    elapsed = time.perf_counter() - started

    assert elapsed < 2.0
    assert "é" in filtered


def test_catalogue_only_findings_and_counts_share_optional_modelo_exemptions() -> None:
    required = {"cli.save"}
    delta = "modelo.schema.303.casilla.continuidad.example.label"
    heading = "modelo.schema.303.form.authored.page-1.heading"
    stray = "modelo.schema.303.form.page.not-a-page.heading"
    leaves = {
        "en": {key: "text" for key in ("cli.save", delta, heading, stray)},
        "es": {key: "texto" for key in (delta, heading, stray)},
    }

    cells, unique, keys, findings = signal_catalogue_coverage(leaves, required)

    assert (cells, unique, keys) == (7, 4, {stray})
    assert signal_catalogue_only_cells(leaves, required) == 2
    assert [(finding["key"], finding["cells"]) for finding in findings] == [(stray, 2)]


def test_spelling_preserves_dictionary_case_and_similarity_normalizes(tmp_path, monkeypatch) -> None:
    from .. import signal_spelling as spelling_module

    class Dictionary:
        def lookup(self, word: str) -> bool:
            return word == "Spanish"

    monkeypatch.setattr(spelling_module, "load_dictionaries", lambda _repository: {"en": Dictionary()})
    spelling, _inventory, _findings = spellcheck_catalogues(
        {"cli.language", "cli.typo"},
        {"en": {"cli.language": "Spanish", "cli.typo": "spanish"}},
        tmp_path,
    )

    assert spelling == {("en", "cli.typo"): ("spanish",)}
    assert human_translation_text("Spanish") == human_translation_text("spanish")


def test_generated_legal_prose_uses_explicit_language_dictionary(tmp_path, monkeypatch) -> None:
    from collections import Counter

    from .. import signal_spelling as spelling_module

    class Dictionary:
        def __init__(self, known: set[str]) -> None:
            self.known = known

        def lookup(self, word: str) -> bool:
            return word in self.known

    page = tmp_path / "docs" / "_generated" / "legal" / "example.rst"
    page.parent.mkdir(parents=True)
    page.write_text(
        'Official wording.\n\n.. raw:: html\n\n   <blockquote lang="es"><p>Dividendos desconocido</p></blockquote>\n',
        encoding="utf-8",
    )
    values: dict[str, dict[str, str]] = {}
    findings: list[dict[str, object]] = []
    inventory_generated_document_file(page, tmp_path, Counter(), findings, values)
    monkeypatch.setattr(
        spelling_module,
        "load_dictionaries",
        lambda _repository: {"en": Dictionary({"Official", "wording"}), "es": Dictionary({"Dividendos"})},
    )
    spelling, _inventory, _findings = spellcheck_catalogues(set(), {}, tmp_path, additional_values=values)

    assert not findings
    assert spelling == {("es", "parallel:docs/_generated/legal/example.rst:line[5]:lang[es]"): ("desconocido",)}


def test_generated_legal_citation_uses_spanish_and_keeps_other_prose_checked(tmp_path, monkeypatch) -> None:
    from collections import Counter

    from .. import signal_spelling as spelling_module

    class Dictionary:
        def __init__(self, known: set[str]) -> None:
            self.known = known

        def lookup(self, word: str) -> bool:
            return word in self.known

    page = tmp_path / "docs" / "_generated" / "legal" / "example.rst"
    page.parent.mkdir(parents=True)
    page.write_text(
        '.. cadrumo-legal-citation: "Ley especial errata"\n\nLey especial errata\n===================\n\n'
        "English misspeling.\n",
        encoding="utf-8",
    )
    values: dict[str, dict[str, str]] = {}
    findings: list[dict[str, object]] = []
    inventory_generated_document_file(page, tmp_path, Counter(), findings, values)
    monkeypatch.setattr(
        spelling_module,
        "load_dictionaries",
        lambda _repository: {"en": Dictionary({"English"}), "es": Dictionary({"Ley", "especial"})},
    )
    spelling, _inventory, _findings = spellcheck_catalogues(set(), {}, tmp_path, additional_values=values)

    assert not findings
    assert spelling == {
        ("es", "parallel:docs/_generated/legal/example.rst:line[4]:lang[es]"): ("errata",),
        ("en", "parallel:docs/_generated/legal/example.rst:line[6]"): ("misspeling",),
    }


def test_generated_legal_citation_marker_must_match_heading(tmp_path) -> None:
    from collections import Counter

    page = tmp_path / "docs" / "_generated" / "legal" / "example.rst"
    page.parent.mkdir(parents=True)
    page.write_text('.. cadrumo-legal-citation: "Ley correcta"\n\nLey typo\n========\n', encoding="utf-8")
    findings: list[dict[str, object]] = []
    inventory_generated_document_file(page, tmp_path, Counter(), findings, {})

    assert [finding["kind"] for finding in findings] == ["docs_generated_source_unreadable"]


def test_intentionally_open_reason_copy_is_optional_but_unknown_family_blocks(tmp_path, monkeypatch) -> None:
    from .. import signal_discovery as discovery

    manager = LocaleManager(tmp_path, tmp_path)
    monkeypatch.setattr(manager, "get_codebase_keys", lambda: set())
    monkeypatch.setattr(
        manager,
        "get_codebase_namespaces",
        lambda: {"tui.home.availability.reason.*", "unknown.family.*"},
    )
    monkeypatch.setattr(discovery, "dynamic_key_families", lambda markers: ({}, tuple(sorted(markers))))
    optional = "tui.home.availability.reason.ready"
    leaves = {"en": {optional: "Ready"}, "es": {}}
    monkeypatch.setattr(discovery, "catalogue_leaves", lambda _manager, _required_keys: (leaves, []))

    required, _, markers, finite, unresolved, discovered_leaves, _ = discovery.discover_signal_catalogues(manager)
    discovery.include_signal_namespace_keys(required, markers, finite, discovered_leaves)

    assert unresolved == ("unknown.family.*",)
    assert optional not in required
    assert discovery.signal_catalogue_coverage(leaves, required)[2] == set()
    assert signal_catalogue_only_cells(leaves, required) == 0


def test_signal_catalogue_reads_cross_owner_desktop_projection(tmp_path, monkeypatch) -> None:
    from .. import _paths, desktop_chrome, signal_discovery

    (tmp_path / "en.yml").write_text("cli:\n  save: Save\n", encoding="utf-8")
    manager = LocaleManager(tmp_path, tmp_path)
    monkeypatch.setattr(_paths, "LOCALES_DIR", tmp_path)
    monkeypatch.setattr(desktop_chrome, "DESKTOP_CHROME_KEYS", frozenset({"desktop.attendance.title", "desktop.other"}))
    monkeypatch.setattr(
        desktop_chrome,
        "desktop_chrome_strings",
        lambda _root, *, keys: {"en": {"desktop.attendance.title": "Attendance", "desktop.other": "Other"}},
    )
    leaves, findings = signal_discovery.catalogue_leaves(manager, {"desktop.attendance.title", "cli.save"})

    assert leaves == {"en": {"cli.save": "Save", "desktop.attendance.title": "Attendance"}}
    assert findings == []
    assert translation_matrix({"desktop.attendance.title"}, leaves)["cells"]["missing"] == 0


def test_parallel_docs_scope_ignores_english_only_catalogues_but_reports_user_gaps(tmp_path) -> None:
    docs = tmp_path / "docs"
    _write_docs_source_cache(docs, "guide.md", "A guide.\n", 'msgid ""\nmsgstr ""\n\nmsgid "A guide."\nmsgstr ""\n')
    generated = docs / "reference" / "generated.md"
    generated.parent.mkdir(parents=True)
    generated.write_text("<!-- GENERATED FILE -->\nGenerated.\n", encoding="utf-8")
    catalogues = docs / "locales"
    for locale, relative, contents in (
        ("es", "guide.po", 'msgid ""\nmsgstr ""\n\nmsgid "A guide."\nmsgstr ""\n'),
        ("ca", "old-guide.po", 'msgid ""\nmsgstr ""\n\nmsgid "Old."\nmsgstr ""\n'),
        ("es", "technical/old.po", "invalid gettext artefact"),
        ("ca", "reference/generated.po", "invalid gettext artefact"),
    ):
        path = catalogues / locale / "LC_MESSAGES" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")
    values: dict[str, dict[str, str]] = {}

    inventory, findings = parallel_localization_inventory(tmp_path, spelling_values=values)

    assert inventory["docs_orphan_catalogue_files"] == 1
    assert inventory["docs_missing_catalogue_files"] == 2
    assert any(finding["kind"] == "docs_orphan_catalogue" and "old-guide.po" in str(finding) for finding in findings)
    assert any(finding["kind"] == "docs_translation_missing" and "guide.po" in str(finding) for finding in findings)
    assert not any("technical/" in str(finding) or "reference/generated.po" in str(finding) for finding in findings)
    assert not any(
        "technical/" in cell or "reference/generated.po" in cell for cells in values.values() for cell in cells
    )
    assert (catalogues / "es" / "LC_MESSAGES" / "technical" / "old.po").is_file()
