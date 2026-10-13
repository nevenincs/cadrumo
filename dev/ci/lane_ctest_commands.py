"""Derive the pytest lanes CTest declares against the built application package."""

from __future__ import annotations

import re
import shlex
from pathlib import Path
from typing import Final

from cadrumo.core.directory_scan import scan_directory
from dev._paths import UTF_8

from .lane_contracts import Lane
from .lane_recipe_commands import _exclusions_of, _marker_expression_of, _paths_of

#: The CMake modules that declare CTest tests.
CTEST_MODULE_DIR: Final = "native/cmake"

#: The justfile recipe that builds the package and runs its CTest suite. A test
#: CTest runs belongs to this recipe's population, exactly as a recipe's own
#: pytest invocation does.
CTEST_RECIPE: Final = "test-native-bundle"

#: One ``add_test(...)`` call, spanning lines up to the parenthesis that closes it.
_ADD_TEST: Final = re.compile(r"\badd_test\((?P<body>[^()]*)\)", re.DOTALL)

_SOURCE_ROOT: Final = "${PROJECT_SOURCE_DIR}/"


def ctest_lanes(text: str, *, source: str) -> list[Lane]:
    """Return one lane per CTest test in ``text`` that runs pytest.

    Only repository paths count as lane paths. A value that still holds a CMake
    variable or generator expression names a build output, such as the staged
    package, and never a test module.
    """
    lanes: list[Lane] = []
    for match in _ADD_TEST.finditer(text):
        try:
            tokens = shlex.split(match.group("body").replace(_SOURCE_ROOT, ""))
        except ValueError:
            continue
        if "pytest" not in tokens:
            continue
        argv = tokens[tokens.index("pytest") :]
        paths = tuple(path for path in _paths_of(argv) if "$" not in path)
        if not paths:
            continue
        lanes.append(
            Lane(
                source=source,
                paths=paths,
                marker_expression=_marker_expression_of(argv),
                recipe=CTEST_RECIPE,
                exclusions=_exclusions_of(argv),
            )
        )
    return lanes


def declared_ctest_lanes(root: Path) -> list[Lane]:
    """Return the pytest lanes every CMake module under ``root`` declares to CTest."""
    directory = root / CTEST_MODULE_DIR
    if not directory.is_dir():
        return []
    lanes: list[Lane] = []
    for module in scan_directory(directory, pattern="*.cmake"):
        lanes.extend(ctest_lanes(module.read_text(encoding=UTF_8), source=f"{CTEST_MODULE_DIR}/{module.name}"))
    return lanes
