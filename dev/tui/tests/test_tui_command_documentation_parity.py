"""The README's command inventory is joined to the live command tree.

The package README is the only inventory of what this tool can be asked to
do, and nothing read it against the tool. Two verbs drifted out of it that
way: ``runs``, which is how an operator finds the review directories on
disk, and ``snapshot``, which is the only sanctioned way to create a second
run at all -- so the README's own ``diff baseline --against latest`` example
named two runs no documented verb could have produced.

The check executes the command tree rather than reading ``cli.py`` as text:
a verb is registered by a decorator at import time, so the registration is
the fact and its source spelling is not.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from ..._paths import UTF_8
from ..cli import app

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_README: Path = Path(__file__).resolve().parents[1] / "README.md"

#: A documented invocation line inside the README's command block.
_INVOCATION = re.compile(r"^\s*uv run --no-sync python -m dev\.tui ([a-z][a-z-]*)", re.MULTILINE)


def _registered_command_names() -> frozenset[str]:
    """Every verb the live Typer application answers to.

    Reads the registration Typer itself holds, so a verb added, renamed or
    withdrawn moves this side without anybody remembering to.
    """
    return frozenset(
        command.name or command.callback.__name__ for command in app.registered_commands if command.callback is not None
    )


def _documented_command_names() -> frozenset[str]:
    """Every verb the README's ``## Commands`` block shows an invocation for.

    Scoped to that block rather than the whole file: the prose below it
    discusses verbs by name in passing, and a mention is not an entry in an
    inventory a reader can work from.
    """
    text = _README.read_text(encoding=UTF_8)
    heading = text.index("\n## Commands\n")
    end = text.find("\n## ", heading + 1)
    block = text[heading : end if end != -1 else len(text)]
    return frozenset(_INVOCATION.findall(block))


def test_the_readme_documents_every_verb_the_command_tree_answers_to() -> None:
    """A verb the tool answers to that the README never shows.

    This is the direction that failed: an operator reading the README cannot
    ask for what it does not name, and the two missing verbs were the ones
    that make the artefact tree navigable.
    """
    undocumented = sorted(_registered_command_names() - _documented_command_names())

    assert not undocumented, (
        f"the command tree answers to {undocumented}, which the README's command block never shows; "
        f"document each one there or withdraw it from {app.info.name!r}"
    )


def test_the_readme_shows_no_verb_the_command_tree_does_not_answer_to() -> None:
    """A README invocation an operator would type and get an error from.

    The inverse direction, and the one a withdrawal or rename breaks: the
    README keeps working as prose long after the verb it invokes is gone.
    """
    phantom = sorted(_documented_command_names() - _registered_command_names())

    assert not phantom, (
        f"the README shows invocations for {phantom}, which the command tree does not register; "
        "an operator typing one of these gets a usage error"
    )
