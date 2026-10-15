"""Exact-session AEAT setup through registered profile and credential operations."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable, Mapping
from pathlib import Path

from pydantic import BaseModel

from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError

from ....application.auth.auth_read_contracts import (
    AUTH_READ_OPERATION_DEFINITION_ID,
    AuthReadProjection,
    AuthReadRequest,
)
from ....application.auth.credential_operations import (
    AUTH_CREDENTIAL_SAVE_OPERATION_DEFINITION_ID,
    AuthCredentialSaveRequest,
    AuthCredentialSaveResult,
)
from ....application.auth.operation_definitions import AuthConfigureOperationRequest
from ....application.auth.sync_readiness import AuthSyncReadiness
from ....application.operations.schema_identity import OperationSchemaIdentityV1
from ....application.user_profile.overview import ProfileOverview
from ....core.auth_provider import AuthProviderKind, ClaveMovilRoute
from ....core.operations import OperationTerminalCondition, profile_operation_subject
from ..operations.runtime_controller import RuntimeOperationController, await_terminal_projection
from .runtime_auth_configuration import configure_runtime_auth


class AeatAuthFieldSaveError(Exception):
    """Identify the attempted public field without copying the rejected input."""

    def __init__(self, path: str) -> None:
        """Keep only the canonical profile path for presentation."""
        super().__init__(path)
        self.path = path


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
    controller = await RuntimeOperationController.submit(
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


async def read_runtime_sync_readiness(client: FrontendClient) -> AuthSyncReadiness:
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


class RuntimeAeatAuthSetup:
    """Bind editable profile facts and protected credentials to their originating session."""

    def __init__(
        self,
        client: FrontendClient,
        *,
        overview: Callable[[], ProfileOverview],
        persist: Callable[[str, str, int, str], ProfileOverview],
        pin: Callable[[], None],
    ) -> None:
        """Bind the authenticated client and its revision-aware profile doors."""
        self.client = client
        self._overview = overview
        self._persist = persist
        self._pin = pin

    async def snapshot(self) -> tuple[ProfileOverview, AuthSyncReadiness]:
        """Reread the exact profile and its authentication requirements."""
        self._pin()
        overview = await asyncio.to_thread(self._overview)
        self._pin()
        readiness = await read_runtime_sync_readiness(self.client)
        self._pin()
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
            for path, value in fields.items():
                if not value.strip():
                    continue
                current = await asyncio.to_thread(self._overview)
                stored = next(
                    (field for section in current.sections for field in section.fields if field.path == path), None
                )
                if stored is not None and not stored.masked and stored.value == value:
                    continue
                try:
                    await asyncio.to_thread(self._persist, path, value, current.record_revision, current.content_digest)
                except Exception as error:
                    raise AeatAuthFieldSaveError(path) from error
                self._pin()
            current = await asyncio.to_thread(self._overview)
            await asyncio.to_thread(
                configure_runtime_auth,
                self.client,
                AuthConfigureOperationRequest(
                    provider=provider,
                    clave_movil_route=route if provider is AuthProviderKind.CLAVE_MOVIL else None,
                    certificate_path=Path(certificate_path).expanduser().resolve(strict=False)
                    if certificate_path.strip()
                    else None,
                    expected_profile_revision=current.record_revision,
                    expected_profile_digest=current.content_digest,
                ),
            )
            self._pin()
            if (
                secret is not None
                and len(secret) > 0
                and provider in {AuthProviderKind.CERTIFICATE, AuthProviderKind.CLAVE_PERMANENTE}
            ):
                encoded = bytearray(json.dumps({"password": secret.decode("utf-8")}), "utf-8")
                try:
                    result = await run_auth_operation(
                        self.client,
                        AUTH_CREDENTIAL_SAVE_OPERATION_DEFINITION_ID,
                        AuthCredentialSaveRequest(provider=provider.value),
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
