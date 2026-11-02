"""Apply already-planned restatement drops to a staged registry tree."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from . import edition_delta_drop_scope as _edition_delta_drop_scope
from . import edition_delta_errors as _edition_delta_errors
from . import edition_delta_fields as _edition_delta_fields
from . import edition_delta_manifest_writer as _edition_delta_manifest_writer
from .edition_delta_drop_planning import _identity_of, _read_family_fragments
from .edition_delta_drop_types import EditionDrop, _MemberFragment


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
