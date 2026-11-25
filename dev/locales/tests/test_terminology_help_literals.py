"""Maintenance CLI help distinguishes immutable field/value syntax from prose."""

import re
from collections import defaultdict
from enum import Enum
from typing import get_args, get_type_hints

import pytest
from typer.testing import CliRunner

from cadrumo.core.i18n.render import tr
from dev.docs.terminology_handbook.cli import app, seed
from dev.docs.terminology_handbook.schema import ConceptRecord, LanguageSection, TermSection

from ..signal_spelling_enrollment import check_dictionary_spelling_words
from ..signal_spelling_segments import translation_spelling_segments

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_LITERAL_FIELDS = {
    "authority": ("source",),
    "field_name": ("short_description", "definition", "scope_note", "source", "term"),
    "field_value": ("source", "term"),
    "relation_kind": ("broader", "related"),
    "seed_source": ("iate", "ubterm", "eurovoc"),
    "term_status": ("term",),
}


@pytest.mark.parametrize("locale", ["ca", "en", "es", "hu"])
@pytest.mark.parametrize("field,tokens", _LITERAL_FIELDS.items())
def test_help_retains_the_actual_input_tokens_as_code(locale: str, field: str, tokens: tuple[str, ...]) -> None:
    key = "docs.terminology.cli." + field
    text = tr(key, locale=locale)
    assert tuple(re.findall(r"`([^`]+)`", text)) == tokens
    words = {
        word for _, words, _ in translation_spelling_segments(text + " misspellledd", key, locale) for word in words
    }
    assert not set(tokens) & words
    assert "misspellledd" in words


def test_relation_names_remain_the_live_concept_relation_fields() -> None:
    assert set(_LITERAL_FIELDS["relation_kind"]) <= ConceptRecord.model_fields.keys()


class EmptyDictionary:
    def lookup(self, word: str) -> bool:
        return False


@pytest.mark.parametrize("locale", ["ca", "es", "hu"])
def test_ordinary_foreign_words_and_typos_remain_checked(locale: str) -> None:
    key = "docs.terminology.cli.authority"
    unknown_words: set[tuple[str, str]] = set()
    unknown_by_cell: dict[tuple[str, str], set[str]] = defaultdict(set)
    check_dictionary_spelling_words(
        locale,
        {word: {(locale, key)} for word in ("source", "term", "sourcce", "misspellledd")},
        {locale: EmptyDictionary()},
        {(locale, key): "source term sourcce misspellledd"},
        unknown_words,
        unknown_by_cell,
    )
    assert unknown_by_cell[(locale, key)] == {"source", "term", "sourcce", "misspellledd"}


@pytest.mark.parametrize(
    "command,tokens",
    [
        ("set", _LITERAL_FIELDS["field_name"]),
        ("relate", _LITERAL_FIELDS["relation_kind"]),
        ("seed", _LITERAL_FIELDS["seed_source"]),
    ],
)
def test_typer_help_renders_the_canonical_literal_tokens(command: str, tokens: tuple[str, ...]) -> None:
    result = CliRunner().invoke(app, [command, "--help"], env={"COLUMNS": "200"})
    assert result.exit_code == 0, result.output
    compact = " ".join(result.output.split())
    for token in tokens:
        assert "`" + token + "`" in compact


def test_language_field_literals_match_the_public_language_and_term_models() -> None:
    assert set(_LITERAL_FIELDS["field_name"]) - {"term"} <= LanguageSection.model_fields.keys()
    assert "label" in TermSection.model_fields


def test_seed_literals_are_choices_of_the_public_cli() -> None:
    source = get_args(get_type_hints(seed, include_extras=True)["source"])[0]
    assert isinstance(source, type) and issubclass(source, Enum)
    assert set(_LITERAL_FIELDS["seed_source"]) <= {str(value.value) for value in source}
