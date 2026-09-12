"""Census: which grounded "no predecessor exists" roots state a cause, and which do not?

A revision declaring a ``predecessor.none`` table states in prose why no earlier
sibling edition exists. Prose grounds the claim and cannot be counted. The
optional ``cause`` token on that table is the machine-readable classification of
the same fact, and this screen is the only thing that answers how much of the
corpus carries one.

Two numbers matter, and they are the same number read twice: how many roots the
corpus declares, and how many of those are still ``unclassified``. A flip is
complete when the second is zero.

Roots are read through the real loader rather than by parsing TOML, so the cause
reported here is the typed value a consumer would see, not a string that
happened to appear in a file. The screen exits 0 whatever it finds and never
writes.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Final

from cadrumo.domain.calculations.registry.revision_contracts import NoPredecessor, NoPredecessorCause

from ..conformance.loader_directory_mode_support import committed_registry_modelos

UNCLASSIFIED: Final = "unclassified"
"""Reported for a root whose ``none`` table omits the optional ``cause`` token."""


@dataclass(frozen=True, slots=True)
class Root:
    """One revision declaring that no earlier sibling edition exists."""

    modelo_id: str
    revision_id: str
    cause: str
    reason: str

    @property
    def classified(self) -> bool:
        """Whether this root states a cause rather than leaving it to be read out of prose."""
        return self.cause != UNCLASSIFIED


def survey() -> Iterator[Root]:
    """Yield every declared root in the committed corpus, in modelo then revision order."""
    for modelo in sorted(committed_registry_modelos(), key=lambda definition: str(definition.id)):
        for revision_id, revision in sorted(modelo.revisions.items()):
            declaration = revision.predecessor
            if not isinstance(declaration, NoPredecessor):
                continue
            yield Root(
                modelo_id=str(modelo.id),
                revision_id=revision_id,
                cause=declaration.cause.value if declaration.cause is not None else UNCLASSIFIED,
                reason=" ".join(declaration.reason.split()),
            )


def main(argv: list[str] | None = None) -> int:
    """Report the corpus roots and how many of them still state no cause."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--unclassified-only",
        action="store_true",
        help="list only the roots still missing a cause",
    )
    parser.add_argument(
        "--reason-chars",
        type=int,
        default=0,
        help="include this many characters of each root's reason prose (0 omits it)",
    )
    args = parser.parse_args(argv)

    roots = tuple(survey())
    classified = sum(1 for root in roots if root.classified)
    counts = {cause.value: sum(1 for root in roots if root.cause == cause.value) for cause in NoPredecessorCause}
    counts[UNCLASSIFIED] = len(roots) - classified
    listed = tuple(root for root in roots if not args.unclassified_only or not root.classified)

    if args.json:
        print(
            json.dumps(
                {
                    "total": len(roots),
                    "classified": classified,
                    "counts": counts,
                    "roots": [
                        {
                            "modelo": root.modelo_id,
                            "revision": root.revision_id,
                            "cause": root.cause,
                            **({"reason": root.reason[: args.reason_chars]} if args.reason_chars else {}),
                        }
                        for root in listed
                    ],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    print("# predecessor_cause_census schema=1")
    print(f"roots total={len(roots)} classified={classified} {UNCLASSIFIED}={counts[UNCLASSIFIED]}")
    for cause in NoPredecessorCause:
        print(f"  {cause.value}={counts[cause.value]}")
    for root in listed:
        line = f"{root.modelo_id} {root.revision_id}: {root.cause}"
        if args.reason_chars:
            line = f"{line} -- {root.reason[: args.reason_chars]}"
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
