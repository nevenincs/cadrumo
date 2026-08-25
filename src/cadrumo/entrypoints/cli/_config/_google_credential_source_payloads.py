"""Typed ``--json`` payload schemas for ``aeat config google credential-source``.

Each class declared here is a strict :class:`OutputSchema` subclass and a
deferred public schema target referenced by production-authored CommandSpec so the JSON-contract test suite can
enumerate the credential-source command surface. Validated results enter
:class:`SchemaEnvelope` through :func:`emit_envelope`.

See Also:
    :mod:`_google_credential_source_cli`
        The ``set`` / ``show`` command handlers these payloads project.
"""

from __future__ import annotations

from pydantic import model_validator

from ....adapters.outbound.google import GoogleCredentialSourceSelection, GoogleImpersonationConfig
from ....core import GoogleCredentialSourceKind
from ....core.json_contract import OutputSchema


class GoogleCredentialSourcePayload(OutputSchema):
    """Flattened, validated projection of a credential-source selection."""

    profile: str
    kind: GoogleCredentialSourceKind
    target_principal: str | None = None
    target_scopes: list[str] = []
    delegates: list[str] = []
    subject: str | None = None
    lifetime_s: int | None = None

    @model_validator(mode="after")
    def _validate_canonical_selection(self) -> GoogleCredentialSourcePayload:
        """Rebuild the canonical selection so flattened fields cannot drift."""
        impersonation = None
        if self.target_principal is not None:
            impersonation = GoogleImpersonationConfig(
                target_principal=self.target_principal,
                target_scopes=tuple(self.target_scopes),
                delegates=tuple(self.delegates),
                subject=self.subject,
                lifetime_s=self.lifetime_s if self.lifetime_s is not None else 3600,
            )
        elif self.target_scopes or self.delegates or self.subject is not None or self.lifetime_s is not None:
            raise ValueError("impersonation fields require target_principal")
        GoogleCredentialSourceSelection(kind=self.kind, impersonation=impersonation)
        return self


class GoogleCredentialSourceSetResult(GoogleCredentialSourcePayload):
    """JSON envelope for ``aeat config google credential-source set``.

    Mirrors the persisted
    :class:`~adapters.outbound.google.GoogleCredentialSourceSelection`
    after :func:`~adapters.outbound.google.save_credential_source_selection`
    writes it for the active profile. The impersonation fields are ``None``
    whenever ``kind`` is ``oauth_desktop``. No SA private key or access
    token field exists anywhere on this payload: the impersonated token is
    re-derived from Application Default Credentials on every use and is
    never persisted.
    """

    operation: str = "config.google.credential_source.set"


class GoogleCredentialSourceShowResult(GoogleCredentialSourcePayload):
    """JSON envelope for ``aeat config google credential-source show``.

    Projects the optional persisted
    :class:`~adapters.outbound.google.GoogleCredentialSourceSelection` for the
    active profile. ``configured`` distinguishes a profile that has never
    opted into a non-default credential source (``kind`` then reports the
    :attr:`~core.GoogleCredentialSourceKind.OAUTH_DESKTOP` default the
    factory dispatch applies) from one with a persisted selection.
    """

    operation: str = "config.google.credential_source.show"
    configured: bool
