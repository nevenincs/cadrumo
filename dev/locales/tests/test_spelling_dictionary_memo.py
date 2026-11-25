"""The parsed-dictionary memo follows the dictionary bytes, never a stale load."""

import hashlib
import json
from pathlib import Path

import pytest

from dev.locales.spelling import DICTIONARY_SPECS, SpellingToolError, dictionary_roots, load_dictionaries

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _synthetic_repository(root: Path, words: tuple[str, ...]) -> Path:
    """Write a manifest-consistent set of tiny pinned dictionary packages."""
    versions = {spec.package: "1.0.0" for spec in DICTIONARY_SPECS if spec.package is not None}
    (root / "package.json").write_text(json.dumps({"devDependencies": versions}), encoding="utf-8")
    for spec in DICTIONARY_SPECS:
        if spec.package is None:
            continue
        package = root / "node_modules" / spec.package
        package.mkdir(parents=True)
        (package / "package.json").write_text(json.dumps({"name": spec.package, "version": "1.0.0"}), encoding="utf-8")
    _write_words(root, words)
    return root


def _write_words(root: Path, words: tuple[str, ...]) -> None:
    for locale, stem in dictionary_roots(root).items():
        stem.parent.mkdir(parents=True, exist_ok=True)
        stem.with_suffix(".aff").write_text("SET UTF-8\n", encoding="utf-8")
        stem.with_suffix(".dic").write_text(
            f"{len(words)}\n" + "".join(f"{word}\n" for word in words), encoding="utf-8"
        )
        if locale == "hu":
            hashes = {
                f"{suffix}_sha256": hashlib.sha256(stem.with_suffix(f".{suffix}").read_bytes()).hexdigest()
                for suffix in ("aff", "dic")
            }
            (stem.parent / "source.json").write_text(json.dumps(hashes), encoding="utf-8")


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


def test_vendored_dictionary_byte_drift_refuses_before_lookup(tmp_path: Path) -> None:
    repository = _synthetic_repository(tmp_path, ("alfa",))
    dictionary_roots(repository)["hu"].with_suffix(".dic").write_text("1\nchanged\n", encoding="utf-8")
    with pytest.raises(SpellingToolError, match="does not match its source receipt"):
        load_dictionaries(repository)
