"""A catalogue composed into a co-commit carries the revision it was read at.

Every one of these catalogues is a SINGLETON row: persisting one entry rewrites
all of them. A write derived from a plain ``load()`` therefore puts the whole
row back and discards whatever another caller committed in between. Nothing
downstream notices -- the surviving entries are each internally valid and the
missing one leaves no hole -- and the cost scales with the catalogue: an audit
entry for events, a tax computation for calculation revisions, a filing record
for the filing catalogue.

A caller composing into a batch cannot use the self-committing ``mutate()``:
the entry has to land in the SAME transaction as the record it describes, or a
failure leaves an advanced pointer over state that never committed. So the
guard it needs is the other one -- read with ``load_revisioned()`` and carry
that revision as ``expected_revision_id`` -- and this gate is what keeps a new
batch from silently omitting it.

WHY A SECOND GATE. The sibling in ``domain/buckets`` gates the bucket event
history alone. This class was never confined to events: the calculate path, the
external-import path, work-unit creation and the prorrata settlement all
composed unguarded reads into batches, and one of them could not even express
the guard, because the shared persistence primitive took no
``expected_revision_id`` at all.

SCOPE, deliberately narrow, so its green is not over-read. It follows a
catalogue only from a ``load()`` inside the SAME function. A catalogue that
arrives as a PARAMETER carries no revision the callee could assert, and those
sites stay unguarded and unreported here; closing them means threading the
revision from whoever performed the read.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from .....tests import non_test_package_python_files, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

#: The composing writes. Both put a whole singleton document back, so both need
#: the revision when what they write was derived from a read.
_COMPOSING_WRITES = frozenset({"to_secure_object_write", "save_with_secure_object_writes"})

#: The module DEFINING the shared event composer, which keeps a deliberate
#: fallback for the narrow domain port: that protocol promises only
#: exists/load/save, so an injected alternative may offer no revisioned read.
#: Excluding the definition rather than the shape keeps a second module adopting
#: it reportable.
_DEFINES_THE_GUARDED_COMPOSER = "src/cadrumo/domain/buckets/event_repository.py"


def _is_plain_load(node: ast.AST) -> bool:
    """Whether ``node`` is a ``<something>.load()`` call, not ``load_revisioned()``."""
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "load"


def _names_bound_to_a_plain_load(scope: ast.AST) -> set[str]:
    """Names assigned from a plain ``load()`` anywhere in ``scope``.

    A later rebinding does not clear the name: ``revisions =
    upsert_calculation_revision(revisions, revision)`` still describes a
    document derived from that read, and it is the shape these paths actually
    use.
    """
    names: set[str] = set()
    for node in ast.walk(scope):
        # Every binding form, not just the bare one. An annotated assignment
        # (``catalogue: WorkUnitCatalogue = repo.load()``) is the shape two live
        # defects used, and matching only ast.Assign made this scan report them
        # as clean -- the same shape-not-property mistake this gate exists to
        # stop being repeated.
        if isinstance(node, ast.Assign) and _is_plain_load(node.value):
            targets: tuple[ast.expr, ...] = tuple(node.targets)
        elif isinstance(node, ast.AnnAssign | ast.NamedExpr) and node.value is not None and _is_plain_load(node.value):
            targets = (node.target,)
        else:
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                names.add(target.id)
            elif isinstance(target, ast.Tuple):
                names.update(element.id for element in target.elts if isinstance(element, ast.Name))
    return names


def unguarded_compositions(tree: ast.AST) -> int:
    """Count composing writes over a document derived from an unrevisioned read."""
    found = 0
    for scope in ast.walk(tree):
        if not isinstance(scope, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        tainted = _names_bound_to_a_plain_load(scope)
        for node in ast.walk(scope):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                continue
            if node.func.attr not in _COMPOSING_WRITES or not node.args:
                continue
            if any(keyword.arg == "expected_revision_id" for keyword in node.keywords):
                continue
            written = node.args[0]
            # The written document is usually a call WRAPPING the read name
            # (upsert_x(catalogue, entry)), so the whole expression is searched
            # rather than only its root.
            if any(
                _is_plain_load(inner) or (isinstance(inner, ast.Name) and inner.id in tainted)
                for inner in ast.walk(written)
            ):
                found += 1
    return found


def test_no_production_batch_composes_an_unrevisioned_document() -> None:
    """The write that silently drops a concurrent entry."""
    offenders: list[str] = []
    for path in non_test_package_python_files():
        if repo_relative(path) == _DEFINES_THE_GUARDED_COMPOSER:
            continue
        try:
            tree = ast.parse(Path(path).read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):  # pragma: no cover - unparsable file is its own failure
            continue
        if unguarded_compositions(tree):
            offenders.append(repo_relative(path))

    assert not offenders, (
        f"these modules compose a co-commit from an unrevisioned read: {sorted(offenders)}. Each "
        "catalogue is a singleton row, so the batch writes it whole and discards any entry another "
        "caller committed in between, leaving no gap to notice. Read with load_revisioned() and pass "
        "that revision as expected_revision_id."
    )


def test_the_detector_recognises_a_wrapped_read() -> None:
    """ANTI-TAUTOLOGY, on the shape these paths actually use.

    The written document is a call wrapping the loaded catalogue, not the
    catalogue itself. An earlier version of this scan looked only at the root of
    the argument and reported two of the four live defects.
    """
    source = (
        "def persist(repository, entry):\n"
        "    catalogue = repository.load()\n"
        "    repository.save_with_secure_object_writes(upsert(catalogue, entry), ())\n"
    )

    assert unguarded_compositions(ast.parse(source)) == 1


def test_the_detector_recognises_an_annotated_binding() -> None:
    """DISCRIMINATING: the binding form that hid two live defects.

    ``catalogue: WorkUnitCatalogue = repo.load()`` is an ``AnnAssign``, not an
    ``Assign``. Tracking only the latter reported ``rename_work_unit`` and
    ``discard_work_unit`` as clean while both rewrote the whole catalogue over a
    concurrent writer.
    """
    source = (
        "def persist(repository, entry):\n"
        "    catalogue: Catalogue = repository.load()\n"
        "    repository.save_with_secure_object_writes(upsert(catalogue, entry), ())\n"
    )

    assert unguarded_compositions(ast.parse(source)) == 1


def test_a_carried_revision_is_not_flagged() -> None:
    """DISCRIMINATING: the fix must actually clear the gate."""
    source = (
        "def persist(repository, entry):\n"
        "    catalogue, revision = repository.load_revisioned()\n"
        "    repository.save_with_secure_object_writes(\n"
        "        upsert(catalogue, entry), (), expected_revision_id=revision\n"
        "    )\n"
    )

    assert unguarded_compositions(ast.parse(source)) == 0


def test_a_document_that_was_never_read_is_not_flagged() -> None:
    """A caller writing a freshly built document has no revision to assert.

    Flagging it would push authors towards inventing one, and an asserted
    revision that was never observed is worse than none.
    """
    source = "def persist(repository):\n    repository.save_with_secure_object_writes(Catalogue(), ())\n"

    assert unguarded_compositions(ast.parse(source)) == 0
