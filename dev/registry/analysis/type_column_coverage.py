"""Which type-column instrument reads each compiled revision, or that none does.

Two gates compare shipped export fields with the official type column. One reads
the derivation records in a generated tree's generation manifest; the other joins
a hand-authored ``export_layouts`` tree to its pinned record design. Each is keyed
on the artefact it reads, so a revision carrying neither artefact is not failed
by either gate and not passed by either: it is simply not in their inputs, and a
green run says nothing about it.

That gap widens as editions stop being generated. An edition authored as stated
rows rather than rendered from a design ships no generation manifest, and a gate
keyed on manifest presence reads it as absent when it is unexamined. It widened
a second way for editions that store their families against a baseline: they
ship no directory of their own either, and a partition keyed on the listing
reported twelve of them as read by nobody while the hand-authored screen could
resolve and compare every one.

This module closes the gap by partitioning every COMPILED revision. Eligibility
comes from what the edition declares about itself -- whether its compiled record
carries an export surface -- and never from which files sit beside it. An edition
declaring no export surface has no type column to compare against and is
reported as such. An edition that declares one and is read by exactly one
instrument is covered. Every other edition is UNCHECKED and named with the
reason, including a revision whose artefacts would be read by both instruments
or by an instrument it does not declare a surface for.

The partition records coverage; it does not grant any. An UNCHECKED revision is
an open question, and the gate beside it fails on one.
"""

from __future__ import annotations

import sys
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision

from ..compiler.authority import compiled_bundled_authority
from ..compiler.export_fragment_grammar import (
    EXPORT_FRAGMENT_PROVENANCE_FILENAME,
    GENERATED_EXPORT_DIRECTORY_NAME,
)

__all__ = [
    "RevisionTypeColumnCoverage",
    "TypeColumnCoverage",
    "classify_revision",
    "type_column_coverage",
]

_HAND_AUTHORED_TREE: Final[str] = "export_layouts"


class TypeColumnCoverage(StrEnum):
    """How one compiled revision's export fields reach a type-column comparison."""

    GENERATED_MANIFEST = "generated_manifest"
    """A generation manifest pairs each field with its design row; the generated-tree gate reads it."""
    HAND_AUTHORED_LAYOUTS = "hand_authored_layouts"
    """An ``export_layouts`` tree is joined to the pinned design by the hand-authored gate."""
    NO_EXPORT_SURFACE = "no_export_surface"
    """The compiled revision resolves no record field, so there is no type column to compare."""
    UNCHECKED = "unchecked"
    """The revision declares an export surface and no instrument reads it, or its artefacts disagree."""


@dataclass(frozen=True, slots=True)
class RevisionTypeColumnCoverage:
    """One compiled revision and the instrument that reads it, with the reason when none does."""

    modelo: str
    revision: str
    coverage: TypeColumnCoverage
    reason: str | None

    @property
    def subject(self) -> str:
        """Return the canonical ``modelo/revision`` identity."""
        return f"{self.modelo}/{self.revision}"

    def render(self) -> str:
        """Return one greppable report line."""
        tail = f" {self.reason}" if self.reason else ""
        return f"{self.coverage.value.upper()} {self.subject}{tail}"


def classify_revision(revision: ModeloRevision, revision_root: Path) -> tuple[TypeColumnCoverage, str | None]:
    """Classify one compiled revision by what it declares and which instrument can read it.

    Args:
        revision: The compiled revision; its declared export layouts decide eligibility.
        revision_root: The revision's directory, inspected only for the artefact
            each instrument reads.

    Returns:
        The coverage state, and a reason for every state other than a clean single instrument.
    """
    # Eligibility is a record FIELD, not a layout. A type column types wire
    # slots, so a layout carrying none -- Modelo 100's five editions declare an
    # ``xml_dictionary`` layout with no records at all -- has nothing either
    # instrument could compare and no gap to report. Asking only whether a
    # layout is declared listed those editions as unread work, when the
    # comparison is undefined for them rather than unimplemented.
    declares_export = any(record.fields for layout in revision.export_layouts for record in layout.records)
    has_manifest = (revision_root / GENERATED_EXPORT_DIRECTORY_NAME / EXPORT_FRAGMENT_PROVENANCE_FILENAME).is_file()
    # The hand-authored screen reads an authored tree where one exists and the
    # resolved layout where none does, so a revision resolving record fields is
    # in its input either way. Keyed on the directory this read "no instrument
    # reads it" for every edition that stores its layout against a baseline.
    has_authored_tree = (revision_root / _HAND_AUTHORED_TREE).is_dir()
    if not declares_export:
        if has_manifest:
            return (
                TypeColumnCoverage.UNCHECKED,
                "an export artefact sits beside a revision whose compiled record resolves no record field",
            )
        # An authored tree beside a revision that resolves no record field is
        # not an unread artefact: the screen opens it and finds no wire slot to
        # compare, so there is nothing either instrument could have read.
        return TypeColumnCoverage.NO_EXPORT_SURFACE, None
    if has_manifest and has_authored_tree:
        return (
            TypeColumnCoverage.UNCHECKED,
            "ships both a generation manifest and an export_layouts tree; the hand-authored gate skips a "
            "manifest-bearing revision, so its authored layouts are compared by neither gate",
        )
    if has_manifest:
        return TypeColumnCoverage.GENERATED_MANIFEST, None
    return TypeColumnCoverage.HAND_AUTHORED_LAYOUTS, None


def type_column_coverage(
    modelos: Iterable[ModeloDefinition], *, modelos_root: Path
) -> tuple[RevisionTypeColumnCoverage, ...]:
    """Partition every compiled revision of ``modelos`` by type-column coverage.

    Args:
        modelos: Compiled modelo definitions; every revision they carry is classified.
        modelos_root: The ``modelos`` directory the definitions were compiled from.

    Returns:
        One row per compiled revision, ordered by modelo then revision id.
    """
    rows: list[RevisionTypeColumnCoverage] = []
    for modelo in sorted(modelos, key=lambda item: str(item.id)):
        for revision in sorted(modelo.revisions.values(), key=lambda item: str(item.id)):
            root = modelos_root / str(modelo.id) / "revisions" / str(revision.id)
            coverage, reason = classify_revision(revision, root)
            rows.append(RevisionTypeColumnCoverage(str(modelo.id), str(revision.id), coverage, reason))
    return tuple(rows)


def main() -> int:
    """Print the coverage census and every revision no instrument reads."""
    rows = type_column_coverage(
        compiled_bundled_authority().modelos, modelos_root=bundled_path("registry", "aeat", "modelos")
    )
    for state in TypeColumnCoverage:
        print(f"{state.value:22s} {sum(1 for row in rows if row.coverage is state)}")
    for row in rows:
        if row.coverage is TypeColumnCoverage.UNCHECKED:
            print(row.render())
    return 0


if __name__ == "__main__":
    sys.exit(main())
