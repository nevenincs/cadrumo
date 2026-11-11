"""Shrink-only gate: no registry result may depend on a particular year.

Runs the year-independence audits over the hydrated registry and compares their
findings with the committed baseline. ``--check`` fails on a finding that is not
in the baseline and on a baseline entry that no longer occurs, so a fix must
shrink the baseline in the same change. ``--write-baseline`` regenerates it.
Without a mode flag the full report is printed with the authored file of each
edition-only declaration.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from cadrumo.domain.calculations.registry.schema import ModeloDefinition
from cadrumo.domain.calculations.registry.schema_catalogues import RegistryCatalogues

from ..compiler.loader import load_registry_tree
from .casilla_lineage_seed_paths import REGISTRY_ROOT
from .edition_member_continuity import dropped_member_findings
from .edition_singleton_audit import (
    EditionSingletonFinding,
    editions_in_support,
    singleton_findings,
    with_paths,
)
from .fact_year_coverage_audit import fact_year_findings
from .period_edition_coverage import period_coverage_findings
from .year_in_declaration_audit import profile_key_year_findings

__all__ = ("BASELINE_PATH", "Ratchet", "compare_with_baseline", "main", "read_baseline", "render_baseline")

BASELINE_PATH = Path(__file__).with_name("year_independence_baseline.txt")
_HEADER = (
    "# Year-independence baseline: findings that exist today and may only shrink.",
    "# Regenerate with: python -m dev.registry.analysis.year_independence_gate --write-baseline",
)


@dataclass(frozen=True, slots=True)
class Ratchet:
    """The outcome of comparing current findings with the baseline."""

    new: tuple[str, ...]
    stale: tuple[str, ...]

    @property
    def holds(self) -> bool:
        """Whether the baseline is exactly the current findings."""
        return not self.new and not self.stale


def compare_with_baseline(current: Iterable[str], baseline: Iterable[str]) -> Ratchet:
    """Return findings missing from the baseline and baseline entries that no longer occur."""
    now, then = set(current), set(baseline)
    return Ratchet(new=tuple(sorted(now - then)), stale=tuple(sorted(then - now)))


def render_baseline(keys: Iterable[str]) -> str:
    """Render the baseline file: header, then one sorted key per line."""
    return "\n".join([*_HEADER, *sorted(set(keys))]) + "\n"


def read_baseline(path: Path) -> tuple[str, ...]:
    """Read baseline keys, ignoring comments and blank lines."""
    if not path.is_file():
        return ()
    lines = (line.strip() for line in path.read_text(encoding="utf-8").splitlines())
    return tuple(line for line in lines if line and not line.startswith("#"))


def _edition_findings(
    modelos: Iterable[ModeloDefinition], catalogues: RegistryCatalogues
) -> tuple[list[EditionSingletonFinding], list[str]]:
    support = catalogues.require_supported_filing_years()
    singles: list[EditionSingletonFinding] = []
    members: list[str] = []
    for modelo in modelos:
        views = editions_in_support(modelo, catalogues, support)
        singles.extend(singleton_findings(str(modelo.id), views))
        members.extend(item.key for item in dropped_member_findings(str(modelo.id), views))
    return singles, members


def collect_keys(
    modelos: tuple[ModeloDefinition, ...], catalogues: RegistryCatalogues, registry_root: Path
) -> tuple[list[str], list[EditionSingletonFinding]]:
    """Run every audit; return all finding keys and the located edition-only findings."""
    support = catalogues.require_supported_filing_years()
    singles, members = _edition_findings(modelos, catalogues)
    gaps, year_valued = fact_year_findings(registry_root, modelos, support)
    keys = [
        *(item.key for item in singles),
        *members,
        *(item.key for item in gaps),
        *(item.key for item in year_valued),
        *(item.key for item in profile_key_year_findings(modelos, support.years)),
        *(item.key for item in period_coverage_findings(modelos, support)),
    ]
    return keys, singles


def _summary(keys: Sequence[str]) -> list[str]:
    counts = Counter((key.split("|")[0], key.split("|")[1]) for key in keys)
    return [
        f"findings: {len(keys)}",
        *(f"  count kind={kind} subject={subject} n={n}" for (kind, subject), n in sorted(counts.items())),
    ]


def main(argv: Sequence[str] | None = None) -> int:
    """Report, check against, or rewrite the year-independence baseline."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--check", action="store_true", help="exit 1 on a new finding or a stale baseline entry")
    parser.add_argument("--write-baseline", action="store_true", help="rewrite the baseline from today's findings")
    parser.add_argument("--registry-root", type=Path, default=REGISTRY_ROOT)
    parser.add_argument("--baseline", type=Path, default=BASELINE_PATH)
    args = parser.parse_args(argv)
    modelos, catalogues = load_registry_tree(args.registry_root)
    keys, singles = collect_keys(modelos, catalogues, args.registry_root)
    if args.write_baseline:
        args.baseline.write_text(render_baseline(keys), encoding="utf-8")
        sys.stdout.write(f"wrote {len(set(keys))} findings to {args.baseline.as_posix()}\n")
        return 0
    if args.check:
        ratchet = compare_with_baseline(keys, read_baseline(args.baseline))
        lines = [f"NEW (not in baseline): {key}" for key in ratchet.new]
        lines += [f"STALE (fixed; remove from baseline): {key}" for key in ratchet.stale]
        sys.stdout.write("\n".join(lines) + ("\n" if lines else "year-independence baseline holds\n"))
        return 0 if ratchet.holds else 1
    located = with_paths(singles, args.registry_root / "modelos")
    lines = [*_summary(keys), *sorted(set(keys)), *(f"{item.key} {item.path}" for item in located)]
    sys.stdout.write("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
