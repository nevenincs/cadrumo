"""No production module appends an audit event onto an unrevisioned load.

The event history is a SINGLETON row: appending one event rewrites all of them.
A caller that reads the catalogue with a plain ``load()`` and writes the result
back -- directly, or composed into another write's batch -- discards whatever
another writer committed in between. Events are content-addressed, so every
survivor stays internally consistent and the discarded one leaves no gap: the
trail reads as complete with an operator's action missing from it.

There are exactly two right answers, and this gate is the boundary between
them. A standalone emission goes through ``emit_bucket_event`` /
``emit_bucket_events``, which append under the repository's revision guard. An
emission that must be ATOMIC with the record it describes cannot use those --
they commit on their own -- so it reads with ``load_revisioned()`` and carries
that revision as ``expected_revision_id`` on its write, re-composing if the
substrate refuses. Either way the read is revisioned; only a bare ``load()``
into an append is always wrong.

WHY THE PROPERTY MOVED. The first version of this gate matched
``save(append_bucket_event(...))`` syntactically and passed green over three
live defects -- two in ``_iva_wallet_seed.py`` and one in ``_reconcile.py`` --
because they bound the appended catalogue to a variable first, so the argument
to ``save`` was a Name rather than a Call. That is the same failure the
line-oriented grep had before it: matching a shape instead of the property.
This version tracks what a name was assigned from, and gates the read rather
than the write.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ....tests import non_test_package_python_files, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _is_plain_load_call(node: ast.AST) -> bool:
    """Whether ``node`` is a ``<something>.load()`` call.

    ``load_revisioned()`` is deliberately NOT matched: it is the revisioned read
    this gate exists to require.
    """
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "load"


def _directly_bound_load_names(scope: ast.AST) -> set[str]:
    """Names bound to a plain ``load()`` result in ``scope``'s own body.

    Nested function bodies are excluded here and inherited explicitly by the
    walk below, so a name is judged in the scope that binds it.
    """
    names: set[str] = set()

    def _descend(node: ast.AST) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                # Not `ast.walk`: it keeps yielding a nested function's
                # descendants after the node itself is skipped, so one
                # function's plain load() would taint that name across every
                # sibling function in the module -- flagging revisioned reads
                # that merely reuse the name.
                continue
            if isinstance(child, ast.Assign) and _is_plain_load_call(child.value):
                for target in child.targets:
                    if isinstance(target, ast.Name):
                        names.add(target.id)
            _descend(child)

    _descend(scope)
    return names


def _count_in_scope(scope: ast.AST, inherited: frozenset[str]) -> int:
    """Count offending appends in ``scope``, descending into nested scopes once.

    A closure can read a catalogue its enclosing scope loaded, so the taint set
    is inherited inward rather than reset per function.
    """
    tainted = inherited | _directly_bound_load_names(scope)
    found = 0
    nested: list[ast.AST] = []

    def _visit(node: ast.AST) -> None:
        nonlocal found
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                nested.append(child)
                continue
            if (
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Name)
                and child.func.id == "append_bucket_event"
                and child.args
            ):
                source = child.args[0]
                if _is_plain_load_call(source) or (isinstance(source, ast.Name) and source.id in tainted):
                    found += 1
            _visit(child)

    _visit(scope)
    for child_scope in nested:
        found += _count_in_scope(child_scope, frozenset(tainted))
    return found


def unrevisioned_appends(tree: ast.AST) -> int:
    """Count ``append_bucket_event`` calls reading from an unrevisioned load.

    A pure function over a parsed tree so the discrimination cases below can
    hand it synthetic source and prove each shape counts or does not.
    """
    return _count_in_scope(tree, frozenset())


#: The module that DEFINES the guarded composer, as opposed to using it. It
#: carries the deliberate narrow-protocol fallback: the domain port promises
#: only exists/load/save, so an injected alternative may offer no revisioned
#: read, and that branch composes from a plain load() by necessity. Excluding
#: the definition rather than every module named here keeps the rule structural
#: -- a second module adopting this shape is still reported.
_DEFINES_THE_GUARDED_COMPOSER = "src/cadrumo/domain/buckets/_event_repository.py"


def test_no_production_module_appends_onto_an_unrevisioned_load() -> None:
    """The read that makes a concurrent audit entry disappear."""
    offenders: list[str] = []
    for path in non_test_package_python_files():
        if repo_relative(path) == _DEFINES_THE_GUARDED_COMPOSER:
            continue
        try:
            tree = ast.parse(Path(path).read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):  # pragma: no cover - unparsable file is its own failure
            continue
        if unrevisioned_appends(tree):
            offenders.append(repo_relative(path))

    assert not offenders, (
        f"these modules append a bucket event onto a plain load(): {sorted(offenders)}. The history is "
        "a singleton row, so writing that back discards any event another writer committed in "
        "between, and content-addressed survivors leave no gap to notice. Emit through "
        "emit_bucket_event, or -- when the entry must be atomic with the record it describes -- read "
        "with load_revisioned() and carry that revision as expected_revision_id."
    )


def test_the_detector_recognises_the_inline_shape() -> None:
    """ANTI-TAUTOLOGY: the shape the first version of this gate did catch."""
    source = "def emit(repository, event):\n    repository.save(append_bucket_event(repository.load(), event))\n"

    assert unrevisioned_appends(ast.parse(source)) == 1


def test_the_detector_recognises_the_variable_bound_shape() -> None:
    """DISCRIMINATING: the shape that passed green over three live defects.

    Binding the appended catalogue to a name before saving it changes nothing
    about the loss and everything about a syntactic matcher. This is the case
    the gate existed for and did not cover.
    """
    source = (
        "def emit(repository, event):\n"
        "    catalogue = repository.load()\n"
        "    updated = append_bucket_event(catalogue, event)\n"
        "    repository.save(updated)\n"
    )

    assert unrevisioned_appends(ast.parse(source)) == 1


def test_a_revisioned_read_is_not_flagged() -> None:
    """The co-commit answer must stay available.

    An event that has to land in the same batch as its record cannot use the
    self-committing emitter. Flagging this would push authors back towards one,
    trading a rare lost audit entry for a routine torn write.
    """
    source = (
        "def persist(repository, record_repository, record, event):\n"
        "    catalogue, revision = repository.load_revisioned()\n"
        "    updated = append_bucket_event(catalogue, event)\n"
        "    record_repository.save_with_secure_object_writes(\n"
        "        record,\n"
        "        (repository.to_secure_object_write(updated, expected_revision_id=revision),),\n"
        "    )\n"
    )

    assert unrevisioned_appends(ast.parse(source)) == 0


def test_an_append_inside_a_guarded_mutation_is_not_flagged() -> None:
    """The standalone answer, as the guard itself composes it.

    ``append_guarded`` hands its callback the already-current catalogue, so the
    append reads a parameter rather than a load. A gate that flagged this would
    red on the very primitive it is protecting.
    """
    source = (
        "def emit(repository, event):\n"
        "    repository.append_guarded(lambda current: append_bucket_event(current, event))\n"
    )

    assert unrevisioned_appends(ast.parse(source)) == 0
