"""The CLI keeps its command remedy, and the sentence every frontend shares carries none."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_LOCALES = Path(__file__).resolve().parents[3] / "locales"
_LANGUAGES = ("en", "es", "ca", "hu")
_COMMAND = "aeat app ledger inventory list"


def _catalogue(language: str, name: str) -> object:
    with (_LOCALES / language / f"{name}.yml").open(encoding="utf-8") as handle:
        catalogue: object = yaml.safe_load(handle)
    return catalogue


def _at(node: object, *path: str) -> object:
    for key in path:
        assert isinstance(node, dict)
        node = node[key]
    return node


@pytest.mark.parametrize("language", _LANGUAGES)
@pytest.mark.parametrize(
    "key",
    ["refusal_activity_conflict", "refusal_activity_not_found", "refusal_duplicate_movement_id"],
)
def test_the_cli_sentence_names_the_command_that_lists_the_records(language: str, key: str) -> None:
    sentence = _at(_catalogue(language, "cli"), "cli", "app", "ledger", "inventory", key)

    assert _COMMAND in str(sentence)


@pytest.mark.parametrize("language", _LANGUAGES)
def test_the_shared_sentences_carry_no_command_movement_id_or_closing_authority(language: str) -> None:
    errors = _at(_catalogue(language, "application"), "application", "inventory", "service", "errors")

    assert isinstance(errors, dict)
    for key, sentence in errors.items():
        assert "aeat " not in str(sentence), key
        assert "%{movement_id}" not in str(sentence), key
        assert "%{correction_id}" not in str(sentence), key


@pytest.mark.parametrize(
    ("language", "word"),
    [("en", "authority"), ("es", "autoridad"), ("ca", "autoritat"), ("hu", "jogalap")],
)
def test_the_shared_sentences_do_not_say_closing_authority(language: str, word: str) -> None:
    errors = _at(_catalogue(language, "application"), "application", "inventory", "service", "errors")

    assert isinstance(errors, dict)
    assert not [key for key, sentence in errors.items() if word in str(sentence)]
