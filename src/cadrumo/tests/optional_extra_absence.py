"""Real import-system absence of one optional extra, for tests of what a core install does.

A surface that offers or refuses a feature by whether its optional extra is
installed decides through :func:`~cadrumo.core.optional_extras.optional_extra_available`,
a spec-only :func:`importlib.util.find_spec` probe. The honest way to exercise
the absent branch is to make that probe observe a genuine absence, not to
replace the probe or the code that calls it: :func:`optional_extra_absent`
puts a real finder at the head of ``sys.meta_path`` that reports the extra's
package as missing, and takes the package's already-imported modules out of
``sys.modules`` for the duration, so both the probe and any import behind it
meet exactly what an installation without the extra meets. Production code runs
unmodified; everything is restored on exit.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from importlib.abc import MetaPathFinder
from importlib.machinery import ModuleSpec
from types import ModuleType
from typing import override

from ..core.optional_extras import OptionalExtra


class _AbsentPackageFinder(MetaPathFinder):
    """A finder that reports one top-level package, and everything under it, as not installed."""

    def __init__(self, package: str) -> None:
        self._package = package

    @override
    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None = None,
        target: ModuleType | None = None,
    ) -> ModuleSpec | None:
        if fullname.split(".")[0] == self._package:
            raise ModuleNotFoundError(f"No module named {fullname!r}", name=fullname)
        return None


@contextmanager
def optional_extra_absent(extra: OptionalExtra) -> Iterator[None]:
    """Make ``extra``'s package unimportable for the scope, as an install without the extra is.

    Args:
        extra: The registered optional extra whose package is hidden.

    Yields:
        Nothing; the absence holds until the scope exits.
    """
    package = extra.import_name.split(".")[0]
    removed = {name: module for name, module in sys.modules.items() if name.split(".")[0] == package}
    for name in removed:
        del sys.modules[name]
    original = sys.meta_path
    sys.meta_path = [_AbsentPackageFinder(package), *original]
    try:
        yield
    finally:
        sys.meta_path = original
        sys.modules.update(removed)


__all__ = ["optional_extra_absent"]
