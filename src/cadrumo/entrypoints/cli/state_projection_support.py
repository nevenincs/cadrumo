"""CLI transport access to the root-composed state-projection ports."""

from __future__ import annotations

from typing import cast

import typer

from ...application.state_projection_ports import StateProjectionReadPorts

_STATE_PROJECTION_PORTS_KEY = "state_projection_read_ports"


def state_projection_read_ports(ctx: typer.Context) -> StateProjectionReadPorts:
    """Return the required bundle composed by the executable CLI root."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    value = root_state.get(_STATE_PROJECTION_PORTS_KEY)
    if not isinstance(value, StateProjectionReadPorts):
        raise RuntimeError("state projection read ports were not composed")
    return value


__all__ = ["state_projection_read_ports"]
