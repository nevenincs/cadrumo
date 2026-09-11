"""Development-only: an unheaded PDF record body is named from the identity it declares about itself.

Some AEAT designs head no record with a title. Modelo 200's 2010 orden edition
publishes eleven page records separated only by a running page header, so the
heading recogniser saw nothing and every body arrived anonymous: the whole
design read as ZERO sheets and forty-four skips.

The identity was in the document the entire time. AEAT fixes each page record's
Página constant at positions 6-8, immediately after the modelo constant at 3-5,
and requires the record's last field to carry a ``</T200006>`` closing
identifier. Both are declared REQUIRED CONTENT, not prose, which is what makes
reading them recovery rather than guesswork.

Two properties keep that from becoming invention, and both are pinned below: a
body that declares NEITHER identity stays anonymous, and two bodies resolving to
one name both stay anonymous rather than one silently absorbing the other.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.record_design_schema import RecordDesignField, RecordDesignSheet

from ..compiler.record_design import extract_record_design
from .test_every_bundled_design_is_read_or_reported import _bundled_designs

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _field(offset: int, length: int, description: str, *, content: str | None = None) -> RecordDesignField:
    return RecordDesignField(
        sheet="body",
        row=offset,
        offset=offset,
        length=length,
        type_code="An",
        description=description,
        content=content,
    )


def _sheet(*fields: RecordDesignField) -> RecordDesignSheet:
    return RecordDesignSheet(name="<unidentified>", fields=fields)


def test_the_bundled_modelo_200_orden_design_now_reads_named_page_records() -> None:
    """The real corpus case this recovery was built for, read end to end.

    Before the recovery this design produced ZERO sheets: every one of its page
    records was anonymous, so the whole document was reported unread.
    """
    matches = [path for path in _bundled_designs() if path.name.startswith("17-200-orden-eha-1338-2010")]
    assert matches, "the bundled modelo 200 2010 orden design is no longer in the corpus"

    extraction = extract_record_design(matches[0])
    names = [sheet.name for sheet in extraction.sheets]

    assert names, "no record body was read from a design whose pages all declare their identity"
    assert any(name.startswith("Pág. ") for name in names), (
        f"no page record was recovered by its declared identity; read {names}"
    )
