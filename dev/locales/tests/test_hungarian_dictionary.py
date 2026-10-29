"""Pinned Hungarian data repairs preserve productive spelling checks."""

from pathlib import Path

import pytest

from dev._paths import REPO_ROOT
from dev.locales._spelling import dictionary_roots, load_dictionaries

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_real_pinned_hungarian_dictionary_repairs_affixes_without_accepting_typos() -> None:
    root = dictionary_roots(REPO_ROOT)["hu"]
    vendor_files: tuple[Path, ...] = (root.with_suffix(".aff"), root.with_suffix(".dic"))
    original = {path: path.read_bytes() for path in vendor_files}

    dictionaries = load_dictionaries(REPO_ROOT)
    hungarian = dictionaries["hu"]

    # These inflections exercise rules whose conditions were damaged by the
    # literal HTML entities, rather than a list of accepted surface words.
    for word in (
        "összeget",
        "sorok",
        "sorokat",
        "évet",
        "lehetőséget",
        "őket",
        "ők",
        "te",
        "neked",
        "nekem",
        "általa",
        "általam",
        "általuk",
        "általunk",
    ):
        assert hungarian.lookup(word), word
    for word in (
        "sorokk",
        "összegett",
        "évvett",
        "lehetőségett",
        "őkkett",
        "őkk",
        "ttee",
        "nekez",
        "neken",
        "általá",
        "általamm",
        "általukk",
        "általunkk",
    ):
        assert not hungarian.lookup(word), word
    for locale in ("ca", "en", "es"):
        assert not dictionaries[locale].lookup("őket"), locale
        for word in ("neked", "nekem", "általa", "általam", "általuk", "általunk"):
            assert not dictionaries[locale].lookup(word), (locale, word)

    assert {path: path.read_bytes() for path in vendor_files} == original
