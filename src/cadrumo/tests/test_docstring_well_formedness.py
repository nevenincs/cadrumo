"""A docstring that misdescribes its own contract, where no gate was looking.

The nitpicky ``-n -W`` Sphinx build proves every cross-reference
RESOLVES. It says nothing about whether a docstring is WELL-FORMED, and
the difference is not cosmetic: a duplicated ``Returns:`` and an
``Args:`` entry naming a parameter the signature does not have both
build clean, and both were shipped and found by a human reading a diff.

That matters here more than it would elsewhere. This project
deliberately carries its reasoning in docstrings — why a cast is safe,
why a guard is narrow, which core struct a module hangs off — so the one
surface treated as authoritative had no structural check at all.

Two checks, chosen because they are decidable from the source alone:

* **A repeated section.** Napoleon renders the second one badly and the
  two disagree in practice: the live instance said the function returned
  a tuple in one block and a single diagnostic in the other.
* **An ``Args:`` entry naming a parameter that does not exist.** This is
  the one closest to correctness rather than style — the docstring is
  describing a contract the function does not have. The live instance
  documented an ``extra_events`` argument, in prose describing a
  different function's relabel, that no caller could ever pass.

**What this does NOT catch, stated plainly so the gate is not read as
covering more than it does.** Of eight prose-asserting-a-property-the-
code-lacks defects found in one session, these checks would have caught
two. The other six were semantic — prose describing behaviour that never
existed anywhere, a comment claiming a regex handled a case it did not.
No structural check reaches those; they need a reader. A ``Raises:``
naming an exception the body does not raise is deliberately absent too,
because a raise legitimately comes from a callee, so the obvious
implementation would fail on correct code.

A hard cut with no stored baseline, which the tree affords: the whole
production surface carried three violations, all fixed alongside this. A
ratchet over an unknown backlog is how a gate gets disabled; a backlog
this size is how one gets enforced.

The third was found late, and by accident. The parameter check shipped
reading a block's indent as the MINIMUM over its section, so a docstring
that resumed prose at the margin after ``Args:`` reported no documented
parameters at all — a clean-looking nothing, over a real ghost entry.
Nothing surfaced it; a leftover mention in an unrelated file did not add
up, and chasing that turned it over. The lesson sits in this gate's own
subject: a detector whose reach is narrower than its stated contract
reads exactly like an invariant that holds, which is why both directions
below are proved rather than assumed.
"""

from __future__ import annotations

import ast
import re
from collections import Counter
from typing import TYPE_CHECKING

import pytest
from sphinx.ext.napoleon.docstring import GoogleDocstring

from .inventory import production_ast_items, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

if TYPE_CHECKING:
    from collections.abc import Iterable


def _napoleon_section_names() -> frozenset[str]:
    """Every section header Napoleon recognises, read from Napoleon.

    Asked of the library rather than hand-listed, so a section this gate
    does not know about cannot quietly become one it ignores. The names
    are built per instance, so an empty docstring is parsed purely to
    obtain them.
    """
    return frozenset(GoogleDocstring("")._sections)


SECTION_NAMES = _napoleon_section_names()

_HEADER: re.Pattern[str] = re.compile(r"^(?P<indent>[ \t]*)(?P<name>[A-Za-z][A-Za-z ]*):[ \t]*$")
_ENTRY = re.compile(r"^(?P<indent>[ \t]+)(?P<name>\*{0,2}[A-Za-z_][A-Za-z0-9_]*)[ \t]*(?:\([^)]*\))?[ \t]*:")

#: Sections whose entries name function parameters.
_ARG_SECTIONS = ("Args", "Arguments", "Parameters")


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip())


def _section_headers(doc: str) -> list[tuple[int, int, str]]:
    """Return ``(line index, indent, canonical name)`` for each recognised header."""
    headers = []
    for index, line in enumerate(doc.splitlines()):
        match = _HEADER.match(line)
        if match is None:
            continue
        name = match.group("name")
        if not isinstance(name, str):
            raise AssertionError("section header regex returned a non-string name")
        canonical_name = name.strip()
        if canonical_name.casefold() in SECTION_NAMES:
            headers.append((index, _indent_of(line), canonical_name))
    return headers


