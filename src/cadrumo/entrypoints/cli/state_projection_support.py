"""CLI transport access to the root-composed state-projection ports."""

from __future__ import annotations

from typing import cast

import typer

from ...application.auth.certificate_secret_backend import CertificateSecretBackendFactory
from ...application.state_projection_ports import StateProjectionReadPorts

_STATE_PROJECTION_PORTS_KEY = "state_projection_read_ports"
_CERTIFICATE_SECRET_BACKEND_FACTORY_KEY = "certificate_secret_backend_factory"


def state_projection_read_ports(ctx: typer.Context) -> StateProjectionReadPorts:
    """Return the required bundle composed by the executable CLI root."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    value = root_state.get(_STATE_PROJECTION_PORTS_KEY)
    if not isinstance(value, StateProjectionReadPorts):
        raise RuntimeError("state projection read ports were not composed")
    return value


def certificate_secret_backend_factory(ctx: typer.Context) -> CertificateSecretBackendFactory:
    """Return the certificate-secret factory supplied by the CLI composition root."""
    root_state = cast("dict[str, object]", ctx.find_root().ensure_object(dict))
    return cast(CertificateSecretBackendFactory, root_state[_CERTIFICATE_SECRET_BACKEND_FACTORY_KEY])


__all__ = ["certificate_secret_backend_factory", "state_projection_read_ports"]
