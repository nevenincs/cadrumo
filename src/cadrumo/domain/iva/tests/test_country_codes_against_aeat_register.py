"""Every country code this repository keys on is one AEAT itself recognises.

The country vocabulary's alpha-2 column was grounded by hand against AEAT's
printed country register in the bundled Manual práctico de Sociedades: a person
read each code beside its Spanish name and confirmed it. That is honest and it is
an attestation -- it holds until the next author adds a row without repeating the
exercise, and nothing in the tree would notice.

This gate replaces the attestation with a check, against a SECOND AEAT authority
that is already bundled and is machine-readable: the ``CountryType2`` enumeration
in AEAT's SII record schema, which is the closed set of country codes AEAT accepts
on a submitted libro de registro. It is the right instrument for this axis
precisely because it is not a general country database -- it is what the tax
authority itself will take.

**What it does and does not prove.** It proves every code the vocabulary keys on
is a code AEAT recognises, so a typo that lands on an unassigned pair, or a
territory code slipped into the country table, reds here. It does NOT prove the
code names the country written beside it: ``PY`` and ``PE`` are both recognised,
and swapping them would pass. That narrower claim is what the printed register
grounds, and the two together are stronger than either.

**The alpha-3 column is grounded elsewhere, and only for membership.** A sibling
gate checks it against the Facturae CountryType enumeration, bundled under
corpus/facturae/, which is the authority for what a Facturae document can state
and therefore the authority for why the column exists at all. So the column is
not author-supplied any more, and this file asserts only its structural
integrity because the substantive check is not its job.

**What no authority in this repository provides is the CORRESPONDENCE**, and
that is the residual the two gates share rather than a gap in either. This one
checks alpha-2 membership against the SII CountryType2; the sibling checks
alpha-3 membership against the Facturae CountryType; the two enumerations have
no overlap, so neither can say that the three-letter code names the same country
as the two-letter one written beside it. A consistent swap of two real pairs
survives both. Only the hand-check against AEAT's printed register speaks to
that, and it is an attestation rather than a check.

See Also:
    :func:`~domain.iva.country_code_for_stated_country_code`
        The consumer of the alpha-3 column this gate cannot ground.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import cast

import pytest

from ....core.resources.bundled_data import bundled_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: AEAT's SII record schema, bundled. The enumeration below is the country set
#: AEAT accepts on a submitted libro de registro, which makes it an authority on
#: this axis rather than a convenience list.
_SII_SCHEMA = ("corpus", "aeat_official", "einvoice_record_schemas", "sii", "SuministroInformacion.xsd")

_ALPHA3_LENGTH = 3


def _aeat_country_codes() -> frozenset[str]:
    """Return the alpha-2 codes AEAT's own SII schema enumerates."""
    text = Path(bundled_path(*_SII_SCHEMA)).read_text(encoding="utf-8", errors="replace")
    block = re.search(r'<simpleType name="CountryType2">(.*?)</simpleType>', text, re.S)
    assert block is not None, "AEAT's SII schema no longer declares CountryType2"
    return frozenset(cast(str, code) for code in re.findall(r'value="([A-Z]{2})"', block.group(1)))


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


def test_the_aeat_register_is_actually_populated() -> None:
    """Fixture anchor. An empty enumeration would satisfy every subset check below.

    This is the failure mode that makes a membership gate worthless: if the
    schema were renamed, restructured, or read as an empty match, ``issubset``
    over an empty set is trivially satisfied for an empty vocabulary and the gate
    would go quietly decorative.
    """
    codes = _aeat_country_codes()

    assert len(codes) > 200, len(codes)
    assert "ES" in codes


def test_every_vocabulary_code_is_one_aeat_recognises() -> None:
    """The substantive check: no invented, mistyped or territory code in the table."""
    recognised = _aeat_country_codes()
    unknown = sorted(str(record["code"]) for record in _vocabulary() if str(record["code"]) not in recognised)

    assert unknown == [], f"country codes AEAT's own register does not carry: {unknown}"


def test_the_gate_would_notice_a_code_aeat_does_not_carry() -> None:
    """Anti-vacuity control, and it is not hypothetical.

    ``IC`` is a real ISO-reserved code for the Canary Islands and is deliberately
    absent from AEAT's country enumeration, because it names a territory rather
    than a country. So a set that contained it would be caught -- which is what
    makes the assertion above a measurement rather than a formality.
    """
    assert "IC" not in _aeat_country_codes()
    assert "XX" not in _aeat_country_codes()


def test_the_alpha3_column_is_structurally_sound() -> None:
    """What CAN be asserted about the ungrounded column, stated as exactly that.

    Distinctness and shape only. No authority in this repository can confirm that
    ``PRY`` names Paraguay, so this deliberately does not claim to; a test that
    compared the column against a list an author wrote in the same session would
    be the tautology the column's own header warns about.
    """
    records = _vocabulary()
    codes = [str(record["alpha3"]) for record in records]

    assert all(len(code) == _ALPHA3_LENGTH and code.isalpha() and code.isupper() for code in codes)
    assert len(set(codes)) == len(codes), "two countries claim one alpha-3 code"
    assert len({str(record["code"]) for record in records}) == len(records), "one alpha-2 code appears twice"