def _section_body(doc: str, wanted: str) -> list[str]:
    """Return the lines belonging to ``wanted``'s section.

    A section ends at the next header OR at the first line that dedents
    back to the header's own level, whichever comes first. The second
    clause is what makes this correct rather than merely plausible: a
    docstring may resume ordinary prose after its ``Args:`` block without
    opening a new section, and treating that prose as part of the block
    silently destroys the reading of everything above it.
    """
    lines = doc.splitlines()
    headers = _section_headers(doc)
    for position, (index, indent, name) in enumerate(headers):
        if name != wanted:
            continue
        end = headers[position + 1][0] if position + 1 < len(headers) else len(lines)
        body = []
        for line in lines[index + 1 : end]:
            if line.strip() and _indent_of(line) <= indent:
                break
            body.append(line)
        return body
    return []


def documented_parameters(doc: str) -> list[str]:
    """Names declared in a docstring's argument section.

    An entry sits at the indent the block opens with, and a wrapped
    continuation line is indented deeper. Both halves of that were learned
    by being wrong on this tree:

    Taking any indented ``name:`` line as an entry reported fifteen
    missing parameters, fourteen of which were wrapped prose containing a
    colon ("... is handed to: the write door") — a detector that spends
    its credibility on noise before it finds anything.

    Taking the block's indent as the MINIMUM over the section then hid a
    real defect, which is the worse failure and the reason this reads from
    the first entry instead. A docstring that resumes prose at the margin
    after its ``Args:`` block dragged that minimum to zero, so every entry
    sat above it and the function reported no documented parameters at
    all — reporting nothing, while looking exactly like a clean result.
    """
    for header in _ARG_SECTIONS:
        body = [line for line in _section_body(doc, header) if line.strip()]
        if not body:
            continue
        base = _indent_of(body[0])
        return [
            match.group("name").lstrip("*")
            for line in body
            if _indent_of(line) == base and (match := _ENTRY.match(line))
        ]
    return []


def repeated_sections(doc: str) -> list[str]:
    """Return every section name appearing more than once in one docstring."""
    counts = Counter(name for _, _, name in _section_headers(doc))
    return sorted(name for name, total in counts.items() if total > 1)


