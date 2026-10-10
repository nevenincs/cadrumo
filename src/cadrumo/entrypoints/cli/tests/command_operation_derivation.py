"""Derive the registered operations each command can submit, and render the table that records them.

The command line reaches the runtime through hand-written call sites, and no
command declaration names the operations its handler submits. This module
derives that relation from three live sources: the command graph, which names
each executable command's handler; the source of the command-line package and
of the runtime client it calls, read for the submissions each handler can
reach; and the operation registry, whose request types settle a submission
whose operation the source selects by the type of its request.

The derivation is the authority and the recorded table is its copy. Run this
module to write the table again after a command, or the operations a command
submits, change::

    python -m cadrumo.entrypoints.cli.tests.command_operation_derivation
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Final

from ....tests.inventory import SRC_CADRUMO, production_python_files
from ...operation_composition import build_production_operation_registry
from ...tests.source_tree_support import SourceTree
from ..command_specs import COMMAND_GRAPH
from ._operation_submission_flow_support import Submission, SubmissionFlow, Symbol

type CliPath = tuple[str, ...]
"""An executable command's operator path, without the executable's own name."""

SCANNED_PACKAGES: Final[tuple[str, ...]] = ("cadrumo/entrypoints/cli/", "cadrumo/adapters/local_runtime/")
"""The packages a command handler's submissions can come from: the command line and the runtime client."""

COMMAND_LINE_PACKAGE: Final[str] = "cadrumo/entrypoints/cli/"

SUBMISSION_RECORD: Final[Symbol] = ("cadrumo/application/runtime/operation_access.py", "RuntimeOperationSubmit")
"""The record whose construction is a submission."""

TABLE_PATH: Final[Path] = SRC_CADRUMO / "entrypoints" / "cli" / "command_operation_table.py"

_LINE_LENGTH: Final[int] = 120


@dataclass(frozen=True, slots=True)
class SelectedOperations:
    """The operations one command selects where the source cannot say which.

    A selection is not trusted. It is accepted only while the command still
    reaches a submission whose operation the reading cannot narrow to one, and
    only for operations inside the family that submission is selected from. A
    selection the reading no longer needs fails rather than lingering.
    """

    cli_path: CliPath
    operation_ids: frozenset[str]
    reason: str


_OVERVIEW_READ_REASON: Final[str] = (
    "the overview read helper indexes one enum-derived id family by the kind field of the request it is given, "
    "and all six reads share one request type"
)
_AUTOMATION_REASON: Final[str] = (
    "the automation runners take the definition id from a contract they look up at run time, "
    "and all seven automation operations share one request type"
)

SELECTED_OPERATIONS: Final[tuple[SelectedOperations, ...]] = (
    SelectedOperations(("app", "overview", "agenda"), frozenset({"overview.agenda"}), _OVERVIEW_READ_REASON),
    SelectedOperations(("app", "overview", "backlog"), frozenset({"overview.backlog"}), _OVERVIEW_READ_REASON),
    SelectedOperations(("app", "overview", "calendar"), frozenset({"overview.calendar"}), _OVERVIEW_READ_REASON),
    SelectedOperations(("app", "overview", "explain"), frozenset({"overview.explain"}), _OVERVIEW_READ_REASON),
    SelectedOperations(("app", "overview", "prepare"), frozenset({"overview.prepare"}), _OVERVIEW_READ_REASON),
    SelectedOperations(("app", "overview", "status"), frozenset({"overview.status"}), _OVERVIEW_READ_REASON),
    SelectedOperations(
        ("config", "profile", "automation", "approve"),
        frozenset({"user-profile.automation-inventory", "user-profile.automation-approve"}),
        _AUTOMATION_REASON,
    ),
    SelectedOperations(
        ("config", "profile", "automation", "decline"),
        frozenset({"user-profile.automation-inventory", "user-profile.automation-decline"}),
        _AUTOMATION_REASON,
    ),
    SelectedOperations(
        ("config", "profile", "automation", "inspect"),
        frozenset({"user-profile.automation-inventory"}),
        _AUTOMATION_REASON,
    ),
    SelectedOperations(
        ("config", "profile", "automation", "list"),
        frozenset({"user-profile.automation-inventory"}),
        _AUTOMATION_REASON,
    ),
)


