"""Declared source population, syntax and presentation bounds for the reachability audit."""

from __future__ import annotations

import re
from typing import Final

from dev.paths import UTF_8

_UTF_8: Final[str] = UTF_8


FINDING_CAP: Final[int] = 40


EXIT_FINDINGS: Final[int] = 3


EXIT_ERROR: Final[int] = 1


DOTTED_SPEC: Final = re.compile(r"^\.*[A-Za-z_][\w.]*(:[A-Za-z_]\w*)?$")


SKIPPED_DIRS: Final[frozenset[str]] = frozenset({"__pycache__"})


# Method names a framework calls by convention rather than by reference.
HOOK_METHOD_NAMES: Final[frozenset[str]] = frozenset(
    {"compose", "render", "model_post_init", "check_action", "on_mount", "on_unmount"},
)


HOOK_METHOD_PREFIXES: Final[tuple[str, ...]] = (
    "on_",
    "_on_",
    "action_",
    "watch_",
    "compute_",
    "validate_",
    "key_",
    "visit_",
)


# ``http.server`` request handlers name a verb handler by the request method: ``do_GET``.
HTTP_VERB_METHOD_PREFIX: Final[str] = "do_"


ENUM_BASE_SUFFIXES: Final[tuple[str, ...]] = ("Enum", "Flag")


# Shipped non-Python payloads that address code by name: registry declarations
# and the locale catalogues. Extracted corpus text is prose about tax law, not
# a reference to a symbol, and is not read.
DATA_GLOBS: Final[tuple[str, ...]] = ("_data/registry/**/*.toml", "_data/registry/**/*.json", "locales/**/*.json")


DATA_TOKEN: Final = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")


# A command leaf token: lowercase words joined by hyphens, as the CLI spells them.
COMMAND_TOKEN: Final = re.compile(r"[a-z][a-z0-9]*(?:[-_][a-z0-9]+)*")


#: ``used by:`` label for the repository's own ``dev/`` tooling and gates.
DEV_LABEL = "dev"


# Distribution build hooks are maintained consumers with their own ownership.
PACKAGING_LABEL = "packaging"

# A production build step that reads Python enums and constants to emit a desktop
# frontend artifact consumes them, though it lives outside every source package.
# Each entry names one script; a directory or a symbol list would widen the claim.
BUILD_GENERATOR_LABEL = "build-generator"
BUILD_GENERATOR_SCRIPTS: Final[tuple[str, ...]] = ("native/desktop/frontend/scripts/ledger_contract.py",)
TRUSTED_OUTSIDE_LABELS: Final[frozenset[str]] = frozenset({DEV_LABEL, PACKAGING_LABEL, BUILD_GENERATOR_LABEL})


MODULE_EXEC_FLAG: Final[str] = "-m"


ENUM_COLLECTION_ATTRS: Final[frozenset[str]] = frozenset(
    {"__members__", "_member_map_", "_member_names_", "_value2member_map_"},
)
