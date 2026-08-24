"""``O_NOFOLLOW`` is only ever requested where the platform provides it.

``os.O_NOFOLLOW`` does not exist on Windows. The idiom used to reach for it,
``getattr(os, "O_NOFOLLOW", 0)``, therefore contributes ZERO to the flags on
this project's primary platform -- the code appears to request no-follow and
does not get it, at every call site, silently.

That is not hypothetical. A reader in ``_sentinel`` relied on exactly this and
followed a symlink on Windows, returning the linked file's contents, while an
identically-named sibling refused the same link. It was found by driving both
functions against a real link rather than by reading the flags, and removed.

Every surviving use is POSIX-gated: inside an ``os.name`` branch, passing
``dir_fd=`` (which Windows does not support), or in a helper named for the
platform it serves. Windows gets its protection from a different mechanism --
an explicit reparse-point refusal -- rather than from a flag that is not there.

WHY THIS IS STRUCTURAL. A behavioural check would need every read path to be
reachable with a link in place, and the paths that matter most are the ones
hardest to drive. What is checkable cheaply and completely is the property
that made the bug possible: a function that asks for no-follow on a path
Windows can reach. The gate is therefore about WHERE the flag is used, and it
names the compensating mechanism so a reader is not left thinking Windows is
unprotected.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ......core import scan_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_CUSTODY_PACKAGE = Path(__file__).resolve().parent.parent
_FLAG = "O_NOFOLLOW"


def _custody_modules() -> tuple[Path, ...]:
    """Return every non-test module in the package, subpackages included.

    Recursive by construction. The sibling gate in this package was made
    recursive one pass earlier and this one was left on ``glob("*.py")`` --
    fixing the instance rather than the class, which is the failure this
    campaign keeps recording. The two scans matched only because the package
    has no subpackages.
    """
    return tuple(
        path
        for path in scan_directory(_CUSTODY_PACKAGE, pattern="*.py", recursive=True)
        if "tests" not in path.parts and "__pycache__" not in path.parts
    )


def _requests_the_flag(node: ast.AST) -> bool:
    """Whether ``node`` is a request for the flag, in either spelling."""
    if isinstance(node, ast.Attribute) and node.attr == _FLAG:
        return True
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "getattr"
        and len(node.args) >= 2
        and isinstance(node.args[1], ast.Constant)
        and node.args[1].value == _FLAG
    )


def _is_platform_test(test: ast.expr) -> bool:
    """Whether ``test`` compares ``os.name`` against a platform literal."""
    if not isinstance(test, ast.Compare):
        return False
    left = test.left
    if not isinstance(left, ast.Attribute) or left.attr != "name":
        return False
    return isinstance(left.value, ast.Name) and left.value.id == "os"


def _posix_gated(scope: ast.FunctionDef | ast.AsyncFunctionDef, function_name: str) -> bool:
    """Whether every flag request in ``scope`` is platform-guarded.

    Containment, not mention. Three admissible gates: the request sits INSIDE
    an ``os.name`` branch; the function passes ``dir_fd=`` (unsupported on
    Windows, so the call cannot succeed there); or its name declares the
    platform it serves.
    """
    if "posix" in function_name.lower():
        return True
    if "dir_fd=" in ast.unparse(scope):
        return True
    guarded: set[int] = set()
    for node in ast.walk(scope):
        if isinstance(node, ast.If) and _is_platform_test(node.test):
            for branch_node in [*node.body, *node.orelse]:
                for inner in ast.walk(branch_node):
                    if _requests_the_flag(inner):
                        guarded.add(id(inner))
    return not any(_requests_the_flag(node) and id(node) not in guarded for node in ast.walk(scope))


def _unguarded_nofollow_sites() -> tuple[str, ...]:
    """Return every function requesting the flag without a platform gate."""
    offenders: list[str] = []
    for path in _custody_modules():
        source = path.read_text(encoding="utf-8")
        if _FLAG not in source:
            continue
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if not any(_requests_the_flag(inner) for inner in ast.walk(node)):
                continue
            if not _posix_gated(node, node.name):
                offenders.append(f"{path.name}:{node.name}")
    return tuple(offenders)


def test_the_scan_finds_real_nofollow_sites() -> None:
    """ANTI-VACUITY: zero offenders is also what a broken scan reports.

    The assertion below is an emptiness check, which a scan that stopped
    parsing, stopped globbing, or stopped matching the flag satisfies
    perfectly. Requiring the walk to still FIND uses of the flag separates a
    clean package from a blind instrument.
    """
    with_flag = [path.name for path in _custody_modules() if _FLAG in path.read_text(encoding="utf-8")]

    assert len(with_flag) >= 3, f"the scan sees {_FLAG} in only {with_flag}; it is not reading the package"


def test_no_function_requests_nofollow_on_a_windows_reachable_path() -> None:
    """DISCRIMINATING: the shape the removed sentinel reader had."""
    offenders = _unguarded_nofollow_sites()

    assert not offenders, (
        f"these functions request {_FLAG} without a platform gate: {list(offenders)}. On Windows "
        f"getattr(os, '{_FLAG}', 0) is 0, so the flag is silently absent and the function follows "
        "links it appears to refuse. Gate the branch on os.name and give Windows its own "
        "reparse-point refusal, as the anchored primitive does."
    )


def _scope_of(*source_lines: str) -> ast.FunctionDef:
    """Parse a snippet holding exactly one function and return it."""
    tree = ast.parse("\n".join(source_lines) + "\n")
    return next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef))


def test_the_gate_recognises_an_ungated_use() -> None:
    """The detector must be able to fail, not merely to pass.

    Written against synthetic functions rather than the tree, so the check
    keeps discriminating once the tree is clean -- which it is, and which is
    exactly when a detector stops being exercised by its own subject.
    """
    ungated = _scope_of(
        "def read(path):",
        '    return os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))',
    )
    gated = _scope_of(
        "def read(path):",
        '    if os.name != "nt":',
        '        return os.open(path, getattr(os, "O_NOFOLLOW", 0))',
        "    return None",
    )

    assert not _posix_gated(ungated, "read")
    assert _posix_gated(gated, "read")


def test_a_platform_branch_that_does_not_enclose_the_flag_guards_nothing() -> None:
    """DISCRIMINATING: the hole the first version of this gate had.

    It asked whether the function's SOURCE contained the gating text. A
    function that branches on ``os.name`` somewhere and then requests the flag
    outside that branch therefore passed -- as did one whose only ``os.name``
    was in a comment. That checked whether the author had thought about
    platforms, not whether this use was guarded.
    """
    branch_elsewhere = _scope_of(
        "def read(path):",
        '    if os.name != "nt":',
        '        log("posix")',
        '    return os.open(path, getattr(os, "O_NOFOLLOW", 0))',
    )
    only_a_comment = _scope_of(
        "def read(path):",
        '    # os.name != "nt" would be the right check here',
        '    return os.open(path, getattr(os, "O_NOFOLLOW", 0))',
    )

    assert not _posix_gated(branch_elsewhere, "read")
    assert not _posix_gated(only_a_comment, "read")