@dataclass(frozen=True, slots=True)
class CommandOperationDerivation:
    """The derived join, and everything that keeps it from being exact.

    ``operations`` holds every executable command, with an empty set for one
    that submits nothing. ``reached_submitters`` names every symbol some
    command reaches that can submit. ``findings`` is empty when the join is
    exact: each entry names one place the reading could not settle, one
    selection that is wrong or no longer needed, or one submission no command
    accounts for.
    """

    operations: Mapping[CliPath, frozenset[str]]
    operations_without_command: frozenset[str]
    reached_submitters: frozenset[Symbol]
    findings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _Settled:
    """What one submission resolves to: its operations, or the family it selects from."""

    operation_ids: frozenset[str]
    family: frozenset[str] | None = None


def derive_command_operations(
    *,
    handlers: Mapping[CliPath, Symbol | None],
    flow: SubmissionFlow,
    operation_request_types: Mapping[str, Symbol],
    command_line_symbols: Iterable[Symbol],
    selections: Iterable[SelectedOperations],
) -> CommandOperationDerivation:
    """Derive, for each executable command, the registered operations its handler can submit.

    Args:
        handlers: Each executable command's handler, or ``None`` for a command
            declared without an implementation, which submits nothing.
        flow: The submission reading over the source tree.
        operation_request_types: Each registered operation's request class.
        command_line_symbols: The symbols every submission of which a command
            must account for. One that submits must be reached by some command.
        selections: The operations named for commands the source cannot settle.
    """
    registered = frozenset(operation_request_types)
    ids_by_type: dict[Symbol, set[str]] = {}
    for operation_id, request_type in operation_request_types.items():
        ids_by_type.setdefault(request_type, set()).add(operation_id)

    entries = tuple(handler for handler in handlers.values() if handler is not None)
    accounted = tuple(command_line_symbols)
    reading = flow.read((*entries, *accounted))
    reached_by_commands = frozenset(flow.reach(entries))
    findings: list[str] = list(reading.untyped_receivers)

    pending_selections: dict[CliPath, SelectedOperations] = {}
    for selection in selections:
        if selection.cli_path in pending_selections:
            findings.append(f"{_spelled(selection.cli_path)}: more than one selection names this command")
        pending_selections[selection.cli_path] = selection

    operations: dict[CliPath, frozenset[str]] = {}
    for cli_path in sorted(handlers):
        handler = handlers[cli_path]
        submitted: set[str] = set()
        families: list[tuple[str, frozenset[str]]] = []
        if handler is not None and not flow.defines(handler):
            findings.append(
                f"{_spelled(cli_path)}: handler {handler[0]}:{handler[1]} is not a function of the scanned packages"
            )
        for submission in () if handler is None else reading.submissions.get(handler, ()):
            settled = _settle(submission, ids_by_type)
            submitted |= settled.operation_ids
            if settled.family is not None:
                families.append((submission.site, settled.family))
            elif not settled.operation_ids:
                findings.append(f"{_spelled(cli_path)}: the submission at {submission.site} names no operation")
        selection = pending_selections.pop(cli_path, None)
        findings.extend(_selection_findings(cli_path, families, selection, registered))
        if selection is not None and families:
            submitted |= selection.operation_ids
        findings.extend(
            f"{_spelled(cli_path)}: {operation_id!r} is not a registered operation"
            for operation_id in sorted(submitted - registered)
        )
        operations[cli_path] = frozenset(submitted)

    findings.extend(
        f"{_spelled(cli_path)}: a selection names a command the graph does not declare as executable"
        for cli_path in sorted(pending_selections)
    )
    findings.extend(
        f"{symbol[0]}:{symbol[1]} submits an operation and no command reaches it"
        for symbol in accounted
        if reading.submissions.get(symbol) and symbol not in reached_by_commands
    )
    return CommandOperationDerivation(
        operations=operations,
        operations_without_command=registered.difference(*operations.values()),
        reached_submitters=frozenset(symbol for symbol in reached_by_commands if reading.submissions.get(symbol)),
        findings=tuple(sorted(set(findings))),
    )


