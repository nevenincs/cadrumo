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
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from cadrumo.core.resources.bundled_data import bundled_path


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


def _count_authored_fields(export_layouts: Path) -> int:
    total = 0
    for fragment in sorted(export_layouts.glob("*.toml")):
        text = fragment.read_text(encoding="utf-8", errors="replace")
        total += text.count("offset =")
    return total


def shipped_export_attestation(modelos_root: Path | None = None) -> Iterator[RevisionAttestation]:
    """Yield one row per shipped export revision, attested or merely cited."""
    root = modelos_root if modelos_root is not None else bundled_path("registry", "aeat", "modelos")
    for revision_root in sorted(root.glob("*/revisions/*")):
        modelo = revision_root.parts[-3]
        revision = revision_root.name
        manifest = revision_root / "export" / "_generation.provenance.json"
        if manifest.is_file():
            derivations = json.loads(manifest.read_text(encoding="utf-8")).get("field_derivations") or []
            yield RevisionAttestation(modelo, revision, DerivationAttestation.ATTESTED, len(derivations))
            continue
        authored = revision_root / "export_layouts"
        if authored.is_dir():
            yield RevisionAttestation(
                modelo,
                revision,
                DerivationAttestation.CITED_ONLY,
                _count_authored_fields(authored),
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
