"""How the terminal interface and MCP reach the work each command does.

A command reaches the other frontends in one of three ways. It submits a
registered operation, which every frontend can submit. It sends a runtime
request or an installation act, which every frontend can send. Or it does its
work in the command-line process, and the same application function is served
to the other frontends by a registered operation, an installation act or an
``authority`` query. The first two are read from the handlers' source and
recorded in the command table. The third cannot be read from a handler that
sends nothing, so it is declared here, one row for each such command.

A command that also submits or sends has a row here when one of its modes does
its work in process: the row names what serves that mode.

The declarations are checked against the live command tree, the operation
registry, the table of installation acts and the harness's tools, in both
directions, by the test beside this module. The agent's command reference is
rendered from them.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from ....application.operator_surface.command_operations import CommandOperations
from ....application.runtime.installation_requests import InstallationAct
from .command_operation_derivation import PROFILE_ADMISSION_ACTION, CliPath

EXECUTE_TOOL: Final = "execute"
INSTALLATION_TOOL: Final = "installation"
AUTHORITY_TOOL: Final = "authority"
SESSION_TOOL: Final = "session"


@dataclass(frozen=True, slots=True)
class ToolRoute:
    """One MCP tool and what it is given to do one piece of work.

    ``selector`` is the operation an ``execute`` runs, the action an
    ``installation`` or a ``session`` call names, or the query an
    ``authority`` call names. A tool that does one thing has none.
    """

    tool: str
    selector: str | None = None


def _operation(*definition_ids: str) -> tuple[ToolRoute, ...]:
    return tuple(ToolRoute(EXECUTE_TOOL, definition_id) for definition_id in definition_ids)


def _act(*acts: InstallationAct) -> tuple[ToolRoute, ...]:
    return tuple(ToolRoute(INSTALLATION_TOOL, act.value) for act in acts)


def _query(*queries: str) -> tuple[ToolRoute, ...]:
    return tuple(ToolRoute(AUTHORITY_TOOL, query) for query in queries)


def _session(*actions: str) -> tuple[ToolRoute, ...]:
    return tuple(ToolRoute(SESSION_TOOL, action) for action in actions)


_PROVISION: Final = _operation("local-reader.provision")

IN_PROCESS_COMMAND_COUNTERPARTS: Final[Mapping[CliPath, tuple[ToolRoute, ...]]] = MappingProxyType(
    {
        # With a session open in the command-line process, the bare invocation prints the overview.
        (): _operation("overview.status"),
        ("app", "ledger", "categories"): _query("categories"),
        ("app", "live", "portals", "list"): _query("portals"),
        ("app", "live", "portals", "view"): _query("portal"),
        ("app", "modelo", "casilla"): _query("casilla"),
        ("app", "modelo", "casillas"): _query("casillas"),
        ("app", "modelo", "describe"): _query("describe"),
        ("app", "modelo", "formulas"): _query("formulas"),
        ("app", "modelo", "list"): _query("modelos"),
        ("app", "modelo", "support-matrix"): _query("support"),
        ("app", "modelo", "review-package", "verify"): _act(InstallationAct.REVIEW_PACKAGE_VERIFY),
        ("app", "modelo", "review-package", "verify-receipt"): _act(InstallationAct.REVIEW_PACKAGE_VERIFY_RECEIPT),
        ("app", "modelo", "review-package", "verify-signature"): _act(InstallationAct.REVIEW_PACKAGE_VERIFY_SIGNATURE),
        # ``--document-only`` verifies the file's own signature and submits nothing.
        ("app", "modelo", "work", "report-verify"): _act(InstallationAct.REPORT_VERIFY_DOCUMENT),
        ("config", "auth", "apoderado", "scopes", "list"): _query("apoderado_scopes"),
        ("config", "auth", "providers"): _query("auth_providers"),
        ("config", "profile", "archive", "import"): _act(
            InstallationAct.ARCHIVE_IMPORT_PREPARE, InstallationAct.ARCHIVE_IMPORT
        ),
        ("config", "profile", "archive", "inspect"): _act(InstallationAct.ARCHIVE_INSPECT),
        # The command parses the certificate itself before it submits the facts it read.
        ("config", "profile", "censo", "import"): _operation("user-profile.censo-certificate-import"),
        ("config", "profile", "list"): _act(InstallationAct.PROFILE_LIST),
        ("config", "profile", "recovery", "disable"): _operation("user-profile.recovery.revoke"),
        ("config", "profile", "recovery", "enable"): _act(InstallationAct.RECOVERY_ENROLL),
        ("config", "provision", "browser"): _operation("browser-runtime.provision"),
        ("config", "provision", "install"): _PROVISION,
        ("config", "provision", "load"): _PROVISION,
        ("config", "provision", "probe"): _operation("local-reader.status"),
        ("config", "provision", "pull"): _PROVISION,
        ("config", "provision", "remove"): _PROVISION,
        ("config", "provision", "report"): _operation("local-reader.report"),
        ("config", "provision", "setup"): _PROVISION,
        ("config", "provision", "start"): _PROVISION,
        ("config", "provision", "status"): _operation("local-reader.status"),
        ("config", "provision", "verify"): _PROVISION,
        ("config", "repair"): _act(InstallationAct.REPAIR_REPORT),
        ("config", "repair", "connectivity"): _operation("diagnostics.connectivity.probe"),
        ("config", "repair", "integrity", "objects"): _operation("diagnostics.secure-objects.check"),
        ("config", "repair", "logs"): _act(InstallationAct.REPAIR_LOGS),
        ("config", "repair", "profile"): _act(InstallationAct.REPAIR_PROFILE),
        ("config", "repair", "quarantine"): _operation("diagnostics.secure-objects.quarantine"),
        ("config", "repair", "reset-progress"): _operation("diagnostics.workflow-progress.reset"),
        ("config", "reset", "status"): _act(InstallationAct.RESET_STATUS),
        ("config", "storage", "check"): _act(InstallationAct.STORAGE_CHECK),
        ("config", "storage", "init"): _act(InstallationAct.STORAGE_INIT),
        ("config", "storage", "list"): _act(InstallationAct.STORAGE_INVENTORY),
        ("config", "storage", "reclaim"): _act(InstallationAct.STORAGE_RECLAIM),
        ("config", "storage", "view"): _act(InstallationAct.STORAGE_INVENTORY),
    }
)
"""Each command that works in the command-line process, and what serves that work to the other frontends."""

_KEY_ENROLLMENT: Final = (
    ToolRoute("authorization_prepare"),
    ToolRoute("authorization_request"),
    ToolRoute("authorization_poll"),
)

SESSION_DOOR_COMMAND_TOOLS: Final[Mapping[CliPath, tuple[ToolRoute, ...]]] = MappingProxyType(
    {
        ("config", "login"): _session("sign_in"),
        ("config", "logout"): _session("sign_out"),
        ("config", "passphrase", "reset"): _session("reset_password"),
        ("config", "profile", "automation", "change"): _KEY_ENROLLMENT,
        ("config", "profile", "automation", "create"): _KEY_ENROLLMENT,
        ("config", "profile", "automation", "deny"): _session("deny_automation"),
        ("config", "profile", "delete"): _session("delete_profile"),
        ("config", "profile", "lock"): _session("lock"),
        ("config", "profile", "resume"): _session("resume"),
        ("config", "profile", "sessions"): _session("list"),
        ("config", "sign-in-status"): _session("sign_in_status"),
    }
)
"""The tools that send, for an MCP client, the session and key requests each of these commands sends.

