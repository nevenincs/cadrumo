"""Profile-service admission supplied by the process that hosts the AEAT CLI."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

import typer

from cadrumo_client.commands.profile_authentication import ProfileAuthenticationMethod
from cadrumo_client.commands.profile_binding import bound_profile_client
from cadrumo_client.commands.secure_input import ProfileSecretSelection
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError


class ProfileConnectionActivator(Protocol):
    """Supply one authenticated profile service without exposing its lifecycle."""

    def __call__(
        self,
        ctx: typer.Context,
        *,
        target_bucket_id: str | None,
        target_profile_label: str | None,
        root_selection: ProfileSecretSelection | None,
        method: ProfileAuthenticationMethod,
        credential_reference: UUID | None,
    ) -> None:
        """Bind the requested service, or refuse before the command runs."""
        ...


def require_bound_profile_connection(
    ctx: typer.Context,
    *,
    target_bucket_id: str | None,
    target_profile_label: str | None,
    root_selection: ProfileSecretSelection | None,
    method: ProfileAuthenticationMethod,
    credential_reference: UUID | None,
) -> None:
    """Consume an injected service; the product never opens its managing host."""
    client = bound_profile_client(ctx)
    if target_bucket_id is not None and str(client.profile_id) != target_bucket_id:
        raise RefusalError(RefusalCode.INVALID_FRAME)
