"""Typed ``--json`` payload schemas for ``cadrumo config google credential-source``.

Each class declared here is a strict :class:`OutputSchema` subclass and is
decorated with :func:`register_schema` so the JSON-contract test suite can
enumerate the credential-source command surface. Validated results enter
:class:`SchemaEnvelope` through :func:`_emit_envelope`.

See Also:
    :mod:`_google_credential_source_cli`
        The ``set`` / ``show`` command handlers these payloads project.
"""

from __future__ import annotations

from .._schemas import OutputSchema, register_schema


@register_schema("config.google.credential_source.set")
class GoogleCredentialSourceSetResult(OutputSchema):
    """JSON envelope for ``cadrumo config google credential-source set``.

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
    profile: str
    kind: str
    target_principal: str | None = None
    target_scopes: list[str] = []
    delegates: list[str] = []
    subject: str | None = None
    lifetime_s: int | None = None


@register_schema("config.google.credential_source.show")
class GoogleCredentialSourceShowResult(OutputSchema):
    """JSON envelope for ``cadrumo config google credential-source show``.

    Projects the optional persisted
    :class:`~adapters.outbound.google.GoogleCredentialSourceSelection` for the
    active profile. ``configured`` distinguishes a profile that has never
    opted into a non-default credential source (``kind`` then reports the
    :attr:`~core.GoogleCredentialSourceKind.OAUTH_DESKTOP` default the
    factory dispatch applies) from one with a persisted selection.
    """

    operation: str = "config.google.credential_source.show"
    profile: str
    configured: bool
    kind: str
    target_principal: str | None = None
    target_scopes: list[str] = []
    delegates: list[str] = []
    subject: str | None = None
    lifetime_s: int | None = None
