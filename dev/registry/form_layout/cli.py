"""Generate, check and report the declared form layouts of every modelo revision.

``generate`` writes each revision's generator-owned ``form_layouts/`` fragment
(``--check`` compares instead and exits non-zero on drift); a reviewed layout is
never overwritten. ``coverage`` states declared and undeclared revisions and
placed, working and unplaced casillas. ``stability`` lists moved placements
that carry no acknowledgement.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Final

import typer

from ..compiler.loader import load_registry_tree
from ..record_design_labels import DATA_ROOT
from .coverage import coverage_rows, coverage_totals
from .generator import generate_modelo_layouts
from .serialization import FORM_LAYOUT_DIRECTORY, form_layout_fragment_path, render_form_layout_toml
from .stability import moved_placements, read_acknowledgements, unacknowledged_moves

__all__ = ["REGISTRY_ROOT", "app", "synchronise_form_layouts"]

REGISTRY_ROOT: Final[Path] = DATA_ROOT / "registry" / "aeat"

app = typer.Typer(
    name="form_layout",
    help="Generate, check and report the declared form layouts of every modelo revision.",
    no_args_is_help=True,
)


def synchronise_form_layouts(
    registry_root: Path,
    data_root: Path,
    *,
    modelos: tuple[str, ...] = (),
    check: bool = False,
) -> tuple[list[str], list[str]]:
    """Bring every selected revision's fragment in line with the generator.

    Returns the changed fragment paths (written, or that would be written under
    ``check``) and one report line per revision left without a layout.
    """
    loaded, catalogues = load_registry_tree(registry_root)
    changed: list[str] = []
    undeclared: list[str] = []
    for modelo in sorted(loaded, key=lambda item: str(item.id)):
        if modelos and str(modelo.id) not in modelos:
            continue
        outcomes = generate_modelo_layouts(modelo, sources=catalogues.sources, data_root=data_root)
        for revision_id, outcome in outcomes.items():
            path = form_layout_fragment_path(
                registry_root / "modelos" / str(modelo.id) / "revisions" / str(revision_id)
            )
            if outcome.layout is None:
                undeclared.append(f"{modelo.id} {revision_id}: {outcome.failure}")
                if path.is_file():
                    changed.append(path.as_posix())
                    if not check:
                        path.unlink()
                        if path.parent.name == FORM_LAYOUT_DIRECTORY and not any(path.parent.iterdir()):
                            path.parent.rmdir()
                continue
            text = render_form_layout_toml(str(revision_id), outcome.layout)
            if path.is_file() and path.read_text(encoding="utf-8") == text:
                continue
            changed.append(path.as_posix())
            if not check:
                path.parent.mkdir(exist_ok=True)
                path.write_text(text, encoding="utf-8", newline="\n")
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
