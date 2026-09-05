"""Gate: the docstring cross-reference screen detects a target that names nothing.

The screen's value is entirely in what it refuses to miss, so the detection is
constructed rather than only pinned against the corpus.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..docstring_reference_targets import (
    collect_defined_names,
    dangling_references,
    docstring_references,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _package(tmp_path: Path, **modules: str) -> Path:
    """Write a miniature package and return the directory to scan."""
    root = tmp_path / "cadrumo"
    root.mkdir()
    for name, source in modules.items():
        (root / f"{name}.py").write_text(source, encoding="utf-8")
    return root


def test_a_reference_to_a_symbol_nothing_defines_is_reported(tmp_path: Path) -> None:
    """The defect: prose naming a function that no longer exists.

    A module docstring told readers the ledger read verbs use
    ``resolve_read_id`` while that function had no caller and a different one
    did the work. Nothing checked the claim, so it outlived the code.
    """
    root = _package(
        tmp_path,
        live='"""Points at :func:`resolve_read_id`, which nothing defines."""\n',
    )
    targets = [item.target for item in dangling_references(root)]
    assert targets == ["resolve_read_id"]


def test_a_reference_to_a_symbol_the_tree_defines_is_not_reported(tmp_path: Path) -> None:
    """The normal case must stay silent or the screen is unreadable."""
    root = _package(
        tmp_path,
        home='"""Home of the resolver."""\n\n\ndef resolve_id() -> None:\n    """Resolve."""\n',
        user='"""Uses :func:`resolve_id` from its neighbour."""\n',
    )
    assert dangling_references(root) == ()


def test_a_third_party_name_the_tree_imports_is_not_reported(tmp_path: Path) -> None:
    """``:class:`BaseModel``` must not need an allowlist to stay quiet."""
    root = _package(
        tmp_path,
        models='"""Models."""\n\nfrom pydantic import BaseModel\n',
        prose='"""Describes a :class:`BaseModel` subclass."""\n',
    )
    assert dangling_references(root) == ()


def test_a_relative_module_role_resolves_to_its_last_segment(tmp_path: Path) -> None:
    """``:mod:`_ledger``` is how a sibling module is habitually named."""
    root = _package(
        tmp_path,
        _ledger='"""A sibling."""\n',
        caller='"""Delegates to :mod:`_ledger`."""\n',
    )
    assert dangling_references(root) == ()


def test_every_role_that_names_code_is_collected(tmp_path: Path) -> None:
    """A role the extractor skips is a defect it can never report."""
    root = _package(
        tmp_path,
        mod=('"""Names :func:`a`, :class:`b`, :data:`c`, :meth:`d`, :attr:`e`, :mod:`f`, :obj:`g` and :exc:`h`."""\n'),
    )
    assert {target for _, target in docstring_references(root)} == set("abcdefgh")


def test_a_defined_name_is_collected_however_it_is_bound(tmp_path: Path) -> None:
    """Classes, functions and both assignment forms all define a name."""
    root = _package(
        tmp_path,
        mod=("class Widget:\n    pass\n\n\ndef build() -> None:\n    pass\n\n\nPLAIN = 1\nANNOTATED: int = 2\n"),
    )
    defined, _imported, _modules = collect_defined_names(root)
    assert {"Widget", "build", "PLAIN", "ANNOTATED"} <= defined


def test_a_subscripted_generic_resolves_through_its_base_and_arguments(tmp_path: Path) -> None:
    """``Envelope[BlobManifest]`` is two claims, not one unresolvable string.

    Splitting only on the parenthesis left the whole subscript intact, so three
    legitimate generics were reported as names the package does not define.
    """
    root = _package(
        tmp_path,
        types="class Envelope:\n    pass\n\n\nclass BlobManifest:\n    pass\n",
        prose='"""Returns an :class:`Envelope[BlobManifest]` for the caller."""\n',
    )
    assert dangling_references(root) == ()


def test_a_subscript_reports_only_the_half_that_is_missing(tmp_path: Path) -> None:
    """A real generic over an unknown argument must still be caught."""
    root = _package(
        tmp_path,
        types="class Envelope:\n    pass\n",
        prose='"""Returns an :class:`Envelope[GhostPayload]`."""\n',
    )
    assert [item.target for item in dangling_references(root)] == ["GhostPayload"]
