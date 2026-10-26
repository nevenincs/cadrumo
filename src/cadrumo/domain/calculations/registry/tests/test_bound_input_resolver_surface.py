"""The registry projector is the sole living bound-input resolver surface."""

from __future__ import annotations

import ast
import unicodedata
from pathlib import Path

import pytest

from .....core.directory_scan import scan_directory
from ..bindings import resolve_available_bound_inputs_by_casilla_id

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_RESOLVER_SUFFIX = "bound_inputs_by_casilla_id"
_RETIRED_RESOLVER = "resolve_bound_inputs_by_casilla_id"


def _production_python_paths() -> tuple[Path, ...]:
    """Return the production modules that can name a bound-input resolver at all.

    Every name either sweep matches -- a ``resolve_*`` definition ending in the
    suffix, or an import of the retired resolver -- contains the suffix, and an
    identifier is spelled in the source after the NFKC normalisation Python
    applies to non-ASCII ones. A module that never spells it has nothing to
    report, so it is not parsed.
    """
    package_root = Path(resolve_available_bound_inputs_by_casilla_id.__code__.co_filename).resolve().parents[3]
    candidates: list[Path] = []
    for path in scan_directory(package_root, pattern="*.py", recursive=True, prune_directories=("tests",)):
        source = path.read_text(encoding="utf-8")
        if _RESOLVER_SUFFIX in (source if source.isascii() else unicodedata.normalize("NFKC", source)):
            candidates.append(path)
    return tuple(candidates)


def _resolver_definitions(paths: tuple[Path, ...]) -> tuple[tuple[str, str], ...]:
    definitions: list[tuple[str, str]] = []
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        definitions.extend(
            (path.name, node.name)
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name.startswith("resolve_")
            and node.name.endswith(_RESOLVER_SUFFIX)
        )
    return tuple(definitions)


def _retired_imports(paths: tuple[Path, ...]) -> tuple[str, ...]:
    importers: list[str] = []
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if any(
            alias.name == _RETIRED_RESOLVER
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            for alias in node.names
        ):
            importers.append(path.name)
    return tuple(importers)


def test_available_bound_input_projector_is_the_sole_resolver_surface() -> None:
    """Keep one public projector and prevent the strict dead surface returning."""
    production_paths = _production_python_paths()

    assert _resolver_definitions(production_paths) == (("bindings.py", "resolve_available_bound_inputs_by_casilla_id"),)
    assert _retired_imports(production_paths) == ()
    assert resolve_available_bound_inputs_by_casilla_id.__module__ == ("cadrumo.domain.calculations.registry.bindings")
