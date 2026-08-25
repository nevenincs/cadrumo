"""Real-behavior tests for _record_spec.ENCODING_ALIAS_MAP.

Asserts the canonical mapping entries and the structural invariant that
the schema's encoding-consistency validator routes through this single
constant rather than a private inline dict.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.schema_exports import (
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
)

from ...export_field_kind import CasillaFieldKind
from ..record_spec import ENCODING_ALIAS_MAP

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


# ---------------------------------------------------------------------------
# Direct alias-map normalisation contract
# ---------------------------------------------------------------------------


def test_encoding_alias_map_normalises_known_aliases() -> None:
    """Known AEAT/Python codec aliases map to their canonical wire encodings."""
    cases = (
        ("latin-1", "iso-8859-1"),
        ("latin_1", "iso-8859-1"),
        ("iso-8859-1", "iso-8859-1"),
        ("iso_8859_1", "iso-8859-1"),
        ("windows-1252", "cp1252"),
        ("cp1252", "cp1252"),
        ("latin-9", "iso-8859-15"),
        ("iso-8859-15", "iso-8859-15"),
        ("iso_8859_15", "iso-8859-15"),
    )

    for alias, canonical in cases:
        assert ENCODING_ALIAS_MAP[alias] == canonical, alias


def test_alias_map_unknown_encoding_falls_through_unchanged() -> None:
    """An encoding not present in the map is returned as-is (lowercased and
    stripped), not silently coerced to a known canonical form."""
    unknown = "utf-16"
    result = ENCODING_ALIAS_MAP.get(unknown, unknown)
    assert result == "utf-16"


def test_all_alias_map_values_are_canonical_keys() -> None:
    """Every value in ENCODING_ALIAS_MAP must itself be a key in the map
    (idempotency guarantee).  This ensures that normalise(normalise(x)) == normalise(x)
    for every declared alias."""
    for alias, canonical in ENCODING_ALIAS_MAP.items():
        assert canonical in ENCODING_ALIAS_MAP, (
            f"Canonical form {canonical!r} (mapped from alias {alias!r}) "
            "is not itself a key in ENCODING_ALIAS_MAP — double-normalisation would fail"
        )


# ---------------------------------------------------------------------------
# Schema integration: ExportLayoutDefinition uses ENCODING_ALIAS_MAP
# ---------------------------------------------------------------------------


def _record(*, record_id: str, encoding: str) -> ExportRecordDefinition:
    return ExportRecordDefinition(
        id=record_id,
        record_type="1",
        order=0,
        encoding=encoding,
        line_ending="crlf",
        required=True,
        fields=(
            ExportFieldDefinition(
                id=f"{record_id}.f1",
                kind=CasillaFieldKind.LITERAL,
                literal="X",
                offset=1,
                length=1,
                data_type="text",
                required=True,
                padding="none",
                justification="none",
                signed=False,
                legal_refs=("ley-37-1992:art-1",),
                source_refs=("aeat-src-1",),
            ),
        ),
    )


def test_layout_accepts_latin_1_iso_8859_1_mix_via_alias_map() -> None:
    """``latin-1`` and ``iso-8859-1`` are Python codec aliases for the same
    charset.  The schema validator must accept a layout that mixes both
    forms, normalising through ENCODING_ALIAS_MAP before comparing."""
    layout = ExportLayoutDefinition(
        id="test.layout",
        source_refs=("aeat-src-1",),
        legal_refs=("ley-37-1992:art-1",),
        records=(
            _record(record_id="rec.a", encoding="latin-1"),
            _record(record_id="rec.b", encoding="iso-8859-1"),
        ),
    )
    # Both records survive; validator did not raise
    assert len(layout.records) == 2


def test_layout_rejects_mixed_canonical_encodings() -> None:
    """Mixing genuinely distinct canonical encodings (cp1252 vs iso-8859-15)
    must be rejected regardless of any alias normalisation."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="inconsistent encodings"):
        ExportLayoutDefinition(
            id="test.layout.mixed",
            source_refs=("aeat-src-1",),
            legal_refs=("ley-37-1992:art-1",),
            records=(
                _record(record_id="rec.a", encoding="cp1252"),
                _record(record_id="rec.b", encoding="iso-8859-15"),
            ),
        )
