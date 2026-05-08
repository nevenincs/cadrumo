"""``aeat archive`` Typer group: portable export and import of every secure object.

Two verbs:

- ``aeat archive export <path>`` — produce a JSON bundle covering every
  registered namespace (or a ``--namespace``-filtered subset) and write
  it to ``<path>``. Re-runnable; the bundle's records are sorted for
  deterministic diffability.
- ``aeat archive import <path>`` — restore a bundle into the encrypted
  SQL backend under the active master key. The default conflict policy
  is ``fail`` so colliding records abort the operation; ``--conflict
  overwrite`` and ``--conflict keep`` switch the discipline.

The bundle is the same JSON shape on every machine, regardless of
master key, so an export taken on machine A round-trips on machine B
provided B has the destination domain code at compatible schema
versions.
"""

from __future__ import annotations

from pathlib import Path

import typer

from ...application.archive import (
    ArchiveBundle,
    ConflictPolicy,
    create_archive,
    restore_archive,
)
from ._common import _emit

app = typer.Typer(
    name="archive",
    no_args_is_help=True,
    help="Export and import every encrypted secure-object the user owns.",
)


@app.command(name="export", help="Write every secure-object to a JSON bundle.")
def export_cmd(
    ctx: typer.Context,
    path: Path = typer.Argument(..., help="Destination file. Parent directory is created if missing."),
    namespace: list[str] = typer.Option(
        [],
        "--namespace",
        "-n",
        help="Restrict the export to one or more registered namespaces. Repeat to add namespaces.",
    ),
    bundle_id: str | None = typer.Option(
        None,
        "--bundle-id",
        help="Optional caller-supplied bundle identifier; defaults to a fresh UUID4 hex string.",
    ),
) -> None:
    """Write the bundle JSON to ``path`` and report a one-line summary."""
    namespaces = tuple(namespace) if namespace else None
    bundle = create_archive(namespaces=namespaces, bundle_id=bundle_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(bundle.model_dump_json(indent=2), encoding="utf-8")
    payload = {
        "bundle_id": bundle.bundle_id,
        "records": len(bundle.records),
        "namespaces": sorted({record.namespace for record in bundle.records}),
        "path": str(path),
    }
    _emit(
        ctx,
        payload,
        [
            f"bundle_id\t{bundle.bundle_id}",
            f"records\t{len(bundle.records)}",
            f"path\t{path}",
        ],
    )


@app.command(name="import", help="Restore a JSON bundle into the encrypted SQL backend.")
def import_cmd(
    ctx: typer.Context,
    path: Path = typer.Argument(..., exists=True, readable=True, help="Bundle file to restore."),
    conflict: ConflictPolicy = typer.Option(
        ConflictPolicy.FAIL,
        "--conflict",
        case_sensitive=False,
        help=(
            "Policy applied when a record collides with an existing object. "
            "fail aborts the restore; keep preserves the live object; "
            "overwrite replaces it."
        ),
    ),
) -> None:
    """Validate and apply the bundle at ``path`` under ``--conflict`` semantics."""
    bundle = ArchiveBundle.model_validate_json(path.read_text(encoding="utf-8"))
    report = restore_archive(bundle, conflict_policy=conflict)
    payload = {
        "bundle_id": report.bundle_id,
        "entries": [
            {
                "namespace": entry.namespace,
                "object_key": entry.object_key,
                "outcome": entry.outcome.value,
            }
            for entry in report.entries
        ],
    }
    _emit(
        ctx,
        payload,
        [
            f"bundle_id\t{report.bundle_id}",
            *(f"{entry.outcome.value}\t{entry.namespace}\t{entry.object_key}" for entry in report.entries),
        ],
    )
