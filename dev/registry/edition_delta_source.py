"""Reading and lifting authored casilla edition source."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from cadrumo.core.toml import freeze_toml_value, parse_toml
from cadrumo.domain.calculations.registry.errors import RegistryLoadError

from . import edition_delta_errors as _edition_delta_errors
from . import edition_delta_fields as _edition_delta_fields
from . import edition_delta_payload as _edition_delta_payload
from . import edition_delta_types as _edition_delta_types
from .compiler.casilla_inheritance import retired_lineages
from .compiler.edition_materialisation import resolve_edition
from .compiler.reference_defaults import default_row_references
from .compiler.reference_resolution import edition_reference_declarations, resolve_row_references
from .edition_round_trip import RowKey
from .source_default_rule import edition_source_default

type _Row = dict[str, object]

type _Declarations = Mapping[str, Mapping[str, tuple[str, ...]]]


@dataclass(frozen=True, slots=True)
class _Block:
    """One casilla row as authored: its text, including any comment run directly above its header."""

    text: str
    row: _Row


@dataclass(frozen=True, slots=True)
class _Fragment:
    path: Path
    preamble: str
    blocks: tuple[_Block, ...]


@dataclass(frozen=True, slots=True)
class _EditionSource:
    revision_id: str
    manifest_text: str
    manifest: _Row
    #: The edition's complete raw revision table, materialised through its
    #: predecessor chain; ``manifest`` is the table it declares itself.
    table: Mapping[str, object]
    fragments: tuple[_Fragment, ...]
    rows: tuple[_Row, ...]
    origins: tuple[str | None, ...]
    declarations: _Declarations
    retired: frozenset[str]
    family_defaults: Mapping[str, tuple[str, ...]]

    def stated_rows(self) -> tuple[_Row, ...]:
        return tuple(block.row for fragment in self.fragments for block in fragment.blocks)


def _as_row(value: object) -> _Row:
    thawed = _edition_delta_payload._thaw(value)
    if not isinstance(thawed, dict):
        raise _edition_delta_errors.MigrationRefusedError(f"expected a table, found {type(value).__name__}")
    return {str(key): item for key, item in thawed.items()}


def _split_blocks(text: str, header: re.Pattern[str] = _edition_delta_fields._ROW_HEADER) -> tuple[str, list[str]]:
    """Split a fragment into its preamble and one text block per member header.

    ``header`` selects the family being read. It defaults to the casilla row
    header so every existing caller keeps its behaviour; the drop operation
    passes the header of whichever family it is reading, because the keyed
    families are laid out on disk exactly as casillas are.
    """
    lines = text.splitlines(keepends=True)
    starts: list[int] = []
    for index, line in enumerate(lines):
        if header.match(line.rstrip("\r\n")):
            start = index
            while start > 0 and lines[start - 1].lstrip().startswith("#") and (not starts or start - 1 > starts[-1]):
                start -= 1
            starts.append(start)
    if not starts:
        return text, []
    bounds = [*starts, len(lines)]
    blocks = ["".join(lines[bounds[index] : bounds[index + 1]]) for index in range(len(starts))]
    return "".join(lines[: starts[0]]), blocks


def _block_row(block: str, section: str = _edition_delta_fields._CASILLAS) -> _Row:
    revisions = parse_toml(block).get("revisions")
    if not isinstance(revisions, dict) or len(revisions) != 1:
        raise _edition_delta_errors.MigrationRefusedError(
            f"{section} block does not declare exactly one revision:\n{block}"
        )
    (revision,) = revisions.values()
    rows = revision.get(section) if isinstance(revision, dict) else None
    if not isinstance(rows, list) or len(rows) != 1:
        raise _edition_delta_errors.MigrationRefusedError(
            f"{section} block does not declare exactly one member:\n{block}"
        )
    return _as_row(rows[0])


def _read_fragments(edition_dir: Path) -> tuple[_Fragment, ...]:
    fragments: list[_Fragment] = []
    for path in sorted((edition_dir / _edition_delta_fields._CASILLAS).glob("*.toml")):
        preamble, texts = _split_blocks(path.read_text(encoding="utf-8"))
        fragments.append(_Fragment(path, preamble, tuple(_Block(text, _block_row(text)) for text in texts)))
    return tuple(fragments)


def _manifest_table(text: str, revision_id: str) -> _Row:
    revisions = parse_toml(text).get("revisions")
    if not isinstance(revisions, dict) or revision_id not in revisions:
        raise _edition_delta_errors.MigrationRefusedError(f"revision.toml does not declare [revisions.{revision_id!r}]")
    return _as_row(revisions[revision_id])


def _read_edition(modelo_dir: Path, revision_id: str) -> _EditionSource:
    edition_dir = modelo_dir / "revisions" / revision_id
    manifest_text = (edition_dir / _edition_delta_fields._MANIFEST).read_text(encoding="utf-8")
    materialised = resolve_edition(modelo_dir, revision_id)
    raw_rows = materialised.table.get(_edition_delta_fields._CASILLAS, ())
    rows = tuple(_as_row(row) for row in (raw_rows if isinstance(raw_rows, list | tuple) else ()))
    origins = materialised.label_origins or tuple(None for _ in rows)
    return _EditionSource(
        revision_id=revision_id,
        manifest_text=manifest_text,
        manifest=_manifest_table(manifest_text, revision_id),
        table=materialised.table,
        fragments=_read_fragments(edition_dir),
        rows=rows,
        origins=origins,
        declarations=edition_reference_declarations(materialised.table, revision_id),
        retired=retired_lineages(materialised.table, revision_id),
        family_defaults={
            key: default
            for section, key in _edition_delta_fields._FAMILY_SOURCE_DEFAULTS
            if (default := _family_source_default(materialised.table, section)) is not None
        },
    )


@dataclass(frozen=True, slots=True)
class _Defaults:
    source_refs: tuple[str, ...] | None
    orden: tuple[str, ...]


def _manifest_defaults(manifest: Mapping[str, object]) -> _Defaults:
    source = manifest.get("casilla_source_refs")
    orden = manifest.get("orden_aplicabilidad", ())
    return _Defaults(
        source_refs=tuple(str(item) for item in source) if isinstance(source, list) and source else None,
        orden=tuple(str(item) for item in orden) if isinstance(orden, list) else (),
    )


def _effective(
    row: _Row,
    *,
    origin: str | None,
    revision_id: str,
    defaults: _Defaults,
    declarations: _Declarations,
) -> _Row | None:
    """The row the loader builds typed construction from, or ``None`` when a reference cannot resolve.

    The planned row goes through the loader's own steps, in the loader's order:
    an inherited row's formula and binding references resolve to this edition's
    declaration of the same lineage, then the edition's reference defaults fill
    the row and its constraints table. ``defaults`` is the planned manifest's,
    which may not be written yet. A row stated here carries ``revision_id`` as
    its origin, where the loader carries none.
    """
    context = f"edition {revision_id!r} casilla {row.get('id')!r}"
    # The loader reads arrays as frozen tuples only; a list would pass unresolved.
    frozen = freeze_toml_value(row)
    if origin is not None and origin != revision_id:
        try:
            frozen = resolve_row_references(
                context, frozen, origin=origin, revision_id=revision_id, declarations=declarations
            )
        except RegistryLoadError:
            return None
    return _as_row(
        default_row_references(context, frozen, source_default=defaults.source_refs or (), orden_default=defaults.orden)
    )


def _lineage(row: Mapping[str, object]) -> str | None:
    value = row.get(_edition_delta_fields._LINEAGE)
    return value if isinstance(value, str) else None


def _row_id(row: Mapping[str, object]) -> str:
    return str(row["id"])


def _row_keys(rows: Sequence[Mapping[str, object]]) -> tuple[RowKey, ...]:
    return tuple((_row_id(row), _lineage(row)) for row in rows)


@dataclass(frozen=True, slots=True)
class _Placed:
    """One materialised row, the raw row the loader holds for it, and the edition that stated it."""

    row: _Row
    origin: str


@dataclass(frozen=True, slots=True)
class _TableLift:
    """What lifting removes from one row or constraints table, and the additions it states instead."""

    removed: frozenset[str] = frozenset()
    additions: tuple[str, ...] | None = None


@dataclass(frozen=True, slots=True)
class _Lift:
    """One row's lifted form and what the lift changes in the row and in its constraints table."""

    row: _Row
    row_lift: _TableLift
    constraint_lift: _TableLift


