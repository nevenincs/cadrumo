"""Pure validation and source-native addressing helpers for AEIP apply plans."""

from __future__ import annotations

import re
from pathlib import Path

from cadrumo.core.external_constants import UTF_8_ENCODING
from cadrumo.core.toml import TomlDecodeError, parse_toml
from cadrumo.domain.calculations.registry.errors import RegistryLoadError

from .planning import _merge_source_refs
from .types import AeipOccurrence, ChainPlanEntry, EvolutionPair


def _add_refusal(refusals: list[str], seen: set[str], detail: str) -> None:
    """Append one stable refusal without flooding a report with duplicates."""
    if detail not in seen:
        seen.add(detail)
        refusals.append(detail)


def _safe_resolve(path: Path, root: Path) -> Path | None:
    """Resolve a path and return it only when it stays below ``root``."""
    try:
        resolved = path.resolve(strict=False)
    except OSError:
        return None
    return resolved if resolved.is_relative_to(root) else None


def _raw_casilla_tables(document: object, revision_id: str) -> tuple[dict[str, object], ...]:
    """Extract raw casilla tables from one source-native TOML document."""
    if not isinstance(document, dict):
        return ()
    revisions = document.get("revisions")
    if not isinstance(revisions, dict):
        return ()
    revision = revisions.get(revision_id)
    if not isinstance(revision, dict):
        return ()
    casillas = revision.get("casillas", ())
    if not isinstance(casillas, list):
        return ()
    tables: list[dict[str, object]] = []
    for raw_table in casillas:
        if not isinstance(raw_table, dict):
            continue
        table: dict[str, object] = {}
        for key, value in raw_table.items():
            if not isinstance(key, str):
                continue
            table[key] = value
        tables.append(table)
    return tuple(tables)


def _locate_casilla_file(
    modelo_root: Path,
    revision_id: str,
    casilla_id: str,
    refusals: list[str],
    seen_refusals: set[str],
) -> Path | None:
    """Find exactly one safe source-native file declaring one casilla.

    The loader is authoritative for semantic materialisation.  This narrow
    raw scan is only localization for the existing insertion helper; it does
    not construct a second registry model or infer a row from its filename.
    """
    revision_root = _revision_source_root(modelo_root, revision_id, casilla_id, refusals, seen_refusals)
    if revision_root is None:
        return None
    casillas_root = revision_root / "casillas"
    candidates = _casilla_source_candidates(casillas_root, revision_id, casilla_id, refusals, seen_refusals)
    if candidates is None:
        return None
    matches = _matching_casilla_paths(
        candidates,
        modelo_root,
        revision_id,
        casilla_id,
        refusals,
        seen_refusals,
    )
    if len(matches) != 1:
        detail = "no source-native casilla fragment found" if not matches else f"{len(matches)} fragments found"
        _add_refusal(refusals, seen_refusals, f"{revision_id}/{casilla_id}: {detail}")
        return None
    return matches[0]


def _revision_source_root(
    modelo_root: Path,
    revision_id: str,
    casilla_id: str,
    refusals: list[str],
    seen_refusals: set[str],
) -> Path | None:
    revision_candidate = modelo_root / "revisions" / revision_id
    if revision_candidate.is_symlink():
        _add_refusal(
            refusals,
            seen_refusals,
            f"{revision_id}/{casilla_id}: revision path is a symlink",
        )
        return None
    revision_root = _safe_resolve(revision_candidate, modelo_root)
    if revision_root is None:
        _add_refusal(
            refusals,
            seen_refusals,
            f"{revision_id}/{casilla_id}: revision path escapes the Modelo 100 registry root",
        )
        return None
    return revision_root


def _casilla_source_candidates(
    casillas_root: Path,
    revision_id: str,
    casilla_id: str,
    refusals: list[str],
    seen_refusals: set[str],
) -> list[Path] | None:
    if casillas_root.is_symlink() or not casillas_root.is_dir():
        _add_refusal(
            refusals,
            seen_refusals,
            f"{revision_id}/{casilla_id}: casillas source directory is missing or unsafe",
        )
        return None

    try:
        return sorted(casillas_root.iterdir(), key=lambda path: path.name)
    except OSError as error:
        _add_refusal(
            refusals,
            seen_refusals,
            f"{revision_id}/{casilla_id}: cannot enumerate casillas source directory: {error}",
        )
        return None


