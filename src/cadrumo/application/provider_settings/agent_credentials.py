"""The signed-in profile's provider credentials, shaped for the hosted-agent controller.

This is the one bridge from provider settings to the agent host. It resolves
the assistant consumer's direct credentials through the shared resolver and
copies each secret into a fresh :class:`bytearray` the controller owns and
wipes after writing the standard-input frame. Providers the assistant reaches
through their own CLI sign-in carry no credential and are left out of the
frame, as are providers with nothing configured or turned off.

Each key is keyed in the frame by cadrumo-agent's own provider identity, the
name its hosting contract accepts. Only key-bearing lanes are carried; a
provider's own sign-in token never enters the frame.

Generations are observed without touching the session's idle time, so the
controller can poll them to decide whether a running agent is still current.
"""

from __future__ import annotations

from typing import override

from ...domain.provider_settings.catalog import ProviderAuthKind, ProviderCatalog, ProviderConsumer
from ..agent_host.controller import (
    AgentCredentialSource,
    AgentGenerations,
    AgentHostError,
    AgentHostRefusal,
    ResolvedAgentCredentials,
)
from ..agent_host.credential_frame import AgentCredential, wipe
from .ports import ProviderSettingsStore
from .resolution import (
    ProviderCredentialResolver,
    ProviderCredentialUnavailable,
    ProviderCredentialUnavailableReason,
    ResolvedDirectCredential,
)

_FRAMED_KINDS = frozenset({ProviderAuthKind.API_KEY, ProviderAuthKind.API_KEY_WITH_BASE_URL})
_SIGNED_OUT_REASONS = frozenset(
    {ProviderCredentialUnavailableReason.NOT_SIGNED_IN, ProviderCredentialUnavailableReason.PROFILE_LOCKED},
)
_SKIPPED_REASONS = frozenset(
    {
        ProviderCredentialUnavailableReason.PROVIDER_DISABLED,
        ProviderCredentialUnavailableReason.CREDENTIAL_MISSING,
        ProviderCredentialUnavailableReason.CONSUMER_NOT_SUPPORTED,
        ProviderCredentialUnavailableReason.RECORD_UNREADABLE,
    },
)


class ProviderSettingsAgentCredentialSource(AgentCredentialSource):
    """Resolve every usable assistant key for one admitted profile, keyed by cadrumo-agent's provider identity.

    A provider whose record is unset with no fallback, turned off or unreadable
    is left out of the frame; its status says why. Only a profile that is not
    signed in, or a store failure, refuses the whole resolution.
    """

    def __init__(
        self,
        *,
        store: ProviderSettingsStore,
        resolver: ProviderCredentialResolver,
        catalog: ProviderCatalog,
    ) -> None:
        """Bind the source to one profile's store and resolver."""
        self._store = store
        self._resolver = resolver
        self._agent_lanes = tuple(
            (entry.id, entry.provider)
            for entry in catalog.providers
            if entry.auth_kind in _FRAMED_KINDS and entry.serves(ProviderConsumer.ASSISTANT)
        )

    @override
    def resolve_for_agent(self) -> ResolvedAgentCredentials:
        """Return fresh credential buffers under the generations they were resolved at.

        Raises:
            AgentHostError: ``SIGNED_OUT`` when the profile is not usable,
                ``CREDENTIALS_UNAVAILABLE`` on a store failure, and
                ``STALE_GENERATION`` when a sign-in or settings change raced
                the resolution.
        """
        before = self.current_generations()
        if before is None:
            raise AgentHostError(AgentHostRefusal.SIGNED_OUT)
        credentials: dict[str, AgentCredential] = {}
        try:
            for lane_id, provider in self._agent_lanes:
                resolution = self._resolver.resolve(lane_id, ProviderConsumer.ASSISTANT)
                if isinstance(resolution, ResolvedDirectCredential):
                    credentials[provider] = AgentCredential(
                        secret=bytearray(resolution.secret.get_secret_value().encode("utf-8")),
                        base_url=resolution.base_url,
                    )
                elif isinstance(resolution, ProviderCredentialUnavailable):
                    _refuse_unless_skippable(resolution.reason)
            if self.current_generations() != before:
                raise AgentHostError(AgentHostRefusal.STALE_GENERATION)
        except BaseException:
            for credential in credentials.values():
                wipe(credential.secret)
            raise
        return ResolvedAgentCredentials(generations=before, credentials=credentials)

    @override
    def current_generations(self) -> AgentGenerations | None:
        """Return the sign-in and provider-settings generations without refreshing idle time."""
        observed = self._store.observe_generations()
        if observed is None:
            return None
        return AgentGenerations(sign_in=observed.sign_in, provider_settings=observed.provider_settings)


def _refuse_unless_skippable(reason: ProviderCredentialUnavailableReason) -> None:
    if reason in _SKIPPED_REASONS:
        return
    if reason in _SIGNED_OUT_REASONS:
        raise AgentHostError(AgentHostRefusal.SIGNED_OUT)
    raise AgentHostError(AgentHostRefusal.CREDENTIALS_UNAVAILABLE)


__all__ = ["ProviderSettingsAgentCredentialSource"]
