"""The AEAT adapter names its HTML parser backend in exactly one place.

BeautifulSoup raises ``FeatureNotFound`` rather than falling back when a named
backend is absent, so every call site that names one is an independent
live-failure axis. Before this gate the package carried nineteen constructions
across eleven modules, three naming ``lxml`` and sixteen ``html.parser``, none
with a stated reason -- a backend split nobody had decided, discoverable only by
grep. The gate keeps the decision singular by construction rather than by
convention.

Gates on the PROPERTY (no module but the constructor builds a document or names
a backend), never on a tally: a construction ceiling would encode this moment,
pass vacuously once someone edited the number, and detect nothing.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from .....core.directory_scan import scan_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_ADAPTER_ROOT = Path(__file__).resolve().parent.parent
_CONSTRUCTOR = _ADAPTER_ROOT / "_html.py"
_BACKEND_LITERALS = frozenset({"lxml", "html.parser", "html5lib"})


def _python_sources() -> list[Path]:
    """Every module in the package but the constructor and this gate.

    The gate excludes itself because it must SPELL the backend names it hunts
    for; without the exclusion it reports its own frozenset. That is the only
    exemption, it is keyed by path rather than by a suppression comment, and
    ``test_the_constructor_names_exactly_one_backend`` re-reads the constructor
    directly so the exemption cannot hide a backend change.
    """
    excluded = {_CONSTRUCTOR, Path(__file__).resolve()}
    return sorted(
        p for p in scan_directory(_ADAPTER_ROOT, pattern="*.py", recursive=True) if p.resolve() not in excluded
    )


def test_only_the_constructor_builds_a_soup() -> None:
    """No module in this package calls ``BeautifulSoup(...)`` directly."""
    offenders: list[str] = []
    for source in _python_sources():
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "BeautifulSoup":
                offenders.append(f"{source.relative_to(_ADAPTER_ROOT)}:{node.lineno}")
    assert not offenders, (
        "these sites construct a document directly instead of calling parse_html: "
        f"{offenders}. The backend is one decision; route the markup through "
        "cadrumo.adapters.outbound.aeat._html.parse_html."
    )


def test_only_the_constructor_names_a_backend() -> None:
    """No module in this package carries a parser-backend name as a literal."""
    offenders: list[str] = []
    for source in _python_sources():
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and node.value in _BACKEND_LITERALS:
                offenders.append(f"{source.relative_to(_ADAPTER_ROOT)}:{node.lineno} -> {node.value!r}")
    assert not offenders, f"these sites name a parser backend outside the one constructor: {offenders}"


def test_the_constructor_names_exactly_one_backend() -> None:
    """The constructor itself declares a single backend, and it is ``lxml``.

    Anchors the gate above to a real choice: without this, deleting the backend
    constant would leave both sweeps passing vacuously.
    """
    tree = ast.parse(_CONSTRUCTOR.read_text(encoding="utf-8"))
    named = {
        node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and node.value in _BACKEND_LITERALS
    }
    assert named == {"lxml"}, f"expected the constructor to name lxml alone, found {named}"
