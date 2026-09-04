"""Verify documented lazy re-export surfaces resolve their public symbols.

This script backs ``just verify-shims``. It intentionally checks only the
documented package-level lazy re-export modules instead of scanning every package
root, because importing the full project surface would turn a shim guard into a
side-effect probe.
"""

from __future__ import annotations

import importlib
from collections.abc import Iterable

#: Modules whose public names are resolved through a lazy re-export surface.
#:
#: Eight package initialisers were listed here with an EMPTY ``__all__``. The
#: package-inertness work emptied them, as the architecture requires, and this
#: gate went on counting them: an empty ``__all__`` iterates no names, so each
#: contributed no assertion and the run still reported nine modules verified.
#: A module with no surface left is a stale declaration, not a passing one.
_LAZY_REEXPORT_MODULES: tuple[str, ...] = ("cadrumo.domain.contribuyente.keys",)


def _module_failures(module_name: str) -> list[str]:
    """Return every way one declared re-export surface fails to hold."""
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:
        # A retired or renamed module must read as a finding naming itself, not
        # as a traceback out of the gate that was asked about it.
        return [f"{module_name}: cannot be imported: {type(exc).__name__}: {exc}"]
    exported = getattr(module, "__all__", None)
    if exported is None:
        return [f"{module_name}: missing __all__"]
    if not isinstance(exported, Iterable) or isinstance(exported, (str, bytes)):
        return [f"{module_name}: __all__ is not an iterable of names"]

    names = list(exported)
    if not names:
        return [
            f"{module_name}: __all__ is empty, so this declaration asserts nothing; "
            "the module has no re-export surface left and belongs out of the list"
        ]

    failures: list[str] = []
    for name in names:
        if not isinstance(name, str):
            failures.append(f"{module_name}: non-string __all__ member {name!r}")
            continue
        try:
            getattr(module, name)
        except Exception as exc:
            failures.append(f"{module_name}.{name}: {type(exc).__name__}: {exc}")
    return failures


def main() -> int:
    """Run the documented lazy re-export verification."""
    importlib.import_module("cadrumo.application.wizard.compiler")
    failures: list[str] = []
    for module_name in _LAZY_REEXPORT_MODULES:
        failures.extend(_module_failures(module_name))
    if failures:
        print("Lazy re-export verification failed:")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print(f"Verified {len(_LAZY_REEXPORT_MODULES)} lazy re-export module(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
