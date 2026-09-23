"""Every literal ``aeat`` argv the acceptance harness builds resolves in the live CLI.

The installed journeys under ``dev/acceptance`` drive a real ``aeat`` binary by
handing it argv tuples such as ``("app", "modelo", "work", "create", ...)``. A
tuple naming a verb or option the CLI does not have is only discovered when the
journey reaches that step of an installed run, which can be an hour in. This gate
reads the same tuples statically and validates each one against the live command
tree with the shared cited-command validator, so a dead verb, a dead subcommand
or a dead option fails in seconds instead.

What counts as an argv: a tuple or list literal whose first element is a string
constant and which, after zero or more root-level options (and the values of the
value-consuming ones), reaches a string constant ``app`` or ``config``. A
harness script's own argparse list (``("--receipt", ...)``) never reaches a
command family and is not an argv.

How each argv is read: the verb path is the run of string constants from the
family token up to the first non-constant element or the first option; every
constant option anywhere in the argv is validated by name (``--x=value`` is split
to ``--x``), including an f-string whose literal head is ``--x=``; any element
that is not a string constant (a variable, a call, a starred expansion) stands in
as an opaque value so option-value accounting still lines up. Options hidden
inside a non-literal element are therefore not seen by this gate.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import pytest

from cadrumo.core.directory_scan import scan_directory
from cadrumo.entrypoints.cli.tests.live_command_validation import (
    CitedCommand,
    live_root_command,
    validate_cited_command,
    value_consuming_option_names,
)
from dev._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_ACCEPTANCE_ROOT = REPO_ROOT / "dev" / "acceptance"

#: The root command families; an argv's verb path starts at one of them.
_COMMAND_FAMILIES = frozenset({"app", "config"})

#: A short flag such as ``-y``. A negative number (``-5``) is a value, not a flag.
_SHORT_FLAG_RE = re.compile(r"^-[A-Za-z]$")

#: Stand-in for an element whose value is only known at run time.
_OPAQUE_VALUE = "{value}"

#: Vacuity floor for the argv population. The harness carried a few hundred
#: literal argvs when this gate landed; a count collapsing toward zero means the
#: extractor stopped matching the harness's shape, not that the harness is clean.
_POPULATION_FLOOR = 150


@dataclass(frozen=True)
class HarnessArgv:
    """One literal argv found in harness source, decomposed for validation."""

    location: str
    cited: CitedCommand


def _constant_text(node: ast.expr) -> str | None:
    """Return the string value of a string-constant node, or ``None``."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _token(node: ast.expr) -> str:
    """Render one argv element as the token the validator reads.

    A string constant is itself. An f-string whose literal head is ``--name=``
    is that option with an opaque inline value, so its name is still validated.
    Anything else is an opaque value.
    """
    text = _constant_text(node)
    if text is not None:
        return text
    if isinstance(node, ast.JoinedStr) and node.values:
        head = _constant_text(node.values[0])
        if head is not None and head.startswith("-") and "=" in head:
            return f"{head.split('=', 1)[0]}={_OPAQUE_VALUE}"
    return _OPAQUE_VALUE


def _family_index(elements: list[ast.expr]) -> int | None:
    """Return the index of the command-family token, or ``None`` when this is no argv.

    The elements before it may only be root-level options, each followed by
    its value when the live root declares it value-consuming.
    """
    root_value_consuming = value_consuming_option_names(live_root_command())
    index = 0
    while index < len(elements):
        text = _constant_text(elements[index])
        if text is None:
            return None
        if text in _COMMAND_FAMILIES:
            return index
        if not text.startswith("-") or text == "-":
            return None
        name = text.split("=", 1)[0]
        index += 2 if "=" not in text and name in root_value_consuming else 1
    return None


def _is_option(token: str) -> bool:
    return token.startswith("--") or _SHORT_FLAG_RE.match(token) is not None


def _cited_argv(elements: list[ast.expr], family: int, location: str) -> CitedCommand:
    """Decompose one argv literal into the validator's cited-command shape."""
    tokens = tuple(_token(element) for element in elements)
    verb_tokens: list[str] = []
    for element in elements[family:]:
        text = _constant_text(element)
        if text is None or text.startswith("-"):
            break
        verb_tokens.append(text)
    cited_options = tuple(token.split("=", 1)[0] for token in tokens if _is_option(token))
    after_verb = tokens[family + len(verb_tokens) :]
    return CitedCommand(
        raw=f"{location}: aeat {' '.join(tokens)}",
        verb_tokens=tuple(verb_tokens),
        cited_options=cited_options,
        has_positional_token=any(not token.startswith("-") for token in after_verb),
        tokens=tokens,
    )