The command table records which requests of the runtime's own door a command
sends. An installation act is asked for by its own name. A request about a
profile's sessions or keys is asked for through the tool named here.
"""

_PRINTS_HELP: Final = "invoked bare, it prints the help of its group, which every frontend holds as text of its own"

COMMANDS_WITH_NO_WORK_TO_SHARE: Final[Mapping[CliPath, str]] = MappingProxyType(
    {
        ("app",): _PRINTS_HELP,
        ("app", "diagnostics"): _PRINTS_HELP,
        ("app", "tui"): "it starts the terminal interface itself",
        ("config",): _PRINTS_HELP,
    }
)
"""Each command that neither reaches the runtime nor does work another frontend could ask for, with the reason."""

_TYPED_READ: Final = (
    "a typed read of records the command line reads through the operation named beside it; "
    "the terminal interface and MCP submit it directly"
)
_FORM_WORKBENCH: Final = (
    "the form workbench, which the terminal interface and MCP drive one request at a time; "
    "the command line reads and edits a form through its work commands"
)
_KEY_PROPOSAL: Final = (
    "a proposal about an automation key, which the command line makes through the runtime's enrollment "
    "requests that its automation commands send"
)


@dataclass(frozen=True, slots=True)
class OperationWithoutCommand:
    """A registered operation no command submits and no command's in-process work is served by.

    ``command_line_operation`` names the operation through which the command
    line reaches the same records, where there is one. It is held to the
    registry and to the command table: a command submits it.
    """

    reason: str
    command_line_operation: str | None = None


OPERATIONS_WITHOUT_A_COMMAND: Final[Mapping[str, OperationWithoutCommand]] = MappingProxyType(
    {
        "ledger.evidence.query": OperationWithoutCommand(_TYPED_READ, "ledger.evidence.list"),
        "ledger.evidence.reader-readiness": OperationWithoutCommand(
            "the evidence screen's own readiness read; the command line reads the reader's state in process "
            "and the other frontends also through local-reader.status"
        ),
        "ledger.evidence.review.summary": OperationWithoutCommand(_TYPED_READ, "ledger.evidence.review.list"),
        "ledger.history.typed": OperationWithoutCommand(_TYPED_READ, "ledger.history"),
        "live.borrador.100.query": OperationWithoutCommand(_TYPED_READ, "live.borrador.100.read"),
        "modelo.036.query": OperationWithoutCommand(_TYPED_READ, "modelo.036.read"),
        "modelo.audit.query": OperationWithoutCommand(_TYPED_READ, "modelo.audit.read"),
        "modelo.bindings.resolve.typed": OperationWithoutCommand(_TYPED_READ, "modelo.bindings.resolve"),
        "modelo.edit.apply": OperationWithoutCommand(_FORM_WORKBENCH),
        "modelo.edit.apply_prerequisite": OperationWithoutCommand(_FORM_WORKBENCH),
        "modelo.edit.preflight": OperationWithoutCommand(_FORM_WORKBENCH),
        "modelo.edit.renew": OperationWithoutCommand(_FORM_WORKBENCH),
        "modelo.history.timeline": OperationWithoutCommand(_TYPED_READ, "modelo.history"),
        "modelo.readiness.summary": OperationWithoutCommand(_TYPED_READ, "modelo.readiness"),
        "modelo.work.casilla_help": OperationWithoutCommand(_FORM_WORKBENCH),
        "modelo.work.form": OperationWithoutCommand(_FORM_WORKBENCH),
        "profile.history.timeline": OperationWithoutCommand(_TYPED_READ, "profile.history"),
        "user-profile.automation-renew": OperationWithoutCommand(_KEY_PROPOSAL),
        "user-profile.automation-request": OperationWithoutCommand(_KEY_PROPOSAL),
        "user-profile.automation-rotate": OperationWithoutCommand(_KEY_PROPOSAL),
        "user-profile.automation-scope": OperationWithoutCommand(_KEY_PROPOSAL),
        "user-profile.bundle-export": OperationWithoutCommand(
            "exports the profile's records as one portable bundle; no command asks for that bundle"
        ),
        "workbench.generation": OperationWithoutCommand(
            "the generation the terminal interface's workbench reads to know its projections are current"
        ),
    }
)
"""Every registered operation that only the terminal interface and MCP submit, with the reason."""

INSTALLATION_ACTS_WITHOUT_A_COMMAND: Final[Mapping[InstallationAct, str]] = MappingProxyType(
    dict[InstallationAct, str]()
)
"""Every installation act no command sends and no command's in-process work is served by, with the reason."""


