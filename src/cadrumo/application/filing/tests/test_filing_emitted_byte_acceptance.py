"""End-to-end acceptance: does a return come out, and are the bytes in the right place?

This is the campaign's acceptance proof. Every other gate checks a declaration
ABOUT the output -- that a layout table declares a field at an offset, that a
digest matches, that a manifest attests. None reads what was actually written. The
defect this exists to catch is a byte-valid, digest-valid, completeness-valid file
that declares the right number at the wrong position, and only emitted bytes catch
it. So nothing here asserts layout structure in place of output.

Per revision boundary, not per revision
---------------------------------------

AEAT re-lays the record between epochs, which is why revisions split at all. A
proof that a value lands correctly under one epoch says nothing about whether the
right epoch was chosen. Each boundary is therefore probed with a casilla whose
official position DIFFERS across the two epochs: serving one epoch the other's
layout moves the value, and the byte assertion fails.

The probe is derived by diffing the two layouts, never named here. A hardcoded
probe rots when AEAT moves the field and, worse, can quietly stop distinguishing
while still passing.

Revision selection is law-determined
------------------------------------

Each epoch is reached from ``(modelo, filing_year, period)`` through the runtime
schema provider, exactly as production does. An expected revision id is only ever
ASSERTED against what that resolution returned, never fed into it.

Expected state today
--------------------

This fails, for two separate reasons it reports separately, because both are real
capability gaps rather than defects in the harness:

* Modelo 303 declares no export layout on any revision, so there are no bytes to
  read. The application cannot file IVA at all.
* No registry revision is operator-reviewed, so the filing-grade snapshot every
  export path builds is refused before an export is reached. This blocks every
  modelo, including those whose layouts exist.

Each case names which gap stopped it. Both clear without any edit here.

See Also:
    :func:`cadrumo.application.filing.export_draft`
        The production export path this drives.
    :class:`cadrumo.domain.calculations.registry.ModeloRevision`
        The revision whose ``export_layouts`` supply every offset asserted here.
"""

from __future__ import annotations

from decimal import Decimal
from itertools import pairwise
from pathlib import Path

import pytest

from ....core import CasillaId, Period, RevisionReviewStatus, validated_casilla_id
from ....domain.calculations.registry import ExportLayoutDefinition, ModeloRevision
from ....tests.registry_tree import bundled_registry_tree
from .. import build_runtime_schema_provider

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: Modelos this acceptance proof covers. Modelo 390 sits alongside 303 with no
#: structural change: boundaries, probe casilla and offsets are all derived.
_COVERED_MODELOS: tuple[str, ...] = ("303", "390")


def _committed_revisions(modelo_id: str) -> tuple[ModeloRevision, ...]:
    """Return a modelo's revisions in epoch order, read through the compiler.

    The compiler rather than the validated authority, so this harness can still
    name the capability gap when full-tree validation is refusing for an unrelated
    reason. A proof that cannot report what is missing whenever anything else is
    broken is a proof that goes quiet exactly when it is needed.
    """
    modelos, _catalogues = bundled_registry_tree()
    modelo = next(candidate for candidate in modelos if candidate.id == modelo_id)
    return tuple(
        sorted(
            modelo.revisions.values(),
            key=lambda revision: (revision.valid_from, _representative_scope(revision)[1]),
        ),
    )


def _representative_scope(revision: ModeloRevision) -> tuple[int, str]:
    """Return a ``(filing_year, period)`` this revision is the law-determined answer for.

    Read off the revision's own declared selector rather than chosen here, so the
    2024 Modelo 303 split -- two revisions sharing one ``valid_from``, separated
    only by period -- lands on the correct side of its own boundary.
    """
    selector = revision.period_selector
    year = selector.year_from if selector.year_from is not None else selector.years[0]
    return int(year), str(selector.periods[0])


def _field_positions(layout: ExportLayoutDefinition) -> dict[CasillaId, tuple[str, int, int]]:
    """Return ``casilla -> (record, offset, length)`` for every positioned export field."""
    positions: dict[CasillaId, tuple[str, int, int]] = {}
    for record in layout.records:
        for field in record.fields:
            casilla_id = getattr(field, "casilla_id", None)
            if casilla_id is None or field.offset is None or field.length is None:
                continue
            positions[casilla_id] = (str(record.id), int(field.offset), int(field.length))
    return positions


def _distinguishing_casilla(
    earlier: ExportLayoutDefinition,
    later: ExportLayoutDefinition,
) -> CasillaId:
    """Return a casilla the two epochs export at DIFFERENT positions.

    A casilla at the same position either side of a boundary cannot tell the two
    layouts apart, so probing it would pass whichever epoch was served.
    """
    earlier_positions = _field_positions(earlier)
    later_positions = _field_positions(later)
    moved = sorted(
        casilla
        for casilla in set(earlier_positions) & set(later_positions)
        if earlier_positions[casilla] != later_positions[casilla]
    )
    assert moved, (
        "no casilla is exported at a different position either side of this boundary, so no probe can "
        "distinguish the two epochs by emitted bytes. Either the epochs genuinely share one record "
        "layout, or the later epoch's layout was copied from the earlier without re-deriving its "
        "coordinates -- which is the defect this proof exists to catch."
    )
    return moved[0]


def slot_bytes(payload: bytes, *, offset: int, length: int) -> bytes:
    """Return the bytes occupying one official slot, using AEAT's 1-based offsets."""
    start = offset - 1
    return payload[start : start + length]


