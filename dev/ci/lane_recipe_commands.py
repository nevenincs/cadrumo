"""Resolve justfile commands and derive their exact pytest and recipe-call scopes."""

from __future__ import annotations

import re
import shlex
import shutil
from pathlib import Path
from typing import Final

from dev.first_party_source import FIRST_PARTY_ROOTS
from dev.packaging.command_execution import run_command
from dev.test_runs.lanes import lane_command_parser

from .lane_configuration import _UTF_8
from .lane_contracts import Lane
from .workflow_run_text import executed_lines

#: Top-level directories a pytest invocation can positionally name. A BARE
#: reference to one of these -- no slash, e.g. a hypothetical `pytest
#: packaging` -- would otherwise match none of `_paths_of`'s other checks and
#: silently fall back to the configured testpaths, the same silent-widening
#: shape as the `--ignore` and `{{}}`-residue defects already fixed here. No
#: current recipe exercises the bare form -- every real invocation already
#: names a subpath (`src/cadrumo`, `packaging/homebrew/tests`), which the
#: `"/" in token` check catches -- so this only closes the gap for whenever
#: one does.
_TOP_LEVEL_TEST_DIRS: Final[frozenset[str]] = frozenset(root.split("/")[0] for root in FIRST_PARTY_ROOTS)


#: A justfile recipe header: a name at column zero, optional parameters and
#: attributes, then a bare `:` -- never `:=`, which is a variable assignment.
_RECIPE_HEADER: Final = re.compile(r"^(?P<name>_?[a-z][\w-]*)\b[^:\n]*:(?![=])")


#: A `just <recipe>` call, in a workflow `run:` or in another recipe's body.
_JUST_CALL: Final = re.compile(r"\bjust\s+(?P<recipe>_?[a-z][\w-]*)")


#: A bare `{{name}}` justfile interpolation. Deliberately narrow: an expression
#: like `{{ if durations == "" { "" } else { ... } }}` does not match a bare
#: identifier and is left exactly as written, per the rule that an unresolved
#: template must stay visibly unresolved rather than being guessed at.
_JUST_VARIABLE_REF: Final = re.compile(r"\{\{\s*(?P<name>[A-Za-z_]\w*)\s*\}\}")


#: A `just --evaluate` output line: `name := "value"`, one per top-level variable.
_JUST_EVALUATE_LINE: Final = re.compile(r'^(?P<name>\S+)\s*:=\s*"(?P<value>.*)"\s*$')


def _marker_expression_of(tokens: list[str]) -> str | None:
    """Return the ``-m`` value from a pytest argv, or None when absent."""
    marker_flag = "-m"  # a pytest selector, not a credential
    for index, token in enumerate(tokens):
        if token == marker_flag and index + 1 < len(tokens):
            return tokens[index + 1]
        if token.startswith(marker_flag) and len(token) > 2:
            return token[2:]
    return None


def _paths_of(tokens: list[str]) -> tuple[str, ...]:
    """Return positional path arguments from a pytest argv."""
    paths: list[str] = []
    skip_next = False
    for index, token in enumerate(tokens):
        if skip_next:
            skip_next = False
            continue
        if token in {"-m", "-k", "-n", "--timeout", "--ignore", "--durations"}:
            skip_next = True
            continue
        if token.startswith("-"):
            continue
        if index == 0 or token in {"pytest", "uv", "run", "python", "-m"}:
            continue
        if token.endswith(".py") or "/" in token or token.split("/")[0] in _TOP_LEVEL_TEST_DIRS:
            paths.append(token.split("::")[0])
    return tuple(paths)


def _exclusions_of(tokens: list[str]) -> tuple[str, ...]:
    """Return every path a pytest argv's ``--ignore`` flags exclude.

    Pytest accepts two spellings for the same flag -- ``--ignore=PATH`` as one
    token and ``--ignore PATH`` as two -- and a lane declared with either form
    excludes the path just as much as the other. Modelling only one form is how
    a lane written the other way keeps reading as if it still reached the file.
    """
    ignore_flag = "--ignore"  # a pytest selector, not a credential
    excluded: list[str] = []
    take_next = False
    for token in tokens:
        if take_next:
            excluded.append(token.split("::")[0])
            take_next = False
            continue
        if token == ignore_flag:
            take_next = True
            continue
        if token.startswith(f"{ignore_flag}="):
            excluded.append(token[len(ignore_flag) + 1 :].split("::")[0])
    return tuple(excluded)


def _pytest_invocations(text: str, *, source: str, default_paths: tuple[str, ...]) -> list[Lane]:
    """Return one lane per pytest invocation in ``text``.

    Only invocations, never every ``-m`` in the file: git's message flag shares
    the spelling, and this repository uses it in the same files.
    """
    lanes: list[Lane] = []
    for line in executed_lines(text):
        if "pytest" not in line:
            continue
        # Drop shell continuations and interpolations that shlex cannot parse.
        cleaned = line.rstrip("\\").replace("${{", "").replace("}}", "")
        try:
            tokens = shlex.split(cleaned)
        except ValueError:
            continue
        if "pytest" not in tokens and not any(token.endswith("pytest") for token in tokens):
            continue
        paths = _paths_of(tokens) or default_paths
        lanes.append(
            Lane(
                source=source,
                paths=paths,
                marker_expression=_marker_expression_of(tokens),
                exclusions=_exclusions_of(tokens),
            )
        )
    return lanes


