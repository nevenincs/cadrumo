"""Read declared source metadata for AEAT record-design extraction."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from pydantic import TypeAdapter, ValidationError

from ....core.external_constants import UTF_8_ENCODING
from .errors import RegistryValidationError
from .record_design_schema import (
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
    sidecar_path = source_path.with_name(source_path.name + _CORRECTION_SUFFIX)
    if not sidecar_path.is_file():
        return EMPTY_CORRECTIONS
    try:
        payload = _JSON_OBJECT_ADAPTER.validate_python(json.loads(sidecar_path.read_text(encoding=UTF_8_ENCODING)))
    except ValidationError as exc:
        raise RegistryValidationError(
            f"{sidecar_path}: correction sidecar must declare a 'corrections' list",
        ) from exc
    try:
        entries = _JSON_ARRAY_ADAPTER.validate_python(payload.get("corrections"))
    except ValidationError as exc:
        raise RegistryValidationError(
            f"{sidecar_path}: correction sidecar must declare a 'corrections' list",
        ) from exc
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
        if isinstance(correction, RecordDesignFieldTypeCorrection):
            type_key = (correction.sheet, correction.source_row)
            if type_key in type_corrections:
                raise RegistryValidationError(
                    f"{sidecar_path}: duplicate type correction for sheet {correction.sheet!r} "
                    f"row {correction.source_row}",
                )
            type_corrections[type_key] = correction
        elif isinstance(correction, RecordDesignRangeStartCorrection):
            range_key = (correction.sheet, correction.declared_start)
            if range_key in range_start_corrections:
                raise RegistryValidationError(
                    f"{sidecar_path}: duplicate range-start correction for sheet "
                    f"{correction.sheet!r} start {correction.declared_start}",
                )
            range_start_corrections[range_key] = correction
        elif isinstance(correction, RecordDesignSinglePositionCorrection):
            position_key = (correction.sheet, correction.position)
            if position_key in single_position_corrections:
                raise RegistryValidationError(
                    f"{sidecar_path}: duplicate single-position correction for sheet "
                    f"{correction.sheet!r} position {correction.position}",
                )
            single_position_corrections[position_key] = correction
        else:
            header_key = (correction.sheet, correction.header_row, correction.column_role)
            if header_key in header_corrections:
                raise RegistryValidationError(
                    f"{sidecar_path}: duplicate header correction for sheet {correction.sheet!r} "
                    f"row {correction.header_row} role {correction.column_role!r}",
                )
            header_corrections[header_key] = correction
    return CorrectionIndex(
        type_corrections=type_corrections,
        header_corrections=header_corrections,
        single_position_corrections=single_position_corrections,
        range_start_corrections=range_start_corrections,
    )


_DECLARED_NON_RECORD_SHEETS_FILENAME: Final[str] = "declared-non-record-sheets.json"
_EMPTY_DECLARED_NON_RECORD_SHEET_REASONS: Final[Mapping[str, str]] = dict[str, str]()


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
    declaration_path = modelo_root / _DECLARED_NON_RECORD_SHEETS_FILENAME
    if not declaration_path.is_file():
        return _EMPTY_DECLARED_NON_RECORD_SHEET_REASONS
    try:
        payload = _JSON_OBJECT_ADAPTER.validate_python(
            json.loads(declaration_path.read_text(encoding=UTF_8_ENCODING)),
        )
    except ValidationError as exc:
        raise RegistryValidationError(
            f"{declaration_path}: must declare a 'declared_non_record_sheets' list",
        ) from exc
    try:
        entries = _JSON_ARRAY_ADAPTER.validate_python(payload.get("declared_non_record_sheets"))
    except ValidationError as exc:
        raise RegistryValidationError(
            f"{declaration_path}: must declare a 'declared_non_record_sheets' list",
        ) from exc
    reasons: dict[str, str] = {}
    for entry in entries:
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
        if sheet in reasons:
            raise RegistryValidationError(f"{declaration_path}: duplicate declaration for sheet {sheet!r}")
        reasons[sheet] = reason
    return reasons