def _source_refs(table: Mapping[str, object]) -> tuple[str, ...] | None:
    value = table.get(_edition_delta_fields._ROW_SOURCE)
    return tuple(str(item) for item in value) if isinstance(value, list) else None


def _table_lift(
    table: Mapping[str, object], *, source_default: tuple[str, ...] | None, orden: tuple[str, ...]
) -> _TableLift:
    removed: set[str] = set()
    additions: tuple[str, ...] | None = None
    refs = _source_refs(table)
    if source_default is not None and refs is not None and refs[: len(source_default)] == source_default:
        rest = refs[len(source_default) :]
        if tuple(dict.fromkeys((*source_default, *rest))) == refs:
            removed.add(_edition_delta_fields._ROW_SOURCE)
            additions = rest or None
    if orden and table.get(_edition_delta_fields._ROW_LEGAL) == list(orden):
        removed.add(_edition_delta_fields._ROW_LEGAL)
    return _TableLift(frozenset(removed), additions)


def _lifted_table(table: Mapping[str, object], lift: _TableLift) -> _Row:
    lifted = {key: value for key, value in table.items() if key not in lift.removed}
    if lift.additions is not None:
        lifted[_edition_delta_fields._ROW_SOURCE_ADDITIONS] = list(lift.additions)
    return lifted


