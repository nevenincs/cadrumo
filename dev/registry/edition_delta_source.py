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

from . import edition_delta_errors, edition_delta_fields, edition_delta_payload, edition_delta_types
from .compiler.casilla_inheritance import retired_lineages
from .compiler.edition_materialisation import resolve_edition
from .compiler.loader_fields import REFERENCE_SECTIONS
from .compiler.reference_defaults import default_row_references
from .compiler.reference_resolution import edition_reference_declarations, resolve_row_references
from .edition_round_trip import RowKey
from .source_default_rule import edition_source_default

type Row = dict[str, object]

type Declarations = Mapping[str, Mapping[str, tuple[str, ...]]]


@dataclass(frozen=True, slots=True)
class Block:
    """One casilla row as authored: its text, including any comment run directly above its header."""

    text: str
    row: Row


@dataclass(frozen=True, slots=True)
class _Fragment:
    path: Path
    preamble: str
    blocks: tuple[Block, ...]


@dataclass(frozen=True, slots=True)
class EditionSource:
    """An edition's revision id, manifest, materialised table and fragments read for migration."""

    revision_id: str
    manifest_text: str
    manifest: Row
    #: The edition's complete raw revision table, materialised through its
    #: predecessor chain; ``manifest`` is the table it declares itself.
    table: Mapping[str, object]
    fragments: tuple[_Fragment, ...]
    rows: tuple[Row, ...]
    origins: tuple[str | None, ...]
    declarations: Declarations
    retired: frozenset[str]
    family_defaults: Mapping[str, tuple[str, ...]]

    def stated_rows(self) -> tuple[Row, ...]:
        """Return the rows stated across the edition's fragments, in block order."""
        return tuple(block.row for fragment in self.fragments for block in fragment.blocks)


def as_row(value: object) -> Row:
    """Thaw a value into a string-keyed row, refusing anything but a table."""
    thawed = edition_delta_payload.thaw(value)
    if not isinstance(thawed, dict):
        raise edition_delta_errors.MigrationRefusedError(f"expected a table, found {type(value).__name__}")
    return {str(key): item for key, item in thawed.items()}


def split_blocks(text: str, header: re.Pattern[str] = edition_delta_fields.ROW_HEADER) -> tuple[str, list[str]]:
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


def block_row(block: str, section: str = edition_delta_fields.CASILLAS) -> Row:
    """Parse a TOML block that declares exactly one revision into its row."""
    revisions = parse_toml(block).get("revisions")
    if not isinstance(revisions, dict) or len(revisions) != 1:
        raise edition_delta_errors.MigrationRefusedError(
            f"{section} block does not declare exactly one revision:\n{block}"
        )
    (revision,) = revisions.values()
    rows = revision.get(section) if isinstance(revision, dict) else None
    if not isinstance(rows, list) or len(rows) != 1:
        raise edition_delta_errors.MigrationRefusedError(
            f"{section} block does not declare exactly one member:\n{block}"
        )
    return as_row(rows[0])


def _read_fragments(edition_dir: Path) -> tuple[_Fragment, ...]:
    fragments: list[_Fragment] = []
    for path in sorted((edition_dir / edition_delta_fields.CASILLAS).glob("*.toml")):
        preamble, texts = split_blocks(path.read_text(encoding="utf-8"))
        fragments.append(_Fragment(path, preamble, tuple(Block(text, block_row(text)) for text in texts)))
    return tuple(fragments)


def manifest_table(text: str, revision_id: str) -> Row:
    """Return the revision table that a manifest declares for the revision id."""
    revisions = parse_toml(text).get("revisions")
    if not isinstance(revisions, dict) or revision_id not in revisions:
        raise edition_delta_errors.MigrationRefusedError(f"revision.toml does not declare [revisions.{revision_id!r}]")
    return as_row(revisions[revision_id])


def read_edition(modelo_dir: Path, revision_id: str) -> EditionSource:
    """Read an edition's manifest and materialised casilla rows from the modelo directory."""
    edition_dir = modelo_dir / "revisions" / revision_id
    manifest_text = (edition_dir / edition_delta_fields.MANIFEST).read_text(encoding="utf-8")
    materialised = resolve_edition(modelo_dir, revision_id)
    raw_rows = materialised.table.get(edition_delta_fields.CASILLAS, ())
    rows = tuple(as_row(row) for row in (raw_rows if isinstance(raw_rows, list | tuple) else ()))
    origins = materialised.label_origins or tuple(None for _ in rows)
    return EditionSource(
        revision_id=revision_id,
        manifest_text=manifest_text,
        manifest=manifest_table(manifest_text, revision_id),
        table=materialised.table,
        fragments=_read_fragments(edition_dir),
        rows=rows,
        origins=origins,
        declarations=edition_reference_declarations(materialised.table, revision_id),
        retired=retired_lineages(materialised.table, revision_id),
        family_defaults={
            key: default
            for section, key in edition_delta_fields.FAMILY_SOURCE_DEFAULTS
            if (default := _family_source_default(materialised.table, section)) is not None
        },
    )


