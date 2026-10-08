"""Write planned casilla fragments and decide whether a plan changes bytes."""

from __future__ import annotations

from pathlib import Path

from . import edition_delta_errors as _edition_delta_errors
from . import edition_delta_fields as _edition_delta_fields
from . import edition_delta_manifest_writer as _edition_delta_manifest_writer
from . import edition_delta_source as _edition_delta_source
from . import edition_delta_types as _edition_delta_types
from . import edition_delta_writer_lifting as _edition_delta_writer_lifting


def _write_edition(edition_dir: Path, work: _edition_delta_source._EditionWork) -> None:
    casillas = edition_dir / _edition_delta_fields._CASILLAS
    originals = {fragment.path.name: fragment.path.read_text(encoding="utf-8") for fragment in work.source.fragments}
    rendered = _render_fragments(work)
    _remove_unrendered_fragments(casillas, originals, rendered)
    _write_rendered_fragments(casillas, originals, rendered)
    if casillas.exists() and not any(casillas.iterdir()):
        casillas.rmdir()
    _edition_delta_manifest_writer.write_manifest(edition_dir / _edition_delta_fields._MANIFEST, work)


def _render_fragments(work: _edition_delta_source._EditionWork) -> dict[str, str]:
    stated = frozenset(work.plan.stated_ids)
    layout = _edition_delta_source._stated_layout(work.source, stated)
    preambles = {
        fragment.path.name: fragment.preamble
        for fragment in work.source.fragments
        if any(_edition_delta_source._row_id(block.row) in stated for block in fragment.blocks)
    }
    return {
        name: preambles[name]
        + "".join(
            _edition_delta_writer_lifting._lifted_text(block, work.lifts[_edition_delta_source._row_id(block.row)])
            for block in blocks
        )
        for name, blocks in layout
    }


def _remove_unrendered_fragments(casillas: Path, originals: dict[str, str], rendered: dict[str, str]) -> None:
    for name in originals:
        if name not in rendered:
            (casillas / name).unlink()


def _write_rendered_fragments(casillas: Path, originals: dict[str, str], rendered: dict[str, str]) -> None:
    for name, text in rendered.items():
        if name not in originals:
            raise _edition_delta_errors.MigrationRefusedError(f"refusing to write fragment name {name!r}")
        if originals.get(name) == text:
            continue
        (casillas / name).write_text(text.rstrip("\n") + "\n", encoding="utf-8", newline="\n")


def _undeclared_defaults(work: _edition_delta_source._EditionWork) -> bool:
    """Whether writing this edition adds a manifest default not declared yet."""
    plan, manifest = work.plan, work.source.manifest
    if plan.source_default is not None and "casilla_source_refs" not in manifest:
        return True
    return any(key not in manifest for key in work.source.family_defaults)


def _has_storage_operations(plan: _edition_delta_types.EditionPlan) -> bool:
    return bool(plan.casilla_overrides or plan.casilla_removals or plan.casilla_positions)


def _lift_only_changes(work: _edition_delta_source._EditionWork) -> bool:
    stated = {_edition_delta_source._row_id(row): row for row in work.source.stated_rows()}
    planned = {row_id: work.lifts[row_id].row for row_id in work.plan.stated_ids}
    return bool(
        _has_storage_operations(work.plan)
        or work.plan.lifted.total()
        or _undeclared_defaults(work)
        or stated != planned
    )


def _declared_changes(work: _edition_delta_source._EditionWork) -> bool:
    return bool(_has_storage_operations(work.plan) or work.plan.lifted.total() or _undeclared_defaults(work))


def _other_plan_changes(work: _edition_delta_source._EditionWork) -> bool:
    plan = work.plan
    return bool(
        plan.inherited_ids
        or _has_storage_operations(plan)
        or plan.lifted.total()
        or plan.basis
        in {
            _edition_delta_types.PredecessorBasis.ADJACENT,
            _edition_delta_types.PredecessorBasis.STORAGE,
        }
        or work.root_declaration is not None
        or _undeclared_defaults(work)
    )


def _edition_changes(work: _edition_delta_source._EditionWork) -> bool:
    """Whether writing this edition's plan would change any byte of it."""
    plan = work.plan
    if plan.basis is _edition_delta_types.PredecessorBasis.BLOCKED:
        return False
    if plan.basis is _edition_delta_types.PredecessorBasis.LIFT_ONLY:
        return _lift_only_changes(work)
    if plan.basis is _edition_delta_types.PredecessorBasis.DECLARED and isinstance(
        work.source.manifest.get("predecessor"), str
    ):
        return _declared_changes(work)
    return _other_plan_changes(work)
