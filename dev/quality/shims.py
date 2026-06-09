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
    "aeat.core",
    "aeat.domain.user_profile",
    "aeat.domain.contribuyente",
    "aeat.domain.contribuyente._keys",
    "aeat.domain.portals",
    "aeat.domain.transactions",
    "aeat.application.user_profile",
    "aeat.application.overview",
    "aeat.application.live",
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
    importlib.import_module("aeat.application.wizard._compiler")
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
