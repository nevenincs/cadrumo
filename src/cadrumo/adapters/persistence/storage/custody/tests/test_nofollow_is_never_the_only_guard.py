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

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_CUSTODY_PACKAGE = Path(__file__).resolve().parent.parent
_FLAG = "O_NOFOLLOW"


def _posix_gated(source_segment: str, function_name: str) -> bool:
    """Whether this function can only run on a platform providing the flag.

    Three admissible gates, each meaning the same thing: an explicit
    ``os.name`` branch, a ``dir_fd=`` argument (unsupported on Windows, so the
    call cannot succeed there), or a name declaring the platform it serves.
    """
    return (
        'os.name != "nt"' in source_segment
        or 'os.name == "posix"' in source_segment
        or "dir_fd=" in source_segment
        or "posix" in function_name.lower()
    )


def _unguarded_nofollow_sites() -> tuple[str, ...]:
    """Return every function requesting the flag without a platform gate."""
    offenders: list[str] = []
    for path in sorted(_CUSTODY_PACKAGE.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        if _FLAG not in source:
            continue
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            segment = ast.get_source_segment(source, node) or ""
            if _FLAG not in segment:
                continue
            if not _posix_gated(segment, node.name):
                offenders.append(f"{path.name}:{node.name}")
    return tuple(offenders)


def test_the_scan_finds_real_nofollow_sites() -> None:
    """ANTI-VACUITY: zero offenders is also what a broken scan reports.

    The assertion below is an emptiness check, which a scan that stopped
    parsing, stopped globbing, or stopped matching the flag satisfies
    perfectly. Requiring the walk to still FIND uses of the flag separates a
    clean package from a blind instrument.
    """
    with_flag = [path.name for path in _CUSTODY_PACKAGE.glob("*.py") if _FLAG in path.read_text(encoding="utf-8")]

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


def test_the_gate_recognises_an_ungated_use() -> None:
    """The detector must be able to fail, not merely to pass.

    Written against a synthetic function rather than the tree, so the check
    keeps discriminating once the tree is clean -- which it is, and which is
    exactly when a detector stops being exercised by its own subject.
    """
    ungated = 'def read(path):\n    return os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))\n'
    gated = 'def read(path):\n    if os.name != "nt":\n        return os.open(path, getattr(os, "O_NOFOLLOW", 0))\n    return None\n'

    assert not _posix_gated(ungated, "read")
    assert _posix_gated(gated, "read")
