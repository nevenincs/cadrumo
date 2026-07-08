"""Parity gate: the live TOML parser must reproduce known-correct registry values.

:func:`aeat.core.read_toml` was swapped from stdlib :mod:`tomllib` to the
Rust-backed :mod:`rtoml`. This test does NOT compare the
parser's output against itself or against a second parser's output (either
shape would pass even if both parsers silently agreed on a WRONG value); it
asserts the CURRENTLY WIRED parser reproduces expected values hand-derived
directly from reading the real, committed registry source files, independent
of any parser invocation. If a future change (a parser swap, a parser
upgrade, a coercion regression) makes ``read_toml``/``parse_toml_text``
diverge from what these real fragments actually declare, this test fails.

The two fixtures are chosen to exercise the value shapes a type-coercion
regression would most plausibly corrupt: a top-level table with string arrays
(``036/manifest.toml``), and a nested table keyed by a quoted string,
carrying a local TOML date, an inline table, a nested integer, and a nested
string array (``036``'s ``2025-02-03-y-siguientes`` revision fragment).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from .. import parse_toml_text, read_toml

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REGISTRY_ROOT = Path(__file__).resolve().parents[2] / "_data" / "registry" / "aeat" / "modelos" / "036"

_MANIFEST_PATH = _REGISTRY_ROOT / "manifest.toml"
_REVISION_PATH = _REGISTRY_ROOT / "revisions" / "2025-02-03-y-siguientes" / "revision.toml"

# Hand-derived directly from reading src/aeat/_data/registry/aeat/modelos/036/manifest.toml.
_EXPECTED_MANIFEST: dict[str, object] = {
    "modelo": {
        "id": "036",
        "title": "Censo de empresarios, profesionales y retenedores",
        "official_name": (
            "Modelo 036. Declaración censal de alta, modificación y baja en el "
            "Censo de empresarios, profesionales y retenedores."
        ),
        "tax_domain": "censo",
        "cadence": "ad_hoc",
        "jurisdiction": "ES-AEAT",
        "output_sensitivity": "identity",
        "legal_refs": [
            "rd-1065-2007:art-9",
            "rd-1065-2007:art-10",
            "rd-1065-2007:art-11",
            "orden-eha-1274-2007:art-1",
            "orden-eha-1274-2007:art-2",
            "orden-hac-1526-2024:art-1",
            "orden-hac-1526-2024:df-unica",
        ],
        "source_refs": [
            "aeat-dr-036-2025",
            "aeat-modelo-036-procedure",
        ],
    },
}

# Hand-derived directly from reading
# src/aeat/_data/registry/aeat/modelos/036/revisions/2025-02-03-y-siguientes/revision.toml.
_EXPECTED_REVISION: dict[str, object] = {
    "revisions": {
        "2025-02-03-y-siguientes": {
            "label": "Modelo 036 desde 3 de febrero de 2025",
            "valid_from": date(2025, 2, 3),
            "period_selector": {
                "year_from": 2025,
                "periods": ["alta", "modificacion", "baja"],
            },
            "legal_refs": [
                "rd-1065-2007:art-9",
                "rd-1065-2007:art-10",
                "rd-1065-2007:art-11",
                "orden-eha-1274-2007:art-1",
                "orden-eha-1274-2007:art-2",
                "orden-hac-1526-2024:art-1",
                "orden-hac-1526-2024:df-unica",
            ],
            "orden_aplicabilidad": [
                "orden-eha-1274-2007:art-1",
                "orden-hac-1526-2024:art-1",
                "orden-hac-1526-2024:df-unica",
            ],
            "source_refs": [
                "aeat-dr-036-2025",
                "aeat-modelo-036-procedure",
            ],
        },
    },
}


def test_read_toml_reproduces_known_manifest_values() -> None:
    """``read_toml`` on the real M036 manifest matches hand-derived expected values."""
    assert _MANIFEST_PATH.is_file(), f"fixture moved or renamed: {_MANIFEST_PATH}"
    parsed = read_toml(_MANIFEST_PATH, error_factory=ValueError)
    assert parsed == _EXPECTED_MANIFEST


def test_read_toml_reproduces_known_revision_values_including_date_and_inline_table() -> None:
    """``read_toml`` on the real M036 revision fragment matches hand-derived expected values.

    Exercises the value shapes a parser-swap regression would most plausibly
    corrupt: a quoted-string table key, a local TOML date (must parse to
    ``datetime.date``, not a string or ``datetime.datetime``), and an inline
    table carrying a nested integer and a nested string array.
    """
    assert _REVISION_PATH.is_file(), f"fixture moved or renamed: {_REVISION_PATH}"
    parsed = read_toml(_REVISION_PATH, error_factory=ValueError)
    assert parsed == _EXPECTED_REVISION

    revision = parsed["revisions"]["2025-02-03-y-siguientes"]  # type: ignore[index]
    valid_from = revision["valid_from"]
    assert isinstance(valid_from, date)
    assert not hasattr(valid_from, "hour"), "valid_from must be a local date, not a datetime"


def test_parse_toml_text_reproduces_known_revision_values_from_the_same_bytes() -> None:
    """``parse_toml_text`` (the in-memory sibling) parses the same real bytes identically.

    Pins the two parse entry points (:func:`read_toml`, :func:`parse_toml_text`)
    to agree, using the SAME real registry fragment and the SAME hand-derived
    expected values as the file-path test above -- not a second parser's
    output, and not each other's.
    """
    text = _REVISION_PATH.read_text(encoding="utf-8")
    parsed = parse_toml_text(text, error_factory=ValueError)
    assert parsed == _EXPECTED_REVISION
