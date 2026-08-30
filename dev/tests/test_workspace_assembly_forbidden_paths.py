"""Zero-remnant fixed point for the retired workspace-assembly private modules.

Lives here rather than under ``src/cadrumo`` because half of what it proves is
genuinely repo-wide: no tracked file anywhere under ``src``, ``docs`` or
``dev`` may still name the rejected ``_workspace_projection.py`` design, and
narrowing the scan to ``src`` alone would leave a stale reference in the
development tooling tree undetected.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from .._paths import REPO_ROOT

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]


def test_workspace_assembly_forbidden_private_paths_have_not_reappeared_in_the_tracked_tree() -> None:
    """Zero-remnant fixed point: enumerate TRACKED files, never walk the filesystem.

    A gitignored mirror or a peer's in-flight deletion can make a filesystem
    walk report a phantom remnant or silently skip a real one; ``git
    ls-files`` is the one census that answers "what does this tree actually
    track" regardless of either. Scoped to ``src``, ``docs``, and ``dev``.
    """
    repository = REPO_ROOT
    forbidden_module_stems = ("_workspace_projection", "_workspace")
    tracked = subprocess.run(
        ("git", "ls-files", "-z", "--", "src", "docs", "dev"),  # noqa: S607
        capture_output=True,
        check=True,
        cwd=repository,
        text=True,
    ).stdout.split(chr(0))
    modelo_package = "src/cadrumo/application/modelo/"
    remnant_paths = tuple(
        entry
        for entry in tracked
        if entry.startswith(modelo_package)
        and entry[len(modelo_package) :] in ("_workspace_projection.py", "_workspace.py")
    )
    assert not remnant_paths, forbidden_module_stems

    scanned_paths = tuple(
        sorted(
            path
            for entry in tracked
            if entry.endswith((".py", ".rst", ".toml"))
            # A path git still tracks can be absent from the working tree
            # while a peer's deletion is in flight. It carries no content to
            # scan, and reading it would fail the gate on someone else's
            # staging state rather than on a genuine remnant.
            if (path := repository / entry).is_file()
        ),
    )
    # workspace.py's own module docstring names "_workspace_projection.py" once,
    # deliberately: it records the REJECTED intermediate design this assembly
    # chose against, and test_workspace.py's own docstring (and this module's)
    # name it for the same reason. Neither is a stale reference thinking that
    # module exists; all three are excluded from the scan for that reason, and
    # nowhere else in the tracked tree may name it.
    excluded_paths = {
        Path(__file__).resolve(),
        (repository / "src/cadrumo/application/modelo/tests/test_workspace.py").resolve(),
    }
    # An exclusion that no longer excludes anything is the failure mode this
    # family of gates exists to catch: it goes on suppressing a file that has
    # stopped naming the forbidden module, so the day that file names it again
    # the gate stays green. Assert the exclusions still earn their place, which
    # is the same both-directions discipline the marker scan's scope gate uses.
    # `workspace.py` was carried here until its module docstring stopped naming
    # the rejected design; it is no longer excluded, so it is now scanned like
    # any other module.
    for excluded in excluded_paths:
        assert re.search(r"(?<![A-Za-z0-9_])_workspace_projection\.py", excluded.read_text(encoding="utf-8")), (
            f"{excluded.relative_to(repository)} is excluded from the remnant scan but no longer names the "
            "forbidden module, so the exclusion suppresses nothing and would hide a real remnant if one returned"
        )
    prose_remnants = tuple(
        path.relative_to(repository)
        for path in scanned_paths
        if path.resolve() not in excluded_paths
        # Match the forbidden module as a whole filename, not a substring: the
        # live conformance suite legitimately names test_workspace_projection.py,
        # which CONTAINS the rejected _workspace_projection.py and would otherwise
        # red this gate on correct code.
        and re.search(r"(?<![A-Za-z0-9_])_workspace_projection\.py", path.read_text(encoding="utf-8"))
    )
    assert not prose_remnants
