"""Enrolment gate: exactly one derivation of registry-tree identity exists.

The identity module is only load-bearing if nothing reaches around it. A second
spelling of the stamp filename, a second computation of the location, or a
second digest derivation is how a build and a runtime come to disagree about
which tree they are looking at -- and that disagreement is silent, because both
sides produce a plausible hex string.

So this gate scans the whole first-party surface, the shipped package and the development tooling tree, and
requires:

* the stamp filename literal to appear in exactly one module;
* the sibling-location join to appear in exactly one module;
* no module outside the identity module to hash a fingerprint tuple set into a
  tree digest of its own.

Scanned from the AST rather than by text, so a match inside a docstring or a
comment does not count and a real call is not missed by a formatting change.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.identity import (
    REGISTRY_IDENTITY_STAMP_FILENAME,
    compute_installed_tree_digest,
    compute_walked_tree_digest,
    registry_identity_stamp_location,
)
from cadrumo.tests import python_files_under

from .._paths import REPO_ROOT as _REPOSITORY_ROOT
from ..quality.unread_inputs import report_unread

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_IDENTITY_MODULE_NAME = "identity.py"
"""The one module permitted to own each derivation below."""

_SCANNED_TREES = ("src", "dev")
"""Every first-party tree. ``dev`` is included because the release stamper lives there."""


def _first_party_modules() -> tuple[Path, ...]:
    """Return every first-party Python module across the scanned trees."""
    modules: list[Path] = []
    for tree in _SCANNED_TREES:
        root = _REPOSITORY_ROOT / tree
        assert root.is_dir(), f"scanned tree {root} is missing; this gate would pass vacuously"
        modules.extend(python_files_under(root))
    return tuple(modules)


def _module_asts() -> Iterator[tuple[Path, ast.Module]]:
    """Yield each first-party module with its parsed tree."""
    modules = _first_party_modules()
    assert len(modules) > 1000, (
        f"only {len(modules)} modules found; a collapsed corpus would let every assertion below pass vacuously"
    )
    for path in modules:
        try:
            yield path, ast.parse(path.read_text(encoding="utf-8"), str(path))
        except (OSError, SyntaxError) as refusal:  # pragma: no cover - a broken module is another gate's finding
            # Ownership of the breakage is elsewhere; the CONSEQUENCE is here. A
            # module that never parses is never searched, so an identity spelling
            # inside it is not found and every assertion below reads as clean. The
            # corpus guard above counts LISTED modules, not parsed ones, so it
            # cannot notice. Announced rather than refused because `dev` is in
            # scope and a peer mid-edit must not red a shared gate.
            report_unread(
                "first-party identity enrolment scan",
                "this module was not parsed, so an identity spelling inside it would not appear "
                "in any finding below",
                [f"{path} ({type(refusal).__name__})"],
            )
            continue


def _modules_containing_string(needle: str) -> frozenset[str]:
    """Return the names of modules with ``needle`` as a real string CONSTANT.

    Reads ``ast.Constant`` nodes only, so prose in a docstring or a comment that
    happens to name the file does not register as a second spelling.
    """
    found: set[str] = set()
    for path, tree in _module_asts():
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and needle in node.value:
                if _is_docstring_constant(tree, node):
                    continue
                found.add(path.name)
                break
    return frozenset(found)


def _is_docstring_constant(tree: ast.Module, node: ast.Constant) -> bool:
    """Whether ``node`` is the docstring of a module, class, or function in ``tree``."""
    for parent in ast.walk(tree):
        if not isinstance(parent, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        body = parent.body
        if body and isinstance(body[0], ast.Expr) and body[0].value is node:
            return True
    return False


def test_the_stamp_filename_is_spelled_in_exactly_one_module() -> None:
    """One literal, one owner.

    A second spelling anywhere means the build could write one name while the
    runtime looks for another -- which does not fail, it merely never finds a
    stamp, and the walk silently returns forever.
    """
    owners = _modules_containing_string(REGISTRY_IDENTITY_STAMP_FILENAME)

    assert owners == {_IDENTITY_MODULE_NAME}, (
        f"the identity stamp filename must be spelled only in {_IDENTITY_MODULE_NAME}; also found in {sorted(owners)}"
    )


def test_no_module_joins_the_stamp_filename_onto_a_path_itself() -> None:
    """Nothing reconstructs the stamp location; every caller asks for it.

    Pairs with the filename gate: a module could import the constant legitimately
    and then join it onto a root of its own choosing, landing the stamp somewhere
    the runtime never reads. The location derivation has one home.
    """
    offenders: set[str] = set()
    for path, tree in _module_asts():
        if path.name == _IDENTITY_MODULE_NAME:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.BinOp) or not isinstance(node.op, ast.Div):
                continue
            if _names_the_stamp_constant(node.right):
                offenders.add(path.name)

    assert not offenders, (
        "the identity stamp location must come from registry_identity_stamp_location, "
        f"never a path join; joined in {sorted(offenders)}"
    )


def _names_the_stamp_constant(node: ast.expr) -> bool:
    """Whether ``node`` is a reference to the stamp-filename constant."""
    if isinstance(node, ast.Name):
        return node.id == "REGISTRY_IDENTITY_STAMP_FILENAME"
    if isinstance(node, ast.Attribute):
        return node.attr == "REGISTRY_IDENTITY_STAMP_FILENAME"
    return False


def test_the_two_digest_derivations_are_distinct_and_neither_is_reimplemented() -> None:
    """The walked and installed derivations disagree, and each has one definition.

    They must disagree because they answer different questions over the same
    input: one folds mtimes and absolute paths, the other deliberately does not.
    If they ever coincided, an installed tree and an authoring tree would share
    a cache entry despite one of them being mutable.
    """
    fingerprints = (("a.toml", 11, 22, "digest-a"),)

    walked = compute_walked_tree_digest(fingerprints)
    installed = compute_installed_tree_digest(
        fingerprints,
        registry_root=Path("nonexistent-root"),
        package_version="1.0.0",
    )

    assert walked != installed
    assert walked and installed

    definitions = {
        path.name
        for path, tree in _module_asts()
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and node.name in {"compute_walked_tree_digest", "compute_installed_tree_digest"}
    }
    assert definitions == {_IDENTITY_MODULE_NAME}, (
        f"each tree-digest derivation must be defined only in {_IDENTITY_MODULE_NAME}; also defined in "
        f"{sorted(definitions - {_IDENTITY_MODULE_NAME})}"
    )


def test_the_walked_digest_moves_with_every_fingerprint_field() -> None:
    """Identity is complete-tree sensitive, which is what the authority-flow rule requires.

    Held here rather than in the verdict tests because the verdict now consumes
    an opaque digest and can no longer see the fields.
    """
    base = (("a.toml", 1, 2, "digest-a"),)
    key = compute_walked_tree_digest(base)

    assert key != compute_walked_tree_digest((("b.toml", 1, 2, "digest-a"),))
    assert key != compute_walked_tree_digest((("a.toml", 9, 2, "digest-a"),))
    assert key != compute_walked_tree_digest((("a.toml", 1, 9, "digest-a"),))
    # A same-size, same-mtime content rewrite re-keys on the digest slot alone.
    assert key != compute_walked_tree_digest((("a.toml", 1, 2, "digest-b"),))
    # Field boundaries are separated, so concatenation cannot forge a match.
    assert compute_walked_tree_digest((("a", 1, 2, "bc"),)) != compute_walked_tree_digest((("a", 1, 2, "b"), ("c",)))


def test_the_stamp_location_is_a_sibling_and_never_inside_the_tree(tmp_path: Path) -> None:
    """The placement rule, asserted rather than trusted to a docstring.

    A stamp inside the root would be walked by the fingerprint it describes, so
    writing it would change the tree's identity and no stamp could ever match.
    """
    root = tmp_path / "registry" / "aeat"
    root.mkdir(parents=True)

    location = registry_identity_stamp_location(root)

    assert location.parent == root.parent
    assert not location.is_relative_to(root)
