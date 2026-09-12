"""The one-time classification ruling that flips every corpus ``none`` root to a stated cause.

Every root in the shipped corpus predates the ``cause`` token, so the first
classification cannot be read out of the corpus -- it has to be ruled on once,
from each root's own reason prose and the authority it cites, and then applied.
This module is that ruling, held as data so the flip is reviewable as a table
rather than buried in a one-shot script.

The ruling is a MAPPING, not an inventory: the set of roots is read from the
corpus at run time, and this table only says which cause each of them was ruled
to carry. A revision counts as a root when its ``predecessor`` declaration is a
``none`` table -- parsed, never matched as text, because a revision naming a
predecessor also spells the word. A mapped key that is not a live root, and a
live root with no mapped cause, are both refused by name: the corpus moves and
the ruling must be re-ruled rather than silently applied to a different set.

It is migration scaffolding with a defined end: once every root states its
cause, the census reads the corpus directly and this table is dead weight.
Delete it then rather than leaving a second, drifting source of truth beside
the corpus it was used to write.
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from cadrumo.domain.calculations.registry.revision_contracts import NoPredecessorCause

_REPO_ROOT: Final = Path(__file__).resolve().parents[3]
_MODELOS_DIR: Final = _REPO_ROOT / "src" / "cadrumo" / "_data" / "registry" / "aeat" / "modelos"

C: Final = NoPredecessorCause

CAUSES: Final[Mapping[tuple[str, str], NoPredecessorCause]] = {
    ("100", "2021"): C.predecessor_row_without_lineage,
    ("100", "2022"): C.predecessor_row_without_lineage,
    ("100", "2023"): C.predecessor_row_without_lineage,
    ("100", "2024"): C.predecessor_row_without_lineage,
    ("100", "2025"): C.predecessor_row_without_lineage,
    # Compound reason; the withdrawal clause is the specific one and dominates the lineage-gap clause.
    ("123", "2024-y-siguientes"): C.unretired_withdrawal,
    ("131", "2026"): C.unretired_withdrawal,
    ("165", "2023-2025"): C.lower_grade,
    ("200", "2025-y-siguientes"): C.predecessor_row_without_lineage,
    # Orden HAC/529/2026 art. 6.3 authorises this edition's own scope; it is not authored from the 2024 copy.
    ("220", "2025"): C.forbidden_by_norm,
    ("222", "2024"): C.predecessor_row_without_lineage,
    # 39 of 54 shared boxes sit at different offsets and eleven position-defined slots shift 78 bytes,
    # so supersede-in-place would not reproduce the official record structure.
    ("222", "2025-y-siguientes"): C.official_structure_differs,
    ("308", "2011-julio-2015"): C.overlapping_predecessor,
    ("308", "2016-2018"): C.predecessor_row_without_lineage,
    ("308", "2019-y-siguientes"): C.predecessor_row_without_lineage,
    ("309", "2016-2017"): C.predecessor_row_without_lineage,
    ("309", "2018-2022"): C.predecessor_row_without_lineage,
    ("309", "2023-y-siguientes"): C.predecessor_row_without_lineage,
    ("322", "2023"): C.predecessor_row_without_lineage,
    ("322", "2024-2025"): C.predecessor_row_without_lineage,
    ("322", "2026-y-siguientes"): C.predecessor_row_without_lineage,
    ("369", "esquema-exterior"): C.parallel_scheme_variants,
    ("369", "esquema-importacion"): C.parallel_scheme_variants,
    ("369", "esquema-union"): C.parallel_scheme_variants,
    ("490", "2022-1t"): C.predecessor_row_without_lineage,
    ("490", "2022-2t-4t"): C.predecessor_row_without_lineage,
    ("490", "2023-y-siguientes"): C.predecessor_row_without_lineage,
    ("604", "2024-y-siguientes"): C.predecessor_row_without_lineage,
}
"""The cause ruled for each root the corpus declared when the ruling was made."""


@dataclass(frozen=True, slots=True)
class Root:
    """One revision whose ``predecessor`` declaration is a ``none`` table."""

    modelo_id: str
    edition_id: str
    manifest: Path

    @property
    def key(self) -> tuple[str, str]:
        """The ``(modelo, edition)`` pair the ruling table is keyed on."""
        return (self.modelo_id, self.edition_id)


def _declares_no_predecessor(table: object) -> bool:
    """Whether one revision table declares the ``none`` form rather than naming a predecessor."""
    if not isinstance(table, dict):
        return False
    declaration = table.get("predecessor")
    return isinstance(declaration, dict) and "none" in declaration


def survey_roots(modelos_dir: Path = _MODELOS_DIR) -> tuple[Root, ...]:
    """Return every root the corpus declares, in modelo then edition order.

    The ``predecessor`` declaration is read with :mod:`tomllib`, so a revision
    that NAMES a predecessor is excluded even though its manifest contains the
    word ``predecessor``.
    """
    roots: list[Root] = []
    for modelo_dir in sorted(path for path in modelos_dir.iterdir() if path.is_dir()):
        revisions_dir = modelo_dir / "revisions"
        if not revisions_dir.is_dir():
            continue
        for edition_dir in sorted(path for path in revisions_dir.iterdir() if path.is_dir()):
            manifest = edition_dir / "revision.toml"
            if not manifest.is_file():
                continue
            document = tomllib.loads(manifest.read_text(encoding="utf-8"))
            declared = document.get("revisions")
            if not isinstance(declared, dict):
                continue
            for edition_id, table in sorted(declared.items()):
                if _declares_no_predecessor(table):
                    roots.append(Root(modelo_id=modelo_dir.name, edition_id=edition_id, manifest=manifest))
    return tuple(roots)


def entries(
    *,
    modelos_dir: Path = _MODELOS_DIR,
    causes: Mapping[tuple[str, str], NoPredecessorCause] = CAUSES,
    display_root: Path = _REPO_ROOT,
) -> list[dict[str, str]]:
    """Return the ruling as the flat records a migration applies.

    Refuses, naming the offenders, when the ruling and the corpus disagree in
    either direction: a mapped key that no longer declares a ``none`` table, or
    a declared root this ruling never ruled on.
    """
    roots = survey_roots(modelos_dir)
    live = {root.key: root for root in roots}

    unmapped = sorted(key for key in live if key not in causes)
    if unmapped:
        named = ", ".join(f"{modelo} {edition}" for modelo, edition in unmapped)
        raise SystemExit(f"corpus declares roots this ruling does not classify: {named}")

    not_a_root = sorted(key for key in causes if key not in live)
    if not_a_root:
        named = ", ".join(f"{modelo} {edition}" for modelo, edition in not_a_root)
        raise SystemExit(f"ruling classifies keys that are not corpus roots: {named}")

    return [
        {
            "manifest_path": root.manifest.relative_to(display_root).as_posix(),
            "edition_id": root.edition_id,
            "cause": causes[root.key].value,
        }
        for root in roots
    ]


def main(argv: list[str] | None = None) -> int:
    """Emit the ruling, to a file with ``--out`` or to stdout."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, help="write the ruling as JSON to this path instead of stdout")
    args = parser.parse_args(argv)

    records = entries()
    counts: dict[str, int] = {}
    for record in records:
        counts[record["cause"]] = counts.get(record["cause"], 0) + 1
    payload = json.dumps({"total": len(records), "counts": counts, "entries": records}, indent=2)

    if args.out is not None:
        args.out.write_text(payload + "\n", encoding="utf-8", newline="\n")
        print(f"wrote {len(records)} entries to {args.out}")
        return 0
    print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