def _settle(submission: Submission, ids_by_type: Mapping[Symbol, set[str]]) -> _Settled:
    """Resolve one submission against the registry's request types.

    An operation is only ever submitted with its own request type. Where the
    definition id reduces to constants, that fact narrows them to the ones
    whose request type the payload was built from. Where it does not, the same
    fact names the operation outright when exactly one operation takes that
    request type, and otherwise names the family the command selects from.
    """
    identity = submission.identity.settled()
    payload = submission.payload.settled()
    payload_is_known = not payload.opaque and not payload.parameters
    by_type = frozenset[str]().union(*(ids_by_type.get(cls, ()) for cls in payload.types)) if payload_is_known else None
    if not identity.opaque and not identity.parameters:
        consistent = identity.constants & by_type if by_type else frozenset[str]()
        return _Settled(operation_ids=consistent or identity.constants)
    family = by_type or identity.members
    if len(family) == 1:
        return _Settled(operation_ids=identity.constants | family)
    return _Settled(operation_ids=identity.constants, family=family)


def _selection_findings(
    cli_path: CliPath,
    families: list[tuple[str, frozenset[str]]],
    selection: SelectedOperations | None,
    registered: frozenset[str],
) -> list[str]:
    """Hold a selection to the submissions it settles: needed, sufficient, and inside their families."""
    spelled = _spelled(cli_path)
    if selection is None:
        return [
            f"{spelled}: the submission at {site} selects its operation at run time from {sorted(family)}; "
            "name the operations this command selects in SELECTED_OPERATIONS, or spell the definition id "
            "so the source says it"
            for site, family in families
        ]
    if not families:
        return [f"{spelled}: the source now settles every submission, so its selection must be removed"]
    findings = [
        f"{spelled}: the selection names {operation_id!r}, which is not a registered operation"
        for operation_id in sorted(selection.operation_ids - registered)
    ]
    if not selection.reason.strip():
        findings.append(f"{spelled}: the selection states no reason")
    findings.extend(
        f"{spelled}: the selection names none of {sorted(family)}, which the submission at {site} selects from"
        for site, family in families
        if family and not selection.operation_ids & family
    )
    if all(family for _site, family in families):
        outside = selection.operation_ids.difference(*(family for _site, family in families))
        findings.extend(
            f"{spelled}: the selection names {operation_id!r}, which no unsettled submission selects from"
            for operation_id in sorted(outside)
        )
    return findings


def _spelled(cli_path: CliPath) -> str:
    return " ".join(cli_path) if cli_path else "(root)"


def live_command_handlers() -> dict[CliPath, Symbol | None]:
    """Name the handler of every executable node of the live command graph."""
    handlers: dict[CliPath, Symbol | None] = {}
    for node in COMMAND_GRAPH.nodes():
        binding = node.spec.handler
        if binding is None:
            continue
        target = binding.target
        handlers[node.path[1:]] = None if target is None else (_module_file(target.module), target.qualname)
    return handlers


def live_operation_request_types() -> dict[str, Symbol]:
    """Name the request class of every operation in the production registry."""
    return {
        definition.definition_id: (
            _module_file(definition.request_type.__module__),
            definition.request_type.__qualname__,
        )
        for definition in build_production_operation_registry().definitions
    }


def _module_file(module: str) -> str:
    return module.replace(".", "/") + ".py"


