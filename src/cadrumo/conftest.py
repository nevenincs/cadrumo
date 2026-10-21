"""Pin package-local test storage before tests import Cadrumo.

Repository-wide fixtures live in the public ``cadrumo.tests.pytest_plugin``
module and are registered by the repo-root conftest. This package conftest
keeps the environment bootstrap needed by direct package test runs.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from .core.storage_environment import (
    prepare_temporary_directory,
    storage_directory,
)

if "CADRUMO_TEST_RUN_SCRATCH" not in os.environ:
    # Preserve the interpreter's standard tool environment while keeping
    # bytecode from a standalone package test run under its test-owned root.
    sys.pycache_prefix = str(storage_directory("CADRUMO_PYTHON_CACHE_DIR", "development/cache/pycache"))

# Child conftests import command-line interface (CLI) and internationalization
# (`i18n`) modules while pytest is collecting tests. Those imports initialise
# logging, which resolves Settings before function-scoped fixtures can establish
# their own temporary storage roots. Set this Cadrumo root first so tests do not
# read a user's legacy product-state directory during collection. Overwritten
# (not `setdefault`) because this conftest is the authoritative source for its
# own process's root, regardless of what the repo-root conftest's permissive
# `setdefault` already set.
#
# Pure stdlib, deliberately NOT `apply_collection_storage_root(overwrite=True)`
# from `.tests`: importing ANY name from `cadrumo.tests` -- or from `.core`,
# as this module's own imports below now do only AFTER this line -- executes
# that package's `__init__.py` body first (Python always initialises a parent
# package before a submodule access completes), and both packages' import
# surfaces have, in practice, drifted to reach production modules carrying a
# module-level `get_logger(__name__)` call. Any such call fires
# `configure_logging()`, which binds its `RotatingFileHandler` exactly once
# per process -- if that binding happens before this line runs, it binds to
# the operator's real log rather than this process's isolated root, and
# nothing later in the process can re-bind it. Spelling the derivation out
# here (mirroring `_collection_storage_root.collection_storage_root`'s own
# `<gettempdir()>/cadrumo-pytest-<pid>`) removes the dependency on either
# package staying import-light for this one safety-critical line.
if "CADRUMO_TEST_RUN_SCRATCH" not in os.environ:
    # Standalone/installed pytest consumers may not load the repository conftest.
    # In that case establish the canonical temp root before child conftests import
    # application modules. Repository runs already have a narrower run scratch.
    _temporary_root = prepare_temporary_directory()
    os.environ.update({"TEMP": str(_temporary_root), "TMP": str(_temporary_root), "TMPDIR": str(_temporary_root)})
    tempfile.tempdir = str(_temporary_root)

_COLLECTION_STORAGE_ROOT = Path(tempfile.gettempdir()) / f"cadrumo-pytest-{os.getpid()}"
os.environ["CADRUMO_LOCAL_STORAGE_ROOT"] = str(_COLLECTION_STORAGE_ROOT)
"""Process-private local-storage root set before child conftests import Cadrumo."""


# The other half of what apply_collection_storage_root(overwrite=True) used
# to do in one call: register the atexit cleanup and stale-sibling sweep for
# the root set above. Splitting the env-var write from this registration is
# exactly the point -- the write must happen before any cadrumo import, the
# registration is only safe (and only needed) after.
def _register_collection_storage_root_cleanup() -> None:
    """Register cleanup only after the collection root is established."""
    from .tests.collection_storage_root import register_collection_storage_root_cleanup

    register_collection_storage_root_cleanup(_COLLECTION_STORAGE_ROOT)


_register_collection_storage_root_cleanup()
