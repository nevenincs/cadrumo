"""Complete import-light production authority for config descendants."""

from __future__ import annotations

from cadrumo_client.commands.spec import CommandSpec

from .collab_command_specs import CONFIG_COLLAB_COMMAND_SPECS
from .custody_command_specs import CONFIG_CUSTODY_COMMAND_SPECS
from .google_command_specs import GOOGLE_COMMAND_SPECS
from .profile_command_specs import PROFILE_COMMAND_SPECS
from .profile_inventory_specs import PROFILE_INVENTORY_COMMAND_SPECS
from .repair_command_specs import CONFIG_REPAIR_COMMAND_SPECS
from .reset_command_specs import CONFIG_RESET_COMMAND_SPECS
from .storage_command_specs import CONFIG_STORAGE_COMMAND_SPECS

CONFIG_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    *CONFIG_COLLAB_COMMAND_SPECS,
    *CONFIG_CUSTODY_COMMAND_SPECS,
    *GOOGLE_COMMAND_SPECS,
    *PROFILE_COMMAND_SPECS,
    *PROFILE_INVENTORY_COMMAND_SPECS,
    *CONFIG_REPAIR_COMMAND_SPECS,
    *CONFIG_RESET_COMMAND_SPECS,
    *CONFIG_STORAGE_COMMAND_SPECS,
)

__all__ = ["CONFIG_COMMAND_SPECS"]
