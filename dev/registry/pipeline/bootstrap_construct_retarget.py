"""Retarget reviewed construct references in isolated export candidates."""

from __future__ import annotations

from pathlib import Path

import rtoml

__all__ = ["retarget_bootstrap_construct_export_layout", "retarget_bootstrap_constructs_in_revision"]


def retarget_bootstrap_construct_export_layout(
    staged_modelo_root: Path,
    *,
    revision: str,
    superseded_layout_id: str,
    generated_layout_id: str,
    expected_references: int,
) -> None:
    """Retarget the explicitly pinned construct members in an isolated candidate."""
    retarget_bootstrap_constructs_in_revision(
        staged_modelo_root / "revisions" / revision,
        revision=revision,
        superseded_layout_id=superseded_layout_id,
        generated_layout_id=generated_layout_id,
        expected_references=expected_references,
    )


def retarget_bootstrap_constructs_in_revision(
    revision_root: Path,
    *,
    revision: str,
    superseded_layout_id: str,
    generated_layout_id: str,
    expected_references: int,
) -> None:
    """Retarget only constructs physically declared in one staged revision."""
    replacements = 0
    updates: list[tuple[Path, dict[str, object]]] = []
    construct_root = revision_root / "constructs"
    for path in sorted(construct_root.glob("*.toml")):
        payload = rtoml.load(path)
        revision_payload = payload.get("revisions", {}).get(revision, {})
        constructs = revision_payload.get("constructs", [])
        changed = False
        for construct in constructs:
            layout_ids = construct.get("export_layouts", [])
            occurrences = layout_ids.count(superseded_layout_id)
            if occurrences:
                construct["export_layouts"] = [
                    generated_layout_id if layout_id == superseded_layout_id else layout_id for layout_id in layout_ids
                ]
                replacements += occurrences
                changed = True
        if changed:
            updates.append((path, payload))
    if replacements != expected_references:
        raise ValueError(
            f"bootstrap superseded layout {superseded_layout_id!r} expected {expected_references} "
            f"construct reference(s), found {replacements}",
        )
    for path, payload in updates:
        path.write_text(rtoml.dumps(payload, pretty=True), encoding="utf-8", newline="")
