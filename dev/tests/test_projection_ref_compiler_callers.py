"""Only the registry loader and the semantic-map loader compile a projection ref.

The scan covers ``dev/registry``, not ``scaffold/registry``. The semantic-map
loader moved there, and scanning a directory that no longer exists finds
nothing while looking exactly like a loader that stopped calling the
compiler -- so the expectation named a path no walk could reach.

The compiler's OWN module is excluded rather than admitted as a third
caller: ``hydrate_filing_projection_ref`` delegates to it inside the same
file, so counting that would make the definition site look like a consumer
and hide whether a real third loader had appeared.

Lives here rather than under ``src/cadrumo`` because the expected answer
names a canonical caller in ``dev/registry`` -- the check only means
something scanning both trees together.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from cadrumo.core.directory_scan import scan_directory

from .._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: The module that DEFINES the compiler. Its own ``hydrate_filing_projection_ref``
#: delegates to it in the same file, which is not a loader reaching for it.
_COMPILER_HOME = Path("src/cadrumo/core/_filing_projection_ref.py")


def test_projection_ref_compiler_has_only_the_two_canonical_loader_callers() -> None:
    """Only the registry loader and the semantic-map loader compile a projection ref.

    The scan covers ``dev/registry``, not ``scaffold/registry``. The semantic-map
    loader moved there, and scanning a directory that no longer exists finds
    nothing while looking exactly like a loader that stopped calling the
    compiler -- so the expectation named a path no walk could reach.

    The compiler's OWN module is excluded rather than admitted as a third
    caller: ``hydrate_filing_projection_ref`` delegates to it inside the same
    file, so counting that would make the definition site look like a consumer
    and hide whether a real third loader had appeared.
    """
    root = REPO_ROOT
    caller_paths: set[Path] = set()
    for source_root in (root / "src" / "cadrumo", root / "dev" / "registry"):
        for module_path in scan_directory(source_root, pattern="*.py", recursive=True, prune_directories=("tests",)):
            tree = ast.parse(module_path.read_text(encoding="utf-8"))
            if any(
                isinstance(node, ast.Call)
                and (
                    (isinstance(node.func, ast.Name) and node.func.id == "compile_filing_projection_ref")
                    or (isinstance(node.func, ast.Attribute) and node.func.attr == "compile_filing_projection_ref")
                )
                for node in ast.walk(tree)
            ):
                caller_paths.add(module_path.relative_to(root))

    assert caller_paths - {_COMPILER_HOME} == {
        Path("src/cadrumo/domain/calculations/registry/loader.py"),
        Path("dev/registry/pipeline/_semantic_map_loader.py"),
    }
