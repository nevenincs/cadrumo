"""``cadrumo.core`` stays importable when its own body constructs ``Settings``.

The package exposes ``BucketPointer``, ``pointer_path`` and ``read_pointer``
through a PEP 562 ``__getattr__`` defined near the END of ``core/__init__``.
Any module imported EARLIER in that file which reaches the settings validator
therefore asks a half-built package for an attribute whose accessor does not
exist yet, and ``import cadrumo.core`` fails outright for the whole process.

That is not hypothetical: adding ``from .time import UtcInstant`` to
``secure_object_write`` (imported at ``core/__init__`` line ~203) pulled
``core.time._clock``, whose module-scope ``get_logger`` configures logging,
which calls ``load_settings()`` — and the tree became unimportable for every
agent until the chain was backed out.

Both links on that path are pinned here, because fixing either one alone leaves
the cycle armed: the settings validator must not reach the facade, and neither
must the pointer-IO module it delegates to.
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

#: Names the ``cadrumo.core`` facade serves only through its late ``__getattr__``.
_LATE_BOUND_FACADE_NAMES = frozenset({"BucketPointer", "pointer_path", "read_pointer"})

#: Modules on the settings-resolution path, which core's own body can reach.
_SETTINGS_PATH_MODULES = ("config.py", "_bucket_pointer_io.py")


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
    imported = _facade_imported_names(_CORE_DIR / module_name)

    assert not (imported & _LATE_BOUND_FACADE_NAMES), (
        f"{module_name} imports {sorted(imported & _LATE_BOUND_FACADE_NAMES)} from the "
        "cadrumo.core facade; those names are served by a __getattr__ defined after "
        "the early submodule imports, so this breaks `import cadrumo.core` outright"
    )


def test_the_late_binding_premise_still_holds() -> None:
    """Anti-tautology: the guard above is only meaningful while these names are late-bound.

    If the facade ever binds them eagerly the constraint becomes vacuous, and
    this test fails to say so rather than passing silently.
    """
    source = (_CORE_DIR / "__init__.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    getattr_line = next(
        node.lineno for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "__getattr__"
    )
    first_submodule_import = min(
        node.lineno
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module is not None
    )

    assert getattr_line > first_submodule_import, (
        "core/__init__ now defines __getattr__ before its submodule imports; "
        "re-derive whether the facade-import guard is still load-bearing"
    )


def test_core_survives_settings_construction_during_its_own_init() -> None:
    """The real failure mode, reproduced at the exact module that triggered it.

    A meta-path hook fires when ``core/__init__`` reaches
    ``secure_object_write`` — the line that broke the tree — and constructs
    ``Settings`` there, which is what the logging chain did. This asserts the
    behaviour rather than the import spelling, so it still holds if the fix is
    later restructured.
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
        importlib.import_module("cadrumo.core")  # importing IS the assertion
    finally:
        sys.meta_path.remove(trigger)
        for name in [key for key in sys.modules if key.startswith("cadrumo")]:
            del sys.modules[name]
        sys.modules.update(original_modules)

    assert _MidInitSettingsTrigger.fired, "the trigger never ran; this test measured nothing"
