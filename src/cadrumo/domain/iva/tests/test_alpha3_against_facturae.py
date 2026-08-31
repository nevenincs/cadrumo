"""The alpha-3 column is checked against the schema that made it necessary.

The country vocabulary carries an alpha-3 code beside every alpha-2 one, and it
carries it for exactly one reason: a Facturae invoice states the country as a
three-letter code, so a document whose ``CountryCode`` reads ``ESP`` would
otherwise establish nothing while being present, parsed and perfectly readable.
The column existed as hand-authored data with no authority behind it, and the
vocabulary's own header said so.

**The authority is the Facturae schema itself, and that is the point rather than
a convenience.** The question the column answers is "what three-letter code can a
Facturae document state", so the set of values the Facturae ``CountryType``
enumerates is not merely *an* authority for it -- it is the definition of the
question. A general ISO register would have answered a broader question the
column does not ask, and adopting one would have reopened the boundary the
vocabulary's own inclusion argument settles.

**What is bundled is the enumeration, not the schema.** The published schema is a
190 KB authored artefact whose redistribution terms are not stated in the file;
the enumeration extracted from it is a list of ISO codes, which is fact rather
than expression. The extract carries a provenance stamp naming the source URL,
the schema version it came from, the retrieval date and the SHA-256 of the
payload it was taken from, so a later reader can re-derive it and can tell WHICH
of the three published 3.2.x schemas grounds the column.

**What this proves, and the residual it leaves.** It proves every alpha-3 the
vocabulary carries is a code a Facturae document can legitimately state, so a
fabricated or mistyped value -- ``PRG`` for Paraguay, say -- reds here. It does
NOT prove the code names the country written beside it: the enumeration is bare
values with no annotations, so ``PRY`` and ``PER`` are both members and swapping
them would pass. That correspondence is grounded by the hand-check against AEAT's
printed register, and the two checks are complementary rather than redundant.

The residual is therefore precise and worth stating rather than implying: a
CONSISTENT swap of two real codes between two real countries survives every
check this repository can make. Closing it needs an authority that maps alpha-3
to a country name, which nothing bundled here provides.

See Also:
    :func:`~domain.iva.country_code_for_stated_country_code`
        The structured leg this column serves.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest

from ....core.resources._boundary import bundled_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ENUMERATION = ("corpus", "facturae", "facturae-3-2-2-country-codes.json")

#: The count published in Facturae 3.2.2. Pinned as a fixture anchor rather than
#: as a contract: it is here so an extract that silently lost most of its rows
#: cannot leave the subset checks below trivially satisfied. A genuine schema
#: revision changing it is expected to change this line with a fresh stamp.
_PUBLISHED_CODE_COUNT = 235


def _facturae_codes() -> frozenset[str]:
    payload = json.loads(Path(bundled_path(*_ENUMERATION)).read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    raw_codes = payload.get("codes")
    assert isinstance(raw_codes, list)
    codes: list[str] = []
    for code in raw_codes:
        assert isinstance(code, str)
        codes.append(code)
    return frozenset(codes)


def _vocabulary() -> list[dict[str, object]]:
    payload = tomllib.loads(Path(bundled_path("registry", "aeat", "iva", "country_names.toml")).read_text("utf-8"))
    raw_country = payload.get("country")
    assert isinstance(raw_country, list)
    rows: list[dict[str, object]] = []
    for raw_row in raw_country:
        assert isinstance(raw_row, dict)
        row: dict[str, object] = {}
        for key, value in raw_row.items():
            assert isinstance(key, str)
            row[key] = value
        rows.append(row)
    return rows


def test_the_bundled_extract_carries_its_provenance() -> None:
    """A bundled authority with no stamp is an assertion wearing a filename.

    Every field here is what a later reader needs to re-derive the extract and to
    tell which published schema grounds the column; a stamp missing the version
    would leave 3.2, 3.2.1 and 3.2.2 indistinguishable.
    """
    stamp = json.loads(Path(bundled_path(*_ENUMERATION)).read_text(encoding="utf-8"))["provenance"]

    assert stamp["schema_version"] == "3.2.2"
    assert stamp["simple_type"] == "CountryType"
    assert stamp["source_url"].startswith("https://www.facturae.gob.es/")
    assert len(stamp["source_sha256"]) == 64
    assert stamp["retrieved_at"]


def test_the_extract_is_populated_and_distinct() -> None:
    """Fixture anchor. An empty or truncated extract satisfies any subset check."""
    codes = _facturae_codes()

    assert len(codes) == _PUBLISHED_CODE_COUNT
    assert all(len(code) == 3 and code.isalpha() and code.isupper() for code in codes)
    assert "ESP" in codes


def test_every_vocabulary_alpha3_is_one_facturae_can_state() -> None:
    """The substantive check: no fabricated or mistyped three-letter code."""
    statable = _facturae_codes()
    unstatable = sorted(
        (str(record["code"]), str(record["alpha3"]))
        for record in _vocabulary()
        if str(record["alpha3"]) not in statable
    )

    assert unstatable == [], f"alpha-3 codes no Facturae document can state: {unstatable}"


def test_the_gate_would_notice_a_plausible_mistyping() -> None:
    """Anti-vacuity control, chosen to be the error this actually guards against.

    ``PRG`` is what a careless hand writes for Paraguay and ``XXX`` is what a
    placeholder looks like; neither is in the enumeration, so the assertion above
    is a measurement rather than a formality. Asserting a nonsense string alone
    would have proved only that the set is not universal.
    """
    statable = _facturae_codes()

    assert "PRG" not in statable
    assert "XXX" not in statable
    assert "PRY" in statable


def test_the_check_cannot_see_a_swap_between_two_real_codes() -> None:
    """The residual, asserted so it is documented by something that runs.

    Both Paraguay's and Peru's codes are members, so a vocabulary that had
    swapped them would satisfy every other case in this file. Writing that down
    as an executable fact stops a later reader treating membership as proof of
    correspondence -- which is the one thing this authority cannot give.
    """
    statable = _facturae_codes()

    assert {"PRY", "PER"} <= statable
