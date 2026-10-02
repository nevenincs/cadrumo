"""Generate, check and report the declared form layouts of every modelo revision.

``generate`` writes each revision's generator-owned ``form_layouts/`` fragment
(``--check`` compares instead and exits non-zero on drift); a reviewed layout is
never overwritten. A layout the delta converter has keyed against its family
baseline has no fragment of its own, so it is compared as the layout it
hydrates to; when a modelo's layouts change, each of its keyed layouts is
written whole again, for the converter to key against the base edition anew.
``coverage`` states declared and undeclared revisions and placed, working and
unplaced casillas. ``stability`` lists moved placements that carry no
acknowledgement.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Final

import tomlkit
import typer

from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_form_layouts import FormLayoutDefinition

from ..compiler.loader import load_registry_tree
from ..record_design_labels import DATA_ROOT
from .coverage import coverage_rows, coverage_totals
from .generator import generate_modelo_layouts
from .serialization import FORM_LAYOUT_DIRECTORY, form_layout_fragment_path, render_form_layout_toml
from .stability import moved_placements, read_acknowledgements, unacknowledged_moves

__all__ = ["REGISTRY_ROOT", "app", "synchronise_form_layouts"]

REGISTRY_ROOT: Final[Path] = DATA_ROOT / "registry" / "aeat"
_FORM_LAYOUT_FAMILY: Final[str] = "form_layouts"
_REVISION_MANIFEST: Final[str] = "revision.toml"
_STORAGE_OPERATIONS: Final[tuple[str, ...]] = ("family_overrides", "family_removals", "family_positions")

app = typer.Typer(
    name="form_layout",
    help="Generate, check and report the declared form layouts of every modelo revision.",
    no_args_is_help=True,
)


def _is_current(path: Path, revision_id: str, revision: ModeloRevision, layout: FormLayoutDefinition | None) -> bool:
    """Whether the revision already declares the generated ``layout``.

    A fragment stating the layout whole must hold the generator's own bytes. A
    layout keyed against its family baseline states no fragment, so it is
    current when the layout it hydrates to is the generated one.
    """
    if layout is None:
        return not path.is_file() and not revision.form_layouts
    if path.is_file():
        return path.read_text(encoding="utf-8") == render_form_layout_toml(revision_id, layout)
    return revision.form_layouts == (layout,)


def _state_layout_whole(revision_root: Path, revision_id: str) -> None:
    """Drop the edition's form-layout storage delta so its fragment states the layout whole.

    A keyed edition asserts the family in ``scoped_families`` and stores its
    layout as operations against its family baseline. Left beside a rewritten
    fragment those operations would patch a member the fragment supersedes;
    an unasserted scoped family is the whole statement the converter keys.
    """
    manifest_path = revision_root / _REVISION_MANIFEST
    if not manifest_path.is_file():
        return
    document = tomlkit.parse(manifest_path.read_text(encoding="utf-8"))
    table = document["revisions"][revision_id]
    changed = False
    for key in _STORAGE_OPERATIONS:
        operations = table.get(key)
        if operations is None:
            continue
        retained = [operation for operation in operations if operation.get("family") != _FORM_LAYOUT_FAMILY]
        if len(retained) == len(operations):
            continue
        changed = True
        if retained:
            operations.clear()
            operations.extend(retained)
        else:
            del table[key]
    scoped = table.get("scoped_families")
    if scoped is not None and _FORM_LAYOUT_FAMILY in scoped:
        changed = True
        remaining = [family for family in scoped if family != _FORM_LAYOUT_FAMILY]
        if remaining:
            table["scoped_families"] = remaining
        else:
            del table["scoped_families"]
    if changed:
        manifest_path.write_text(tomlkit.dumps(document), encoding="utf-8", newline="\n")


def _write_layout(path: Path, revision_id: str, layout: FormLayoutDefinition | None) -> None:
    """Write ``layout`` as the revision's whole fragment, or remove the fragment when there is none."""
    _state_layout_whole(path.parent.parent, revision_id)
    if layout is not None:
        path.parent.mkdir(exist_ok=True)
        path.write_text(render_form_layout_toml(revision_id, layout), encoding="utf-8", newline="\n")
        return
    if path.is_file():
        path.unlink()
        if path.parent.name == FORM_LAYOUT_DIRECTORY and not any(path.parent.iterdir()):
            path.parent.rmdir()


