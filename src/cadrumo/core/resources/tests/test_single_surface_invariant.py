"""Structural guards on how production code locates bundled data.

Production modules must not define parallel ``_DEFAULT_*_ROOT`` locator
constants over :func:`~cadrumo.core.resources.bundled_data.bundled_path`, and
must not walk ``__file__`` out of the installed ``cadrumo`` package.
"""

from __future__ import annotations

import pathlib
import re
from pathlib import Path

import pytest

from ....tests.inventory import package_python_files, production_python_files, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _is_production_module(path: Path) -> bool:
    """Production = .py file that is neither a test nor conftest."""
    if path.suffix != ".py":
        return False
    name = path.name
    if name == "conftest.py":
        return False
    return not (name.startswith("test_") or name.startswith("_test_"))


def _production_files() -> list[Path]:
    return sorted(p for p in production_python_files() if _is_production_module(p))


def test_no_default_root_constants_in_production() -> None:
    """No production module defines a parallel ``_DEFAULT_*_ROOT`` constant."""

    pattern = re.compile(r"^_DEFAULT_[A-Z_]+_ROOT\s*=\s*bundled_path", re.MULTILINE)
    offenders: list[str] = []
    for path in _production_files():
        rel = repo_relative(path)
        text = path.read_text(encoding="utf-8")
        if pattern.search(text):
            offenders.append(rel)
    assert not offenders, (
        "production files defining "
        "_DEFAULT_*_ROOT = bundled_path(...) found; these must "
        f"call the owning resource loader instead: {offenders}"
    )


_FILE_WALK_RE = re.compile(
    r"Path\(__file__\)\.resolve\(\)((?:\.parent)+)|Path\(__file__\)\.resolve\(\)\.parents\[(\d+)\]",
)


def test_no_production_module_walks_out_of_the_package() -> None:
    """No production module may walk ``__file__`` out of the ``cadrumo`` package.

    Cadrumo ships as an installed application: at runtime there is no
    repository and no "project", only an application data root. Walking
    far enough up from ``__file__`` to escape the package reconstructs a
    source-checkout layout, which on an installed build lands in
    ``site-packages`` — or inside a packaging tool's ephemeral cache,
    where a prune can destroy whatever was written there. That is exactly
    the hazard :mod:`cadrumo.core.config_state_root` exists to close, so
    precisely one module may compute it, behind ``RunMode.CHECKOUT``.

    Walking *within* the package is fine and is NOT flagged: a wheel ships
    ``cadrumo/``'s own modules, so e.g. ``application/wizard`` reaching
    ``entrypoints/cli`` resolves correctly in every run mode. The gate is
    therefore depth-aware — it compares hop count against how deep the
    file sits — rather than banning ``__file__`` arithmetic outright.

    This is an eradication ratchet. It replaced a guard that policed
    *unused* ``PROJECT_ROOT`` imports, which turned vacuous the moment the
    constant was deleted; the property still worth defending is that the
    concept never comes back.
    """
    offenders: list[str] = []
    for path in package_python_files(include_data=True):
        rel = repo_relative(path)
        if "/tests/" in rel:
            continue
        # Depth inside the package: src/cadrumo/a/b/mod.py sits 2 dirs below the
        # root, so depth+1 hops reach `cadrumo/` itself and anything beyond escapes.
        depth = len(pathlib.PurePosixPath(rel).parts) - 3
        for match in _FILE_WALK_RE.finditer(path.read_text(encoding="utf-8")):
            hops = match.group(1).count(".parent") if match.group(1) else int(match.group(2)) + 1
            if hops > depth + 1:
                offenders.append(f"{rel} (walks {hops} up from depth {depth})")
    assert not offenders, (
        "production modules walking __file__ out of the cadrumo package "
        "(resolve operator paths through the application data root instead — "
        f"Settings.cadrumo_local_storage_root): {offenders}"
    )