def _matching_casilla_paths(
    candidates: list[Path],
    modelo_root: Path,
    revision_id: str,
    casilla_id: str,
    refusals: list[str],
    seen_refusals: set[str],
) -> list[Path]:
    matches: list[Path] = []
    for path in candidates:
        if path.suffix.lower() != ".toml":
            continue
        if path.is_symlink() or _safe_resolve(path, modelo_root) is None:
            _add_refusal(
                refusals,
                seen_refusals,
                f"{revision_id}/{casilla_id}: unsafe casilla fragment path {path}",
            )
            continue
        try:
            document = parse_toml(path.read_text(encoding=UTF_8_ENCODING))
        except (OSError, UnicodeError, TomlDecodeError) as error:
            _add_refusal(
                refusals,
                seen_refusals,
                f"{revision_id}/{casilla_id}: cannot parse casilla fragment {path}: {error}",
            )
            continue
        tables = _raw_casilla_tables(document, revision_id)
        if any(str(table.get("id", "")) == casilla_id for table in tables):
            matches.append(path)
    return matches


def _origin_value(value: object) -> str | None:
    """Read an enum or raw lineage origin as its canonical token."""
    if value is None:
        return None
    token = getattr(value, "value", value)
    return str(token)


def _source_refs_are_grounded(refs: tuple[str, ...]) -> bool:
    """Require a non-empty list of non-blank source catalogue ids."""
    return bool(refs) and all(isinstance(ref, str) and bool(ref.strip()) for ref in refs)


def _grounded_row_evidence(pair: EvolutionPair, earlier: AeipOccurrence, later: AeipOccurrence) -> str:
    """Render deterministic, source-backed evidence for a grounded successor row."""
    refs = _merge_source_refs(earlier, later)
    if not _source_refs_are_grounded(refs):
        raise RegistryLoadError(
            f"{pair.chain_id} {pair.from_revision}->{pair.to_revision}: missing authoritative source refs",
        )
    evidence = (
        f"AEAT Diseño de Registros sources {', '.join(refs)}: Modelo 100 "
        f"{earlier.revision_id}/{earlier.casilla_id} and {later.revision_id}/{later.casilla_id} "
        f"resolve the adjudicated AEIP programme {later.title!r}; transition classified "
        f"{pair.evolution_kind} from the official Spanish labels."
    )
    if len(evidence) > 1024:
        raise RegistryLoadError(
            f"{pair.chain_id} {pair.from_revision}->{pair.to_revision}: grounded evidence exceeds 1024 characters",
        )
    return evidence


def _pair_endpoints(entry: ChainPlanEntry, pair: EvolutionPair) -> tuple[AeipOccurrence, AeipOccurrence | None] | None:
    """Return the source and target occurrences represented by an evolution pair."""
    earlier = [occurrence for occurrence in entry.occurrences if occurrence.revision_id == pair.from_revision]
    if len(earlier) != 1:
        return None
    if pair.evolution_kind == "retired":
        return earlier[0], None
    later = [occurrence for occurrence in entry.occurrences if occurrence.revision_id == pair.to_revision]
    if len(later) != 1:
        return None
    return earlier[0], later[0]


def _evolution_core(record: object) -> tuple[str, str, str, str] | None:
    """Get the identity-bearing fields from a loaded evolution record."""
    values: list[str] = []
    for field_name in ("continuidad_id", "from_revision", "to_revision", "evolution_kind"):
        value = getattr(record, field_name, None)
        if value is None:
            return None
        values.append(str(getattr(value, "value", value)))
    if len(values) != 4:
        return None
    return values[0], values[1], values[2], values[3]


def _expected_evolution_id(modelo_id: str, casilla_id: str, pair: EvolutionPair) -> str:
    """Use the loader's source-native record identity convention."""
    return f"m{modelo_id}-{casilla_id}-{pair.from_revision}-{pair.to_revision}-{pair.evolution_kind}"


def _safe_evolution_filename(casilla_id: str, pair: EvolutionPair) -> str | None:
    """Return a source-native filename only for safe single-component fields."""
    tokens = (casilla_id, pair.from_revision, pair.to_revision, pair.evolution_kind)
    if any(re.fullmatch(r"[A-Za-z0-9_-]+", token) is None for token in tokens):
        return None
    # Loader-owned continuity fragment names are dot/dash filenames; the
    # schema's evolution token keeps underscores.  Match existing source-native
    # files (``legal-refs-evolved.toml``) without changing the record token.
    kind_filename = pair.evolution_kind.replace("_", "-")
    return f"{casilla_id}-{pair.from_revision}-{pair.to_revision}-{kind_filename}.toml"
