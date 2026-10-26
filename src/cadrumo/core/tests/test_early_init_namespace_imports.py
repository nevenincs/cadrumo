"""Settings construction remains safe during a core submodule import."""

from __future__ import annotations

import importlib.abc
import sys
from typing import override

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_core_survives_settings_construction_during_submodule_import() -> None:
    """Reproduce settings construction during a core submodule import.

    A meta-path hook fires when ``cadrumo.core.secure_object_write`` is imported
    and constructs ``Settings`` there, which is what the original logging chain
    did. Importing the defining module must remain safe during package re-entry.

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
                # String-form import by necessity: this hook fires DURING
                # `cadrumo.core`'s own init with every `cadrumo.*` entry
                # cleared from `sys.modules`. Resolve the owning module with
                # relative spelling while keeping the same package identity.
                importlib.import_module(".config", package="cadrumo.core").load_settings()
            return None

    trigger = _MidInitSettingsTrigger()
    sys.meta_path.insert(0, trigger)
    try:
        # Relative, string-form import by necessity: the assertion IS a fresh
        # import of `cadrumo.core` from a wiped `sys.modules`.
        importlib.import_module("..", package=__package__)
        # Import the defining module directly. Reading its symbol back is the
        # assertion: an unsafe package re-entry raises before this point.
        from ..secure_object_write import SecureObjectWrite

        assert SecureObjectWrite is not None
    finally:
        sys.meta_path.remove(trigger)
        for name in [key for key in sys.modules if key.startswith("cadrumo")]:
            del sys.modules[name]
        sys.modules.update(original_modules)

    assert _MidInitSettingsTrigger.fired, "the trigger never ran; this test measured nothing"
