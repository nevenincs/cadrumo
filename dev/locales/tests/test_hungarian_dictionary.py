"""Pinned Hungarian data repairs preserve productive spelling checks."""

from pathlib import Path

import pytest

from dev.locales.spelling import dictionary_roots, load_dictionaries
from dev.paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_real_pinned_hungarian_dictionary_repairs_affixes_without_accepting_typos() -> None:
    root = dictionary_roots(REPO_ROOT)["hu"]
    vendor_files: tuple[Path, ...] = (root.with_suffix(".aff"), root.with_suffix(".dic"))
    original = {path: path.read_bytes() for path in vendor_files}

    dictionaries = load_dictionaries(REPO_ROOT)
    hungarian = dictionaries["hu"]

    # These include original dictionary inflections and pronouns previously
    # damaged by the npm normalization.
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
        "őrzésének",
        "profilőrzéshez",
        "nekik",
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
        "őketén",
        "nekedén",
        "nekemén",
        "általaáltalaáltal",
        "profileőrzéshez",
    ):
        assert not hungarian.lookup(word), word
    for locale in ("ca", "en", "es"):
        assert not dictionaries[locale].lookup("őket"), locale
        for word in ("neked", "nekem", "általa", "általam", "általuk", "általunk"):
            assert not dictionaries[locale].lookup(word), (locale, word)

    assert {path: path.read_bytes() for path in vendor_files} == original
