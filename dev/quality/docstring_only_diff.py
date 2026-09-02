"""Prove an edit added docstrings and changed no executable code.

A docstring-insertion task must not alter behaviour. Comparing text cannot show
that; comparing the parsed tree with every docstring stripped can. This reads
the committed version of each file from git (a read-only ``git show``) and the
working-tree version, removes the docstring node from every module, class, and
function in both, and compares the unparsed result.

Exit code 0 means every checked file differs from its committed version by
docstrings alone. Any other difference is reported and exits 1.
"""

from __future__ import annotations

import ast
import shutil
import subprocess
import sys
from pathlib import Path


def _strip_docstrings(tree: ast.AST) -> ast.AST:
    """Remove the docstring statement from every node that can carry one."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        body = node.body
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            node.body = body[1:] or [ast.Pass()]
    return tree


def _skeleton(source: str) -> str:
    """Return the code with all docstrings removed, normalised by unparsing."""
    return ast.unparse(_strip_docstrings(ast.parse(source)))


def _committed(path: str, ref: str) -> str | None:
    """Return ``path`` as of ``ref``, or None when it is not tracked there."""
    git = shutil.which("git")
    if git is None:
        msg = "git executable not found on PATH"
        raise RuntimeError(msg)
    result = subprocess.run(  # noqa: S603  # resolved absolute git path, fixed argument list, no shell
        [git, "show", f"{ref}:{path}"],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.decode("utf-8")


def check(paths: list[str], ref: str = "HEAD") -> int:
    """Report any file whose executable code differs from ``ref``."""
    offenders: list[str] = []
    checked = 0
    for path in paths:
        before = _committed(path, ref)
        if before is None:
            offenders.append(f"{path}: not tracked at {ref} (a new file is not a docstring-only change)")
            continue
        after = Path(path).read_text(encoding="utf-8")
        try:
            if _skeleton(before) != _skeleton(after):
                offenders.append(f"{path}: executable code changed, not docstrings alone")
        except SyntaxError as exc:
            offenders.append(f"{path}: does not parse ({exc})")
        checked += 1
    for line in offenders:
        print(line)
    print(f"checked {checked} file(s); {len(offenders)} offender(s)")
    return 1 if offenders else 0


if __name__ == "__main__":
    argv = sys.argv[1:]
    raise SystemExit(check(argv) if argv else 0)
