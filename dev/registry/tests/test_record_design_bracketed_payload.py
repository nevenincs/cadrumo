"""Development-only: a record's opaque payload region is accounted for, and only when it is opaque.

Some AEAT records wrap a block of content between two constant rows and then
describe what sits between them in PROSE instead of numbering it. Modelo 200's
2010 orden edition is the worked case: ``Constante "<VECTOR>"`` occupies 329-336
and ``Constante "</VECTOR>"`` occupies 637-645, and the 300 bytes between them
are described as "Vector de páginas ... y el resto a blancos hasta completar las
300 posiciones".

Contiguity read that as a 300-byte hole and reported the record as partly read.
That is wrong in the way that matters most for this checker: it is
indistinguishable from the dropped-row defect the check exists to catch, so a
genuine reader bug in such a record would have hidden behind an expected
complaint.

The span comes from the two markers' own declared offsets, never from parsing
the prose -- which is what makes it reading rather than invention. The prose
agrees exactly (337 to 636 is 300 positions) and is corroboration only.

THE NARROWING IS THE POINT. Crediting a bracket unconditionally would let a
genuinely dropped row hide between two markers. So a bracket earns its region
only when the design numbers NOTHING inside it. Modelo 200's structural
``<AUX>`` wrapper numbers five rows inside itself and is therefore not credited
-- it does not need to be, since those rows already tile it.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.record_design_schema import RecordDesignField, RecordDesignSheet

from ..compiler.record_design_pdf_state import contiguity_failure

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _field(offset: int, length: int, description: str) -> RecordDesignField:
    return RecordDesignField(
        sheet="body",
        row=offset,
        offset=offset,
        length=length,
        type_code="An",
        description=description,
    )


def _opaque_payload_sheet() -> RecordDesignSheet:
    return RecordDesignSheet(
        name="body",
        fields=(
            _field(1, 8, 'Constante "<VECTOR>"'),
            _field(309, 9, 'Constante "</VECTOR>"'),
        ),
        total_positions=317,
    )


def test_a_record_whose_only_hole_is_an_opaque_payload_reads_whole() -> None:
    assert contiguity_failure(_opaque_payload_sheet()) is None
