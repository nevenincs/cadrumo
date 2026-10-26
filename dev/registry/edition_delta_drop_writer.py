"""Write already-planned restatement drops to a caller-owned staged registry tree."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from . import edition_delta_drop_scope as _edition_delta_drop_scope
from . import edition_delta_errors as _edition_delta_errors
from . import edition_delta_fields as _edition_delta_fields
from . import edition_delta_manifest_writer as _edition_delta_manifest_writer
from .edition_delta_drop_planning import _identity_of, _read_family_fragments
from .edition_delta_drop_types import EditionDrop, FamilyDrop, _MemberFragment

__all__ = ("stage_declaration_drop",)


def _rewrite_family_fragment(
    fragment: _MemberFragment, family: _edition_delta_drop_scope._DroppableFamily, dropped: frozenset[str]
) -> None:
    """Remove the dropped members from one fragment, deleting a fragment left holding nothing."""
    kept = [block for block in fragment.blocks if _identity_of(block.row, family) not in dropped]
    if len(kept) == len(fragment.blocks):
        return
    if kept:
        text = fragment.preamble + "".join(block.text for block in kept)
        fragment.path.write_text(text.rstrip("\n") + "\n", encoding="utf-8", newline="\n")
        return
    if fragment.preamble.strip() and not all(
        not line.strip() or line.lstrip().startswith("#") for line in fragment.preamble.splitlines()
    ):
        raise _edition_delta_errors.MigrationRefusedError(
            f"{fragment.path}: every member would be dropped but the fragment carries declarations outside them, "
            "which this tool does not rewrite",
        )
    fragment.path.unlink()


def _write_drop(
    modelo_dir: Path, edition: EditionDrop, families: Mapping[str, _edition_delta_drop_scope._DroppableFamily]
) -> None:
    """Apply one edition's planned drops to a staged tree."""
    edition_dir = modelo_dir / "revisions" / edition.revision_id
    attestations = tuple(attestation for drop in edition.families for attestation in drop.lineage_attestations)
    if attestations:
        manifest_path = edition_dir / _edition_delta_fields._MANIFEST
        text = manifest_path.read_text(encoding="utf-8")
        manifest_path.write_text(
            _edition_delta_manifest_writer._append_lineage_attestations(text, attestations),
            encoding="utf-8",
            newline="\n",
        )
    for drop in edition.families:
        if not drop.dropped:
            continue
        family = families[drop.section]
        dropped = frozenset(drop.dropped)
        for fragment in _read_family_fragments(edition_dir, drop.section):
            _rewrite_family_fragment(fragment, family, dropped)
        section_dir = edition_dir / drop.section
        if section_dir.is_dir() and not any(section_dir.iterdir()):
            section_dir.rmdir()


def _family_drop_comments(
    modelo_dir: Path,
    edition: EditionDrop,
    drop: FamilyDrop,
    family: _edition_delta_drop_scope._DroppableFamily,
) -> list[str]:
    from .source_tree_installation import toml_comments

    comments: list[str] = []
    dropped = frozenset(drop.dropped)
    for fragment in _read_family_fragments(modelo_dir / "revisions" / edition.revision_id, drop.section):
        for block in fragment.blocks:
            identity = _identity_of(block.row, family)
            if identity in dropped:
                comments.extend(
                    f"# Original {drop.section} {identity} commentary: {comment}"
                    for comment in toml_comments(block.text)
                )
        if fragment.blocks and all(_identity_of(block.row, family) in dropped for block in fragment.blocks):
            comments.extend(
                f"# Original {drop.section} fragment {fragment.path.name}: {comment}"
                for comment in toml_comments(fragment.preamble)
            )
    return comments


def _preserve_drop_comments(
    modelo_dir: Path,
    edition: EditionDrop,
    families: Mapping[str, _edition_delta_drop_scope._DroppableFamily],
) -> list[str]:
    return [
        comment
        for drop in edition.families
        for comment in _family_drop_comments(modelo_dir, edition, drop, families[drop.section])
    ]


def _append_drop_comments(manifest: Path, comments: Sequence[str]) -> None:
    if not comments:
        return
    text = manifest.read_text(encoding="utf-8")
    manifest.write_text(text.rstrip() + "\n\n" + "\n".join(comments) + "\n", encoding="utf-8", newline="\n")


def stage_declaration_drop(modelo_dir: Path, edition: EditionDrop) -> None:
    """Write a planned drop to a caller-owned staging tree, retaining row commentary.

    This does not publish source or attest authority. The caller must compare
    complete materialised definitions before accepting the staged representation.
    """
    families = {family.section: family for family in _edition_delta_drop_scope._DROPPABLE_FAMILIES}
    comments = _preserve_drop_comments(modelo_dir, edition, families)
    _write_drop(modelo_dir, edition, families)
    manifest = modelo_dir / "revisions" / edition.revision_id / _edition_delta_fields._MANIFEST
    _append_drop_comments(manifest, comments)
