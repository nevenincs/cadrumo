"""Generate, check and report the declared form layouts of every modelo revision.

``generate`` writes each revision's generator-owned ``form_layouts/`` fragment
(``--check`` compares instead and exits non-zero on drift); a reviewed layout is
never overwritten. ``coverage`` states declared and undeclared revisions and
placed, working and unplaced casillas. ``stability`` lists moved placements
that carry no acknowledgement.
"""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Annotated, Final

import typer

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema_form_layouts import FormLayoutReviewState

from ..compiler.loader import load_registry_tree
from ..record_design_labels import DATA_ROOT
from .coverage import coverage_rows, coverage_totals
from .generator import LayoutGeneration, generate_modelo_layouts
from .serialization import FORM_LAYOUT_DIRECTORY, form_layout_fragment_path, render_form_layout_toml
from .stability import moved_placements, read_acknowledgements, unacknowledged_moves

__all__ = ["REGISTRY_ROOT", "app", "synchronise_form_layouts", "synchronise_selected_form_layout"]

REGISTRY_ROOT: Final[Path] = DATA_ROOT / "registry" / "aeat"

app = typer.Typer(
    name="form_layout",
    help="Generate, check and report the declared form layouts of every modelo revision.",
    no_args_is_help=True,
)


def _remove_empty_layout_directory(path: Path) -> None:
    if path.parent.name == FORM_LAYOUT_DIRECTORY and not any(path.parent.iterdir()):
        path.parent.rmdir()


def _record_undeclared_layout(path: Path, *, check: bool, changed: list[str]) -> None:
    if not path.is_file():
        return
    changed.append(path.as_posix())
    if check:
        return
    path.unlink()
    _remove_empty_layout_directory(path)


def _record_generated_layout(path: Path, text: str, *, check: bool, changed: list[str]) -> None:
    if path.is_file() and path.read_text(encoding="utf-8") == text:
        return
    changed.append(path.as_posix())
    if check:
        return
    path.parent.mkdir(exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _require_owned_layout_directory(path: Path) -> None:
    """Refuse a layout directory holding a fragment the generator does not own.

    The loader merges every fragment of the section, so the generated fragment
    written beside another one leaves a revision that no longer loads.
    """
    if not path.parent.is_dir():
        return
    foreign = sorted(entry.name for entry in path.parent.iterdir() if entry.name != path.name)
    if foreign:
        raise RegistryValidationError(
            f"form layout directory {path.parent.as_posix()} holds fragments its generator does not own: "
            + ", ".join(foreign)
        )


def _record_revision_layout(
    registry_root: Path,
    modelo_id: str,
    revision_id: str,
    outcome: LayoutGeneration,
    *,
    check: bool,
    changed: list[str],
    undeclared: list[str],
) -> None:
    path = form_layout_fragment_path(registry_root / "modelos" / modelo_id / "revisions" / revision_id)
    _require_owned_layout_directory(path)
    if outcome.layout is None:
        undeclared.append(f"{modelo_id} {revision_id}: {outcome.failure}")
        _record_undeclared_layout(path, check=check, changed=changed)
        return
    text = render_form_layout_toml(revision_id, outcome.layout)
    _record_generated_layout(path, text, check=check, changed=changed)


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
            _record_revision_layout(
                registry_root,
                str(modelo.id),
                str(revision_id),
                outcome,
                check=check,
                changed=changed,
                undeclared=undeclared,
            )
    return changed, undeclared


def synchronise_selected_form_layout(
    registry_root: Path,
    data_root: Path,
    *,
    modelo_id: str,
    revision_id: str,
    expected_old_sha256: str,
    expected_new_sha256: str,
) -> bool:
    """Write only one generated form after exact old/new byte preconditions."""
    loaded, catalogues = load_registry_tree(registry_root)
    modelo = next((item for item in loaded if str(item.id) == modelo_id), None)
    if modelo is None or revision_id not in modelo.revisions:
        raise RegistryValidationError("selected form owner revision is absent")
    revision = modelo.revisions[revision_id]
    if len(revision.form_layouts) != 1 or revision.form_layouts[0].review.state is FormLayoutReviewState.REVIEWED:
        raise RegistryValidationError("selected form owner requires one unreviewed generated layout")
    path = form_layout_fragment_path(registry_root / "modelos" / modelo_id / "revisions" / revision_id)
    if not path.is_file() or sha256(path.read_bytes()).hexdigest() != expected_old_sha256:
        raise RegistryValidationError("selected form owner old fragment changed")
    outcome = generate_modelo_layouts(modelo, sources=catalogues.sources, data_root=data_root)[revision_id]
    if outcome.layout is None:
        raise RegistryValidationError(f"selected form owner cannot generate its layout: {outcome.failure}")
    text = render_form_layout_toml(revision_id, outcome.layout)
    if sha256(text.encode("utf-8")).hexdigest() != expected_new_sha256:
        raise RegistryValidationError("selected form owner output differs from the reviewed candidate")
    changed: list[str] = []
    _record_generated_layout(path, text, check=False, changed=changed)
    if changed not in ([], [path.as_posix()]):
        raise RegistryValidationError("selected form owner changed an unexpected path")
    return bool(changed)


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
