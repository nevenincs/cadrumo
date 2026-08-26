"""Complete production-authored command authority for the shipped CLI."""

from __future__ import annotations

from ._app_diagnostics_command_specs import DIAGNOSTICS_COMMAND_SPECS
from ._app_ledger_command_specs import LEDGER_COMMAND_SPECS
from ._app_live_command_specs import LIVE_COMMAND_SPECS
from ._app_quickfile_command_specs import QUICKFILE_COMMAND_SPECS
from ._command_spec import CommandSpec, CommandSpecGraph
from ._config._command_specs import CONFIG_COMMAND_SPECS
from ._modelo_audit_command_specs import MODELO_AUDIT_COMMAND_SPECS, MODELO_ROOT_COMMAND_SPEC
from ._modelo_core_command_specs import MODELO_CORE_COMMAND_SPECS
from ._modelo_nonwork_command_specs import MODELO_NONWORK_COMMAND_SPECS
from ._modelo_projection_command_specs import MODELO_PROJECTION_COMMAND_SPECS
from ._modelo_readiness_command_specs import MODELO_READINESS_COMMAND_SPECS
from ._modelo_work_command_specs import MODELO_WORK_COMMAND_SPECS
from ._overview_command_specs import OVERVIEW_COMMAND_SPECS
from ._registry_command_specs import REGISTRY_COMMAND_SPECS
from ._review_command_specs import REVIEW_COMMAND_SPECS
from ._root_command_specs import ROOT_COMMAND_SPECS

COMMAND_SPECS: tuple[CommandSpec, ...] = (
    *ROOT_COMMAND_SPECS,
    *CONFIG_COMMAND_SPECS,
    *DIAGNOSTICS_COMMAND_SPECS,
    *LEDGER_COMMAND_SPECS,
    *LIVE_COMMAND_SPECS,
    MODELO_ROOT_COMMAND_SPEC,
    *MODELO_AUDIT_COMMAND_SPECS,
    *MODELO_CORE_COMMAND_SPECS,
    *MODELO_NONWORK_COMMAND_SPECS,
    *MODELO_PROJECTION_COMMAND_SPECS,
    *MODELO_READINESS_COMMAND_SPECS,
    *MODELO_WORK_COMMAND_SPECS,
    *OVERVIEW_COMMAND_SPECS,
    *QUICKFILE_COMMAND_SPECS,
    *REGISTRY_COMMAND_SPECS,
    *REVIEW_COMMAND_SPECS,
)

COMMAND_GRAPH = CommandSpecGraph(COMMAND_SPECS)

__all__ = ["COMMAND_GRAPH", "COMMAND_SPECS"]
