"""The parsed-dictionary memo follows the dictionary bytes, never a stale load."""

import json
from pathlib import Path

import pytest

from dev.locales._spelling import DICTIONARY_SPECS, dictionary_roots, load_dictionaries

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _synthetic_repository(root: Path, words: tuple[str, ...]) -> Path:
    """Write a manifest-consistent set of tiny pinned dictionary packages."""
    versions = {spec.package: "1.0.0" for spec in DICTIONARY_SPECS}
    (root / "package.json").write_text(json.dumps({"devDependencies": versions}), encoding="utf-8")
    for spec in DICTIONARY_SPECS:
        package = root / "node_modules" / spec.package
        package.mkdir(parents=True)
        (package / "package.json").write_text(json.dumps({"name": spec.package, "version": "1.0.0"}), encoding="utf-8")
    _write_words(root, words)
    return root


def _write_words(root: Path, words: tuple[str, ...]) -> None:
    for stem in dictionary_roots(root).values():
        stem.with_suffix(".aff").write_text("SET UTF-8\n", encoding="utf-8")
        stem.with_suffix(".dic").write_text(
            f"{len(words)}\n" + "".join(f"{word}\n" for word in words), encoding="utf-8"
        )


def test_an_edited_dictionary_is_parsed_afresh(tmp_path: Path) -> None:
    repository = _synthetic_repository(tmp_path, ("alfa",))
    first = load_dictionaries(repository)
    assert all(dictionary.lookup("alfa") for dictionary in first.values())
    assert not any(dictionary.lookup("beta") for dictionary in first.values())

    _write_words(repository, ("alfa", "beta"))
    second = load_dictionaries(repository)

    assert all(dictionary.lookup("beta") for dictionary in second.values())


def test_a_caller_cannot_change_what_the_next_caller_loads(tmp_path: Path) -> None:
    repository = _synthetic_repository(tmp_path, ("alfa",))
    first = load_dictionaries(repository)
    first.clear()

    assert set(load_dictionaries(repository)) == {spec.locale for spec in DICTIONARY_SPECS}
