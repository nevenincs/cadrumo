"""Screen: test modules the default lane cannot see.

A test that is never selected reports nothing, and pytest reports the run that
selected it as passing. That is the failure mode this screen exists for: a
change was verified in this campaign against a run of its own test module that
had deselected all 24 of its tests, and the exit code was 0. The signal that
caught it was the collected count being lower than the file obviously held,
which is a signal a person has to notice. This makes it a report.

The default lane is read from the project's own `addopts` rather than restated
here, so the screen cannot drift from the selection it describes. Three
conditions are reported:

- ``no_execution_marker`` - the module carries none of the execution markers,
  so no lane selects it and its tests run nowhere at all. This is the sharpest
  condition, because nothing about the module looks unusual and its tests are
  indistinguishable from tests that pass.
- ``other_execution_lane`` - the module declares a valid execution marker that
  is not the default lane's. It runs, in its own lane. Reported so that a
  reader asking why a module did not run in the default lane gets an answer
  rather than silence, never as a defect.
- ``held_out_by_marker`` - the module carries a marker the default lane
  excludes. Legitimate by design: heavy external tooling and the OS credential
  store cannot run in a plain lane. Reported so the set stays visible and is
  enrolled somewhere, never as a defect on its own.
- ``per_function_markers_only`` - the module has no module-level `pytestmark`
  but decorates individual tests. The screen cannot decide visibility from the
  module level alone and says so rather than guessing.

Marker detection is static. A module-level ``pytestmark`` assignment is read
from the syntax tree, which is how every module in this tree declares markers,
and no test is imported or executed to produce this report. That keeps the
screen fast and free of the collection side effects it is meant to describe.

The screen exits 0 whatever it finds. It reports; it does not gate.
"""

from __future__ import annotations

import argparse
import ast
import collections
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

#: Exactly one of these must be carried by every test module; the marker
#: contract in the project configuration is the authority for the set.
_EXECUTION_MARKERS = frozenset({"unit", "integration", "aeat_live"})

__all__ = [
    "LaneVisibility",
    "default_lane_predicate",
    "module_markers",
    "visibility_census",
]

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_MARKER_EXPR = re.compile(r"-m\s+'([^']+)'")


def default_lane_predicate(pyproject: Path) -> tuple[str, frozenset[str]]:
    """Return the default lane's required execution marker and the markers it excludes.

    Read from the project's own ``addopts`` so this screen describes the lane
    that actually runs. A hand-copied predicate would be one more declaration
    of the same fact, free to drift from it.
    """
    config = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    addopts = config["tool"]["pytest"]["ini_options"]["addopts"]
    match = _MARKER_EXPR.search(addopts)
    if match is None:
        raise ValueError("addopts declares no -m marker expression")
    words = match.group(1).split()
    required = words[0]
    excluded = {words[index + 1] for index, word in enumerate(words) if word == "not"}
    return required, frozenset(excluded)


@dataclass(frozen=True, slots=True)
class LaneVisibility:
    """One test module and why the default lane does or does not select it."""

    module: str
    kind: str
    markers: tuple[str, ...]


def module_markers(tree: ast.Module) -> tuple[str, ...] | None:
    """Return the module-level ``pytestmark`` marker names, or ``None`` when absent.

    ``None`` and ``()`` mean different things and are kept apart: no assignment
    at all versus an assignment naming nothing.
    """
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else []
        if not any(isinstance(item, ast.Name) and item.id == "pytestmark" for item in targets):
            continue
        value = node.value  # type: ignore[union-attr]
        elements = value.elts if isinstance(value, ast.List | ast.Tuple) else [value]
        found: list[str] = []
        for element in elements:
            current = element
            if isinstance(current, ast.Call):
                current = current.func
            if isinstance(current, ast.Attribute):
                found.append(current.attr)
        return tuple(found)
    return None


def visibility_census(
    roots: tuple[Path, ...], *, required: str, excluded: frozenset[str]
) -> tuple[LaneVisibility, ...]:
    """Report every test module the default lane does not fully select."""
    findings: list[LaneVisibility] = []
    for root in roots:
        for path in sorted(root.rglob("test_*.py")):
            if "__pycache__" in path.parts:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            if not any(
                isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith("test_")
                for node in ast.walk(tree)
            ):
                continue
            markers = module_markers(tree)
            # Named relative to the repository when it sits inside one, and to the
            # scanned root otherwise, so the census can be run over a constructed
            # tree without the reporting path deciding whether it works.
            anchor = _REPO_ROOT if path.is_relative_to(_REPO_ROOT) else root
            module = path.relative_to(anchor).as_posix()
            if markers is None:
                decorated = any(
                    isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.decorator_list
                    for node in ast.walk(tree)
                )
                kind = "per_function_markers_only" if decorated else "no_execution_marker"
                findings.append(LaneVisibility(module=module, kind=kind, markers=()))
                continue
            held = sorted(set(markers) & excluded)
            execution = sorted(set(markers) & _EXECUTION_MARKERS)
            if not execution:
                findings.append(LaneVisibility(module=module, kind="no_execution_marker", markers=markers))
            elif held:
                findings.append(LaneVisibility(module=module, kind="held_out_by_marker", markers=tuple(held)))
            elif required not in markers:
                findings.append(LaneVisibility(module=module, kind="other_execution_lane", markers=tuple(execution)))
    return tuple(findings)


def main(argv: list[str] | None = None) -> int:
    """Print one greppable row per module and a closing census; always exit 0."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--kind", action="append", help="report only these kinds (repeatable)")
    args = parser.parse_args(argv)

    required, excluded = default_lane_predicate(_REPO_ROOT / "pyproject.toml")
    roots = tuple(path for path in (_REPO_ROOT / "dev", _REPO_ROOT / "tests") if path.is_dir())
    findings = visibility_census(roots, required=required, excluded=excluded)
    wanted = set(args.kind) if args.kind else None
    tally: collections.Counter[str] = collections.Counter(item.kind for item in findings)
    for finding in findings:
        if wanted is not None and finding.kind not in wanted:
            continue
        sys.stdout.write(
            f"lane_visibility module={finding.module} kind={finding.kind} markers={','.join(finding.markers) or '-'}\n"
        )
    kinds = " ".join(f"{kind}={count}" for kind, count in sorted(tally.items()))
    sys.stdout.write(
        f"summary lane_requires={required} lane_excludes={','.join(sorted(excluded))} modules={len(findings)} {kinds}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
