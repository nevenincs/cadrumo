"""Development-only source metadata for AEAT record-design extraction."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from pydantic import TypeAdapter, ValidationError

from cadrumo.core.external_constants import UTF_8_ENCODING
from cadrumo.core.resources.bundled_data import resolve_data_root_copies
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.record_design_schema import (
    RecordDesignCorrection,
    RecordDesignFieldTypeCorrection,
    RecordDesignHeaderCellCorrection,
    RecordDesignRangeStartCorrection,
    RecordDesignSinglePositionCorrection,
)

type TypeCorrectionIndex = Mapping[tuple[str, int], RecordDesignFieldTypeCorrection]
type HeaderCorrectionIndex = Mapping[tuple[str, int, str], RecordDesignHeaderCellCorrection]
type SinglePositionCorrectionIndex = Mapping[tuple[str, int], RecordDesignSinglePositionCorrection]
type _RangeStartCorrectionIndex = Mapping[tuple[str, int], RecordDesignRangeStartCorrection]

EMPTY_HEADER_CORRECTIONS: Final[HeaderCorrectionIndex] = dict[tuple[str, int, str], RecordDesignHeaderCellCorrection]()

_CORRECTION_SUFFIX: Final[str] = ".record-design-correction.json"
_CORRECTION_ADAPTER: Final[TypeAdapter[RecordDesignCorrection]] = TypeAdapter(RecordDesignCorrection)
#: A parsed JSON object, typed at the boundary rather than left as the bare
#: ``Any`` ``json.loads`` returns -- every sidecar loader below validates its
#: top-level shape and each list entry through this one adapter.
_JSON_OBJECT_ADAPTER: Final[TypeAdapter[dict[str, object]]] = TypeAdapter(dict[str, object])
#: A parsed JSON array, typed the same way as :data:`_JSON_OBJECT_ADAPTER` for
#: the same reason -- an ``isinstance(value, list)`` narrows a bare ``object``
#: to a still-unparameterised ``list``, and this validates AND types it.
_JSON_ARRAY_ADAPTER: Final[TypeAdapter[list[object]]] = TypeAdapter(list[object])


def _load_annotation_entries(path: Path, field_name: str, error_message: str) -> list[object]:
    """Decode one annotation document and return its required JSON list."""
    try:
        payload = _JSON_OBJECT_ADAPTER.validate_python(json.loads(path.read_text(encoding=UTF_8_ENCODING)))
    except ValidationError as exc:
        raise RegistryValidationError(f"{path}: {error_message}") from exc
    try:
        return _JSON_ARRAY_ADAPTER.validate_python(payload.get(field_name))
    except ValidationError as exc:
        raise RegistryValidationError(f"{path}: {error_message}") from exc


def _resolve_annotation(path: Path) -> Path | None:
    """Locate one record-design annotation across every installed data root.

    An annotation here is hand-authored grounding that means nothing on its own:
    a correction sidecar names a blank cell in ONE binary, and a declared
    non-record sheet names a tab in ONE modelo's designs. Its position is
    therefore expressed relative to the binary it annotates -- and that is
    exactly what a plain sibling read cannot survive, because the distribution
    split is by file suffix rather than by directory. The binaries ship in the
    ``cadrumo_data`` companions while these declarations stay in the
    command-bearing tree, so an installed cohort resolves the binary under one
    root and the annotation under another. Reading the annotation from the
    binary's own root alone finds nothing, and finding nothing is
    indistinguishable from the ordinary case of no annotation being authored --
    the design then reports a partial read for a packaging reason, with nothing
    saying so.

    Resolution therefore spans the roots rather than the directory. What it will
    not do is pick a winner: an annotation published with different content
    under two roots is a split that has gone wrong in the other direction, and
    silently preferring either copy would decide a grounding question by
    installation order.

    Args:
        path: Where the annotation sits relative to the file it annotates, in
            whichever root that file resolved under.

    Returns:
        The readable copy, or ``None`` when no root carries one -- which stays
        the ordinary "no annotation was authored" answer that leaves the
        parser's behaviour unchanged.

    Raises:
        RegistryValidationError: Two or more roots carry the annotation with
            differing content.
    """
    copies = resolve_data_root_copies(path)
    if not copies:
        return None
    chosen, *others = copies
    payload = chosen.read_bytes()
    divergent = [other for other in others if other.read_bytes() != payload]
    if divergent:
        locations = ", ".join(str(item) for item in divergent)
        raise RegistryValidationError(
            f"{path.name}: this record-design annotation is published with differing content under "
            f"more than one installed data root ({chosen} and {locations}); the annotated design has "
            "one grounding, so resolve the divergence at the source rather than letting installation "
            "order choose which correction applies",
        )
    return chosen


@dataclass(frozen=True)
class CorrectionIndex:
    """One binary's declared corrections, split by the row they address.

    ``type_corrections`` keys on ``(sheet, source_row)`` -- one data row.
    ``header_corrections`` keys on ``(sheet, header_row, column_role)`` -- one
    header column, since a header row's blank cell is looked up by ROLE
    (``"length"``) at probe time, not by a data row number.
    ``single_position_corrections`` keys on ``(sheet, position)`` -- one PDF row
    that was never read, so it has no source row to be keyed by.
    """

    type_corrections: TypeCorrectionIndex
    header_corrections: HeaderCorrectionIndex
    single_position_corrections: SinglePositionCorrectionIndex = field(
        default_factory=dict[tuple[str, int], RecordDesignSinglePositionCorrection],
    )
    #: Keys on ``(sheet, declared_start)`` -- the start AEAT printed, which is
    #: what identifies the row being corrected.
    range_start_corrections: _RangeStartCorrectionIndex = field(
        default_factory=dict[tuple[str, int], RecordDesignRangeStartCorrection],
    )


EMPTY_CORRECTIONS: Final[CorrectionIndex] = CorrectionIndex(
    type_corrections={},
    header_corrections={},
    single_position_corrections={},
    range_start_corrections={},
)


def _store_type_correction(
    corrections: dict[tuple[str, int], RecordDesignFieldTypeCorrection],
    correction: RecordDesignFieldTypeCorrection,
    sidecar_path: Path,
) -> None:
    """Store a field-type correction, rejecting a repeated source row."""
    key = (correction.sheet, correction.source_row)
    if key in corrections:
        raise RegistryValidationError(
            f"{sidecar_path}: duplicate type correction for sheet {correction.sheet!r} row {correction.source_row}",
        )
    corrections[key] = correction


def _store_range_start_correction(
    corrections: dict[tuple[str, int], RecordDesignRangeStartCorrection],
    correction: RecordDesignRangeStartCorrection,
    sidecar_path: Path,
) -> None:
    """Store a range-start correction, rejecting a repeated declared start."""
    key = (correction.sheet, correction.declared_start)
    if key in corrections:
        raise RegistryValidationError(
            f"{sidecar_path}: duplicate range-start correction for sheet "
            f"{correction.sheet!r} start {correction.declared_start}",
        )
    corrections[key] = correction


def _store_single_position_correction(
    corrections: dict[tuple[str, int], RecordDesignSinglePositionCorrection],
    correction: RecordDesignSinglePositionCorrection,
    sidecar_path: Path,
) -> None:
    """Store a single-position correction, rejecting a repeated PDF position."""
    key = (correction.sheet, correction.position)
    if key in corrections:
        raise RegistryValidationError(
            f"{sidecar_path}: duplicate single-position correction for sheet "
            f"{correction.sheet!r} position {correction.position}",
        )
    corrections[key] = correction


def _store_header_correction(
    corrections: dict[tuple[str, int, str], RecordDesignHeaderCellCorrection],
    correction: RecordDesignHeaderCellCorrection,
    sidecar_path: Path,
) -> None:
    """Store a header correction, rejecting a repeated header role."""
    key = (correction.sheet, correction.header_row, correction.column_role)
    if key in corrections:
        raise RegistryValidationError(
            f"{sidecar_path}: duplicate header correction for sheet {correction.sheet!r} "
            f"row {correction.header_row} role {correction.column_role!r}",
        )
    corrections[key] = correction


def _index_correction(
    type_corrections: dict[tuple[str, int], RecordDesignFieldTypeCorrection],
    header_corrections: dict[tuple[str, int, str], RecordDesignHeaderCellCorrection],
    single_position_corrections: dict[tuple[str, int], RecordDesignSinglePositionCorrection],
    range_start_corrections: dict[tuple[str, int], RecordDesignRangeStartCorrection],
    correction: RecordDesignCorrection,
    sidecar_path: Path,
) -> None:
    """Route one validated correction to its kind-specific index."""
    if isinstance(correction, RecordDesignFieldTypeCorrection):
        _store_type_correction(type_corrections, correction, sidecar_path)
    elif isinstance(correction, RecordDesignRangeStartCorrection):
        _store_range_start_correction(range_start_corrections, correction, sidecar_path)
    elif isinstance(correction, RecordDesignSinglePositionCorrection):
        _store_single_position_correction(single_position_corrections, correction, sidecar_path)
    else:
        _store_header_correction(header_corrections, correction, sidecar_path)


def _correction_index(entries: list[object], sidecar_path: Path) -> CorrectionIndex:
    """Validate and index all entries from one correction sidecar."""
    type_corrections: dict[tuple[str, int], RecordDesignFieldTypeCorrection] = {}
    header_corrections: dict[tuple[str, int, str], RecordDesignHeaderCellCorrection] = {}
    single_position_corrections: dict[tuple[str, int], RecordDesignSinglePositionCorrection] = {}
    range_start_corrections: dict[tuple[str, int], RecordDesignRangeStartCorrection] = {}
    for entry in entries:
        # ``strict=False`` here only: JSON has no tuple literal, so the sidecar's
        # ``editions_read`` array arrives as a ``list`` and needs the ordinary
        # list-to-tuple coercion. Every field's own type is still checked --
        # this does not relax ``min_length``, blank-string, discriminator, or shape checks.
        correction = _CORRECTION_ADAPTER.validate_python(entry, strict=False)
        _index_correction(
            type_corrections,
            header_corrections,
            single_position_corrections,
            range_start_corrections,
            correction,
            sidecar_path,
        )
    return CorrectionIndex(
        type_corrections=type_corrections,
        header_corrections=header_corrections,
        single_position_corrections=single_position_corrections,
        range_start_corrections=range_start_corrections,
    )


def load_corrections(source_path: Path) -> CorrectionIndex:
    """Load a hand-authored, per-binary sidecar declaring record-design corrections.

    Colocated with the exact source binary it corrects, named
    ``<binary-name>.record-design-correction.json`` -- a distinct suffix from
    the parser's own generated ``.extracted.json``/``.extracted.md`` cache, so
    a hand-authored grounding declaration is never confused with, or
    overwritten by, machine output. Absent for the overwhelming majority of
    bundled binaries, which read as AEAT published them; this returns empty
    indexes for those, so the parser's behaviour is unchanged unless a sidecar
    is deliberately authored. One file, one discriminated ``corrections`` list
    -- a field-type correction and a header-cell correction may both appear in
    it, per :data:`RecordDesignCorrection`.
    """
    sidecar_path = _resolve_annotation(source_path.with_name(source_path.name + _CORRECTION_SUFFIX))
    if sidecar_path is None:
        return EMPTY_CORRECTIONS
    entries = _load_annotation_entries(
        sidecar_path,
        "corrections",
        "correction sidecar must declare a 'corrections' list",
    )
    return _correction_index(entries, sidecar_path)


_DECLARED_NON_RECORD_SHEETS_FILENAME: Final[str] = "declared-non-record-sheets.json"
_EMPTY_DECLARED_NON_RECORD_SHEET_REASONS: Final[Mapping[str, str]] = dict[str, str]()


def _declared_sheet_reason(entry: object, declaration_path: Path) -> tuple[str, str]:
    """Decode one declared non-record sheet and its reviewer reason."""
    try:
        entry_map = _JSON_OBJECT_ADAPTER.validate_python(entry)
    except ValidationError as exc:
        raise RegistryValidationError(
            f"{declaration_path}: every entry needs a string 'sheet' and a string 'reason'",
        ) from exc
    sheet_value = entry_map.get("sheet")
    reason_value = entry_map.get("reason")
    if not isinstance(sheet_value, str) or not isinstance(reason_value, str):
        raise RegistryValidationError(
            f"{declaration_path}: every entry needs a string 'sheet' and a string 'reason'",
        )
    sheet = sheet_value.strip()
    reason = reason_value.strip()
    if not sheet or not reason:
        raise RegistryValidationError(f"{declaration_path}: 'sheet' and 'reason' must be non-blank")
    return sheet, reason


def load_declared_non_record_sheet_reasons(source_path: Path) -> Mapping[str, str]:
    """Load one modelo's declared, sourced reasons for sheets that are never records.

    Lives once per MODELO directory (sibling to that modelo's own
    ``manifest.json``), not per binary: a legend or lookup tab AEAT republishes
    unchanged across several editions is one judgement, not one per file. This
    never turns a skip into a read -- the sheet stays in
    :attr:`RecordDesignExtraction.skipped` exactly as before -- it only
    replaces the parser's own generic header-probe failure message with the
    grounded reason a reviewer recorded after opening the design. The
    extractor cannot itself tell a lookup tab apart from a dropped record
    body, so that judgement is a registry act, never inferred here.
    """
    modelo_root = source_path.parent.parent
    declaration_path = _resolve_annotation(modelo_root / _DECLARED_NON_RECORD_SHEETS_FILENAME)
    if declaration_path is None:
        return _EMPTY_DECLARED_NON_RECORD_SHEET_REASONS
    entries = _load_annotation_entries(
        declaration_path,
        "declared_non_record_sheets",
        "must declare a 'declared_non_record_sheets' list",
    )
    reasons: dict[str, str] = {}
    for entry in entries:
        sheet, reason = _declared_sheet_reason(entry, declaration_path)
        if sheet in reasons:
            raise RegistryValidationError(f"{declaration_path}: duplicate declaration for sheet {sheet!r}")
        reasons[sheet] = reason
    return reasons
