"""Preflight source-backed evolution records for an AEIP apply plan."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from cadrumo.core.external_constants import UTF_8_ENCODING
from cadrumo.core.toml import TomlDecodeError, parse_toml

from . import constants as _constants
from .apply_support import (
    _add_refusal,
    _evolution_core,
    _expected_evolution_id,
    _safe_evolution_filename,
    _safe_resolve,
    _source_refs_are_grounded,
)
from .planning import render_evolution_record
from .types import AeipEvolutionWrite, ChainPlanEntry, EvolutionPair

_Core = tuple[str, str, str, str]
_Desired = dict[_Core, tuple[ChainPlanEntry, EvolutionPair, str]]
_Existing = dict[_Core, list[tuple[str, Any]]]
_PairEndpoint = tuple[ChainPlanEntry, EvolutionPair, Any, Any | None]


def desired_evolutions(
    pair_endpoints: list[_PairEndpoint],
    refusals: list[str],
    seen_refusals: set[str],
) -> _Desired:
    """Index planned evolution identities and validate their evidence claims."""
    desired: _Desired = {}
    for entry, pair, earlier, later in pair_endpoints:
        endpoint = earlier if later is None else later
        if not _source_refs_are_grounded(pair.source_refs):
            _add_refusal(
                refusals,
                seen_refusals,
                f"{pair.chain_id} {pair.from_revision}->{pair.to_revision}: evolution has no authoritative source refs",
            )
        if not pair.legal_refs:
            _add_refusal(
                refusals,
                seen_refusals,
                f"{pair.chain_id} {pair.from_revision}->{pair.to_revision}: evolution has no legal refs",
            )
        core = _evolution_identity(pair)
        if core in desired:
            _add_refusal(refusals, seen_refusals, f"duplicate planned evolution {core!r}")
        desired[core] = (entry, pair, endpoint.casilla_id)
    return desired


def _evolution_identity(pair: EvolutionPair) -> _Core:
    return pair.chain_id, pair.from_revision, pair.to_revision, pair.evolution_kind


def existing_evolutions(
    definition: Any,
    desired: _Desired,
    refusals: list[str],
    seen_refusals: set[str],
) -> tuple[_Existing, int, int]:
    """Index canonical AEIP evolution records and return expected/unexpected counts."""
    existing_by_core: _Existing = defaultdict(list)
    for revision_id, revision in definition.revisions.items():
        for record in revision.casilla_continuidad_evolutions:
            core = _evolution_core(record)
            if core is None or not core[0].startswith(_constants.CHAIN_PREFIX):
                continue
            existing_by_core[core].append((str(revision_id), record))
            _check_materialized_revision(revision_id, record, refusals, seen_refusals)
    existing_count = sum(len(records) for core, records in existing_by_core.items() if core in desired)
    unexpected_count = sum(len(records) for core, records in existing_by_core.items() if core not in desired)
    return existing_by_core, existing_count, unexpected_count


def _check_materialized_revision(
    revision_id: str,
    record: Any,
    refusals: list[str],
    seen_refusals: set[str],
) -> None:
    if str(record.to_revision) != str(revision_id):
        _add_refusal(
            refusals,
            seen_refusals,
            f"evolution {record.id!s} is materialized under {revision_id!r} but targets {record.to_revision!s}",
        )


def prepare_evolution_writes(
    modelo_root: Path,
    modelo_id: str,
    desired: _Desired,
    existing_by_core: _Existing,
    refusals: list[str],
    seen_refusals: set[str],
) -> list[AeipEvolutionWrite]:
    """Validate existing records and build writes for missing source fragments."""
    writes: list[AeipEvolutionWrite] = []
    for core, (_entry, pair, casilla_id) in sorted(desired.items()):
        records = existing_by_core.get(core, [])
        if _check_existing_records(core, pair, casilla_id, records, modelo_id, refusals, seen_refusals):
            continue
        _append_new_evolution(
            modelo_root,
            modelo_id,
            core,
            pair,
            casilla_id,
            writes,
            refusals,
            seen_refusals,
        )
    return writes


def _check_existing_records(
    core: _Core,
    pair: EvolutionPair,
    casilla_id: str,
    records: list[tuple[str, Any]],
    modelo_id: str,
    refusals: list[str],
    seen_refusals: set[str],
) -> bool:
    if len(records) > 1:
        _add_refusal(refusals, seen_refusals, f"duplicate existing evolution {core!r}")
    if not records:
        return False
    _, record = records[0]
    expected_id = _expected_evolution_id(modelo_id, casilla_id, pair)
    if str(record.id) != expected_id:
        _add_refusal(refusals, seen_refusals, f"evolution {core!r} has conflicting id {record.id!s}")
    if tuple(str(ref) for ref in record.legal_refs) != tuple(pair.legal_refs):
        _add_refusal(refusals, seen_refusals, f"evolution {core!r} legal refs conflict with adjudicated plan")
    if not _source_refs_are_grounded(tuple(str(ref) for ref in record.source_refs)):
        _add_refusal(refusals, seen_refusals, f"evolution {core!r} has empty source refs")
    return True


def _append_new_evolution(
    modelo_root: Path,
    modelo_id: str,
    core: _Core,
    pair: EvolutionPair,
    casilla_id: str,
    writes: list[AeipEvolutionWrite],
    refusals: list[str],
    seen_refusals: set[str],
) -> None:
    filename = _safe_evolution_filename(casilla_id, pair)
    if filename is None:
        _add_refusal(refusals, seen_refusals, f"evolution {core!r} has unsafe source-native filename fields")
        return
    path = _evolution_target_path(modelo_root, pair, filename, core, refusals, seen_refusals)
    if path is None:
        return
    content = _validated_evolution_content(pair, casilla_id, modelo_id, core, refusals, seen_refusals)
    if content is None:
        return
    if _existing_target_matches(path, content, core, refusals, seen_refusals):
        return
    writes.append(AeipEvolutionWrite(path=path, pair=pair, casilla_id=casilla_id, content=content))


def _evolution_target_path(
    modelo_root: Path,
    pair: EvolutionPair,
    filename: str,
    core: _Core,
    refusals: list[str],
    seen_refusals: set[str],
) -> Path | None:
    target_dir_candidate = modelo_root / "revisions" / pair.to_revision / "casilla_continuidad_evolutions"
    if target_dir_candidate.is_symlink():
        _add_refusal(refusals, seen_refusals, f"evolution {core!r} target directory is a symlink")
        return None
    target_dir = _safe_resolve(target_dir_candidate, modelo_root)
    if target_dir is None or not target_dir.is_dir():
        _add_refusal(refusals, seen_refusals, f"evolution {core!r} target directory is missing or unsafe")
        return None
    path = _safe_resolve(target_dir / filename, modelo_root)
    if path is None or (path.exists() and path.is_symlink()):
        _add_refusal(refusals, seen_refusals, f"evolution {core!r} target file is unsafe")
        return None
    return path


def _validated_evolution_content(
    pair: EvolutionPair,
    casilla_id: str,
    modelo_id: str,
    core: _Core,
    refusals: list[str],
    seen_refusals: set[str],
) -> str | None:
    content = render_evolution_record(pair, casilla_id=casilla_id, modelo_id=modelo_id) + "\n"
    try:
        parsed = parse_toml(content)
    except TomlDecodeError as error:
        _add_refusal(refusals, seen_refusals, f"evolution {core!r} rendered invalid TOML: {error}")
        return None
    record = _rendered_evolution_record(parsed, pair.to_revision)
    expected_id = _expected_evolution_id(modelo_id, casilla_id, pair)
    if not isinstance(record, dict) or record.get("id") != expected_id:
        _add_refusal(refusals, seen_refusals, f"evolution {core!r} rendered identity does not round-trip")
        return None
    if not record.get("source_refs"):
        _add_refusal(refusals, seen_refusals, f"evolution {core!r} rendered without source refs")
        return None
    return content


def _rendered_evolution_record(parsed: Any, to_revision: str) -> Any:
    revisions = parsed.get("revisions", {})
    revision = revisions.get(to_revision, {}) if isinstance(revisions, dict) else {}
    records = revision.get("casilla_continuidad_evolutions", ()) if isinstance(revision, dict) else ()
    return records[0] if isinstance(records, list) and len(records) == 1 else None


def _existing_target_matches(
    path: Path,
    content: str,
    core: _Core,
    refusals: list[str],
    seen_refusals: set[str],
) -> bool:
    if not path.exists():
        return False
    try:
        existing_text = path.read_text(encoding=UTF_8_ENCODING)
    except (OSError, UnicodeError) as error:
        _add_refusal(refusals, seen_refusals, f"evolution {core!r} cannot read colliding target: {error}")
        return True
    if existing_text != content:
        _add_refusal(refusals, seen_refusals, f"evolution {core!r} collides with different existing file {path}")
    # Exact files are idempotent; canonical loading normally counted them above.
    return True
