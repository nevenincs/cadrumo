"""Complete import-light production authority for config descendants."""

from __future__ import annotations

from .._command_spec import CommandSpec
from ._auth_command_specs import AUTH_COMMAND_SPECS
from ._check_command_specs import CONFIG_CHECK_COMMAND_SPECS
from ._collab_command_specs import CONFIG_COLLAB_COMMAND_SPECS
from ._custody_command_specs import CONFIG_CUSTODY_COMMAND_SPECS
from ._google_command_specs import GOOGLE_COMMAND_SPECS
from ._profile_command_specs import PROFILE_COMMAND_SPECS
from ._profile_inventory_specs import PROFILE_INVENTORY_COMMAND_SPECS
from ._provision_command_specs import CONFIG_PROVISION_COMMAND_SPECS
from ._repair_command_specs import CONFIG_REPAIR_COMMAND_SPECS
from ._reset_command_specs import CONFIG_RESET_COMMAND_SPECS
from ._storage_command_specs import CONFIG_STORAGE_COMMAND_SPECS

CONFIG_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    *AUTH_COMMAND_SPECS,
    *CONFIG_CHECK_COMMAND_SPECS,
    *CONFIG_COLLAB_COMMAND_SPECS,
    *CONFIG_CUSTODY_COMMAND_SPECS,
    *GOOGLE_COMMAND_SPECS,
    *PROFILE_COMMAND_SPECS,
    *PROFILE_INVENTORY_COMMAND_SPECS,
    *CONFIG_PROVISION_COMMAND_SPECS,
    *CONFIG_REPAIR_COMMAND_SPECS,
    *CONFIG_RESET_COMMAND_SPECS,
    *CONFIG_STORAGE_COMMAND_SPECS,
)

__all__ = ["CONFIG_COMMAND_SPECS"]
