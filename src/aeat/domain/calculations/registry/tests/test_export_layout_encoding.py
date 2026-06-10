"""Encoding-consistency invariant on ExportLayoutDefinition.

A fichero-BOE export layout publishes one wire encoding per
modelo-year per AEAT's published spec; mixing encodings across the
records inside a single layout would produce a payload no single
decoder can faithfully re-parse. ``latin-1`` and ``iso-8859-1`` are
Python codec aliases for the same charset — the validator normalises
them before comparison so the alias mix is accepted as consistent.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ..._export_field_kind import CasillaFieldKind
from .._schema import (
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _record(*, record_id: str, encoding: str) -> ExportRecordDefinition:
    return ExportRecordDefinition(
        id=record_id,
        record_type="record",
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
                legal_refs=("liva.art-1",),
                source_refs=("aeat.src.1",),
            ),
        ),
    )


def test_layout_with_one_encoding_validates() -> None:
    """A single declared encoding is the trivial happy path."""

    layout = ExportLayoutDefinition(
        id="layout.single",
        format="fixed_width",
        source_refs=("aeat.src.1",),
        legal_refs=("liva.art-1",),
        records=(
            _record(record_id="record.a", encoding="iso-8859-1"),
            _record(record_id="record.b", encoding="iso-8859-1"),
        ),
    )
    assert layout.records[0].encoding == "iso-8859-1"


def test_layout_with_alias_encodings_validates() -> None:
    """``latin-1`` and ``iso-8859-1`` are codec aliases — accepted as consistent."""

    layout = ExportLayoutDefinition(
        id="layout.aliased",
        format="fixed_width",
        source_refs=("aeat.src.1",),
        legal_refs=("liva.art-1",),
        records=(
            _record(record_id="record.a", encoding="latin-1"),
            _record(record_id="record.b", encoding="iso-8859-1"),
        ),
    )
    # Both records survive; the validator normalises through the
    # alias map so the mix is treated as consistent.
    assert tuple(r.encoding for r in layout.records) == ("latin-1", "iso-8859-1")


def test_layout_with_mixed_canonical_encodings_rejected() -> None:
    """Mixing cp1252 with iso-8859-15 is a genuine inconsistency — rejected."""

    with pytest.raises(ValidationError, match="inconsistent encodings"):
        ExportLayoutDefinition(
            id="layout.mixed",
            format="fixed_width",
            source_refs=("aeat.src.1",),
            legal_refs=("liva.art-1",),
            records=(
                _record(record_id="record.a", encoding="cp1252"),
                _record(record_id="record.b", encoding="iso-8859-15"),
            ),
        )


def test_xml_dictionary_layout_skips_record_encoding_check() -> None:
    """XML-dictionary layouts have no record-level encoding to validate."""

    layout = ExportLayoutDefinition(
        id="layout.xml",
        format="xml_dictionary",
        dictionary_source_ref="aeat.dict.1",
        source_refs=("aeat.dict.1",),
        legal_refs=("liva.art-1",),
        records=(),
    )
    assert layout.format == "xml_dictionary"