def live_submission_flow() -> SubmissionFlow:
    """Return a fresh submission reading over the live command-line package and runtime client."""
    tree = SourceTree(SRC_CADRUMO.parent, packages=frozenset({SRC_CADRUMO.name}))
    return SubmissionFlow(tree, scanned=SCANNED_PACKAGES, submission=SUBMISSION_RECORD)


def command_line_files() -> tuple[str, ...]:
    """Name every production file of the command-line package, relative to the source tree."""
    root = SRC_CADRUMO.parent
    paths = (path.relative_to(root).as_posix() for path in production_python_files())
    return tuple(path for path in paths if path.startswith(COMMAND_LINE_PACKAGE))


@cache
def derive_live_command_operations() -> CommandOperationDerivation:
    """Derive the join from the live command graph, source tree and production registry.

    The reading and every syntax tree it parsed are dropped with this call;
    only the derived join is kept.
    """
    flow = live_submission_flow()
    return derive_command_operations(
        handlers=live_command_handlers(),
        flow=flow,
        operation_request_types=live_operation_request_types(),
        command_line_symbols=tuple(symbol for path in command_line_files() for symbol in flow.symbols(path)),
        selections=SELECTED_OPERATIONS,
    )


_TABLE_HEADER: Final[str] = '''"""The registered operations each executable command can submit.

Generated from the command graph, the source of the command handlers and the
operation registry. Do not edit it by hand. After a command, or the operations
a command submits, change, write it again with::

    python -m cadrumo.entrypoints.cli.tests.command_operation_derivation

Each row pairs one executable command with one operation its handler can
submit. The command is spelled by its operator path without the executable's
own name, so the root callback has the empty path. A command that submits
nothing has one row whose operation is ``None``: that it submits nothing is
recorded, not left out. A group's rows describe the group's own callback and
not the commands below it.

The rows are an upper bound on one handler's reachable code. A command with
several modes lists every operation any mode can submit.
"""

from __future__ import annotations

from typing import Final

'''


def render_command_operation_table(derivation: CommandOperationDerivation) -> str:
    """Render the derived join as the source of the recorded table module."""
    lines = [_TABLE_HEADER, "COMMAND_OPERATION_ROWS: Final[tuple[tuple[tuple[str, ...], str | None], ...]] = (\n"]
    for cli_path in sorted(derivation.operations):
        operation_ids = sorted(derivation.operations[cli_path])
        lines.extend(_row(cli_path, operation_id) for operation_id in operation_ids or (None,))
    lines.append(")\n")
    lines.append('"""One row for each executable command and each operation it can submit."""\n\n')
    lines.append("OPERATIONS_WITHOUT_COMMAND: Final[tuple[str, ...]] = (\n")
    lines.extend(f'    "{operation_id}",\n' for operation_id in sorted(derivation.operations_without_command))
    lines.append(")\n")
    lines.append('"""Every registered operation no command submits."""\n')
    return "".join(lines)


def _row(cli_path: CliPath, operation_id: str | None) -> str:
    """Render one row the way the formatter lays it out: on one line when it fits, exploded when it does not."""
    spelled_path = "(" + ", ".join(f'"{token}"' for token in cli_path) + ("," if len(cli_path) == 1 else "") + ")"
    spelled_operation = "None" if operation_id is None else f'"{operation_id}"'
    single = f"    ({spelled_path}, {spelled_operation}),\n"
    if len(single) - 1 <= _LINE_LENGTH:
        return single
    return f"    (\n        {spelled_path},\n        {spelled_operation},\n    ),\n"


def main() -> int:
    """Write the recorded table from the live derivation, refusing while the derivation has findings."""
    derivation = derive_live_command_operations()
    if derivation.findings:
        print("the command-operation join is not exact; the table was not written:")
        for finding in derivation.findings:
            print(f"  - {finding}")
        return 1
    rendered = render_command_operation_table(derivation)
    TABLE_PATH.write_text(rendered, encoding="utf-8", newline="\n")
    print(f"wrote {TABLE_PATH} ({len(derivation.operations)} commands)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
