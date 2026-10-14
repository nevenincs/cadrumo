"""Answer the runtime's request for the hosted assistant's credentials, inside the profile worker.

Only the worker holds the profile's key, so only the worker can read the
encrypted provider settings. It resolves the requested providers for the
assistant under one live session's custody and answers the verified runtime
parent on the private control pipe: one document naming each credential, then
one protected frame holding the secrets in that order. Nothing here logs,
caches or persists a secret.
"""

from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING

from pydantic import ValidationError

from ...adapters.local_runtime.runtime_frame_io import write_document, write_secret
from ...adapters.local_runtime.worker_transport import WorkerChannel
from ...adapters.persistence.storage.master_key.profile_worker_custody import ProfileWorkerCustody
from ...application.agent_host.credential_frame import wipe
from ...application.runtime.profile_worker import (
    ProfileWorkerAgentCredential,
    ProfileWorkerAgentCredentials,
    ProfileWorkerAgentCredentialsRequest,
)
from ...application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from ...core.errors.hierarchy import CadrumoError
from ...core.hashing import canonical_json_bytes, sha256_hex
from ...core.logging import get_logger
from ...core.storage_environment import storage_mode

if TYPE_CHECKING:
    from ...domain.provider_settings.catalog import ProviderCatalog

_LOGGER = get_logger(__name__)


def serve_agent_credentials(
    channel: WorkerChannel, custody: ProfileWorkerCustody, request: ProfileWorkerAgentCredentialsRequest
) -> None:
    """Resolve and write the requested providers' assistant credentials for one live session."""
    material = bytearray()
    try:
        with custody.section(request.session_id):
            credentials, unset, generation = _resolve(custody, request, material)
        write_document(
            channel,
            ProfileWorkerAgentCredentials(
                identity=custody.identity,
                request_id=request.request_id,
                generation=generation,
                credentials=credentials,
                unset=unset,
            ),
            deadline=time.monotonic() + 5,
        )
        if credentials:
            write_secret(channel, material, deadline=time.monotonic() + 5)
    finally:
        wipe(material)


def _resolve(
    custody: ProfileWorkerCustody, request: ProfileWorkerAgentCredentialsRequest, material: bytearray
) -> tuple[tuple[ProfileWorkerAgentCredential, ...], tuple[str, ...], str]:
    # Imported here, not at module load: a worker reaches readiness on every sign-in, and only an agent's
    # start asks for these credentials.
    from ...adapters.persistence.provider_settings.store import build_provider_settings_store
    from ...application.provider_settings.catalog_source import ProvidedProviderCatalogSource
    from ...application.provider_settings.resolution import (
        ProviderCredentialResolver,
        ProviderCredentialUnavailable,
        ProviderCredentialUnavailableReason,
        ResolvedProviderSignIn,
    )
    from ...domain.provider_settings.catalog import ProviderConsumer

    session_refusals = frozenset(
        {ProviderCredentialUnavailableReason.NOT_SIGNED_IN, ProviderCredentialUnavailableReason.PROFILE_LOCKED}
    )
    catalog = request_catalog(request)
    try:
        resolver = ProviderCredentialResolver(
            store=build_provider_settings_store(bucket_id=str(custody.identity.binding.profile_id)),
            catalog_source=ProvidedProviderCatalogSource(catalog),
            environment=os.environ,
            storage_mode=storage_mode().mode,
        )
    except CadrumoError as error:
        raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE) from error
    credentials: list[ProfileWorkerAgentCredential] = []
    unset: list[str] = []
    states: list[str] = []
    for provider in catalog.credential_lane_ids:
        resolved = resolver.resolve(provider, ProviderConsumer.ASSISTANT)
        if isinstance(resolved, ProviderCredentialUnavailable):
            if resolved.reason in session_refusals:
                raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
            states.append(f"{provider}:unavailable:{resolved.reason.value}")
            _LOGGER.info("agent credential unavailable provider=%s reason=%s", provider, resolved.reason.value)
            if resolved.reason is ProviderCredentialUnavailableReason.CREDENTIAL_MISSING:
                unset.append(provider)
            continue
        states.append(f"{provider}:{resolved.generation}")
        if isinstance(resolved, ResolvedProviderSignIn):
            # The provider's own sign-in serves the assistant; Cadrumo hands over no secret for it.
            continue
        secret = bytearray(resolved.secret.get_secret_value(), "utf-8")
        try:
            credentials.append(
                ProfileWorkerAgentCredential(provider=provider, base_url=resolved.base_url, secret_bytes=len(secret))
            )
            material += secret
        finally:
            wipe(secret)
    # The generation names which settings each provider resolved from; it never sees a key.
    generation = sha256_hex("\n".join(["cadrumo.agent-credentials.v1", *states]).encode())
    return tuple(credentials), tuple(unset), generation


def request_catalog(request: ProfileWorkerAgentCredentialsRequest) -> ProviderCatalog:
    """Read the request's catalog document through the catalog's own parser, refusing it as invalid otherwise."""
    from ...domain.provider_settings.catalog import parse_provider_catalog

    try:
        return parse_provider_catalog(canonical_json_bytes(request.catalog).decode("utf-8"))
    except (ValidationError, CadrumoError):
        raise AutomationCustodyError(AutomationCustodyCode.INVALID) from None
