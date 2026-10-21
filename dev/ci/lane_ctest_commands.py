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

#: The justfile recipe that builds the package and runs ordinary CTest tests.
CTEST_RECIPE: Final = "test-native-bundle"

#: CTest tests labeled ``external_tool`` are owned by the opt-in live recipe.
CTEST_EXTERNAL_TOOL_RECIPE: Final = "test-native-live"

#: One ``add_test(...)`` call, spanning lines up to the parenthesis that closes it.
_ADD_TEST: Final = re.compile(r"\badd_test\((?P<body>[^()]*)\)", re.DOTALL)
_SET_TEST_PROPERTIES: Final = re.compile(r"\bset_tests_properties\((?P<body>[^()]*)\)", re.DOTALL)

_SOURCE_ROOT: Final = "${PROJECT_SOURCE_DIR}/"


def ctest_lanes(text: str, *, source: str) -> list[Lane]:
    """Return one lane per CTest test in ``text`` that runs pytest.

    Only repository paths count as lane paths. A value that still holds a CMake
    variable or generator expression names a build output, such as the staged
    package, and never a test module.
    """
    labels_by_test = _labels_by_test(text)
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
        test_name = tokens[1] if len(tokens) > 1 and tokens[0] == "NAME" else ""
        recipe = (
            CTEST_EXTERNAL_TOOL_RECIPE
            if "external_tool" in labels_by_test.get(test_name, frozenset())
            else CTEST_RECIPE
        )
        lanes.append(
            Lane(
                source=source,
                paths=paths,
                marker_expression=_marker_expression_of(argv),
                recipe=recipe,
                exclusions=_exclusions_of(argv),
            )
        )
    return lanes


def _labels_by_test(text: str) -> dict[str, frozenset[str]]:
    """Read CTest ``LABELS`` properties by declared test name.

    CTest labels define the execution boundary: an external-tool test belongs
    to the opt-in live recipe even when its command happens to invoke pytest.
    Other properties are read as CMake key/value pairs, so a label survives
    alongside values such as ``TIMEOUT`` and ``RESOURCE_LOCK``.
    """
    labels: dict[str, set[str]] = {}
    for match in _SET_TEST_PROPERTIES.finditer(text):
        try:
            tokens = shlex.split(match.group("body"))
        except ValueError:
            continue
        try:
            properties_at = tokens.index("PROPERTIES")
        except ValueError:
            continue
        test_names = tokens[:properties_at]
        properties = tokens[properties_at + 1 :]
        for index in range(0, len(properties) - 1, 2):
            if properties[index] != "LABELS":
                continue
            values = set(properties[index + 1].split(";"))
            for name in test_names:
                labels.setdefault(name, set()).update(value for value in values if value)
    return {name: frozenset(values) for name, values in labels.items()}


def declared_ctest_lanes(root: Path) -> list[Lane]:
    """Return the pytest lanes every CMake module under ``root`` declares to CTest."""
    directory = root / CTEST_MODULE_DIR
    if not directory.is_dir():
        return []
    lanes: list[Lane] = []
    for module in scan_directory(directory, pattern="*.cmake"):
        lanes.extend(ctest_lanes(module.read_text(encoding=UTF_8), source=f"{CTEST_MODULE_DIR}/{module.name}"))
    return lanes
