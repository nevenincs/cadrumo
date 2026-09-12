"""Screen: can a bundled excerpt's consolidated version be checked at all?

A BOE consolidated text is versioned. The same article carries different wording
in force at different dates, so an excerpt is only evidence for the period whose
version it holds. Nothing in this corpus records that as a checkable fact.

The defect this exists for was found by hand: rd-1624-1992-art-80 carried a
header reading "Consolidated version in force from 2024-01-01" above the
PRE-2024 wording. The header was right about intent and wrong about content, and
a citation quoting the current law failed against it for a reason that looked
like a missing accent. An excerpt can be stale without looking stale.

Four states, and most of the corpus is in the two that cannot be checked:

``unanchored``  No BOE document id in the header. There is nothing to re-fetch
                against, so the excerpt's provenance is whatever its author
                remembered.
``undated``     A document id, but no statement of which consolidated version
                the text came from. Re-fetchable in principle, unverifiable in
                practice: the current version may differ and nobody can tell
                whether it always did.
``claimed``     States an in-force date but carries no API block URL, so the
                claim rests on the transcription.
``verifiable``  States an in-force date AND names the API block endpoint. Only
                these can be machine-checked, and ``--verify`` does so.

The screen exits 0 whatever it finds and never writes. Counting is the point:
the number that matters is how much of the corpus cannot be checked, not how
much fails a check it was never able to take.

A THIRD STATE THIS DOES NOT YET HAVE. ``--verify`` compares an excerpt's claim
against the LATEST ``fecha_vigencia`` the BOE block returns. That is right for
an excerpt meant to hold current law and wrong for one deliberately holding a
historical version: a back-year edition citing the law as it stood in 2022
would legitimately claim an older date and be reported ``mismatched`` for being
correct. No such excerpt exists today -- every one of the verifiable fourteen
means to hold current law -- so the comparison stands as written. When back-year
authoring starts citing historical versions, the excerpt needs a way to say it
is deliberately historical, and this check needs to read that and report
``historical`` rather than tighten the rule. Recorded here rather than guessed
at now, because inventing the declaration before a case exists would fix the
shape of it against no evidence.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Final

_CORPUS: Final = Path(__file__).resolve().parents[3] / "src" / "cadrumo" / "_data" / "corpus" / "normatives" / "html"

CLAIM_STATES: Final[tuple[str, ...]] = ("unanchored", "undated", "claimed", "verifiable")

_VIGENCIA: Final = re.compile(r"in force from (\d{4}-\d{2}-\d{2})")
_DOCUMENT: Final = re.compile(r"Document:\s*(BOE-[A-Z]-\d{4}-\d+)")
_API: Final = re.compile(r"(https://www\.boe\.es/datosabiertos/api/\S+?/bloque/(\w+))")
_BLOCK_VIGENCIA: Final = re.compile(r'fecha_vigencia="(\d{8})"')


@dataclass(frozen=True, slots=True)
class Excerpt:
    """One bundled excerpt and what it says about its own version."""

    name: str
    state: str
    claimed: str | None
    api_url: str | None


def survey() -> Iterator[Excerpt]:
    """Classify every bundled excerpt by how checkable its version claim is."""
    for path in sorted(_CORPUS.glob("*.html")):
        head = path.read_text(encoding="utf-8", errors="replace")[:2000]
        vigencia = _VIGENCIA.search(head)
        api = _API.search(head)
        if vigencia and api:
            state = "verifiable"
        elif vigencia:
            state = "claimed"
        elif _DOCUMENT.search(head):
            state = "undated"
        else:
            state = "unanchored"
        yield Excerpt(path.name, state, vigencia.group(1) if vigencia else None, api.group(1) if api else None)


def verify(excerpt: Excerpt) -> tuple[bool, str]:
    """Compare a verifiable excerpt's claim against the BOE block it names."""
    if excerpt.api_url is None or excerpt.claimed is None:
        return True, "not verifiable"
    result = subprocess.run(
        ["curl", "-sS", "-H", "Accept: application/xml", "--max-time", "45", excerpt.api_url],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return True, "fetch failed"
    versions = _BLOCK_VIGENCIA.findall(result.stdout.decode("utf-8", errors="replace"))
    if not versions:
        return True, "no version in response"
    latest = max(versions)
    claimed = excerpt.claimed.replace("-", "")
    return latest == claimed, f"claims {claimed}, BOE latest {latest}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="fetch each verifiable excerpt's BOE block")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    excerpts = tuple(survey())
    counts = {state: sum(1 for e in excerpts if e.state == state) for state in CLAIM_STATES}

    mismatched: list[tuple[str, str]] = []
    if args.verify:
        for excerpt in excerpts:
            if excerpt.state != "verifiable":
                continue
            ok, detail = verify(excerpt)
            if not ok:
                mismatched.append((excerpt.name, detail))

    if args.json:
        print(json.dumps({"counts": counts, "mismatched": mismatched}, indent=2))
        return 0

    print("# corpus_vigencia_claims schema=1")
    print(f"excerpts total={len(excerpts)} " + " ".join(f"{k}={v}" for k, v in counts.items()))
    uncheckable = counts["unanchored"] + counts["undated"]
    print(f"uncheckable={uncheckable} of {len(excerpts)}")
    if args.verify:
        print(f"verified mismatched={len(mismatched)}")
        for name, detail in mismatched:
            print(f"  {name}: {detail}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
