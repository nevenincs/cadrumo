"""Sphinx's own words reach the one compile as every language's word at once.

The catalogues are real compiled gettext catalogues written here, so the words
come back through the same ``gettext`` machinery a build reads them through. The
expected strings are stated in this file: what a word reads in each language,
and what filling one with an argument must produce.
"""

from __future__ import annotations

import copy
from collections.abc import Iterator, Mapping
from pathlib import Path

import pytest

from ..compile_slots import MARK, CompileSlots, Rendering, activate, deactivate
from ..sphinx_messages import _catalogue, _mark_frozen_words, _MarkingTranslations

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_LANGUAGES: tuple[str, ...] = ("en", "es", "ca")


@pytest.fixture
def slots() -> Iterator[CompileSlots]:
    """Record marks for three languages, and stop recording after the test."""
    yield activate(_LANGUAGES)
    deactivate()


def _write_catalogue(directory: Path, language: str, translations: Mapping[str, str]) -> None:
    """Write one language's compiled catalogue of Sphinx's own messages."""
    from babel.messages.catalog import Catalog
    from babel.messages.mofile import write_mo

    catalogue = Catalog(charset="utf-8")
    for message, translation in translations.items():
        catalogue.add(message, translation)
    path = directory / language / "LC_MESSAGES" / "sphinx.mo"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as stream:
        write_mo(stream, catalogue)


@pytest.fixture
def translations(tmp_path: Path) -> _MarkingTranslations:
    """Answer three languages from catalogues only two of them carry."""
    _write_catalogue(tmp_path, "es", {"Index": "Índice", "Toggle navigation of %s": "Conmutar %s"})
    _write_catalogue(tmp_path, "ca", {"Index": "Índex", "Toggle navigation of %s": "Commuta %s"})
    return _MarkingTranslations([_catalogue(language, [tmp_path]) for language in _LANGUAGES], Rendering.PLAIN)


def test_a_word_every_language_reads_the_same_is_not_marked(
    slots: CompileSlots, translations: _MarkingTranslations
) -> None:
    """A word no catalogue translates is the one string every build writes."""
    assert translations.gettext("Permalink") == "Permalink"
    assert slots.values == []


def test_a_word_that_differs_is_the_mark_reading_every_language(
    slots: CompileSlots, translations: _MarkingTranslations
) -> None:
    """The word a language has no translation for stays the message, as its build leaves it."""
    marked = translations.gettext("Index")
    assert MARK.fullmatch(marked) is not None
    assert slots.values == [("Index", "Índice", "Índex")]
    assert slots.renderings == [Rendering.PLAIN]


def test_a_word_resolved_before_the_compile_could_answer_it_is_marked_from_its_message(
    slots: CompileSlots, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sphinx resolves some of its own words while a module is imported.

    That is before ``setup(app)`` replaces the translators, so the word is
    already one language's plain string and no lookup of ours ever sees it. The
    module index's name is the one in this tree, and it reaches a root through
    the object inventory. The attribute is named by its own owner here, so a
    renamed one fails rather than silently going unmarked.
    """
    from sphinx.domains.python import PythonModuleIndex

    _write_catalogue(tmp_path, "es", {"Python Module Index": "Índice de módulos Python"})
    _write_catalogue(tmp_path, "ca", {"Python Module Index": "Índex de mòduls de Python"})
    monkeypatch.setattr(PythonModuleIndex, "localname", "Python Module Index")
    _mark_frozen_words([_catalogue(language, [tmp_path]) for language in _LANGUAGES])
    assert MARK.fullmatch(PythonModuleIndex.localname) is not None
    assert slots.values == [("Python Module Index", "Índice de módulos Python", "Índex de mòduls de Python")]
    assert slots.renderings == [Rendering.PLAIN]


def test_filling_a_word_builds_a_mark_from_every_language_filled(
    slots: CompileSlots, translations: _MarkingTranslations
) -> None:
    """Filling the mark would throw it away, so each language's own word is filled instead."""
    title = slots.mark(Rendering.DOCUTILS, ["Ledger", "Libro", "Llibre"])
    filled = translations.gettext("Toggle navigation of %s") % title
    assert MARK.fullmatch(filled) is not None
    assert slots.values[-1] == (
        "Toggle navigation of Ledger",
        "Conmutar Libro",
        "Commuta Llibre",
    )


def test_a_marked_word_comes_back_from_a_pickled_environment_still_fillable(
    slots: CompileSlots, translations: _MarkingTranslations
) -> None:
    """A reader process hands its environment back pickled, with Sphinx's own words on it.

    A deep copy rebuilds the word through the same reduction pickling uses.
    """
    restored = copy.deepcopy(translations.gettext("Toggle navigation of %s"))

    assert MARK.fullmatch(restored) is not None
    assert slots.values == [("Toggle navigation of %s", "Conmutar %s", "Commuta %s")]
    restored % "x"
    assert slots.values[-1] == ("Toggle navigation of x", "Conmutar x", "Commuta x")