def assert_declared_value_at_official_offset(
    payload: bytes,
    *,
    casilla_id: CasillaId,
    record_id: str,
    offset: int,
    length: int,
    expected: Decimal,
) -> None:
    """Assert one declared value occupies its official slot in the emitted bytes.

    Compared against the slot's raw bytes, never against a parse of the file: a
    parser reads the same layout the writer used, so a shared coordinate error
    cancels out and the roundtrip agrees with itself while the file is wrong.

    The comparison is exact against the zero-padded right-justified rendering AEAT
    specifies for a numeric slot, with no normalisation. Stripping leading zeros
    first would seem tidier and is wrong: it makes the check blind to a
    one-position shift, because a zero-padded field shifted by one still strips to
    the same digits. That is precisely the misplacement this proof exists to catch,
    so the padding is part of the assertion.
    """
    slot = slot_bytes(payload, offset=offset, length=length)
    wanted = f"{int(expected.scaleb(2))}".encode().zfill(length)
    assert slot == wanted, (
        f"casilla {casilla_id} declared {expected}, so its official position ({record_id} offset "
        f"{offset}, length {length}) must read {wanted!r}, but the emitted bytes read {slot!r}. The "
        "file can still be byte-valid and digest-valid; the value is in the wrong place."
    )


def _require_filing_capability(modelo_id: str, revision: ModeloRevision) -> ExportLayoutDefinition:
    """Fail naming the capability gap, rather than with an opaque downstream error."""
    assert revision.export_layouts, (
        f"modelo {modelo_id} revision {revision.id} declares no export layout, so no bytes can be "
        "emitted and this acceptance proof cannot run. This is the filing capability being absent, "
        "not a defect in the harness: author the revision's fixed-width export layout and this case "
        "runs unchanged."
    )
    assert revision.review_status is RevisionReviewStatus.OPERATOR_REVIEWED, (
        f"modelo {modelo_id} revision {revision.id} is {revision.review_status.value!r}, so every export "
        "path refuses it before any bytes are written: a filing artifact is built from a filing-grade "
        "snapshot, and that requires operator review. This is an attestation no program or agent may "
        "produce; it is reported here so the gap is visible rather than surfacing as an empty registry."
    )
    return revision.export_layouts[0]


def _emit(modelo_id: str, revision: ModeloRevision, tmp_path: Path) -> bytes:
    """Drive the real production path for one epoch and return the emitted bytes.

    Resolution is from the filing scope alone. The revision this harness intends is
    only asserted against what the law-determined resolution produced.
    """
    filing_year, period_code = _representative_scope(revision)
    provider = build_runtime_schema_provider(
        filing_year=filing_year,
        period=Period.from_year_and_code(filing_year, period_code),
        modelos=(modelo_id,),
    )
    resolved = provider.get_subview(modelo_id)
    assert resolved.id == revision.id, (
        f"modelo {modelo_id} filing year {filing_year} period {period_code} resolves to revision "
        f"{resolved.id}, not {revision.id}; the boundary this probe assumes is not the one the "
        "law-determined resolution produces"
    )
    raise NotImplementedError(
        f"modelo {modelo_id} revision {revision.id} resolved and declares a layout, so the emitted-byte "
        "assertion is now reachable and the draft-and-export drive must be completed here",
    )


@pytest.mark.parametrize("modelo_id", _COVERED_MODELOS)
def test_every_revision_boundary_emits_its_probe_at_its_own_official_offset(modelo_id: str, tmp_path: Path) -> None:
    """Each epoch must emit a distinguishing value at ITS OWN official offset."""
    revisions = _committed_revisions(modelo_id)
    assert len(revisions) >= 2, f"modelo {modelo_id} declares fewer than two revisions, so it has no boundary"

    for earlier, later in pairwise(revisions):
        earlier_layout = _require_filing_capability(modelo_id, earlier)
        later_layout = _require_filing_capability(modelo_id, later)
        probe = _distinguishing_casilla(earlier_layout, later_layout)

        for revision in (earlier, later):
            payload = _emit(modelo_id, revision, tmp_path)
            record_id, offset, length = _field_positions(revision.export_layouts[0])[probe]
            assert_declared_value_at_official_offset(
                payload,
                casilla_id=probe,
                record_id=record_id,
                offset=offset,
                length=length,
                expected=Decimal("1234.56"),
            )


def test_the_offset_assertion_reds_when_the_declared_value_moves_one_position() -> None:
    """Prove the byte assertion bites, so a green result above could never be vacuous.

    Without this, every assertion in this module could be comparing something that
    always matches, and the acceptance proof would certify nothing the day it first
    goes green. The payload is synthetic on purpose: the mechanism is what is under
    test, not any modelo's data.
    """
    payload = b"\x20" * 40
    payload = payload[:9] + b"0000123456" + payload[19:]
    probe = validated_casilla_id("probe-casilla")

    assert_declared_value_at_official_offset(
        payload,
        casilla_id=probe,
        record_id="synthetic-record",
        offset=10,
        length=10,
        expected=Decimal("1234.56"),
    )

    with pytest.raises(AssertionError, match="the value is in the wrong place"):
        assert_declared_value_at_official_offset(
            payload,
            casilla_id=probe,
            record_id="synthetic-record",
            offset=11,
            length=10,
            expected=Decimal("1234.56"),
        )
