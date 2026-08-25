"""``cadrumo.core`` stays importable when a submodule import constructs ``Settings``.

The package once bound most of its surface eagerly and served a handful of names
through a PEP 562 ``__getattr__`` defined near the END of ``core/__init__``. Any
module imported EARLIER in that file which reached the settings validator asked a
half-built package for an attribute whose accessor did not exist yet, and
``import cadrumo.core`` failed outright for the whole process.

That is not hypothetical: adding ``from .time import UtcInstant`` to
``secure_object_write`` (then imported at ``core/__init__`` line ~203) pulled
``core.time._clock``, whose module-scope ``get_logger`` configures logging,
which calls ``load_settings()`` — and the tree became unimportable for every
agent until the chain was backed out.

The facade now resolves its ENTIRE public surface through ``__getattr__`` and
imports no submodule while it executes, so there is no longer an "earlier"
module to reach back from. That is asserted directly rather than assumed, and
the two links on the original path stay pinned, because the reach-back returns
the moment an eager import does: the settings validator must not reach the
facade, and neither must the pointer-IO module it delegates to.
"""

from __future__ import annotations

import ast
import importlib.abc
import sys
from pathlib import Path
from typing import override

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_CORE_DIR = Path(__file__).resolve().parent.parent


def _late_bound_facade_names() -> frozenset[str]:
    """Every name the ``cadrumo.core`` facade serves through its ``__getattr__``.

    Read from the live map rather than hand-listed. Three names were pinned here
    when only three were late-bound; the facade now resolves its whole public
    surface that way, and a hand-list would have kept asserting the original
    three while the other three-hundred-odd went unwatched.
    """
    from ... import core

    return frozenset(core._LAZY_EXPORTS)


#: Modules on the settings-resolution path, which core's own body can reach.
_SETTINGS_PATH_MODULES = ("config.py", "bucket_pointer.py")


def test_bucket_pointer_public_surface_is_defining_module_only() -> None:
    """Pointer APIs have no core-facade bridge or lazy binding."""
    from ... import core
    from .. import bucket_pointer

    names = (
        "BucketPointer",
        "pointer_path",
        "read_pointer",
        "require_active_bucket_id",
        "resolve_active_bucket_id",
        "resolve_repository_bucket_id",
        "write_pointer",
    )

    assert all(not hasattr(core, name) for name in names)
    assert all(hasattr(bucket_pointer, name) for name in names)
    assert all(name not in core._LAZY_EXPORTS for name in names)
    assert all(name not in core.__all__ for name in names)


def _facade_imported_names(module_path: Path) -> set[str]:
    """Return every name ``module_path`` imports from the ``cadrumo.core`` facade.

    Covers both module-level and function-local ``from . import X`` statements,
    since the failing import in ``config.py`` was function-local.
    """
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module is None:
            names.update(alias.name for alias in node.names)
    return names


@pytest.mark.parametrize("module_name", _SETTINGS_PATH_MODULES)
def test_settings_path_modules_never_import_late_bound_facade_names(module_name: str) -> None:
    """A module core can reach mid-init must name the owning submodule instead."""
    late_bound = _late_bound_facade_names()
    imported = _facade_imported_names(_CORE_DIR / module_name)

    assert late_bound, "the facade exposed no late-bound names; this guard would pass vacuously"
    assert not (imported & late_bound), (
        f"{module_name} imports {sorted(imported & late_bound)} from the "
        "cadrumo.core facade; those names are served by __getattr__, so a module "
        "the settings path reaches must name the owning submodule instead"
    )