def _lift(row: _Row, *, source_default: tuple[str, ...] | None, orden: tuple[str, ...]) -> _Lift:
    row_lift = _table_lift(row, source_default=source_default, orden=orden)
    lifted = _lifted_table(row, row_lift)
    constraint_lift = _TableLift()
    constraints = row.get(_edition_delta_fields._CONSTRAINTS)
    if isinstance(constraints, dict):
        constraint_lift = _table_lift(constraints, source_default=source_default, orden=orden)
        lifted[_edition_delta_fields._CONSTRAINTS] = _lifted_table(constraints, constraint_lift)
    return _Lift(lifted, row_lift, constraint_lift)


@dataclass(frozen=True, slots=True)
class _EditionWork:
    """An edition's plan together with what writing it needs."""

    plan: _edition_delta_types.EditionPlan
    source: _EditionSource
    lifts: Mapping[str, _Lift]
    root_declaration: _Row | None


@dataclass(frozen=True, slots=True)
class _EditionLift:
    """One edition's materialised rows, the default they share, and each row's lifted form."""

    rows: tuple[_Row, ...]
    source_default: tuple[str, ...] | None
    withheld: str | None
    lifts: Mapping[str, _Lift]
    defaults: _Defaults


def _effective_rows(source: _EditionSource) -> tuple[_Row, ...]:
    """The edition's materialised rows as the loader finally holds them, with its declared defaults inlined."""
    declared = _manifest_defaults(source.manifest)
    effective = [
        _effective(
            row,
            origin=origin,
            revision_id=source.revision_id,
            defaults=declared,
            declarations=source.declarations,
        )
        for row, origin in zip(source.rows, source.origins, strict=True)
    ]
    if any(row is None for row in effective):
        raise _edition_delta_errors.MigrationRefusedError(
            f"edition {source.revision_id!r}: an inherited reference does not resolve on input"
        )
    return tuple(row for row in effective if row is not None)


def _edition_lift(source: _EditionSource) -> _EditionLift:
    """Derive the edition's shared ``source_refs`` default and lift every materialised row against it.

    A default the manifest already declares is the one the loader will apply, so
    it is kept rather than re-derived: deriving a different run would rewrite
    rows against a default the manifest does not state. No full-copy edition
    declares one, so this only ever binds on the chain path.
    """
    declared = _manifest_defaults(source.manifest)
    rows = _effective_rows(source)
    derived, withheld = edition_source_default(rows)
    source_default, withheld = (declared.source_refs, None) if declared.source_refs is not None else (derived, withheld)
    return _EditionLift(
        rows=rows,
        source_default=source_default,
        withheld=withheld,
        lifts={_row_id(row): _lift(row, source_default=source_default, orden=declared.orden) for row in rows},
        defaults=_Defaults(source_refs=source_default, orden=declared.orden),
    )


def _stated_layout(source: _EditionSource, stated: frozenset[str]) -> list[tuple[str, list[_Block]]]:
    """The fragments that remain once only ``stated`` rows are kept, ordered as the loader reads them.

    Each fragment keeps its authored file name. Casilla sections are packed into
    one ``0001-declarations.toml`` per edition, and dropping rows from it does
    not change what the file is.
    """
    layout: list[tuple[str, list[_Block]]] = []
    for fragment in source.fragments:
        kept = [block for block in fragment.blocks if _row_id(block.row) in stated]
        if kept:
            layout.append((fragment.path.name, kept))
    names = [name for name, _ in layout]
    duplicated = sorted(name for name, count in Counter(names).items() if count > 1)
    if duplicated:
        raise _edition_delta_errors.MigrationRefusedError(
            f"edition {source.revision_id!r}: fragments would share the names {duplicated!r}"
        )
    return sorted(layout, key=lambda item: item[0])


def _family_source_default(table: Mapping[str, object], section: str) -> tuple[str, ...] | None:
    """The edition's shared leading ``source_refs`` run for ``section``, or ``None`` when none derives."""
    members = _family_members(table, section)
    if not members:
        return None
    default, _reason = edition_source_default(members)
    return default


def _members(
    raw: Mapping[str, object], section: str, *, singleton: bool = False
) -> tuple[Mapping[str, object], ...] | None:
    value = raw.get(section)
    if value is None:
        return ()
    if singleton and isinstance(value, Mapping):
        return (cast(Mapping[str, object], value),)
    if singleton or not isinstance(value, list | tuple) or any(not isinstance(item, Mapping) for item in value):
        return None
    return tuple(cast(Mapping[str, object], item) for item in value)


def _family_members(table: Mapping[str, object], section: str) -> tuple[_Row, ...]:
    """Return the edition's resolved members for ``section``, in declared order."""
    raw = table.get(section, ())
    return tuple(_as_row(member) for member in (raw if isinstance(raw, list | tuple) else ()))