def synchronise_form_layouts(
    registry_root: Path,
    data_root: Path,
    *,
    modelos: tuple[str, ...] = (),
    check: bool = False,
) -> tuple[list[str], list[str]]:
    """Bring every selected revision's layout in line with the generator.

    Returns the changed fragment paths (written, or that would be written under
    ``check``) and one report line per revision left without a layout.

    A keyed layout is a delta against its family baseline's stored layout, so
    once any layout of a modelo changes, every keyed layout of that modelo is
    written whole again rather than left patching a baseline that moved.
    Re-running the delta converter on the modelo keys them afresh.
    """
    loaded, catalogues = load_registry_tree(registry_root)
    changed: list[str] = []
    undeclared: list[str] = []
    for modelo in sorted(loaded, key=lambda item: str(item.id)):
        if modelos and str(modelo.id) not in modelos:
            continue
        outcomes = generate_modelo_layouts(modelo, sources=catalogues.sources, data_root=data_root)
        modelo_root = registry_root / "modelos" / str(modelo.id) / "revisions"
        stale: set[str] = set()
        for revision_id, outcome in outcomes.items():
            if outcome.layout is None:
                undeclared.append(f"{modelo.id} {revision_id}: {outcome.failure}")
            path = form_layout_fragment_path(modelo_root / str(revision_id))
            if not _is_current(path, str(revision_id), modelo.revisions[revision_id], outcome.layout):
                stale.add(str(revision_id))
        if check:
            changed.extend(
                form_layout_fragment_path(modelo_root / revision_id).as_posix() for revision_id in sorted(stale)
            )
            continue
        if not stale:
            continue
        keyed = {
            str(revision_id)
            for revision_id, revision in modelo.revisions.items()
            if _FORM_LAYOUT_FAMILY in revision.scoped_families
        }
        for revision_id in sorted(stale | keyed):
            revision = modelo.revisions[revision_id]
            outcome = outcomes.get(revision_id)
            layout = outcome.layout if outcome is not None else (revision.form_layouts or (None,))[0]
            path = form_layout_fragment_path(modelo_root / revision_id)
            _write_layout(path, revision_id, layout)
            changed.append(path.as_posix())
    return changed, undeclared


@app.command()
def generate(
    modelo: Annotated[list[str] | None, typer.Option(help="Restrict to these modelos (repeatable).")] = None,
    check: Annotated[bool, typer.Option(help="Compare instead of writing; exit 1 on drift.")] = False,
) -> None:
    """Write (or check) every revision's generated form layout fragment."""
    changed, undeclared = synchronise_form_layouts(REGISTRY_ROOT, DATA_ROOT, modelos=tuple(modelo or ()), check=check)
    for line in undeclared:
        typer.echo(f"undeclared: {line}")
    verb = "stale" if check else "written"
    for path in changed:
        typer.echo(f"{verb}: {path}")
    typer.echo(f"{len(changed)} fragment(s) {verb}, {len(undeclared)} revision(s) without a layout")
    if check and changed:
        raise typer.Exit(1)


@app.command()
def coverage(
    json_output: Annotated[bool, typer.Option("--json", help="Emit the rows and totals as JSON.")] = False,
) -> None:
    """Report declared layouts and placed, working and unplaced casillas per revision."""
    loaded, _catalogues = load_registry_tree(REGISTRY_ROOT)
    rows = coverage_rows(loaded)
    totals = coverage_totals(rows)
    if json_output:
        typer.echo(json.dumps({"totals": totals, "revisions": [row.as_json() for row in rows]}, ensure_ascii=False))
        return
    for row in rows:
        reasons = ", ".join(f"{reason} {count}" for reason, count in sorted(row.unplaced_reasons.items()))
        state = "undeclared" if not row.declared else f"{row.review_state} {row.seed_source}"
        typer.echo(
            f"{row.modelo_id} {row.revision_id}: {state}; casillas {row.casillas}, on form {row.on_form}, "
            f"working {row.working_figure}, unplaced {row.unplaced}" + (f" ({reasons})" if reasons else "")
        )
    typer.echo(" ".join(f"{key}={value}" for key, value in totals.items()))


@app.command()
def stability() -> None:
    """List moved placements without an acknowledgement, and stale acknowledgements."""
    loaded, _catalogues = load_registry_tree(REGISTRY_ROOT)
    missing, stale = unacknowledged_moves(moved_placements(loaded), read_acknowledgements())
    for move in missing:
        typer.echo(
            f"unacknowledged: {move.modelo_id} {move.revision_id} {move.casilla_id} "
            f"{move.from_position} -> {move.to_position}"
        )
    for move in stale:
        typer.echo(f"stale acknowledgement: {move.modelo_id} {move.revision_id} {move.casilla_id}")
    if missing or stale:
        raise typer.Exit(1)
