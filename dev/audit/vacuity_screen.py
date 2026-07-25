"""Screen the test surface for gates that assert an empty result without scanning.

The shape this finds is the one that shipped twice in a single day: a gate walks
a corpus, asserts the violation set is empty, and would pass identically if the
walk had found nothing at all. A scan that cannot match reports exactly what a
clean tree reports, so nothing distinguishes the two states from the outside.

This is a SCREEN, not a gate. It produces a worklist to read, deliberately
over-reporting rather than under-reporting, because the two failure modes are not
symmetric: a false positive costs one read, and a false negative is the defect
itself. Two classes of expected false positive are known and are not bugs here.

- A legitimate absence assertion, where empty IS the property under test (a
  module proven deleted, a missing file proven to yield nothing).
- A corpus guarded OFF-MODULE, where emptiness of the shared substrate would
  fail loudly in a sibling gate that asserts a concrete known path is present.
  Such a guard counts, and a hit whose substrate carries one is not a finding.

What it does NOT see, stated so the coverage is not overread: it detects one of
the four known shapes only. A gate asserting a TOTAL where the property is a
DECOMPOSITION passes this screen, as does a pattern that compiles but cannot
match, and an escape that has outlived the construct justifying it. Those are
found by measuring a compiled pattern against a target and a near-miss, which is
per-gate work this screen cannot do for you.

Run as ``python -m dev.audit.vacuity_screen``.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

#: Trees carrying gate modules. Both are required to exist: a screen that
#: silently walked nothing would be the very defect it hunts.
SCREENED_TREES = ("src/cadrumo/tests", "dev")


def asserts_emptiness(node: ast.stmt) -> bool:
    """True when ``node`` asserts a collection is empty or a count is zero."""
    if not isinstance(node, ast.Assert):
        return False
    test = node.test
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        return True
    if not (isinstance(test, ast.Compare) and len(test.ops) == 1 and isinstance(test.ops[0], ast.Eq)):
        return False
    right = test.comparators[0]
    if isinstance(right, ast.List | ast.Tuple | ast.Set) and not right.elts:
        return True
    if isinstance(right, ast.Dict) and not right.keys:
        return True
    return isinstance(right, ast.Constant) and right.value == 0


def proves_it_scanned(node: ast.stmt) -> bool:
    """True when ``node`` asserts a lower bound, a membership, or a truthy corpus.

    Any of these fails when the walk returns nothing, which is the property that
    separates a measured clean result from a blind one.
    """
    if not isinstance(node, ast.Assert):
        return False
    test = node.test
    if isinstance(test, ast.Compare) and len(test.ops) == 1:
        return isinstance(test.ops[0], ast.GtE | ast.Gt | ast.In)
    return isinstance(test, ast.Name | ast.Call)


def screen(root: Path) -> tuple[int, list[tuple[str, str, int]]]:
    """Return the module count screened and the flagged ``(path, function, line)``."""
    flagged: list[tuple[str, str, int]] = []
    scanned = 0
    for tree in SCREENED_TREES:
        base = root / tree
        if not base.is_dir():
            raise SystemExit(f"screened tree is missing, so the result would be meaningless: {base}")
        for path in base.rglob("test_*.py"):
            scanned += 1
            try:
                parsed = ast.parse(path.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            module_proves = any(proves_it_scanned(n) for n in ast.walk(parsed))
            for func in ast.walk(parsed):
                if not isinstance(func, ast.FunctionDef) or not func.name.startswith("test_"):
                    continue
                body = list(ast.walk(func))
                if not any(asserts_emptiness(n) for n in body):
                    continue
                if module_proves or any(proves_it_scanned(n) for n in body):
                    continue
                flagged.append((path.relative_to(root).as_posix(), func.name, func.lineno))
    return scanned, flagged


def main() -> int:
    """Print the worklist. Always exits 0 -- this reports, it does not gate."""
    root = Path(__file__).resolve().parents[2]
    scanned, flagged = screen(root)

    if scanned == 0:
        raise SystemExit("screened zero modules; the result would be meaningless")

    print(f"screened {scanned} test modules under {', '.join(SCREENED_TREES)}")
    print(f"flagged {len(flagged)} empty-assert functions with no proof they scanned anything\n")
    for path, func, line in sorted(flagged):
        print(f"{path}:{line}  {func}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
