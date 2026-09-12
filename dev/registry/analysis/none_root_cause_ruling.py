"""The one-time classification ruling that flips every corpus ``none`` root to a stated cause.

Every root in the shipped corpus predates the ``cause`` token, so the first
classification cannot be read out of the corpus -- it has to be ruled on once,
from each root's own reason prose and the authority it cites, and then applied.
This module is that ruling, held as data so the flip is reviewable as a table
rather than buried in a one-shot script.

It is migration scaffolding with a defined end: once every root states its
cause, the census reads the corpus directly and this table is dead weight.
Delete it then rather than leaving a second, drifting source of truth beside
the corpus it was used to write.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Final

from cadrumo.domain.calculations.registry.revision_contracts import NoPredecessorCause

_REPO_ROOT: Final = Path(__file__).resolve().parents[3]
_MODELOS_DIR: Final = _REPO_ROOT / "src" / "cadrumo" / "_data" / "registry" / "aeat" / "modelos"

C: Final = NoPredecessorCause

RULING: Final[tuple[tuple[str, str, NoPredecessorCause], ...]] = (
    ("100", "2021", C.predecessor_row_without_lineage),
    ("100", "2022", C.predecessor_row_without_lineage),
    ("100", "2023", C.predecessor_row_without_lineage),
    ("100", "2024", C.predecessor_row_without_lineage),
    ("100", "2025", C.predecessor_row_without_lineage),
    # Compound reason; the withdrawal clause is the specific one and dominates the lineage-gap clause.
    ("123", "2024-y-siguientes", C.unretired_withdrawal),
    ("131", "2026", C.unretired_withdrawal),
    ("151", "2025-y-siguientes", C.predecessor_row_without_lineage),
    ("165", "2023-2025", C.lower_grade),
    ("200", "2025-y-siguientes", C.predecessor_row_without_lineage),
    # Orden HAC/529/2026 art. 6.3 authorises this edition's own scope; it is not authored from the 2024 copy.
    ("220", "2025", C.forbidden_by_norm),
    ("222", "2024", C.predecessor_row_without_lineage),
    # 39 of 54 shared boxes sit at different offsets and eleven position-defined slots shift 78 bytes,
    # so supersede-in-place would not reproduce the official record structure.
    ("222", "2025-y-siguientes", C.official_structure_differs),
    ("308", "2011-julio-2015", C.overlapping_predecessor),
    ("308", "2016-2018", C.predecessor_row_without_lineage),
    ("308", "2019-y-siguientes", C.predecessor_row_without_lineage),
    ("309", "2016-2017", C.predecessor_row_without_lineage),
    ("309", "2018-2022", C.predecessor_row_without_lineage),
    ("309", "2023-y-siguientes", C.predecessor_row_without_lineage),
    ("322", "2023", C.predecessor_row_without_lineage),
    ("322", "2024-2025", C.predecessor_row_without_lineage),
    ("322", "2026-y-siguientes", C.predecessor_row_without_lineage),
    ("369", "esquema-exterior", C.parallel_scheme_variants),
    ("369", "esquema-importacion", C.parallel_scheme_variants),
    ("369", "esquema-union", C.parallel_scheme_variants),
    ("490", "2022-1t", C.predecessor_row_without_lineage),
    ("490", "2022-2t-4t", C.predecessor_row_without_lineage),
    ("490", "2023-y-siguientes", C.predecessor_row_without_lineage),
    ("604", "2024-y-siguientes", C.predecessor_row_without_lineage),
)
"""Every corpus root, in modelo then edition order, with the cause ruled for it."""

EXPECTED_ROOTS: Final = 29


def manifest_path(modelo_id: str, edition_id: str) -> Path:
    """Return the revision manifest that carries this root's ``predecessor`` declaration."""
    return _MODELOS_DIR / modelo_id / "revisions" / edition_id / "revision.toml"


def entries() -> list[dict[str, str]]:
    """Return the ruling as the flat records a migration applies, refusing an unresolvable path."""
    if len(RULING) != EXPECTED_ROOTS:
        raise SystemExit(f"ruling covers {len(RULING)} roots, expected {EXPECTED_ROOTS}")
    records: list[dict[str, str]] = []
    for modelo_id, edition_id, cause in RULING:
        path = manifest_path(modelo_id, edition_id)
        if not path.is_file():
            raise SystemExit(f"{modelo_id} {edition_id}: no manifest at {path}")
        text = path.read_text(encoding="utf-8")
        if "predecessor" not in text:
            raise SystemExit(f"{modelo_id} {edition_id}: manifest declares no predecessor")
        records.append(
            {
                "manifest_path": path.relative_to(_REPO_ROOT).as_posix(),
                "edition_id": edition_id,
                "cause": cause.value,
            }
        )
    return records


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
