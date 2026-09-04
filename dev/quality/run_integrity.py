"""Decide whether a saved pytest run is usable as evidence.

A failure-set comparison is only as good as the two runs behind it, and a run
can be unusable in ways that read as success. This campaign hit four of them,
and each looked like a result:

- A worker died and took its remaining tests with it, so the failure list is a
  subset of unknown size. The repository's own reporter says so in an
  ``INCOMPLETE RUN`` banner, and the banner is easy not to read when the summary
  line beneath it reports a plausible tally.
- A marker deselected most of a file, so three passing tests stood for
  twenty-four. This one cannot be given a verdict from a saved run, and the
  reason is worth stating: under xdist a marker-filtered run prints NO
  deselection count anywhere. Its only trace is the collected population -
  ``6 workers [356 items]`` against ``[371 items]`` - which means nothing
  without the number it should have been. The population is therefore reported
  on every row so two runs can be compared for it, and the caller supplies the
  expectation this module cannot.
- A run reported nothing at all, which a comparison reads as "no failures".
- A run was piped through a filter, so the exit status belonged to the filter
  and a red lane read as zero.

The banners exist. What did not exist is a single verdict a caller can act on,
so the sweep was a grep somebody had to remember - which is the shape of defect
this whole campaign is about. This turns it into a command.

It reads a SAVED run rather than invoking pytest, deliberately. The point is to
judge the artefact a comparison was drawn from, possibly long after, and a tool
that re-ran the suite would answer a different question about a different tree.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys
from dataclasses import dataclass
from typing import Final

__all__ = [
    "VERDICTS",
    "RunIntegrity",
    "classify_run",
]

#: Every verdict this can assign, declared once so a caller can branch on the
#: set without reading the strings out of this module.
VERDICTS: Final[tuple[str, ...]] = (
    "usable",
    "lost_workers",
    "nothing_ran",
    "no_summary",
)

#: The repository's own reporters. Matched rather than re-derived: they already
#: know things this parser does not, such as how many collected tests never
#: reported.
_INCOMPLETE = "INCOMPLETE RUN"
_NOTHING_RAN = "NOTHING RAN"
_CRASHED = re.compile(r"worker '(\w+)' crashed while running '([^']+)'")
_UNREPORTED = re.compile(r"(\d+) of (\d+) collected test\(s\) never reported an outcome")
#: The collected population, in either shape pytest writes it: the xdist worker
#: line, and the plain collection line when no workers are used.
_COLLECTED = re.compile(r"(?:workers? \[(\d+) items?\]|collected (\d+) items?)")
_SUMMARY = re.compile(r"^=+ (.*?) in \d+\.\d+s.*?=+$", re.MULTILINE)
_COUNT = re.compile(r"(\d+) (passed|failed|error|errors|skipped|xfailed|xpassed|deselected|warning|warnings)")


@dataclass(frozen=True, slots=True)
class RunIntegrity:
    """What a saved pytest run says about its own completeness."""

    verdict: str
    counts: dict[str, int]
    #: ``(worker, test)`` for each worker that died mid-test.
    crashed: tuple[tuple[str, str], ...]
    #: How many collected tests never reported, per the repository's reporter.
    unreported: int
    collected: int

    @property
    def usable(self) -> bool:
        """Whether a failure set drawn from this run means anything."""
        return self.verdict == "usable"

    def headline(self) -> str:
        """One line naming the verdict and what supports it."""
        tally = " ".join(f"{name}={value}" for name, value in sorted(self.counts.items()))
        detail = (
            f" unreported={self.unreported}/{self.collected}"
            if self.unreported
            else (f" collected={self.collected}" if self.collected else "")
        )
        crashed = f" crashed={len(self.crashed)}" if self.crashed else ""
        return f"run_integrity verdict={self.verdict} {tally}{detail}{crashed}"


def classify_run(text: str) -> RunIntegrity:
    """Return what ``text`` - a saved pytest run - says about its completeness.

    ``lost_workers`` outranks everything else it might also be. A run that lost
    a worker AND deselected half its tests is unusable for the first reason, and
    reporting the second would invite fixing the marker and re-reading the same
    subset.

    A run with no recognisable summary line is ``no_summary`` rather than
    assumed empty: output truncated by a pipe, or a process killed before it
    finished writing, produces exactly that, and calling it "nothing failed" is
    the mistake this module exists to stop.
    """
    crashed = tuple(_CRASHED.findall(text))
    unreported_match = _UNREPORTED.search(text)
    unreported = int(unreported_match.group(1)) if unreported_match else 0
    collected = int(unreported_match.group(2)) if unreported_match else 0
    if not collected:
        # The banner reports a population only when a worker was lost, so the
        # ordinary case reads it from the collection line instead.
        collected_match = _COLLECTED.search(text)
        if collected_match:
            collected = int(collected_match.group(1) or collected_match.group(2))

    summary = _SUMMARY.findall(text)
    counts: dict[str, int] = {}
    if summary:
        for value, name in _COUNT.findall(summary[-1]):
            key = "errors" if name == "error" else ("warnings" if name == "warning" else name)
            counts[key] = counts.get(key, 0) + int(value)

    if crashed or _INCOMPLETE in text or unreported:
        verdict = "lost_workers"
    elif _NOTHING_RAN in text or (summary and not counts):
        verdict = "nothing_ran"
    elif not summary:
        verdict = "no_summary"
    else:
        verdict = "usable"
    return RunIntegrity(
        verdict=verdict,
        counts=counts,
        crashed=crashed,
        unreported=unreported,
        collected=collected,
    )


def main() -> int:
    """Classify each saved run named on the command line.

    Exits non-zero when any run is unusable, so a comparison can be gated on it
    rather than on somebody remembering to look.
    """
    parser = argparse.ArgumentParser(description="Judge whether a saved pytest run is usable as evidence.")
    parser.add_argument("paths", nargs="+", help="saved pytest output files")
    arguments = parser.parse_args()

    unusable = 0
    for name in arguments.paths:
        path = pathlib.Path(name)
        try:
            result = classify_run(path.read_text(encoding="utf-8", errors="replace"))
        except OSError as error:
            sys.stdout.write(f"run_integrity verdict=unreadable path={path} detail={error!r}\n")
            unusable += 1
            continue
        sys.stdout.write(f"{result.headline()} path={path}\n")
        for worker, test in result.crashed:
            sys.stdout.write(f"run_integrity crashed worker={worker} test={test}\n")
        if not result.usable:
            unusable += 1
    sys.stdout.write(f"summary runs={len(arguments.paths)} unusable={unusable}\n")
    return 1 if unusable else 0


if __name__ == "__main__":
    raise SystemExit(main())
