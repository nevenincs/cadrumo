"""Gate: the docstring cross-reference screen detects a target that names nothing.

The screen's value is entirely in what it refuses to miss, so the detection is
constructed rather than only pinned against the corpus.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..docstring_reference_targets import (
    DocstringReferenceScanError,
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


def test_a_file_the_walk_listed_but_cannot_read_refuses(tmp_path: Path) -> None:
    """The observed failure: a listed path that is gone by the time it is read.

    A real run of this screen died in pathlib internals on
    ``FileNotFoundError`` for a test module that existed when the walk
    enumerated it and had been deleted before the read reached it. The screen
    already classifies two read failures as skippable -- a file this Python
    cannot parse and one it cannot decode, neither of which can carry a
    docstring worth checking -- so the crash was an unclassified third case,
    not a decision. Skipping it instead would be worse: the screen would
    report a clean result over a corpus smaller than the one it walked.

    The fixture is a DIRECTORY named ``*.py``, which ``rglob`` lists and
    ``read_text`` refuses. That needs no symlink privilege, so the proof
    holds on a machine where this suite would otherwise skip it.
    """
    root = _package(tmp_path, live='"""Live module."""\n')
    (root / "unreadable.py").mkdir()

    with pytest.raises(DocstringReferenceScanError, match="could not read"):
        dangling_references(root)


def test_an_unparseable_or_undecodable_file_is_still_skipped(tmp_path: Path) -> None:
    """The refusal must not swallow the two failures that were always tolerated.

    Proving the new branch fires is only half the claim. A guard that also
    reddened on a syntactically broken file would change what the screen
    measures, so both tolerated classes are driven here against the real
    function rather than assumed unaffected.
    """
    root = _package(
        tmp_path,
        live='"""Points at :func:`resolve_read_id`."""\n',
        broken="def (" + chr(92) + "n",
    )
    (root / "undecodable.py").write_bytes(bytes([0xFF, 0xFE, 0x00, 0x41]))

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


def test_a_package_the_tree_imports_from_is_known(tmp_path: Path) -> None:
    """The source package counts, not only the symbols taken from it.

    A module writing ``from package.sub import name`` makes ``package`` a name
    this tree demonstrably knows; recording only the imported symbol would let
    ``:mod:`package``` read as naming nothing.
    """
    root = _package(
        tmp_path,
        user='"""Uses :mod:`cryptography`."""\n\nfrom cryptography.hazmat.primitives import hashes\n',
    )
    assert dangling_references(root) == ()


def test_a_package_the_tree_never_imports_is_still_reported(tmp_path: Path) -> None:
    """Widening to import sources must not blind the screen to real misses."""
    root = _package(tmp_path, user='"""Uses :mod:`nowhere_at_all`."""\n')
    assert [item.target for item in dangling_references(root)] == ["nowhere_at_all"]


def test_only_module_names_cross_in_from_a_sibling_tree() -> None:
    """A gate may cite its counterpart in `dev/tests`; that module is real.

    Pulling in every SYMBOL those trees define was tried and dropped: it would
    let a shipped docstring resolve against a dev-only function and stop
    reporting a reference that crosses out of the package, which is a finding
    rather than noise. Measured at the time, the wider rule found nothing the
    narrow one missed.
    """
    from ..docstring_reference_targets import _SIBLING_TREES

    assert any(tree.name == "dev" for tree in _SIBLING_TREES)
