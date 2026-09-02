"""Screen: constants whose name carries more than one value.

The name-collision census asks whether one word names two behaviours. This asks
the same question of data, where the failure is quieter. A reader who greps a
constant and finds two definitions with the same value learns nothing alarming.
A reader who finds two definitions with *different* values has to work out
which one the code in front of them reached, and nothing in the name helps.

Two conditions are reported and the distinction between them is the whole point:

- ``value_conflict`` - one name, more than one value. A grep for this name
  returns two different truths.
- ``value_agreement`` - one name, one value, several modules. Repetition rather
  than ambiguity. Sometimes worth collapsing and sometimes deliberate, so it is
  reported without judgement.

Visibility is carried on every row because it decides how far the damage
reaches. A module-private constant is scoped by the underscore that names it:
it cannot be imported, so two modules holding different values under one
private name are two local facts that never meet. A *public* name carrying two
values is a different matter, because a consumer choosing an import has no
signal that the choice changes the value.

Only literals are read. A constant built by a call or a comprehension has no
value this screen can compare, and guessing at one would be worse than
declining. Booleans are skipped: ``True`` under one name in two modules is not
evidence of anything.

The screen exits 0 whatever it finds. The public-visibility invariant it
protects is gated separately.
"""

from __future__ import annotations

import argparse
import ast
import collections
import sys
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "ConstantFinding",
    "collect_constants",
    "constant_census",
]

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent.parent / "src" / "cadrumo"
_COMPARABLE = (str, int, float, tuple, frozenset)


@dataclass(frozen=True, slots=True)
class ConstantFinding:
    """One constant name defined in more than one module."""

    name: str
    kind: str
    public: bool
    sites: tuple[tuple[str, str], ...]

    @property
    def detail(self) -> str:
        """A one-line rendering of every module claiming this name and its value."""
        return " | ".join(f"{module}={value}" for module, value in self.sites)


def _assigned_name(node: ast.stmt) -> str | None:
    """Return the constant name a module-level statement binds, if it binds one."""
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        return node.targets[0].id
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
        return node.target.id
    return None


def collect_constants(root: Path) -> dict[str, dict[str, str]]:
    """Return every module-level literal constant, keyed by name then by module."""
    found: dict[str, dict[str, str]] = collections.defaultdict(dict)
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts or "tests" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        module = path.relative_to(root).as_posix()
        for node in tree.body:
            name = _assigned_name(node)
            if name is None or not name.lstrip("_").isupper():
                continue
            try:
                value = ast.literal_eval(node.value)  # type: ignore[arg-type]
            except (ValueError, TypeError, SyntaxError):
                continue
            if isinstance(value, bool) or not isinstance(value, _COMPARABLE):
                continue
            found[name][module] = repr(value)
    return dict(found)


def constant_census(constants: dict[str, dict[str, str]]) -> tuple[ConstantFinding, ...]:
    """Classify every constant name that more than one module defines."""
    findings: list[ConstantFinding] = []
    for name, sites in sorted(constants.items()):
        if len(sites) < 2:
            continue
        kind = "value_conflict" if len(set(sites.values())) > 1 else "value_agreement"
        findings.append(
            ConstantFinding(
                name=name,
                kind=kind,
                public=not name.startswith("_"),
                sites=tuple(sorted(sites.items())),
            )
        )
    return tuple(findings)


def main(argv: list[str] | None = None) -> int:
    """Print one greppable row per finding and a closing census; always exit 0."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--kind", action="append", help="report only these kinds (repeatable)")
    parser.add_argument("--public-only", action="store_true", help="report only public names")
    args = parser.parse_args(argv)

    findings = constant_census(collect_constants(_PACKAGE_ROOT))
    wanted = set(args.kind) if args.kind else None
    tally: collections.Counter[str] = collections.Counter(item.kind for item in findings)
    public_conflicts = sum(1 for item in findings if item.kind == "value_conflict" and item.public)
    for finding in findings:
        if wanted is not None and finding.kind not in wanted:
            continue
        if args.public_only and not finding.public:
            continue
        visibility = "public" if finding.public else "private"
        sys.stdout.write(
            f"constant name={finding.name} kind={finding.kind} visibility={visibility} sites={finding.detail}\n"
        )
    kinds = " ".join(f"{kind}={count}" for kind, count in sorted(tally.items()))
    sys.stdout.write(f"summary constants={len(findings)} {kinds} public_value_conflicts={public_conflicts}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