@dataclass(frozen=True, slots=True)
class Defaults:
    """The manifest defaults for source references and orden that rows inherit."""

    source_refs: tuple[str, ...] | None
    orden: tuple[str, ...]


def _manifest_defaults(manifest: Mapping[str, object]) -> Defaults:
    source = manifest.get("casilla_source_refs")
    orden = manifest.get("orden_aplicabilidad", ())
    return Defaults(
        source_refs=tuple(str(item) for item in source) if isinstance(source, list) and source else None,
        orden=tuple(str(item) for item in orden) if isinstance(orden, list) else (),
    )


def edition_delta_source_effective(
    row: Row,
    *,
    origin: str | None,
    revision_id: str,
    defaults: Defaults,
    declarations: Declarations,
) -> Row | None:
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
    return as_row(
        default_row_references(context, frozen, source_default=defaults.source_refs or (), orden_default=defaults.orden)
    )


def edition_delta_source_effective_restating_references(
    row: Row,
    successor: Row,
    *,
    origin: str | None,
    revision_id: str,
    defaults: Defaults,
    declarations: Declarations,
) -> Row | None:
    """The inherited row's effective form where the successor states the references it cannot inherit.

    A successor that removes or replaces a formula or binding its predecessor's
    row names cannot inherit that reference, so it must state the row's
    reference fields itself; the loader applies that override before it
    resolves references. When the predecessor's references resolve, this is
    :func:`edition_delta_source_effective`. Otherwise the successor's reference
    fields stand in for resolution only, and the returned row carries the
    predecessor's own reference values back, so a difference against the
    successor still states each reference it changes or removes. ``None`` when
    even the successor's references do not resolve.
    """
    effective = edition_delta_source_effective(
        row, origin=origin, revision_id=revision_id, defaults=defaults, declarations=declarations
    )
    if effective is not None:
        return effective
    stand_in: Row = {key: value for key, value in row.items() if key not in REFERENCE_SECTIONS}
    stand_in.update({key: successor[key] for key in REFERENCE_SECTIONS if key in successor})
    resolved = edition_delta_source_effective(
        stand_in, origin=origin, revision_id=revision_id, defaults=defaults, declarations=declarations
    )
    if resolved is None:
        return None
    restored: Row = {key: value for key, value in resolved.items() if key not in REFERENCE_SECTIONS}
    restored.update({key: row[key] for key in REFERENCE_SECTIONS if key in row})
    return restored


def lineage(row: Mapping[str, object]) -> str | None:
    """Return a row's lineage identifier when it is text, otherwise None."""
    value = row.get(edition_delta_fields.LINEAGE)
    return value if isinstance(value, str) else None


def row_id(row: Mapping[str, object]) -> str:
    """Return a row's identifier as text."""
    return str(row["id"])


def _row_keys(rows: Sequence[Mapping[str, object]]) -> tuple[RowKey, ...]:
    return tuple((row_id(row), lineage(row)) for row in rows)


@dataclass(frozen=True, slots=True)
class Placed:
    """One materialised row, the raw row the loader holds for it, and the edition that stated it."""

    row: Row
    origin: str


@dataclass(frozen=True, slots=True)
class TableLift:
    """What lifting removes from one row or constraints table, and the additions it states instead."""

    removed: frozenset[str] = frozenset()
    additions: tuple[str, ...] | None = None


@dataclass(frozen=True, slots=True)
class Lift:
    """One row's lifted form and what the lift changes in the row and in its constraints table."""

    row: Row
    row_lift: TableLift
    constraint_lift: TableLift


def _source_refs(table: Mapping[str, object]) -> tuple[str, ...] | None:
    value = table.get(edition_delta_fields.ROW_SOURCE)
    return tuple(str(item) for item in value) if isinstance(value, list) else None


def _table_lift(
    table: Mapping[str, object], *, source_default: tuple[str, ...] | None, orden: tuple[str, ...]
) -> TableLift:
    removed: set[str] = set()
    additions: tuple[str, ...] | None = None
    refs = _source_refs(table)
    if source_default is not None and refs is not None and refs[: len(source_default)] == source_default:
        rest = refs[len(source_default) :]
        if tuple(dict.fromkeys((*source_default, *rest))) == refs:
            removed.add(edition_delta_fields.ROW_SOURCE)
            additions = rest or None
    if orden and table.get(edition_delta_fields.ROW_LEGAL) == list(orden):
        removed.add(edition_delta_fields.ROW_LEGAL)
    return TableLift(frozenset(removed), additions)


def _lifted_table(table: Mapping[str, object], lift: TableLift) -> Row:
    lifted = {key: value for key, value in table.items() if key not in lift.removed}
    if lift.additions is not None:
        lifted[edition_delta_fields.ROW_SOURCE_ADDITIONS] = list(lift.additions)
    return lifted


