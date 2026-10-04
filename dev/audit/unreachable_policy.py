"""Declared source population, syntax and presentation bounds for the reachability audit."""

from __future__ import annotations

import re
from typing import Final

from dev._paths import UTF_8

_UTF_8: Final[str] = UTF_8


_FINDING_CAP: Final[int] = 40


_EXIT_FINDINGS: Final[int] = 3


_EXIT_ERROR: Final[int] = 1


_DOTTED_SPEC: Final = re.compile(r"^\.*[A-Za-z_][\w.]*(:[A-Za-z_]\w*)?$")


_SKIPPED_DIRS: Final[frozenset[str]] = frozenset({"__pycache__"})


# Method names a framework calls by convention rather than by reference.
_HOOK_METHOD_NAMES: Final[frozenset[str]] = frozenset(
    {"compose", "render", "model_post_init", "check_action", "on_mount", "on_unmount"},
)


_HOOK_METHOD_PREFIXES: Final[tuple[str, ...]] = (
    "on_",
    "_on_",
    "action_",
    "watch_",
    "compute_",
    "validate_",
    "key_",
    "visit_",
)


_ENUM_BASE_SUFFIXES: Final[tuple[str, ...]] = ("Enum", "Flag")


# Shipped non-Python payloads that address code by name: registry declarations
# and the locale catalogues. Extracted corpus text is prose about tax law, not
# a reference to a symbol, and is not read.
_DATA_GLOBS: Final[tuple[str, ...]] = ("_data/registry/**/*.toml", "_data/registry/**/*.json", "locales/**/*.json")


_DATA_TOKEN: Final = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")


# A command leaf token: lowercase words joined by hyphens, as the CLI spells them.
_COMMAND_TOKEN: Final = re.compile(r"[a-z][a-z0-9]*(?:[-_][a-z0-9]+)*")


#: ``used by:`` label for the repository's own ``dev/`` tooling and gates.
_DEV_LABEL = "dev"


_MODULE_EXEC_FLAG: Final[str] = "-m"


_ENUM_COLLECTION_ATTRS: Final[frozenset[str]] = frozenset(
    {"__members__", "_member_map_", "_member_names_", "_value2member_map_"},
)
