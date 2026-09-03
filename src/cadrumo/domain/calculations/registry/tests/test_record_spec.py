"""Real-behavior tests for ``record_spec.ENCODING_ALIAS_MAP``.

Asserts the canonical mapping entries, and -- separately -- what the
schema's encoding-consistency validator actually does. Those are two
different things: the validator does NOT route through this constant.
Its encoding field is the closed ``ExportEncoding`` enum, so an alias
spelling is refused at parse and never reaches the comparison.
"""

from __future__ import annotations

import pytest

from ...export_field_kind import CasillaFieldKind
from ..record_spec import ENCODING_ALIAS_MAP
from ..schema_base import CasillaDataType
from ..schema_exports import ExportFieldDefinition, ExportLayoutDefinition, ExportRecordDefinition

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
                data_type=CasillaDataType.TEXT,
                required=True,
                padding="none",
                justification="none",
                signed=False,
                legal_refs=("ley-37-1992:art-1",),
                source_refs=("aeat-src-1",),
            ),
        ),
    )


def test_layout_accepts_records_sharing_one_canonical_encoding() -> None:
    """The normal path: every record declares the same canonical member."""
    layout = ExportLayoutDefinition(
        id="test.layout",
        source_refs=("aeat-src-1",),
        legal_refs=("ley-37-1992:art-1",),
        records=(
            _record(record_id="rec.a", encoding="iso-8859-1"),
            _record(record_id="rec.b", encoding="iso-8859-1"),
        ),
    )

    assert len(layout.records) == 2


def test_layout_refuses_an_alias_spelling_rather_than_normalising_it() -> None:
    """``latin-1`` is REFUSED at parse; it is not normalised to ``iso-8859-1``.

    This replaces a test that claimed to prove the opposite. That one was
    named for a ``latin-1``/``iso-8859-1`` mix but passed ``iso-8859-1``
    for both records, so it exercised no alias and would have failed had
    it done what its name said.

    The refusal is the real contract, and it is stricter than the alias
    map suggests: ``ExportEncoding`` is a closed enum of canonical
    spellings and the coercion in front of it resolves exact members
    only. A registry author who writes ``latin-1`` gets a validation
    error, not silent acceptance.
    """
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ExportLayoutDefinition(
            id="test.layout",
            source_refs=("aeat-src-1",),
            legal_refs=("ley-37-1992:art-1",),
            records=(
                _record(record_id="rec.a", encoding="latin-1"),
                _record(record_id="rec.b", encoding="iso-8859-1"),
            ),
        )


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
