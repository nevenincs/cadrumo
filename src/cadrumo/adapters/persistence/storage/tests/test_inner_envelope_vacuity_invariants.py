"""Ensure inner-envelope readers derive current versions from their namespaces."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from .....tests import production_python_files, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_PREDICATE_NAME = "inner_envelope_version_is_current"


def _module_level_version_constants(tree: ast.AST) -> set[str]:
    derived: set[str] = set()
    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, ast.Assign):
            continue
        value = node.value
        if isinstance(value, ast.Attribute) and value.attr == "schema_version":
            derived.update(target.id for target in node.targets if isinstance(target, ast.Name))
    return derived


def _predicate_calls(tree: ast.AST) -> list[ast.Call]:
    calls: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
        if name == _PREDICATE_NAME:
            calls.append(node)
    return calls


def undelegated_version_arguments(source: str) -> list[int]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    derived = _module_level_version_constants(tree)
    offenders: list[int] = []
    for call in _predicate_calls(tree):
        if len(call.args) < 2:
            continue
        expected = call.args[1]
        if isinstance(expected, ast.Attribute) and expected.attr == "schema_version":
            continue
        if isinstance(expected, ast.Name) and expected.id in derived:
            continue
        offenders.append(call.lineno)
    return sorted(offenders)


def _reader_sources() -> list[tuple[Path, str]]:
    readers: list[tuple[Path, str]] = []
    for path in production_python_files():
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _PREDICATE_NAME in source:
            readers.append((path, source))
    return readers


def test_every_reader_takes_its_expected_version_from_the_registry() -> None:
    offenders = [
        f"{repo_relative(path)}:{lineno}"
        for path, source in _reader_sources()
        for lineno in undelegated_version_arguments(source)
    ]
    assert offenders == [], (
        "inner-envelope readers must derive expected versions from their own "
        f"namespace definitions; offenders: {offenders}"
    )


_LITERAL_EXPECTED_VERSION = """
from ..storage import inner_envelope_version_is_current

def load(envelope):
    return inner_envelope_version_is_current(envelope.schema_version, 1)
"""

_DERIVED_VIA_MODULE_CONSTANT = """
from ..storage import CATALOGUE_NAMESPACE, inner_envelope_version_is_current

_CATALOGUE_VERSION = CATALOGUE_NAMESPACE.schema_version

def load(envelope):
    return inner_envelope_version_is_current(envelope.schema_version, _CATALOGUE_VERSION)
"""

_DERIVED_INLINE = """
from ..storage import CATALOGUE_NAMESPACE, inner_envelope_version_is_current

def load(envelope):
    return inner_envelope_version_is_current(envelope.schema_version, CATALOGUE_NAMESPACE.schema_version)
"""


def test_the_derivation_check_flags_a_restated_literal() -> None:
    assert undelegated_version_arguments(_LITERAL_EXPECTED_VERSION) == [5]


def test_the_derivation_check_accepts_a_namespace_derived_constant() -> None:
    assert undelegated_version_arguments(_DERIVED_VIA_MODULE_CONSTANT) == []


def test_the_derivation_check_accepts_an_inline_namespace_attribute() -> None:
    assert undelegated_version_arguments(_DERIVED_INLINE) == []


def test_the_derivation_check_reaches_live_readers() -> None:
    call_sites = sum(len(_predicate_calls(ast.parse(source))) for _, source in _reader_sources())
    assert call_sites > 0, "the inner-envelope derivation scan reached no live reader"
