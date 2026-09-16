"""Production command graph: root declarations plus demand-loaded spec families."""

from __future__ import annotations

from ._root_command_specs import ROOT_COMMAND_SPECS
from .command_spec import CommandSpecFamily, CommandSpecGraph, DeferredTarget


def _family(mount_key: str, module: str, qualname: str) -> CommandSpecFamily:
    return CommandSpecFamily(mount_key, DeferredTarget(module, qualname, __package__))


COMMAND_GRAPH = CommandSpecGraph(
    ROOT_COMMAND_SPECS,
    (
        _family("config", ".config.command_specs", "CONFIG_COMMAND_SPECS"),
        _family("app", "._app_diagnostics_command_specs", "DIAGNOSTICS_COMMAND_SPECS"),
        _family("app", "._app_ledger_command_specs", "LEDGER_COMMAND_SPECS"),
        _family("app", "._app_live_command_specs", "LIVE_COMMAND_SPECS"),
        _family("app", "._modelo_audit_command_specs", "MODELO_ROOT_COMMAND_SPEC"),
        _family("app_modelo", "._modelo_audit_command_specs", "MODELO_AUDIT_COMMAND_SPECS"),
        _family("app_modelo", "._modelo_core_command_specs", "MODELO_CORE_COMMAND_SPECS"),
        _family("app_modelo", "._modelo_nonwork_command_specs", "MODELO_NONWORK_COMMAND_SPECS"),
        _family("app_modelo", "._modelo_projection_command_specs", "MODELO_PROJECTION_COMMAND_SPECS"),
        _family("app_modelo", "._modelo_readiness_command_specs", "MODELO_READINESS_COMMAND_SPECS"),
        _family("app_modelo", "._modelo_spreadsheet_command_specs", "MODELO_SPREADSHEET_COMMAND_SPECS"),
        _family("app_modelo", ".modelo_work_command_specs", "MODELO_WORK_COMMAND_SPECS"),
        _family("app", "._overview_command_specs", "OVERVIEW_COMMAND_SPECS"),
        _family("app", "._app_quickfile_command_specs", "QUICKFILE_COMMAND_SPECS"),
        _family("app", "._review_command_specs", "REVIEW_COMMAND_SPECS"),
    ),
)

__all__ = ["COMMAND_GRAPH"]