def test_core_init_performs_no_eager_submodule_imports() -> None:
    """The invariant that retires the whole hazard class, not just its known instance.

    The outage above needed a module imported DURING ``core/__init__`` that
    reached back for a name bound only later in the same file. That required an
    eager submodule import to exist at all. The facade now resolves its entire
    public surface through ``__getattr__`` and imports no submodule while it
    executes, so there is no "earlier" module left to reach back from.

    This replaces an ordering assertion (``__getattr__`` defined after the first
    submodule import) that could no longer be evaluated once the last eager
    import went: with none left, its ``min()`` had nothing to take. Asserting
    the absence directly is strictly stronger -- it holds the condition that
    makes the reach-back impossible, and it fails the moment an eager import
    returns, which is also the moment the import-cost regression returns.
    """
    tree = ast.parse((_CORE_DIR / "__init__.py").read_text(encoding="utf-8"))
    eager = [
        f"line {node.lineno}: from {'.' * node.level}{node.module} import ..."
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module is not None
    ]

    assert eager == [], (
        "core/__init__ imports its own submodules at import time again: "
        f"{eager}. Every process in this tree imports this package, so an eager "
        "binding here is paid by all of them, and it re-arms the mid-init "
        "reach-back this module exists to prevent. Add the name to _LAZY_EXPORTS "
        "and its static binding to the TYPE_CHECKING block instead."
    )


def test_core_survives_settings_construction_while_resolving_a_facade_name() -> None:
    """The real failure mode, reproduced at the first module the facade resolves.

    A meta-path hook fires when ``cadrumo.core.secure_object_write`` is imported
    — the module whose eager import broke the tree — and constructs ``Settings``
    there, which is what the logging chain did. This asserts the behaviour
    rather than the import spelling, so it still holds after restructuring.

    The trigger used to fire during ``core/__init__`` itself. It cannot any
    more: the facade imports no submodule while it executes, so the hook is
    reached one step later, when ``__getattr__`` resolves a name that module
    owns. That is the surviving shape of the same hazard — a settings
    construction re-entering ``cadrumo.core`` from inside a submodule import —
    and the assertion is unchanged: the facade name must still resolve.

    Without re-pointing, the hook simply never ran and the test passed having
    measured nothing, which is why the ``fired`` assertion below is load-bearing.
    """
    # Every other test in this worker process imported `cadrumo.*` before this
    # one ran, and every class object those tests hold (pydantic model schemas,
    # module-level singletons, cached instances) is bound to THOSE module
    # objects. Deleting the cadrumo.* entries here forces a genuinely fresh
    # import for the assertion below, but without restoring the original
    # entries afterward, every later test in this worker sees fresh re-imports
    # that mint NEW class objects sharing the OLD ones' qualified names --
    # e.g. a pydantic strict-model isinstance check on `ManifestKdfParams`
    # then fails against an instance built from the pre-wipe class. Save the
    # original entries and restore them in `finally` so no other test in this
    # process observes any effect of the wipe.
    original_modules = {key: module for key, module in sys.modules.items() if key.startswith("cadrumo")}
    for name in original_modules:
        del sys.modules[name]

    class _MidInitSettingsTrigger(importlib.abc.MetaPathFinder):
        fired = False

        @override
        def find_spec(self, fullname: str, path: object = None, target: object = None) -> None:
            if fullname == "cadrumo.core.secure_object_write" and not _MidInitSettingsTrigger.fired:
                _MidInitSettingsTrigger.fired = True
                # Absolute, string-form import by necessity: this hook fires
                # DURING `cadrumo.core`'s own init with every `cadrumo.*` entry
                # cleared from `sys.modules`. A relative import would resolve
                # through this test module's own package and re-enter the very
                # init under measurement, so `import_module` is what preserves
                # the absolute semantics the assertion depends on.
                importlib.import_module("cadrumo.core.config").load_settings()
            return None

    trigger = _MidInitSettingsTrigger()
    sys.meta_path.insert(0, trigger)
    try:
        # Absolute, string-form import by necessity: the assertion IS a fresh
        # absolute import of `cadrumo.core` from a wiped `sys.modules`, which a
        # relative form cannot reproduce.
        core = importlib.import_module("cadrumo.core")
        # Resolving a name owned by the triggering module is what now drives the
        # hook, and reading it back IS the assertion: if the settings
        # construction re-entered a half-built facade this raises.
        assert core.SecureObjectWrite is not None
    finally:
        sys.meta_path.remove(trigger)
        for name in [key for key in sys.modules if key.startswith("cadrumo")]:
            del sys.modules[name]
        sys.modules.update(original_modules)

    assert _MidInitSettingsTrigger.fired, "the trigger never ran; this test measured nothing"