def harness_argvs_in_source(source: str, origin: str) -> list[HarnessArgv]:
    """Return every literal ``aeat`` argv in one module's source, in line order."""
    literals = sorted(
        (node for node in ast.walk(ast.parse(source)) if isinstance(node, (ast.Tuple, ast.List)) and node.elts),
        key=lambda node: (node.lineno, node.col_offset),
    )
    found: list[HarnessArgv] = []
    for node in literals:
        family = _family_index(node.elts)
        if family is None:
            continue
        location = f"{origin}:{node.lineno}"
        found.append(HarnessArgv(location=location, cited=_cited_argv(node.elts, family, location)))
    return found


def _harness_modules() -> tuple[Path, ...]:
    """Every Python module under the acceptance harness, its tests included."""
    return scan_directory(_ACCEPTANCE_ROOT, pattern="*.py", recursive=True)


@cache
def _harness_argvs() -> tuple[HarnessArgv, ...]:
    """Every literal argv across the acceptance harness."""
    found: list[HarnessArgv] = []
    for module in _harness_modules():
        origin = module.relative_to(REPO_ROOT).as_posix()
        found.extend(harness_argvs_in_source(module.read_text(encoding="utf-8"), origin))
    return tuple(found)


def test_every_harness_argv_resolves_in_the_live_cli() -> None:
    """No acceptance journey hands the installed CLI a verb or option it lacks."""
    violations = [violation for argv in _harness_argvs() for violation in validate_cited_command(argv.cited)]
    assert not violations, (
        f"{len(violations)} acceptance-harness argv(s) do not resolve in the live CLI:\n  " + "\n  ".join(violations)
    )


def test_the_gate_checks_a_real_argv_population() -> None:
    """ANTI-VACUITY: an extractor that matched nothing would report a clean harness."""
    count = len(_harness_argvs())
    assert count >= _POPULATION_FLOOR, (
        f"only {count} literal argvs extracted from {_ACCEPTANCE_ROOT.relative_to(REPO_ROOT).as_posix()} "
        f"(floor {_POPULATION_FLOOR}); the extractor has stopped matching the harness's argv shape"
    )


_DEAD_SUBCOMMAND_SOURCE = """
def configure(cli):
    cli.run(("config", "profile", "set", "iva.redeme_enrolled", "true"))
"""

_DEAD_OPTION_SOURCE = """
def configure(cli, year):
    cli.run(("config", "profile", "edit", f"income-{year}", "--quiet", "--iva-no-such-flag"))
"""

_LIVE_SOURCE = """
def configure(cli, year):
    cli.run(("config", "profile", "edit", f"income-{year}", "--quiet", "--iva-redeme-enrolled"))
    cli.run(("--format", "json", "config", "profile", "status"))
"""

_NOT_AN_ARGV_SOURCE = """
def parse(parser, receipt):
    parser.parse_args(("--receipt", receipt))
    families = ["application", "configuration"]
"""


def _violations_in(source: str) -> list[str]:
    argvs = harness_argvs_in_source(source, "synthetic.py")
    assert argvs, "the extractor produced no argv from the synthetic source, so this control would hold vacuously"
    return [violation for argv in argvs for violation in validate_cited_command(argv.cited)]


def test_a_nonexistent_subcommand_is_flagged() -> None:
    """DETECTOR TEETH: the defect that cost an hour-long installed run is caught statically."""
    violations = _violations_in(_DEAD_SUBCOMMAND_SOURCE)

    assert len(violations) == 1, violations
    assert "`set`" in violations[0]
    assert "synthetic.py:3" in violations[0]


def test_a_nonexistent_option_is_flagged() -> None:
    """DETECTOR TEETH: a real verb with an option it does not declare is caught."""
    violations = _violations_in(_DEAD_OPTION_SOURCE)

    assert len(violations) == 1, violations
    assert "--iva-no-such-flag" in violations[0]


def test_live_argvs_pass_including_a_root_option_prefix() -> None:
    """The other direction: a detector that flagged everything would fail the harness at once."""
    argvs = harness_argvs_in_source(_LIVE_SOURCE, "synthetic.py")

    assert [" ".join(argv.cited.verb_tokens) for argv in argvs] == ["config profile edit", "config profile status"]
    assert [violation for argv in argvs for violation in validate_cited_command(argv.cited)] == []


def test_a_list_that_never_reaches_a_command_family_is_not_an_argv() -> None:
    """The verb anchor keeps harness-internal argument lists out of the population."""
    assert harness_argvs_in_source(_NOT_AN_ARGV_SOURCE, "synthetic.py") == []
