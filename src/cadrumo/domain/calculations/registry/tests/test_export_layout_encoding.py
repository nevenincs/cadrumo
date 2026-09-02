"""Encoding-consistency invariant on ExportLayoutDefinition.

A fichero-BOE export layout publishes one wire encoding per
modelo-year per AEAT's published spec; mixing encodings across the
records inside a single layout would produce a payload no single
decoder can faithfully re-parse. The encoding vocabulary carries one member per charset, so a record
declares the canonical spelling and an alias is refused at the field.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from .....core.export_layout_format import ExportLayoutFormat
from ...export_field_kind import CasillaFieldKind
from ..authority import bundled_authority
from ..fixed_width_codec import ExportEncoding
from ..schema_exports import ExportFieldDefinition, ExportLayoutDefinition, ExportRecordDefinition

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
                legal_refs=("ley-37-1992:art-1",),
                source_refs=("aeat-src-1",),
            ),
        ),
    )


def test_layout_with_one_encoding_validates() -> None:
    """A single declared encoding is the trivial happy path."""

    layout = ExportLayoutDefinition(
        id="layout.single",
        format=ExportLayoutFormat.FIXED_WIDTH,
        source_refs=("aeat-src-1",),
        legal_refs=("ley-37-1992:art-1",),
        records=(
            _record(record_id="record.a", encoding="iso-8859-1"),
            _record(record_id="record.b", encoding="iso-8859-1"),
        ),
    )
    assert layout.records[0].encoding == "iso-8859-1"


def test_layout_refuses_the_retired_alias_spelling() -> None:
    """The alias is no longer representable at the field, so the layout refuses it.

    It once was, and the validator folded it together with the canonical spelling
    before comparing records. Collapsing the encoding vocabulary onto one member per
    charset retired that tolerance deliberately: a value with two spellings is a value
    with two definitions, and the fold was the compensating construct that made the
    duplication survivable. Tolerance still exists where author input is first read --
    the export-tree generator validates a raw token against the alias map before
    writing a canonical one -- which is the boundary that should carry it.
    """
    with pytest.raises(ValidationError):
        ExportLayoutDefinition(
            id="layout.aliased",
            format=ExportLayoutFormat.FIXED_WIDTH,
            source_refs=("aeat-src-1",),
            legal_refs=("ley-37-1992:art-1",),
            records=(
                _record(record_id="record.a", encoding="latin-1"),
                _record(record_id="record.b", encoding="iso-8859-1"),
            ),
        )


def test_layout_with_mixed_canonical_encodings_rejected() -> None:
    """Mixing cp1252 with iso-8859-15 is a genuine inconsistency — rejected."""

    with pytest.raises(ValidationError, match="inconsistent encodings"):
        ExportLayoutDefinition(
            id="layout.mixed",
            format=ExportLayoutFormat.FIXED_WIDTH,
            source_refs=("aeat-src-1",),
            legal_refs=("ley-37-1992:art-1",),
            records=(
                _record(record_id="record.a", encoding="cp1252"),
                _record(record_id="record.b", encoding="iso-8859-15"),
            ),
        )


def test_xml_dictionary_layout_skips_record_encoding_check() -> None:
    """XML-dictionary layouts have no record-level encoding to validate."""

    layout = ExportLayoutDefinition(
        id="layout.xml",
        format=ExportLayoutFormat.XML_DICTIONARY,
        dictionary_source_ref="aeat-dict-1",
        source_refs=("aeat-dict-1",),
        legal_refs=("ley-37-1992:art-1",),
        records=(),
        # Mandatory on this format: AEAT declares the Aux block first in every
        # declaration and no dictionary describes it, so the layout must.
        aux_idioma="E",
    )
    assert layout.format is ExportLayoutFormat.XML_DICTIONARY


def test_the_stored_token_hydrates_to_its_member() -> None:
    """A manifest's canonical token still becomes the member it names."""
    layout = ExportLayoutDefinition(
        id="layout.hydrated",
        format="fixed_width",  # reason: passing the raw on-disk token is what this asserts
        source_refs=("aeat-src-1",),
        legal_refs=("ley-37-1992:art-1",),
        records=(_record(record_id="record.a", encoding="iso-8859-1"),),
    )

    assert layout.records[0].encoding is ExportEncoding.ISO_8859_1


def test_an_unrecognised_export_format_token_is_refused_naming_the_accepted_set() -> None:
    """The refusal the closed set buys, at the boundary rather than downstream.

    Under the retired bare ``Literal`` an unknown token was refused too, with a
    message naming the literal's members. What the enum adds is a single home the
    accepted set is read from, so the refusal and every consumer branch cannot
    drift apart. The accepted values are asserted to be IN the message because a
    refusal that does not say what it wanted sends an author back to the source.
    """
    with pytest.raises(ValidationError) as refusal:
        ExportLayoutDefinition(
            id="layout.bad",
            format="fichero_boe",  # reason: passing the raw on-disk token is what this asserts
            source_refs=("aeat-src-1",),
            legal_refs=("ley-37-1992:art-1",),
            records=(),
        )

    message = str(refusal.value)
    assert "fichero_boe" in message
    for member in ExportLayoutFormat:
        assert member.value in message


def test_the_bundled_registry_hydrates_every_layout_format_to_a_member() -> None:
    """Every declared layout in the real tree carries a member, not a string.

    Asserted on ``type(...) is`` rather than on equality, because a
    :class:`~enum.StrEnum` member compares and hashes equal to its own value: a
    field that stayed a plain string would satisfy every ``==`` and every ``in``
    check in this suite. The identity of the TYPE is the only assertion that
    moves when the lift is undone.

    The member coverage is asserted too, so this cannot pass by examining a tree
    with no layouts, or one that happens to declare only one shape.
    """
    authority = bundled_authority()
    formats = [
        layout.format
        for modelo in authority.modelos
        for revision in modelo.revisions.values()
        for layout in revision.export_layouts
    ]

    assert formats, "the bundled registry must declare export layouts, or this proves nothing"
    assert all(type(item) is ExportLayoutFormat for item in formats)
    assert set(formats) == set(ExportLayoutFormat), "both declared shapes must be exercised by the real tree"