class CommandReach(StrEnum):
    """How one command's work reaches the terminal interface and MCP."""

    SUBMITS_OPERATION = "submits a registered operation"
    SENDS_RUNTIME_REQUEST = "sends a runtime request or an installation act"
    WORKS_IN_PROCESS = "works in process, with a declared counterpart"
    NO_WORK_TO_SHARE = "has no work to share"
    UNREACHED = "does work no other frontend can ask for"


_INSTALLATION_ACTIONS: Final = frozenset(act.value for act in InstallationAct)


def requests_beyond_admission(row: CommandOperations) -> frozenset[str]:
    """Name the runtime requests a command sends besides the one that admits it to a profile."""
    return frozenset(row.runtime_requests) - {PROFILE_ADMISSION_ACTION}


def command_reach(
    row: CommandOperations,
    *,
    in_process: Mapping[CliPath, tuple[ToolRoute, ...]] = IN_PROCESS_COMMAND_COUNTERPARTS,
    no_work: Mapping[CliPath, str] = COMMANDS_WITH_NO_WORK_TO_SHARE,
) -> CommandReach:
    """Say how one recorded command reaches the other frontends, taking the first way that applies.

    A command admitted to a profile has sent nothing about its work yet, so
    the admission request alone does not count as reaching the runtime.
    """
    if row.operation_ids:
        return CommandReach.SUBMITS_OPERATION
    if requests_beyond_admission(row):
        return CommandReach.SENDS_RUNTIME_REQUEST
    if in_process.get(row.cli_path):
        return CommandReach.WORKS_IN_PROCESS
    if row.cli_path in no_work:
        return CommandReach.NO_WORK_TO_SHARE
    return CommandReach.UNREACHED


