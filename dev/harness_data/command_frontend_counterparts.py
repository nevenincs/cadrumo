"""Declared MCP counterparts for work the tax CLI performs in its own process.

The current tax command join owns command and operation identities. These
finite declarations add routes the join cannot observe and mark person-only
file, profile and installation work. They contain no source census or proofs.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from cadrumo.application.operations.person_acts import operation_is_persons_act
from cadrumo.application.operator_surface.command_operations import CommandOperations
from cadrumo_client.contracts.installation_requests import InstallationAct

type CliPath = tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ToolRoute:
    """A tool and the operation or public query selector given to it."""

    tool: str
    selector: str | None = None


def _operation(identity: str) -> tuple[ToolRoute, ...]:
    return (ToolRoute("execute", identity),)


def _query(selector: str) -> tuple[ToolRoute, ...]:
    return (ToolRoute("authority", selector),)


IN_PROCESS_COMMAND_COUNTERPARTS: Final = MappingProxyType(
    {
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
        # The certificate parser is an in-process preview before optional fact import.
        ("config", "profile", "censo", "import"): _operation("user-profile.censo-certificate-import"),
        ("config", "provision", "browser"): _operation("browser-runtime.provision"),
        ("config", "provision", "install"): _operation("local-reader.provision"),
        ("config", "provision", "load"): _operation("local-reader.provision"),
        ("config", "provision", "probe"): _operation("local-reader.status"),
        ("config", "provision", "pull"): _operation("local-reader.provision"),
        ("config", "provision", "remove"): _operation("local-reader.provision"),
        ("config", "provision", "report"): _operation("local-reader.report"),
        ("config", "provision", "setup"): _operation("local-reader.provision"),
        ("config", "provision", "start"): _operation("local-reader.provision"),
        ("config", "provision", "status"): _operation("local-reader.status"),
        ("config", "provision", "verify"): _operation("local-reader.provision"),
        ("config", "repair", "connectivity"): _operation("diagnostics.connectivity.probe"),
        ("config", "repair", "integrity", "objects"): _operation("diagnostics.secure-objects.check"),
        ("config", "repair", "quarantine"): _operation("diagnostics.secure-objects.quarantine"),
        ("config", "repair", "reset-progress"): _operation("diagnostics.workflow-progress.reset"),
    }
)

PERSON_ACT_COMMANDS: Final = frozenset(
    {
        ("app", "modelo", "review-package", "verify"),
        ("app", "modelo", "review-package", "verify-receipt"),
        ("app", "modelo", "review-package", "verify-signature"),
        # Document-only verification works on a file outside the admitted profile.
        ("app", "modelo", "work", "report-verify"),
        ("config", "login"),
        ("config", "logout"),
        ("config", "profile", "archive", "import"),
        ("config", "profile", "archive", "inspect"),
        ("config", "profile", "create"),
        ("config", "profile", "delete"),
        ("config", "profile", "list"),
        ("config", "repair"),
        ("config", "repair", "logs"),
        ("config", "repair", "profile"),
        ("config", "reset", "resume"),
        ("config", "reset", "start"),
        ("config", "reset", "status"),
        ("config", "storage", "check"),
        ("config", "storage", "init"),
        ("config", "storage", "list"),
        ("config", "storage", "reclaim"),
        ("config", "storage", "view"),
    }
)

COMMANDS_WITH_NO_WORK_TO_SHARE: Final = frozenset({("app",), ("app", "diagnostics"), ("config",)})

_PERSON_CONNECTION_REQUESTS: Final = frozenset(act.value for act in InstallationAct) | {
    "human_sign_out",
    "profile_delete",
    "profile_delete_prepare",
    "session_lock",
}


def is_person_act(row: CommandOperations, *, secret_operations: frozenset[str]) -> bool:
    """Keep direct person-only commands and the contracts' secret acts out of MCP routes."""
    return (
        row.cli_path in PERSON_ACT_COMMANDS
        or bool(set(row.connection_requests) & _PERSON_CONNECTION_REQUESTS)
        or any(
            operation_is_persons_act(identity, ephemeral_secret_required=identity in secret_operations)
            for identity in row.operation_ids
        )
    )


def other_frontend_routes(row: CommandOperations) -> tuple[ToolRoute, ...]:
    """Return the existing in-process counterpart; refuse an undeclared empty command."""
    routes = IN_PROCESS_COMMAND_COUNTERPARTS.get(row.cli_path)
    if routes is not None:
        return routes
    if not row.operation_ids and row.cli_path not in PERSON_ACT_COMMANDS | COMMANDS_WITH_NO_WORK_TO_SHARE:
        raise ValueError(f"command has no declared operation or counterpart: {row.cli_path!r}")
    return ()
