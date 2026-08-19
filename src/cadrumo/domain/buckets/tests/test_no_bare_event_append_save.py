"""No production module writes the audit trail with a bare load-append-save.

``emit_bucket_event`` exists so every emitting domain shares one
id-build-append-save sequence, and it appends through the catalogue's revision
guard. The catalogue is a SINGLETON row, so appending one event rewrites all of
them: a caller that instead writes ``repository.save(append_bucket_event(...))``
discards whatever another process committed between its own load and save.

That loss is the worst shape an audit trail can take. Events are
content-addressed, so every survivor is internally consistent and the discarded
one leaves no gap -- the trail reads as complete while an operator's action has
vanished from it.

Two production sites carried exactly that shape: purchase-invoice evidence
attachment and the profile-activation record written at login. Both now go
through the shared emitter, and this gate is what keeps the shape from
returning, because nothing about reading the call site makes it look wrong.

SCOPE, deliberately narrow. This forbids only the bare
``save(append_bucket_event(...))`` composition, which is never right: it is
neither guarded nor atomic with anything. It does NOT forbid composing an event
into a CO-COMMIT -- ``to_secure_object_write(append_bucket_event(...))`` handed
to a repository's ``extra_writes`` -- because there the event must land in the
same transaction as the record it describes, and the self-committing emitter
cannot provide that. Those sites carry the same lost-update exposure and need a
guarded-composition seam rather than this rule; they are recorded in the
campaign audit rather than pretended to be covered here.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ....tests import non_test_package_python_files, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _bare_append_saves(tree: ast.AST) -> int:
    """Count ``<anything>.save(append_bucket_event(...))`` calls in ``tree``."""
    found = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not (isinstance(node.func, ast.Attribute) and node.func.attr == "save"):
            continue
        for argument in node.args:
            if (
                isinstance(argument, ast.Call)
                and isinstance(argument.func, ast.Name)
                and argument.func.id == "append_bucket_event"
            ):
                found += 1
    return found


def test_no_production_module_saves_a_bare_appended_event() -> None:
    """The shape that silently drops a concurrent audit entry."""
    offenders: list[str] = []
    for path in non_test_package_python_files():
        try:
            tree = ast.parse(Path(path).read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):  # pragma: no cover - unparsable file is its own failure
            continue
        if _bare_append_saves(tree):
            offenders.append(repo_relative(path))

    assert not offenders, (
        f"these modules write the bucket audit trail with a bare load-append-save: {sorted(offenders)}. "
        "The catalogue is a singleton row, so this discards any event another process committed in "
        "between, and content-addressed events leave no gap to notice it. Emit through "
        "emit_bucket_event, or -- when the event must be atomic with the record it describes -- "
        "compose it into that write's extra_writes instead."
    )


def test_the_detector_recognises_the_forbidden_shape() -> None:
    """ANTI-TAUTOLOGY: a gate that matched nothing would pass over a live defect.

    This is the exact source both fixed sites carried, so the gate is shown to
    recognise the real thing rather than only an absence.
    """
    source = "def emit(repository, event):\n    repository.save(append_bucket_event(repository.load(), event))\n"

    assert _bare_append_saves(ast.parse(source)) == 1


def test_the_detector_leaves_a_co_commit_composition_alone() -> None:
    """DISCRIMINATING: the legitimate shape must not be swept up.

    An event composed into another write's ``extra_writes`` is atomic with the
    record it describes. Flagging it would push authors towards a
    self-committing emitter and break that atomicity -- trading a rare lost
    audit entry for a routine torn write.
    """
    source = (
        "def persist(repository, event_repository, record, event):\n"
        "    repository.save_with_secure_object_writes(\n"
        "        record,\n"
        "        (event_repository.to_secure_object_write(\n"
        "            append_bucket_event(event_repository.load(), event)),),\n"
        "    )\n"
    )

    assert _bare_append_saves(ast.parse(source)) == 0