def reach_of_every_command(rows: Iterable[CommandOperations]) -> dict[CommandReach, tuple[CliPath, ...]]:
    """Group every recorded command by how it reaches the other frontends, keeping the empty groups."""
    grouped: dict[CommandReach, list[CliPath]] = {reach: [] for reach in CommandReach}
    for row in rows:
        grouped[command_reach(row)].append(row.cli_path)
    return {reach: tuple(sorted(paths)) for reach, paths in grouped.items()}


def other_frontend_routes(row: CommandOperations) -> tuple[ToolRoute, ...]:
    """Name every tool route to a command's work besides executing the operations it submits.

    These are the installation acts it sends, the session and key tools that
    send its other runtime requests, and what serves the work it does in
    process, each once and in that order. Declared routes keep the order they
    are declared in, which is the order a client calls them in.
    """
    sent = sorted(action for action in requests_beyond_admission(row) if action in _INSTALLATION_ACTIONS)
    routes = (
        *(ToolRoute(INSTALLATION_TOOL, action) for action in sent),
        *SESSION_DOOR_COMMAND_TOOLS.get(row.cli_path, ()),
        *IN_PROCESS_COMMAND_COUNTERPARTS.get(row.cli_path, ()),
    )
    return tuple(dict.fromkeys(routes))


__all__ = [
    "AUTHORITY_TOOL",
    "COMMANDS_WITH_NO_WORK_TO_SHARE",
    "EXECUTE_TOOL",
    "INSTALLATION_ACTS_WITHOUT_A_COMMAND",
    "INSTALLATION_TOOL",
    "IN_PROCESS_COMMAND_COUNTERPARTS",
    "OPERATIONS_WITHOUT_A_COMMAND",
    "SESSION_DOOR_COMMAND_TOOLS",
    "SESSION_TOOL",
    "CommandReach",
    "OperationWithoutCommand",
    "ToolRoute",
    "command_reach",
    "other_frontend_routes",
    "reach_of_every_command",
    "requests_beyond_admission",
]
