"""Drift between the registered CRUD noun-group catalogue and the live command tree.

The catalogue in ``cadrumo.application.operator_surface.crud_registry`` calls
itself the single source of truth for the mutating noun-group shape, and its
docstring says a conformance harness consumes it "to detect drift between
shipped Typer subgroups and the locked design". No such comparison existed:
the catalogue's own tests import only the catalogue, so every assertion held
the hand-written contract against itself and passed while the live tree moved
underneath it.

This module performs the comparison the catalogue was written for. It walks
the real ``COMMAND_GRAPH`` -- the same graph the CLI mounts and the command
schema projects from -- and reports, per registered noun-group, the declared
verbs that no live command provides.

DIRECTION, AND WHY ONLY ONE. A declared verb that does not exist is an exact,
checkable defect: the contract names a command the operator cannot run. The
reverse direction -- a live verb absent from the catalogue -- needs a rule for
which live subgroups are "mutating noun-groups" at all, and every candidate
rule here is a guess that would flag orthogonal-axis and lifecycle verbs the
contract deliberately admits. A gate that cries wolf gets switched off, so
this one checks the direction it can prove.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Final

_BASELINE_PATH: Final[Path] = Path(__file__).with_name("crud_contract_drift_baseline.toml")


@dataclass(frozen=True, slots=True)
class DeclaredVerbDrift:
    """One registered noun-group verb the live command tree does not provide."""

    cli_path: str
    verb: str

    @property
    def key(self) -> str:
        """Return the stable ``"<cli path> <verb>"`` identity used by the baseline."""
        return f"{self.cli_path} {self.verb}"


def live_command_paths() -> frozenset[tuple[str, ...]]:
    """Return every mounted command path, from the graph the CLI itself mounts."""
    from cadrumo.entrypoints.cli.command_specs import COMMAND_GRAPH

    return frozenset(tuple(node.path) for node in COMMAND_GRAPH.nodes())


def declared_verb_drift(*, live_paths: frozenset[tuple[str, ...]] | None = None) -> tuple[DeclaredVerbDrift, ...]:
    """Return every catalogue-declared verb absent from the live command tree."""
    from cadrumo.application.operator_surface.crud_registry import BUILTIN_CRUD_CATALOGUE

    paths = live_command_paths() if live_paths is None else live_paths
    drift: list[DeclaredVerbDrift] = []
    for entry in BUILTIN_CRUD_CATALOGUE.entries:
        group = tuple(entry.cli_path.split())
        for verb in sorted(entry.all_verb_names()):
            if (*group, verb) not in paths:
                drift.append(DeclaredVerbDrift(entry.cli_path, verb))
    return tuple(drift)


def baseline_keys(path: Path | None = None) -> frozenset[str]:
    """Return the accepted drift keys, which this gate may shrink but never grow."""
    source = _BASELINE_PATH if path is None else path
    parsed = tomllib.loads(source.read_text(encoding="utf-8"))
    accepted = parsed.get("accepted", [])
    return frozenset(str(item) for item in accepted)
