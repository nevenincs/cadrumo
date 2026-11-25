"""Screen: how much of the shipped export surface can be checked against its own source.

Every export field cites an official record design. A GENERATED field also ships
a provenance manifest recording the design row it was derived from, so the
citation can be checked: the comparison is a read. A HAND-AUTHORED field ships
the citation and nothing else, so the claim that it derives from that design is
unfalsifiable by any instrument in this repository.

That is not an accusation about the authored fields. Most of them are probably
right, and the point is exactly that "probably" is all anyone can say. The
divergence census that found a fifth of the GENERATED surface contradicting its
own designs was only possible because the generated half carries the join. Run
against the authored half, the same census cannot start.

This screen reports the ratio, because the ratio is the finding. It does not
judge an authored field and cannot: judging one would require the join whose
absence is being reported.

The screen exits 0 whatever it finds. It reports; it does not gate.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision

from ..compiler.authority import compiled_bundled_authority
from ..compiler.export_fragment_grammar import (
    EXPORT_FRAGMENT_PROVENANCE_FILENAME,
    GENERATED_EXPORT_DIRECTORY_NAME,
)


class DerivationAttestation(StrEnum):
    """Whether a revision's export fields can be checked against their cited design."""

    ATTESTED = "attested"
    """A generation manifest pairs each field with the design row it came from."""

    CITED_ONLY = "cited_only"
    """The revision cites a design and records no derivation from it."""


@dataclass(frozen=True, slots=True)
class RevisionAttestation:
    """One shipped export revision and whether its derivation is recorded."""

    modelo: str
    revision: str
    attestation: DerivationAttestation
    field_count: int

    @property
    def is_checkable(self) -> bool:
        """Whether an instrument can compare this revision to its own source."""
        return self.attestation is DerivationAttestation.ATTESTED


def _count_authored_fields(revision: ModeloRevision) -> int:
    """Positioned fields across the revision's effective export layouts, inherited ones included."""
    return sum(
        1
        for layout in revision.export_layouts
        for record in layout.records
        for field in record.fields
        if field.offset is not None
    )


def shipped_export_attestation(
    modelos: Iterable[ModeloDefinition] | None = None,
    modelos_root: Path | None = None,
) -> Iterator[RevisionAttestation]:
    """Yield one row per shipped export revision, attested or merely cited.

    A revision is shipped when it has a generation manifest or declares export
    layouts. The layouts are read from the hydrated revision, so a revision that
    inherits its predecessor's hand-authored layout without a directory of its
    own is counted rather than omitted. Manifests are per-revision artefacts and
    are read from ``modelos_root``.
    """
    root = modelos_root if modelos_root is not None else bundled_path("registry", "aeat", "modelos")
    definitions = modelos if modelos is not None else compiled_bundled_authority().modelos
    for modelo in sorted(definitions, key=lambda definition: str(definition.id)):
        for revision in sorted(modelo.revisions.values(), key=lambda candidate: str(candidate.id)):
            manifest = (
                root
                / str(modelo.id)
                / "revisions"
                / str(revision.id)
                / GENERATED_EXPORT_DIRECTORY_NAME
                / EXPORT_FRAGMENT_PROVENANCE_FILENAME
            )
            if manifest.is_file():
                derivations = json.loads(manifest.read_text(encoding="utf-8")).get("field_derivations") or []
                yield RevisionAttestation(
                    str(modelo.id), str(revision.id), DerivationAttestation.ATTESTED, len(derivations)
                )
            elif revision.export_layouts:
                yield RevisionAttestation(
                    str(modelo.id),
                    str(revision.id),
                    DerivationAttestation.CITED_ONLY,
                    _count_authored_fields(revision),
                )


def screen_authority(_authority: object = None, _modelo_ids: Sequence[str] = ()) -> Sequence[RevisionAttestation]:
    """Entry point matching the screens register's calling convention."""
    return tuple(shipped_export_attestation())


def main() -> int:
    """Report what share of the shipped export surface is checkable against its source."""
    rows = tuple(shipped_export_attestation())
    attested = [row for row in rows if row.is_checkable]
    cited = [row for row in rows if not row.is_checkable]
    attested_fields = sum(row.field_count for row in attested)
    cited_fields = sum(row.field_count for row in cited)
    total = attested_fields + cited_fields
    print(f"shipped export revisions: {len(rows)}  ({len(attested)} attested, {len(cited)} cited only)")
    print(f"fields whose derivation is recorded:     {attested_fields}")
    print(f"fields citing a design with no record:   {cited_fields}")
    if total:
        print(f"\ncheckable share of the shipped export surface: {100 * attested_fields / total:.1f}%")
    print(
        "\nThe divergence census that found a fifth of the attested surface contradicting its own\n"
        "designs cannot be run against the rest. Their citations are not wrong; they are unfalsifiable.",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