def signature_parameters(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """Every name the function can actually be passed, less the bound receiver."""
    args = node.args
    names = {parameter.arg for parameter in (*args.posonlyargs, *args.args, *args.kwonlyargs)}
    if args.vararg:
        names.add(args.vararg.arg)
    if args.kwarg:
        names.add(args.kwarg.arg)
    return names - {"self", "cls"}


def _documented_nodes(tree: ast.AST) -> Iterable[tuple[ast.AST, str]]:
    """Yield every node carrying a docstring, paired with it."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            continue
        doc = ast.get_docstring(node)
        if doc:
            yield node, doc


def _describe(path_label: str, node: ast.AST) -> str:
    return f"{path_label}:{getattr(node, 'lineno', 1)} {getattr(node, 'name', '<module>')}"


def test_no_docstring_repeats_a_section() -> None:
    """A section written twice renders badly and says two things.

    The instance that prompted this gate declared ``Returns:`` twice,
    once describing a tuple and once a single diagnostic. A reader
    consulting the contract found whichever they read first.
    """
    offenders = [
        f"{_describe(repo_relative(path), node)} -> {names}"
        for path, tree in production_ast_items()
        for node, doc in _documented_nodes(tree)
        if (names := repeated_sections(doc))
    ]
    assert not offenders, "these docstrings declare the same section more than once: " + "; ".join(offenders)


def test_no_docstring_documents_a_parameter_that_does_not_exist() -> None:
    """An argument entry naming nothing in the signature misstates the contract.

    Not a formatting complaint: a caller reading it would pass an
    argument the function rejects, and a reviewer would believe a
    behaviour nothing implements. The instance that prompted this
    documented an ``extra_events`` parameter, in prose lifted from a
    different function, that no caller could pass.
    """
    offenders = []
    for path, tree in production_ast_items():
        for node, doc in _documented_nodes(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            real = signature_parameters(node)
            ghosts = sorted(set(documented_parameters(doc)) - real)
            if ghosts:
                offenders.append(
                    f"{_describe(repo_relative(path), node)} -> documents {ghosts}, accepts {sorted(real)}"
                )
    assert not offenders, (
        "these docstrings document parameters the signature does not have; "
        "remove the entry or restore the parameter: " + "; ".join(offenders)
    )


# ── proof that each check bites, and that neither bites at random ────────


_REPEATED = '''"""Do a thing.

    Returns:
        A tuple.

    Returns:
        A diagnostic.
    """'''

_WELL_FORMED = '''"""Do a thing.

    Args:
        value: The input.

    Returns:
        A tuple.
    """'''

_GHOST_ARG = '''"""Do a thing.

    Args:
        value: The input.
        extra_events: A parameter this function does not take.
    """'''

_WRAPPED_PROSE = '''"""Do a thing.

    Args:
        value: The input, which the caller is expected to have already
            handed to: the write door, before this runs.
    """'''

_PROSE_RESUMES_AFTER_ARGS = '''"""Do a thing.

    Args:
        value: The input.
        extra_events: A parameter this function does not take.

    This paragraph resumes at the margin without opening a section, which
    is ordinary in this codebase and must not blind the reader above it.
    """'''


def _docstring_of(source: str) -> str:
    """Parse a constructed function and hand back its docstring."""
    tree = ast.parse(f"def f(value):\n    {source}\n")
    function = tree.body[0]
    assert isinstance(function, ast.FunctionDef)
    doc = ast.get_docstring(function)
    assert doc is not None
    return doc


def test_the_repeated_section_check_catches_a_doubled_block() -> None:
    """Driven with a constructed docstring, so the tree is never made wrong."""
    assert repeated_sections(_docstring_of(_REPEATED)) == ["Returns"]


def test_the_repeated_section_check_clears_a_well_formed_docstring() -> None:
    """The negative half: a check that flagged either way would prove nothing."""
    assert not repeated_sections(_docstring_of(_WELL_FORMED))


def test_the_parameter_check_catches_an_entry_with_no_parameter() -> None:
    """The ghost-argument direction, against a signature taking only ``value``."""
    documented = documented_parameters(_docstring_of(_GHOST_ARG))
    assert sorted(set(documented) - {"value"}) == ["extra_events"]


def test_the_parameter_check_reads_wrapped_prose_as_prose() -> None:
    """The precision half, and the reason the indent constraint exists.

    A continuation line mentioning a colon is not an entry. Without this
    the check reports a ghost for ordinary wrapped prose, and a gate that
    cries wolf on correct code is one somebody switches off.
    """
    assert documented_parameters(_docstring_of(_WRAPPED_PROSE)) == ["value"]


def test_prose_resuming_after_the_args_block_does_not_hide_its_entries() -> None:
    """The recall case, and the one this gate shipped broken.

    A docstring that returns to the margin after ``Args:`` was reading as
    a block with no entries at all, because the block's indent was taken
    as the minimum over everything up to the next header and the trailing
    prose dragged it to zero. The gate then reported nothing for that
    function — indistinguishable from a clean one, and it silently passed
    over a real ghost parameter until a discrepancy in an unrelated check
    exposed it.

    The direction is what makes this worth a dedicated proof: a detector
    that over-reports gets argued with, while one that under-reports is
    simply believed.
    """
    documented = documented_parameters(_docstring_of(_PROSE_RESUMES_AFTER_ARGS))
    assert documented == ["value", "extra_events"], (
        f"entries must survive prose that dedents after the block, but read {documented}"
    )


def test_the_section_vocabulary_really_came_from_napoleon() -> None:
    """A vocabulary that silently emptied would make both checks vacuous.

    Napoleon builds its section table per instance, so this reads a
    private attribute; if that ever stops existing the set would fall to
    empty and every docstring above would pass for want of a header the
    gate recognises.
    """
    assert {"args", "returns", "raises", "attributes"} <= SECTION_NAMES, (
        f"the Napoleon section vocabulary looks wrong: {sorted(SECTION_NAMES)}"
    )
