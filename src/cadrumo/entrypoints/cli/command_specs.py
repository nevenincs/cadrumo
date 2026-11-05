"""Production command graph: root declarations plus demand-loaded spec families."""

from __future__ import annotations

from cadrumo_client.commands.graph import CommandSpecFamily, CommandSpecGraph
from cadrumo_client.commands.shared_contracts import DeferredTarget

from .command_targets import resolve_deferred_target
from .root_command_specs import ROOT_COMMAND_SPECS


def _family(mount_key: str, module: str, qualname: str) -> CommandSpecFamily:
    return CommandSpecFamily(mount_key, DeferredTarget(module, qualname, __package__))


COMMAND_GRAPH = CommandSpecGraph(
    ROOT_COMMAND_SPECS,
    (
        _family("config", ".config.command_specs", "CONFIG_COMMAND_SPECS"),
        _family("app", ".app_diagnostics_command_specs", "DIAGNOSTICS_COMMAND_SPECS"),
        _family("app", ".app_ledger_command_specs", "LEDGER_COMMAND_SPECS"),
        _family("app", ".app_live_command_specs", "LIVE_COMMAND_SPECS"),
        _family("app", ".modelo_audit_command_specs", "MODELO_ROOT_COMMAND_SPEC"),
        _family("app_modelo", ".modelo_audit_command_specs", "MODELO_AUDIT_COMMAND_SPECS"),
        _family("app_modelo", ".modelo_core_command_specs", "MODELO_CORE_COMMAND_SPECS"),
        _family("app_modelo", ".modelo_nonwork_command_specs", "MODELO_NONWORK_COMMAND_SPECS"),
        _family("app_modelo", ".modelo_projection_command_specs", "MODELO_PROJECTION_COMMAND_SPECS"),
        _family("app_modelo", ".modelo_readiness_command_specs", "MODELO_READINESS_COMMAND_SPECS"),
        _family("app_modelo", ".modelo_spreadsheet_command_specs", "MODELO_SPREADSHEET_COMMAND_SPECS"),
        _family("app_modelo", ".modelo_work_command_specs", "MODELO_WORK_COMMAND_SPECS"),
        _family("app", ".overview_command_specs", "OVERVIEW_COMMAND_SPECS"),
        _family("app", ".app_quickfile_command_specs", "QUICKFILE_COMMAND_SPECS"),
        _family("app", ".review_command_specs", "REVIEW_COMMAND_SPECS"),
    ),
    resolver=resolve_deferred_target,
)

__all__ = ["COMMAND_GRAPH"]
