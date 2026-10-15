"""Process effects supplied to the AEAT interface by its owning host."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import typer

from cadrumo_client.contracts.contracts import RefusalCode, RefusalError

from ...application.bucket_maintenance.contracts import BucketDeletionAssessment

_SERVICES_KEY = "cadrumo.cli.invocation_services"


@dataclass(frozen=True)
class CliInvocationServices:
    """Effects the interface requests without owning processes or connections."""

    launch_tui: Callable[[], None]
    delete_profile: Callable[[BucketDeletionAssessment], str]


def bind_invocation_services(ctx: typer.Context, services: CliInvocationServices) -> None:
    """Supply one invocation's externally owned effects."""
    ctx.meta[_SERVICES_KEY] = services


def invocation_services(ctx: typer.Context) -> CliInvocationServices:
    """Require services supplied by the owner; never construct a host locally."""
    services = ctx.meta.get(_SERVICES_KEY)
    if not isinstance(services, CliInvocationServices):
        raise RefusalError(RefusalCode.INVALID_FRAME)
    return services
