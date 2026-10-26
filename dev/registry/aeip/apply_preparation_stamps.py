"""Preflight continuity stamps against the live AEIP source declarations."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from cadrumo.core.external_constants import UTF_8_ENCODING
from cadrumo.core.i18n.render import MissingTranslationError

from . import constants as _constants
from .apply_support import (
    _add_refusal,
    _grounded_row_evidence,
    _locate_casilla_file,
    _origin_value,
    _source_refs_are_grounded,
)
from .types import AeipOccurrence, AeipStampWrite, ChainPlanEntry, EvolutionPair

_RowKey = tuple[str, str]
_PlannedRow = tuple[str, bool, AeipOccurrence]
_PairEndpoint = tuple[ChainPlanEntry, EvolutionPair, AeipOccurrence, AeipOccurrence | None]


def prepare_stamp_writes(
    modelo_root: Path,
    current_rows: dict[_RowKey, Any],
    planned_rows: dict[_RowKey, _PlannedRow],
    pair_endpoints: list[_PairEndpoint],
    refusals: list[str],
    seen_refusals: set[str],
) -> tuple[int, list[AeipStampWrite]]:
    """Return the stable row-stamp plan and count rows already stamped."""
    from dev.registry.analysis.casilla_lineage_seed_writer import insert_lineage_keys

    existing_stamps = 0
    stamp_writes: list[AeipStampWrite] = []
    for key, (chain_id, is_successor, occurrence) in sorted(planned_rows.items()):
        current = current_rows.get(key)
        if current is None:
            _add_refusal(refusals, seen_refusals, f"{key[0]}/{key[1]} is absent from canonical Modelo 100 load")
            continue
        current_id, current_origin, current_evidence = _validate_live_row(
            key, chain_id, occurrence, current, refusals, seen_refusals
        )
        if current_id == chain_id:
            existing_stamps += 1
        expected = _expected_lineage(
            key,
            chain_id,
            is_successor,
            occurrence,
            current_origin,
            current_evidence,
            pair_endpoints,
            refusals,
            seen_refusals,
        )
        missing = _missing_lineage(expected, current_id, current_origin, current_evidence)
        if missing:
            _append_stamp(
                modelo_root,
                key,
                missing,
                insert_lineage_keys,
                stamp_writes,
                refusals,
                seen_refusals,
            )
    return existing_stamps, stamp_writes


def _validate_live_row(
    key: _RowKey,
    chain_id: str,
    occurrence: AeipOccurrence,
    current: Any,
    refusals: list[str],
    seen_refusals: set[str],
) -> tuple[str | None, str | None, object]:
    _validate_row_surface(key, occurrence, current, refusals, seen_refusals)
    _validate_row_refs(key, occurrence, current, refusals, seen_refusals)
    return _current_lineage_values(key, chain_id, current, refusals, seen_refusals)


def _validate_row_surface(
    key: _RowKey,
    occurrence: AeipOccurrence,
    current: Any,
    refusals: list[str],
    seen_refusals: set[str],
) -> None:
    if (
        _constants.ANEXO_A_SECTION_LEAF not in tuple(current.section or ())
        or str(current.semantic_role or "") != _constants.EVENT_SEMANTIC_ROLE
    ):
        _add_refusal(refusals, seen_refusals, f"{key[0]}/{key[1]} is no longer an AEIP event row")
    try:
        current_label = current.get_label(_constants.SOURCE_LOCALE)
    except MissingTranslationError:
        current_label = ""
    if (
        current_label != occurrence.label
        or tuple(str(item) for item in current.localization_keys) != occurrence.localization_keys
    ):
        _add_refusal(refusals, seen_refusals, f"{key[0]}/{key[1]} label/localization changed since adjudication")


def _validate_row_refs(
    key: _RowKey,
    occurrence: AeipOccurrence,
    current: Any,
    refusals: list[str],
    seen_refusals: set[str],
) -> None:
    if tuple(str(item) for item in current.legal_refs) != occurrence.legal_refs:
        _add_refusal(refusals, seen_refusals, f"{key[0]}/{key[1]} legal refs changed since adjudication")
    current_sources = tuple(str(item) for item in current.source_refs)
    if not _source_refs_are_grounded(current_sources):
        _add_refusal(refusals, seen_refusals, f"{key[0]}/{key[1]} has no authoritative source refs")
    elif current_sources != occurrence.source_refs:
        _add_refusal(refusals, seen_refusals, f"{key[0]}/{key[1]} source refs changed since adjudication")


def _current_lineage_values(
    key: _RowKey,
    chain_id: str,
    current: Any,
    refusals: list[str],
    seen_refusals: set[str],
) -> tuple[str | None, str | None, object]:
    current_id = None if current.continuidad_id is None else str(current.continuidad_id)
    current_origin = _origin_value(current.continuidad_origin)
    current_evidence = current.continuidad_evidence
    if current_id is not None and current_id != chain_id:
        _add_refusal(
            refusals,
            seen_refusals,
            f"{key[0]}/{key[1]} already carries conflicting continuidad_id {current_id!r}",
        )
    return current_id, current_origin, current_evidence


def _expected_lineage(
    key: _RowKey,
    chain_id: str,
    is_successor: bool,
    occurrence: AeipOccurrence,
    current_origin: str | None,
    current_evidence: object,
    pair_endpoints: list[_PairEndpoint],
    refusals: list[str],
    seen_refusals: set[str],
) -> dict[str, str]:
    expected = {"continuidad_id": chain_id}
    if is_successor:
        endpoint = _predecessor_endpoint(chain_id, occurrence, pair_endpoints)
        if endpoint is None:
            _add_refusal(refusals, seen_refusals, f"{key[0]}/{key[1]} has no grounded predecessor pair")
        else:
            expected.update(continuidad_origin="grounded", continuidad_evidence=_grounded_row_evidence(*endpoint))
        _check_successor_origin(key, current_origin, current_evidence, refusals, seen_refusals)
    elif current_origin is not None or current_evidence is not None:
        _add_refusal(refusals, seen_refusals, f"{key[0]}/{key[1]} chain root already carries origin/evidence")
    return expected


def _predecessor_endpoint(
    chain_id: str,
    occurrence: AeipOccurrence,
    pair_endpoints: list[_PairEndpoint],
) -> tuple[EvolutionPair, AeipOccurrence, AeipOccurrence] | None:
    for entry, pair, earlier, later in pair_endpoints:
        if entry.chain_id == chain_id and later is not None and later.revision_id == occurrence.revision_id:
            return pair, earlier, later
    return None


def _check_successor_origin(
    key: _RowKey,
    current_origin: str | None,
    current_evidence: object,
    refusals: list[str],
    seen_refusals: set[str],
) -> None:
    if current_origin == "grounded":
        if not isinstance(current_evidence, str) or not current_evidence.strip():
            _add_refusal(refusals, seen_refusals, f"{key[0]}/{key[1]} grounded origin has empty evidence")
    elif current_origin is not None:
        _add_refusal(
            refusals,
            seen_refusals,
            f"{key[0]}/{key[1]} carries conflicting continuity origin {current_origin!r}",
        )
    elif current_evidence is not None:
        _add_refusal(refusals, seen_refusals, f"{key[0]}/{key[1]} carries evidence without grounded origin")


def _missing_lineage(
    expected: dict[str, str],
    current_id: str | None,
    current_origin: str | None,
    current_evidence: object,
) -> dict[str, str]:
    missing: dict[str, str] = {}
    if current_id is None and "continuidad_id" in expected:
        missing["continuidad_id"] = expected["continuidad_id"]
    if current_origin is None and "continuidad_origin" in expected:
        missing["continuidad_origin"] = expected["continuidad_origin"]
    if current_evidence is None and "continuidad_evidence" in expected:
        missing["continuidad_evidence"] = expected["continuidad_evidence"]
    return missing


def _append_stamp(
    modelo_root: Path,
    key: _RowKey,
    missing: dict[str, str],
    insert_lineage_keys: Callable[[str, str, Mapping[str, Mapping[str, str]]], tuple[str, set[str]]],
    stamp_writes: list[AeipStampWrite],
    refusals: list[str],
    seen_refusals: set[str],
) -> None:
    path = _locate_casilla_file(modelo_root, key[0], key[1], refusals, seen_refusals)
    if path is None:
        return
    try:
        raw_text = path.read_text(encoding=UTF_8_ENCODING)
        _, done = insert_lineage_keys(raw_text, key[0], {key[1]: missing})
    except (OSError, UnicodeError, ValueError) as error:
        _add_refusal(refusals, seen_refusals, f"{key[0]}/{key[1]} lineage insertion refused: {error}")
        return
    if done != {key[1]}:
        _add_refusal(refusals, seen_refusals, f"{key[0]}/{key[1]} was not uniquely located by insertion helper")
        return
    stamp_writes.append(AeipStampWrite(path=path, revision_id=key[0], casilla_id=key[1], keys=tuple(missing.items())))
