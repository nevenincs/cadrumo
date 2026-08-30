"""Verify documented lazy re-export surfaces resolve their public symbols.

This script backs ``just verify-shims``. It intentionally checks only the
documented package-level lazy re-export modules instead of scanning every package
root, because importing the full project surface would turn a shim guard into a
side-effect probe.
"""

from __future__ import annotations

import importlib
from collections.abc import Iterable

_LAZY_REEXPORT_MODULES: tuple[str, ...] = (
    "cadrumo.core",
    "cadrumo.domain.user_profile",
    "cadrumo.domain.contribuyente",
    "cadrumo.domain.contribuyente.keys",
    "cadrumo.domain.portals",
    "cadrumo.domain.transactions",
    "cadrumo.application.user_profile",
    "cadrumo.application.overview",
    "cadrumo.application.live",
)


def _module_failures(module_name: str) -> list[str]:
    module = importlib.import_module(module_name)
    exported = getattr(module, "__all__", None)
    if exported is None:
        return [f"{module_name}: missing __all__"]
    if not isinstance(exported, Iterable) or isinstance(exported, (str, bytes)):
        return [f"{module_name}: __all__ is not an iterable of names"]

    failures: list[str] = []
    for name in exported:
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