def edition_delta_source_lift(row: Row, *, source_default: tuple[str, ...] | None, orden: tuple[str, ...]) -> Lift:
    """Lift a row's shared source and orden values into defaults, constraints included."""
    row_lift = _table_lift(row, source_default=source_default, orden=orden)
    lifted = _lifted_table(row, row_lift)
    constraint_lift = TableLift()
    constraints = row.get(edition_delta_fields.CONSTRAINTS)
    if isinstance(constraints, dict):
        constraint_lift = _table_lift(constraints, source_default=source_default, orden=orden)
        lifted[edition_delta_fields.CONSTRAINTS] = _lifted_table(constraints, constraint_lift)
    return Lift(lifted, row_lift, constraint_lift)


@dataclass(frozen=True, slots=True)
class EditionWork:
    """An edition's plan together with what writing it needs."""

    plan: edition_delta_types.EditionPlan
    source: EditionSource
    lifts: Mapping[str, Lift]
    root_declaration: Row | None
    casilla_override_replacements: tuple[Row, ...] = ()


@dataclass(frozen=True, slots=True)
class EditionLift:
    """One edition's materialised rows, the default they share, and each row's lifted form."""

    rows: tuple[Row, ...]
    source_default: tuple[str, ...] | None
    withheld: str | None
    lifts: Mapping[str, Lift]
    defaults: Defaults


def effective_rows(source: EditionSource) -> tuple[Row, ...]:
    """The edition's materialised rows as the loader finally holds them, with its declared defaults inlined."""
    declared = _manifest_defaults(source.manifest)
    effective = [
        edition_delta_source_effective(
            row,
            origin=origin,
            revision_id=source.revision_id,
            defaults=declared,
            declarations=source.declarations,
        )
        for row, origin in zip(source.rows, source.origins, strict=True)
    ]
    if any(row is None for row in effective):
        raise edition_delta_errors.MigrationRefusedError(
            f"edition {source.revision_id!r}: an inherited reference does not resolve on input"
        )
    return tuple(row for row in effective if row is not None)


def edition_lift(source: EditionSource) -> EditionLift:
    """Derive the edition's shared ``source_refs`` default and lift every materialised row against it.

    A default the manifest already declares is the one the loader will apply, so
    it is kept rather than re-derived: deriving a different run would rewrite
    rows against a default the manifest does not state. No full-copy edition
    declares one, so this only ever binds on the chain path.
    """
    declared = _manifest_defaults(source.manifest)
    rows = effective_rows(source)
    derived, withheld = edition_source_default(rows)
    source_default, withheld = (declared.source_refs, None) if declared.source_refs is not None else (derived, withheld)
    return EditionLift(
        rows=rows,
        source_default=source_default,
        withheld=withheld,
        lifts={
            row_id(row): edition_delta_source_lift(row, source_default=source_default, orden=declared.orden)
            for row in rows
        },
        defaults=Defaults(source_refs=source_default, orden=declared.orden),
    )


def stated_layout(source: EditionSource, stated: frozenset[str]) -> list[tuple[str, list[Block]]]:
    """The fragments that remain once only ``stated`` rows are kept, ordered as the loader reads them.

    Each fragment keeps its authored file name. Casilla sections are packed into
    one ``0001-declarations.toml`` per edition, and dropping rows from it does
    not change what the file is.
    """
    layout: list[tuple[str, list[Block]]] = []
    for fragment in source.fragments:
        kept = [block for block in fragment.blocks if row_id(block.row) in stated]
        if kept:
            layout.append((fragment.path.name, kept))
    names = [name for name, _ in layout]
    duplicated = sorted(name for name, count in Counter(names).items() if count > 1)
    if duplicated:
        raise edition_delta_errors.MigrationRefusedError(
            f"edition {source.revision_id!r}: fragments would share the names {duplicated!r}"
        )
    return sorted(layout, key=lambda item: item[0])


def _family_source_default(table: Mapping[str, object], section: str) -> tuple[str, ...] | None:
    """The edition's shared leading ``source_refs`` run for ``section``, or ``None`` when none derives."""
    members = family_members(table, section)
    if not members:
        return None
    default, _reason = edition_source_default(members)
    return default


def members(
    raw: Mapping[str, object], section: str, *, singleton: bool = False
) -> tuple[Mapping[str, object], ...] | None:
    """Read the member tables of a section from a raw table, optionally as a singleton."""
    value = raw.get(section)
    if value is None:
        return ()
    if singleton and isinstance(value, Mapping):
        return (cast(Mapping[str, object], value),)
    if singleton or not isinstance(value, list | tuple) or any(not isinstance(item, Mapping) for item in value):
        return None
    return tuple(cast(Mapping[str, object], item) for item in value)


def family_members(table: Mapping[str, object], section: str) -> tuple[Row, ...]:
    """Return the edition's resolved members for ``section``, in declared order."""
    raw = table.get(section, ())
    return tuple(as_row(member) for member in (raw if isinstance(raw, list | tuple) else ()))