def _justfile_lanes(text: str, *, default_paths: tuple[str, ...]) -> list[Lane]:
    """Return the justfile's pytest lanes, each attributed to its recipe.

    Attribution is what lets a caller ask whether CI reaches a lane. A recipe
    header sits at column zero and ends in a bare ``:`` (``:=`` is a variable
    assignment); every indented line beneath it belongs to that recipe.
    """
    lanes: list[Lane] = []
    current: str | None = None
    for raw in text.splitlines():
        header = _RECIPE_HEADER.match(raw)
        if header is not None:
            name = header.group("name")
            if not isinstance(name, str):
                raise RuntimeError("recipe header did not provide a textual name")
            current = name
            continue
        # A non-indented, non-header, non-comment line ends the preceding recipe
        # body: an attribute (`[group('testing')]`) or a variable assignment.
        # Comments do not, because a `#` line between a doc attribute and its
        # header sits at column zero without interrupting anything.
        if raw[:1] not in {" ", "\t", "@"} and raw.strip() and not raw.lstrip().startswith("#"):
            current = None
        for lane in _pytest_invocations(raw, source="justfile", default_paths=default_paths):
            lanes.append(
                Lane(
                    source=lane.source,
                    paths=lane.paths,
                    marker_expression=lane.marker_expression,
                    recipe=current,
                    exclusions=lane.exclusions,
                )
            )
    return lanes


def _recipes_invoked_by(text: str, parameterless: frozenset[str] = frozenset()) -> set[str]:
    """Return every recipe name an EXECUTED ``just <recipe>`` call in ``text`` names.

    Executed, because this reads justfile recipe BODIES as well as workflow
    ``run:`` blocks, and a body is a script with prose in it. Six comment lines
    in this justfile name a real recipe inside an explanatory sentence --
    "Verify the result with `just doctor-browser`" -- and harvesting the raw
    text counted every one of them as an invocation. Five were also invoked for
    real, so they cost nothing; ``check-rag`` was reached by nothing else and
    was reported CI-invoked on the strength of a sentence mentioning it.

    The error runs the dangerous way. A recipe wrongly counted as reached makes
    the lanes it declares read as covered by CI, which is precisely the
    reassurance :func:`ci_invoked_lanes` exists to withhold; a recipe wrongly
    counted as unreached would at least say so out loud. The workflow side of
    this was already closed -- ``run:`` blocks are read out of parsed YAML, so
    step names and workflow comments never reach here -- and the justfile side
    was not.
    """
    invoked: set[str] = set()
    for line in executed_lines(text):
        invoked.update(_lane_transport_recipes(line))
        for match in _JUST_CALL.finditer(line):
            recipe = match.group("recipe")
            invoked.add(recipe)
            # `just a b` runs both when `a` takes no parameters; otherwise `b`
            # is `a`'s argument. Only a declared parameterless recipe chains.
            for token in line[match.end() :].split():
                if recipe not in parameterless or token not in parameterless:
                    break
                recipe = token
                invoked.add(recipe)
    return invoked


#: The module that runs just recipes by name on a recipe's behalf.
_LANE_TRANSPORT_MODULE: Final = "dev.test_runs"


def _lane_transport_recipes(line: str) -> set[str]:
    """Return the recipes a ``python -m dev.test_runs lanes ...`` call runs.

    The transport invokes each named lane as ``just <lane>``, so those names
    are recipe calls the ``just`` pattern cannot see. They are read with the
    transport's own parser, so an option value is never mistaken for a lane.
    """
    try:
        tokens = shlex.split(line)
    except ValueError:
        return set()
    recipes: set[str] = set()
    for index, word in enumerate(tokens[:-1]):
        if word != "-m" or tokens[index + 1] != _LANE_TRANSPORT_MODULE:
            continue
        arguments: list[str] = []
        for argument in tokens[index + 2 :]:
            if argument in {"&&", "||", ";", "|"}:
                break
            arguments.append(argument)
        try:
            parsed, _ = lane_command_parser().parse_known_args(arguments)
        except SystemExit:
            continue
        recipes.update(str(lane) for lane in parsed.lane)
    return recipes


def _parameterless_recipes(text: str) -> frozenset[str]:
    """Return the justfile recipes whose header declares no parameter."""
    names: set[str] = set()
    for raw in text.splitlines():
        header = _RECIPE_HEADER.match(raw)
        if header is not None and not raw[header.end("name") :].split(":", 1)[0].strip():
            names.add(header.group("name"))
    return frozenset(names)


