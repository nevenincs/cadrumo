"""Import-light tuple composer for the complete app live CommandSpec family."""

from __future__ import annotations

from ._app_live_borrador_command_specs import LIVE_BORRADOR_COMMAND_SPECS
from ._app_live_deudas_command_specs import LIVE_DEUDAS_COMMAND_SPECS
from ._app_live_expedientes_command_specs import LIVE_EXPEDIENTES_COMMAND_SPECS
from ._app_live_foundation_command_specs import LIVE_FOUNDATION_COMMAND_SPECS
from ._app_live_iva_wallet_command_specs import LIVE_IVA_WALLET_COMMAND_SPECS
from ._app_live_justificante_command_specs import LIVE_JUSTIFICANTE_COMMAND_SPECS
from ._app_live_notifications_command_specs import LIVE_NOTIFICATIONS_COMMAND_SPECS
from ._app_live_portals_command_specs import LIVE_PORTALS_COMMAND_SPECS
from ._app_live_verify_command_specs import LIVE_VERIFY_COMMAND_SPECS
from .command_spec import CommandSpec

LIVE_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    *LIVE_FOUNDATION_COMMAND_SPECS,
    *LIVE_IVA_WALLET_COMMAND_SPECS,
    *LIVE_NOTIFICATIONS_COMMAND_SPECS,
    *LIVE_PORTALS_COMMAND_SPECS,
    *LIVE_DEUDAS_COMMAND_SPECS,
    *LIVE_EXPEDIENTES_COMMAND_SPECS,
    *LIVE_JUSTIFICANTE_COMMAND_SPECS,
    *LIVE_VERIFY_COMMAND_SPECS,
    *LIVE_BORRADOR_COMMAND_SPECS,
)

__all__ = ["LIVE_COMMAND_SPECS"]
