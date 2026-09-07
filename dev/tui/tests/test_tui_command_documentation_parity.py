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
from typer.main import get_command

from ..._paths import UTF_8
from .._artifacts import FrameFailureKind
from ..cli import app

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_README: Path = Path(__file__).resolve().parents[1] / "README.md"

#: A documented invocation line inside the README's command block.
_INVOCATION = re.compile(r"^\s*uv run --no-sync python -m dev\.tui ([a-z][a-z-]*)", re.MULTILINE)

#: The same line, kept whole so the options after the verb stay attached to it.
_INVOCATION_LINE = re.compile(
    r"^\s*uv run --no-sync python -m dev\.tui (?P<verb>[a-z][a-z-]*)(?P<rest>[^\n]*)$",
    re.MULTILINE,
)

#: An option token as prose spells it, long or short.
_OPTION = re.compile(r"(?<![\w-])(--?[a-z][a-z-]*)")

#: Options belonging to ``uv`` rather than to this tool, on every documented line.
_FOREIGN_OPTIONS = frozenset({"--no-sync"})

#: A failure-kind bullet under the render-loop heading.
_FAILURE_BULLET = re.compile(r"^- \*\*([a-z]+)\*\*", re.MULTILINE)


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


def _readme_text() -> str:
    """The README as bytes on disk decode it."""
    return _README.read_text(encoding=UTF_8)


def _section(heading: str) -> str:
    """The README text under one ``##`` heading, up to the next one.

    Scoped rather than whole-file for the same reason the command block is:
    a name mentioned in passing elsewhere is not an entry in an inventory a
    reader can work from.
    """
    text = _readme_text()
    start = text.index(f"\n## {heading}\n")
    end = text.find("\n## ", start + 1)
    return text[start : end if end != -1 else len(text)]


def _live_options() -> dict[str, frozenset[str]]:
    """Every option token each verb accepts, from the built command tree.

    Taken from the Click command Typer builds, so the flags are the ones the
    parser will actually match -- including the ``--no-`` half of a boolean
    pair, which the decorator's source spelling hides inside one string.
    """
    built = get_command(app)
    resolved: dict[str, frozenset[str]] = {}
    for name, command in built.commands.items():  # type: ignore[attr-defined]
        tokens: set[str] = set()
        for parameter in command.params:
            tokens.update(parameter.opts)
            tokens.update(parameter.secondary_opts)
        resolved[name] = frozenset(token for token in tokens if token.startswith("-"))
    return resolved


def test_every_option_a_documented_invocation_passes_exists_on_that_verb() -> None:
    """A README example an operator can copy, paste, and be refused by.

    The command block is the one place a reader is invited to copy from
    verbatim, so an option that moved or was withdrawn turns each example
    into a usage error rather than into out-of-date prose.
    """
    live = _live_options()
    unknown: list[str] = []
    for match in _INVOCATION_LINE.finditer(_section("Commands")):
        verb = match.group("verb")
        accepted = live.get(verb, frozenset())
        for token in _OPTION.findall(match.group("rest")):
            if token not in _FOREIGN_OPTIONS and token not in accepted:
                unknown.append(f"{verb} {token}")

    assert not unknown, (
        f"the README's command block passes {sorted(unknown)}, which the named verb does not accept; "
        "an operator copying that line gets a usage error"
    )


def test_every_option_the_readme_names_in_prose_exists_somewhere_in_the_tool() -> None:
    """A flag the prose tells an operator to reach for that no verb answers to.

    ``--replace``, ``--retries`` and ``--no-skip-refused`` are described in
    prose rather than shown in the block, so the block-scoped check above
    never sees them. Package-wide rather than per-verb because the prose
    discusses a flag without always naming the verb it belongs to.
    """
    accepted = frozenset().union(*_live_options().values())
    named = {token for token in _OPTION.findall(_readme_text()) if token.startswith("--")}
    phantom = sorted(named - accepted - _FOREIGN_OPTIONS)

    assert not phantom, (
        f"the README tells an operator to pass {phantom}, which no verb accepts; "
        "the flag was renamed or withdrawn and the prose kept describing it"
    )


def test_the_readme_explains_every_way_a_frame_can_fail() -> None:
    """The render-loop section against the manifest's own vocabulary.

    The kinds were spelled four times before this: the enum, a bare string
    literal in the render loop, a prose list in the manifest field docstring,
    and these bullets. Three of those are now one typed enum, and this joins
    the surviving prose to it -- in the direction that matters to a reader,
    who meets an unexplained word in a manifest they were told to read.
    """
    documented = frozenset(_FAILURE_BULLET.findall(_section("How the render loop handles failure")))
    unexplained = sorted(frozenset(FrameFailureKind) - documented)

    assert not unexplained, (
        f"a frame can be recorded as {unexplained}, which the README's failure section never explains; "
        "a reader meeting that word in a manifest has nowhere to look it up"
    )


def test_the_readme_explains_no_failure_the_manifest_cannot_record() -> None:
    """The inverse: prose describing an outcome the tool cannot produce.

    A kind withdrawn from the enum leaves its paragraph standing, and the
    paragraph reads exactly like the ones that are still true.
    """
    documented = frozenset(_FAILURE_BULLET.findall(_section("How the render loop handles failure")))
    phantom = sorted(documented - frozenset(FrameFailureKind))

    assert not phantom, (
        f"the README explains {phantom} as ways a frame can fail, but no manifest can record them; "
        "the kind was renamed or withdrawn and its paragraph stayed"
    )