def _recipe_bodies(text: str) -> dict[str, str]:
    """Return each justfile recipe's body, keyed by recipe name."""
    bodies: dict[str, list[str]] = {}
    current: str | None = None
    for raw in text.splitlines():
        header = _RECIPE_HEADER.match(raw)
        if header is not None:
            name = header.group("name")
            if not isinstance(name, str):
                raise RuntimeError("recipe header did not provide a textual name")
            current = name
            bodies.setdefault(current, [])
            continue
        if current is not None:
            if raw.strip() and raw[:1] not in {" ", "\t", "@"} and not raw.lstrip().startswith("#"):
                current = None
                continue
            bodies[current].append(raw)
    return {name: "\n".join(lines) for name, lines in bodies.items()}


def resolve_just_executable() -> str:
    """Return the absolute path to ``just`` on PATH.

    The sole canonical resolution point for this repository's tooling. Fails
    closed: a missing ``just`` raises rather than returning ``None`` or an
    empty string for a caller to silently treat as "nothing to check" --
    exactly the failure mode the module docstring's reachability rationale
    warns against, generalised to every ``just``-dependent gate and script.
    """
    executable = shutil.which("just")
    if executable is None:
        message = "just is not on PATH"
        raise RuntimeError(message)
    return executable


def _just_variables(root: Path) -> dict[str, str]:
    """Return every top-level justfile variable, resolved by ``just`` itself.

    This module parses the justfile as TEXT, so a recipe body that names a
    variable (``{{harness_exclusions}}``) reads as the literal eight characters
    ``harness_exclusions`` wrapped in braces -- not the ``--ignore=...`` string
    it expands to at run time -- unless that expansion is resolved here first.
    An unresolved template can still happen to parse as a plausible-looking
    path, which is exactly how this class of gap produces a wrong answer
    instead of a loud one. Delegating to ``just`` rather than hand-rolling
    justfile expression evaluation keeps this module honest about what it can
    and cannot parse: a construct richer than a bare variable reference (an
    ``if`` expression, a function call) is not attempted and is left visibly
    unresolved.

    Fails closed: a missing or failing ``just`` raises rather than silently
    falling back to the unresolved text, because a silent fallback is
    indistinguishable from a correct empty result.
    """
    just = resolve_just_executable()
    completed = run_command(
        [just, "--evaluate"],
        cwd=root,
    )
    variables: dict[str, str] = {}
    for line in completed.stdout.splitlines():
        match = _JUST_EVALUATE_LINE.match(line)
        if match is not None:
            variables[match.group("name")] = match.group("value")
    return variables


def _substitute_just_variables(text: str, variables: dict[str, str]) -> str:
    """Replace every bare ``{{name}}`` reference in ``text`` with its value.

    A reference naming a variable ``just --evaluate`` did not resolve -- an
    unrecognised name, or a richer expression this module does not attempt --
    is left exactly as written rather than guessed at.
    """
    return _JUST_VARIABLE_REF.sub(lambda match: variables.get(match.group("name"), match.group(0)), text)


def resolved_justfile_text(root: Path) -> str:
    """Return the justfile's text with every top-level ``{{name}}`` resolved.

    The one place any consumer should ask "what does this justfile actually
    say": resolution is real ``just`` resolution (``just --evaluate``), not a
    hand-rolled regex against raw text, so a consumer reading this text sees
    exactly what ``just`` would substitute -- never a literal ``{{name}}``
    token misread as a nonsense path. Returns the empty string when there is
    no justfile, so a caller can treat "no justfile" and "empty justfile" the
    same way without a separate existence check.
    """
    justfile = root / "justfile"
    if not justfile.exists():
        return ""
    return _substitute_just_variables(justfile.read_text(encoding=_UTF_8), _just_variables(root))


def resolved_recipe_commands(root: Path, recipe: str) -> tuple[str, ...]:
    """Return one justfile recipe's command lines, resolved and ``@``-stripped.

    This is what ``just <recipe>`` actually executes, in order. A consumer that
    instead regexed raw justfile text for a recipe's body would see the
    literal token ``{{name}}`` in place of the value it expands to, which stops
    matching the moment a recipe's paths move into a variable -- exactly the
    shape that broke when the harness recipe's member paths did.
    """
    body = _recipe_bodies(resolved_justfile_text(root)).get(recipe, "")
    # `_recipe_bodies` does not treat an unindented comment as ending a body (a
    # doc comment can sit between a header and its own body without splitting
    # it), so a trailing comment block belonging to the NEXT recipe reads as
    # part of THIS one until the next non-comment line. A real command line is
    # never a bare comment, so it is filtered here rather than by widening the
    # shared boundary rule other callers already depend on.
    return tuple(line.removeprefix("@") for line in executed_lines(body))


def _recipe_closure(command: str, bodies: dict[str, str], parameterless: frozenset[str]) -> set[str]:
    """Close over all recipe calls while retaining already reached names."""
    reached = _recipes_invoked_by(command, parameterless)
    frontier = set(reached)
    while frontier:
        nxt: set[str] = set()
        for name in frontier:
            for called in _recipes_invoked_by(bodies.get(name, ""), parameterless):
                if called not in reached:
                    reached.add(called)
                    nxt.add(called)
        frontier = nxt
    return reached
