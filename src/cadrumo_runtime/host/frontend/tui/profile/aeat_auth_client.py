"""AEAT authentication client using registered profile and credential operations."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable, Mapping
from pathlib import Path

from pydantic import BaseModel

from cadrumo.application.auth.auth_read_contracts import (
    AUTH_READ_OPERATION_DEFINITION_ID,
    AuthReadProjection,
    AuthReadRequest,
)
from cadrumo.application.auth.credential_operations import (
    AUTH_CREDENTIAL_SAVE_OPERATION_DEFINITION_ID,
    AuthCredentialSaveRequest,
    AuthCredentialSaveResult,
)
from cadrumo.application.auth.operation_definitions import AuthConfigureOperationRequest
from cadrumo.application.auth.sync_readiness import AuthSyncReadiness
from cadrumo.application.operations.schema_identity import OperationSchemaIdentityV1
from cadrumo.application.user_profile.overview import ProfileOverview
from cadrumo.core.auth_provider import AuthProviderKind, ClaveMovilRoute
from cadrumo.core.operations import OperationTerminalCondition, profile_operation_subject
from cadrumo.entrypoints.tui.profile.auth_fields import AeatAuthFieldSaveError
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError, ProfileViewCollection
from cadrumo_client.transport.operation_controller import OperationController, await_terminal_projection

from .auth_configuration_client import configure_profile_authentication


async def run_auth_operation[ResultT: BaseModel](
    client: FrontendClient,
    definition: str,
    payload: BaseModel,
    result_type: type[ResultT],
    *,
    secret: bytearray | None = None,
) -> ResultT:
    """Settle one admitted operation, validating its exact profile and session."""
    profile_id, session_id = client.profile_id, client.session_id
    subject = profile_operation_subject(str(profile_id))
    deadline = time.monotonic() + 120
    controller = await OperationController.submit(
        client,
        definition_id=definition,
        subject_ref=subject,
        payload=payload,
        expected_session_id=session_id,
        deadline=deadline,
        secret=secret,
    )
    await controller.start()
    state = await await_terminal_projection(
        controller,
        definition_id=definition,
        subject_ref=subject,
        request_schema=OperationSchemaIdentityV1.from_model(
            schema_id=definition + ".request",
            schema_version=1,
            model_type=type(payload),
        ),
        deadline=deadline,
    )
    if state.terminal_condition is not OperationTerminalCondition.SUCCEEDED:
        raise FrontendRefusedError(state.refusal_ref or state.failure_error_code or RefusalCode.UNAVAILABLE.value)
    result = await controller.read_settled_result(state, result_type, result_version=1)
    if (
        client.session_id != session_id
        or client.profile_id != profile_id
        or getattr(result, "profile_id", profile_id) != profile_id
    ):
        raise RefusalError(RefusalCode.INVALID_FRAME)
    return result


async def read_sync_readiness(client: FrontendClient) -> AuthSyncReadiness:
    """Read persisted readiness from the same authority the sync worker uses."""
    result = await run_auth_operation(
        client,
        AUTH_READ_OPERATION_DEFINITION_ID,
        AuthReadRequest(profile_id=client.profile_id, kind="sync_readiness"),
        AuthReadProjection,
    )
    if result.kind != "sync_readiness" or result.sync_readiness is None:
        raise RefusalError(RefusalCode.INVALID_FRAME)
    return result.sync_readiness


class AeatAuthClient:
    """Bind editable profile facts and protected credentials to their originating session."""

    def __init__(
        self,
        client: FrontendClient,
        *,
        overview: Callable[[], ProfileOverview],
        persist: Callable[[str, str, int, str], ProfileViewCollection],
        pin: Callable[[], None],
    ) -> None:
        """Bind the authenticated client and its revision-aware profile doors."""
        self.client = client
        self._overview = overview
        self._persist = persist
        self._pin = pin
        self._baseline: ProfileOverview | None = None

    async def read_readiness(self) -> AuthSyncReadiness:
        """Keep live readiness checks independent of the paginated profile view."""
        self._pin()
        readiness = await read_sync_readiness(self.client)
        self._pin()
        return readiness

    async def snapshot(self) -> tuple[ProfileOverview, AuthSyncReadiness]:
        """Reread the exact profile and its authentication requirements."""
        self._pin()
        overview = await asyncio.to_thread(self._overview)
        self._pin()
        readiness = await self.read_readiness()
        self._baseline = overview
        return overview, readiness

    async def save(
        self,
        provider: AuthProviderKind,
        route: ClaveMovilRoute,
        fields: Mapping[str, str],
        certificate_path: str,
        secret: bytearray | None,
    ) -> tuple[ProfileOverview, AuthSyncReadiness]:
        """Save facts serially with fresh CAS baselines; secrets never become facts."""
        try:
            self._pin()
            current = self._baseline or await asyncio.to_thread(self._overview)
            # The editor's displayed revision is the CAS baseline. A concurrent
            # writer must produce a conflict, never an unnoticed merge.
            self._baseline = None
            revision, digest = current.record_revision, current.content_digest
            for path, value in fields.items():
                if not value.strip():
                    continue
                stored = next(
                    (field for section in current.sections for field in section.fields if field.path == path), None
                )
                if stored is not None and not stored.masked and stored.value == value:
                    continue
                try:
                    saved = await asyncio.to_thread(self._persist, path, value, revision, digest)
                    if saved.profile_id != self.client.profile_id or saved.record_revision < revision:
                        raise RefusalError(RefusalCode.INVALID_FRAME)
                    revision, digest = saved.record_revision, saved.content_digest
                except Exception as error:
                    raise AeatAuthFieldSaveError(path) from error
                self._pin()
            await asyncio.to_thread(
                configure_profile_authentication,
                self.client,
                AuthConfigureOperationRequest(
                    provider=provider,
                    clave_movil_route=route if provider is AuthProviderKind.CLAVE_MOVIL else None,
                    certificate_path=Path(certificate_path).expanduser().resolve(strict=False)
                    if certificate_path.strip()
                    else None,
                    expected_profile_revision=revision,
                    expected_profile_digest=digest,
                ),
            )
            self._pin()
            if (
                secret is not None
                and len(secret) > 0
                and provider in {AuthProviderKind.CERTIFICATE, AuthProviderKind.CLAVE_PERMANENTE}
            ):
                encoded = bytearray(json.dumps({"password": secret.decode("utf-8")}), "utf-8")
                credential_provider = "certificate" if provider is AuthProviderKind.CERTIFICATE else "clave_permanente"
                try:
                    result = await run_auth_operation(
                        self.client,
                        AUTH_CREDENTIAL_SAVE_OPERATION_DEFINITION_ID,
                        AuthCredentialSaveRequest(provider=credential_provider),
                        AuthCredentialSaveResult,
                        secret=encoded,
                    )
                    if result.provider != provider.value or not result.saved:
                        raise RefusalError(RefusalCode.INVALID_FRAME)
                finally:
                    encoded[:] = bytes(len(encoded))
            return await self.snapshot()
        finally:
            if secret is not None:
                secret[:] = bytes(len(secret))
