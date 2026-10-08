"""Validate and retire reviewed manual export-layout bootstrap authority."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import suppress
from hashlib import sha256
from pathlib import Path

import rtoml

from cadrumo.core.directory_scan import DirectoryEntryKind, scan_directory
from cadrumo.core.hashing import canonical_json_bytes
from cadrumo.core.link_safety import is_link_like
from cadrumo.core.toml import parse_toml
from cadrumo.domain.calculations.registry.schema import ModeloDefinition

from ..compiler.loader import load_modelo_directory, load_shared_catalogues

__all__ = [
    "bootstrap_layout_supersession_fingerprint",
    "bootstrap_manual_source_revision_root",
    "require_stable_layout_identity_for_storage_lineage",
    "retire_bootstrap_manual_export_layout",
    "validate_bootstrap_manual_export_layout_supersession",
]


def validate_bootstrap_manual_export_layout_supersession(
    source_modelo_root: Path,
    *,
    revision: str,
    superseded_layout_id: str,
    expected_references: int,
    generated_layout_id: str | None = None,
    source_ref: str | None = None,
    source_sha256: str | None = None,
    manual_source_sha256: str | None = None,
    manual_origin_revision: str | None = None,
) -> str:
    """Prove one reviewed manual layout and return a receipt over its source pins.

    A bootstrap declaration identifies one exact loader-visible manual layout.
    It cannot authorize dropping an absent layout, a generated tree, multiple
    layouts, or a construct-reference count that changed since review.
    """
    revision_root = source_modelo_root / "revisions" / revision
    _require_manual_supersession_target(revision_root, revision)
    loaded = load_modelo_directory(source_modelo_root)
    loaded_revision = _required_supersession_revision(loaded, revision)
    manual_source_root, manual_revision = bootstrap_manual_source_revision_root(
        source_modelo_root, loaded, revision=revision, expected_origin_revision=manual_origin_revision
    )
    _require_inherited_supersession_pins(
        manual_source_root,
        revision_root,
        manual_origin_revision=manual_origin_revision,
        source_ref=source_ref,
        source_sha256=source_sha256,
    )
    _require_manual_source_fingerprint(manual_source_root, manual_source_sha256)
    _require_manual_layout_identity(manual_source_root, manual_revision, superseded_layout_id)
    _require_loaded_layout_identity(loaded_revision, superseded_layout_id)
    _require_reviewed_bootstrap_source(
        source_modelo_root,
        loaded_revision,
        source_ref=source_ref,
        source_sha256=source_sha256,
    )
    if generated_layout_id is not None:
        require_stable_layout_identity_for_storage_lineage(
            loaded,
            revision=revision,
            superseded_layout_id=superseded_layout_id,
            generated_layout_id=generated_layout_id,
        )
    _require_construct_reference_count(loaded_revision, superseded_layout_id, expected_references)
    return bootstrap_layout_supersession_fingerprint(revision_root)


def _require_manual_supersession_target(revision_root: Path, revision: str) -> None:
    export_root = revision_root / "export"
    if export_root.exists() or is_link_like(export_root):
        raise ValueError(f"bootstrap supersession target {revision!r} already has a generated export tree")


def _required_supersession_revision(modelo: ModeloDefinition, revision: str):
    loaded_revision = modelo.revisions.get(revision)
    if loaded_revision is None:
        raise ValueError(f"bootstrap supersession revision {revision!r} is not declared")
    return loaded_revision


def _require_inherited_supersession_pins(
    manual_source_root: Path,
    revision_root: Path,
    *,
    manual_origin_revision: str | None,
    source_ref: str | None,
    source_sha256: str | None,
) -> None:
    if manual_source_root == revision_root:
        return
    if manual_origin_revision is None:
        raise ValueError("inherited bootstrap supersession requires an exact manual origin revision")
    if source_ref is None or source_sha256 is None:
        raise ValueError("inherited bootstrap supersession requires an exact source reference and digest")


def _require_manual_source_fingerprint(manual_source_root: Path, expected_sha256: str | None) -> None:
    if expected_sha256 is not None and bootstrap_layout_supersession_fingerprint(manual_source_root) != expected_sha256:
        raise ValueError("bootstrap superseded manual ancestor changed after source review")


def _require_manual_layout_identity(manual_source_root: Path, revision: str, expected_layout_id: str) -> None:
    manual_ids = _manual_export_layout_ids(manual_source_root / "export_layouts", revision=revision)
    if manual_ids != (expected_layout_id,):
        raise ValueError(
            f"bootstrap supersession expected exactly manual layout {expected_layout_id!r}; manual={manual_ids!r}",
        )


def _require_loaded_layout_identity(loaded_revision, expected_layout_id: str) -> None:
    loaded_ids = tuple(str(layout.id) for layout in loaded_revision.export_layouts)
    if loaded_ids != (expected_layout_id,):
        raise ValueError(
            f"bootstrap supersession expected exactly manual layout {expected_layout_id!r}; loaded={loaded_ids!r}",
        )


def _require_reviewed_bootstrap_source(
    source_modelo_root: Path,
    loaded_revision,
    *,
    source_ref: str | None,
    source_sha256: str | None,
) -> None:
    if source_ref is None and source_sha256 is None:
        return
    source_ref, source_sha256 = _require_bootstrap_source_pair(source_ref, source_sha256)
    _require_bootstrap_source_citation(loaded_revision, source_ref)
    _require_bootstrap_catalogue_digest(source_modelo_root, source_ref, source_sha256)


def _require_bootstrap_source_pair(source_ref: str | None, source_sha256: str | None) -> tuple[str, str]:
    if not source_ref or not source_sha256:
        raise ValueError("bootstrap supersession source reference and digest must be paired")
    return source_ref, source_sha256


def _require_bootstrap_source_citation(loaded_revision, source_ref: str) -> None:
    if source_ref not in {str(ref) for ref in loaded_revision.export_layouts[0].source_refs}:
        raise ValueError(f"bootstrap superseded layout does not cite source {source_ref!r}")


def _require_bootstrap_catalogue_digest(
    source_modelo_root: Path,
    source_ref: str,
    source_sha256: str,
) -> None:
    sources = load_shared_catalogues(source_modelo_root.parent.parent).sources
    source = next((item for ref, item in sources.items() if str(ref) == source_ref), None)
    if source is None or source.sha256 != source_sha256:
        raise ValueError(f"bootstrap supersession source {source_ref!r} digest changed or is absent")


def _require_construct_reference_count(loaded_revision, superseded_layout_id: str, expected_references: int) -> None:
    references = sum(
        str(layout_id) == superseded_layout_id
        for construct in loaded_revision.constructs
        for layout_id in construct.export_layouts
    )
    if references != expected_references:
        raise ValueError(
            f"bootstrap superseded layout {superseded_layout_id!r} expected {expected_references} "
            f"construct reference(s), found {references}",
        )


def bootstrap_manual_source_revision_root(
    source_modelo_root: Path,
    modelo: ModeloDefinition,
    *,
    revision: str,
    expected_origin_revision: str | None = None,
) -> tuple[Path, str]:
    """Trace the unique physical manual declaration along declared family storage."""
    current = revision
    seen: set[str] = set()
    while current not in seen:
        seen.add(current)
        manual_root = _physical_manual_revision_root(
            source_modelo_root,
            current,
            expected_origin_revision=expected_origin_revision,
        )
        if manual_root is not None:
            return manual_root, current
        current = _declared_manual_storage_ancestor(modelo, current, revision, expected_origin_revision)
    raise ValueError(f"bootstrap superseded manual layout storage ancestry cycles: {revision!r}")


def _physical_manual_revision_root(
    source_modelo_root: Path,
    revision: str,
    *,
    expected_origin_revision: str | None,
) -> Path | None:
    revision_root = source_modelo_root / "revisions" / revision
    if (revision_root / "export").exists() or is_link_like(revision_root / "export"):
        raise ValueError(f"bootstrap manual ancestor {revision!r} already has generated export authority")
    manual_root = revision_root / "export_layouts"
    if not manual_root.exists() and not is_link_like(manual_root):
        return None
    if is_link_like(manual_root) or not manual_root.is_dir():
        raise ValueError(f"bootstrap manual ancestor is not a regular directory: {manual_root}")
    if expected_origin_revision is not None and revision != expected_origin_revision:
        raise ValueError(f"bootstrap manual origin is {revision!r}, not reviewed {expected_origin_revision!r}")
    return revision_root


def _declared_manual_storage_ancestor(
    modelo: ModeloDefinition,
    current: str,
    target_revision: str,
    expected_origin_revision: str | None,
) -> str:
    if current == expected_origin_revision:
        raise ValueError(f"bootstrap reviewed manual origin {current!r} has no physical declaration")
    declared = modelo.revisions.get(current)
    if declared is None or declared.family_storage_baseline is None:
        raise ValueError(f"bootstrap superseded manual layout has no declared storage ancestor: {target_revision!r}")
    return str(declared.family_storage_baseline)


def require_stable_layout_identity_for_storage_lineage(
    modelo: ModeloDefinition,
    *,
    revision: str,
    superseded_layout_id: str,
    generated_layout_id: str,
) -> None:
    """Refuse a new ID when another edition hydrates that layout through shared storage."""
    if generated_layout_id == superseded_layout_id:
        return
    revisions = {str(key): item for key, item in modelo.revisions.items()}

    def storage_ancestors(revision_id: str) -> set[str]:
        ancestors: set[str] = set()
        current = revisions[revision_id]
        while current.family_storage_baseline is not None:
            baseline = str(current.family_storage_baseline)
            if baseline in ancestors or baseline not in revisions:
                raise ValueError(f"invalid export-layout storage ancestry for {revision_id!r}")
            ancestors.add(baseline)
            current = revisions[baseline]
        return ancestors

    target_ancestors = storage_ancestors(revision)
    for sibling_id, sibling in revisions.items():
        if sibling_id == revision or not any(
            str(layout.id) == superseded_layout_id for layout in sibling.export_layouts
        ):
            continue
        if sibling_id in target_ancestors or revision in storage_ancestors(sibling_id):
            raise ValueError(
                f"bootstrap supersession of {revision!r} must retain stable layout id "
                f"{superseded_layout_id!r} shared with storage-linked revision {sibling_id!r}",
            )


def _manual_export_layout_ids(manual_root: Path, *, revision: str) -> tuple[str, ...]:
    """Read explicit loader-visible layout identities from manual fragments."""
    _require_manual_fragment_directory(manual_root)
    identifiers: list[str] = []
    for fragment in sorted(scan_directory(manual_root, pattern="*.toml", recursive=True)):
        identifiers.extend(_manual_fragment_layout_ids(fragment, revision=revision))
    return tuple(identifiers)


def _require_manual_fragment_directory(manual_root: Path) -> None:
    if is_link_like(manual_root) or not manual_root.is_dir():
        raise ValueError(f"bootstrap supersession manual fragment root is not a regular directory: {manual_root}")


def _manual_fragment_layout_ids(fragment: Path, *, revision: str) -> tuple[str, ...]:
    if is_link_like(fragment) or not fragment.is_file():
        raise ValueError(f"bootstrap supersession manual fragment is not a regular file: {fragment}")
    payload = parse_toml(fragment.read_text("utf-8"))
    revision_payload = payload.get("revisions", {}).get(revision, {})
    declarations = revision_payload.get("export_layouts", [])
    if not isinstance(declarations, list):
        raise ValueError(f"bootstrap supersession manual layouts are malformed in {fragment}")
    return tuple(_manual_fragment_layout_id(item, fragment) for item in declarations)


def _manual_fragment_layout_id(declaration: object, fragment: Path) -> str:
    identifier = declaration.get("id") if isinstance(declaration, Mapping) else None
    if not isinstance(identifier, str) or not identifier:
        raise ValueError(f"bootstrap supersession manual layout has no exact id in {fragment}")
    return identifier


def bootstrap_layout_supersession_fingerprint(revision_root: Path) -> str:
    """Hash every regular file in the revision that a bundle cutover replaces."""
    if is_link_like(revision_root) or not revision_root.is_dir():
        raise ValueError(f"bootstrap supersession source revision is not a regular directory: {revision_root}")
    members: list[tuple[str, str]] = []
    for path in sorted(scan_directory(revision_root, recursive=True, select=DirectoryEntryKind.FILES)):
        if is_link_like(path) or not path.is_file():
            raise ValueError(f"bootstrap supersession source member is not a regular file: {path}")
        members.append((path.relative_to(revision_root).as_posix(), sha256(path.read_bytes()).hexdigest()))
    return sha256(canonical_json_bytes(members)).hexdigest()


def retire_bootstrap_manual_export_layout(
    revision_root: Path,
    *,
    revision: str,
    superseded_layout_id: str,
) -> None:
    """Remove one pinned manual layout from staged fragments, retaining other content."""
    manual_root = revision_root / "export_layouts"
    removed = sum(
        _retire_manual_layout_from_fragment(fragment, revision=revision, superseded_layout_id=superseded_layout_id)
        for fragment in sorted(scan_directory(manual_root, pattern="*.toml", recursive=True))
    )
    if removed != 1:
        raise ValueError(
            f"bootstrap superseded layout {superseded_layout_id!r} expected one manual declaration, found {removed}",
        )
    with suppress(OSError):
        manual_root.rmdir()


def _retire_manual_layout_from_fragment(fragment: Path, *, revision: str, superseded_layout_id: str) -> int:
    payload, revisions, revision_payload, declarations = _manual_layout_fragment_state(fragment, revision=revision)
    retained = [
        declaration
        for declaration in declarations
        if not isinstance(declaration, Mapping) or declaration.get("id") != superseded_layout_id
    ]
    removed = len(declarations) - len(retained)
    if not removed:
        return 0
    _write_retained_manual_layouts(fragment, payload, revisions, revision_payload, retained, revision)
    return removed


def _manual_layout_fragment_state(fragment: Path, *, revision: str):
    if is_link_like(fragment) or not fragment.is_file():
        raise ValueError(f"bootstrap supersession manual fragment is not a regular file: {fragment}")
    payload = parse_toml(fragment.read_text("utf-8"))
    revisions = payload.get("revisions", {})
    revision_payload = revisions.get(revision, {}) if isinstance(revisions, Mapping) else {}
    declarations = revision_payload.get("export_layouts", []) if isinstance(revision_payload, Mapping) else []
    if not isinstance(declarations, list):
        raise ValueError(f"bootstrap supersession manual layouts are malformed in {fragment}")
    return payload, revisions, revision_payload, declarations


def _write_retained_manual_layouts(
    fragment: Path,
    payload: dict[str, object],
    revisions: dict[str, object],
    revision_payload: dict[str, object],
    retained: list[object],
    revision: str,
) -> None:
    if retained:
        revision_payload["export_layouts"] = retained
    else:
        revision_payload.pop("export_layouts", None)
    if not revision_payload:
        revisions.pop(revision, None)
    if not revisions:
        payload.pop("revisions", None)
    if payload:
        fragment.write_text(rtoml.dumps(payload, pretty=True), encoding="utf-8", newline="")
    else:
        fragment.unlink()
