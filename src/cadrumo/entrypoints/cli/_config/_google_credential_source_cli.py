"""``aeat config google credential-source ...`` — select the Google credential source.

Wires the per-profile :class:`~adapters.outbound.google.GoogleCredentialSourceSelection`
persisted by the ``google-sa-impersonation`` core slice
(:func:`~adapters.outbound.google.save_credential_source_selection` /
:func:`~adapters.outbound.google.load_credential_source_selection`) into an
operator verb, so a gestor can opt a profile into service-account impersonation
(:attr:`~core.GoogleCredentialSourceKind.SERVICE_ACCOUNT_IMPERSONATION`) without
a programmatic call, or restore the default interactive OAuth Desktop flow
(:attr:`~core.GoogleCredentialSourceKind.OAUTH_DESKTOP`).

Two commands:

- ``set --kind oauth-desktop|service-account-impersonation [--target-principal
  <sa-email>] [--scope <scope> ...] [--delegate <sa-email> ...] [--subject
  <user-email>] [--lifetime-seconds <seconds>]`` — persist the selection for
  the active profile via
  :func:`~adapters.outbound.google.save_credential_source_selection`.
  ``--target-principal`` is required exactly when ``--kind
  service-account-impersonation`` is chosen; the underlying
  :class:`~adapters.outbound.google.GoogleCredentialSourceSelection` /
  :class:`~adapters.outbound.google.GoogleImpersonationConfig` validators
  enforce the pairing.
- ``show`` — report the persisted selection for the active profile
  (:func:`~adapters.outbound.google.describe_impersonation_target` renders the
  exact SA email an operator would grant IAM roles to before doing so),
  falling back to reporting the
  :attr:`~core.GoogleCredentialSourceKind.OAUTH_DESKTOP` default when no
  selection has been persisted.

Neither command performs a live ADC discovery or IAM token exchange; the
persisted selection is dispatched by
:func:`~adapters.outbound.storage.build_google_credentials` the next time a
Google-backed command builds credentials for this profile
(``aeat-architecture-boundaries`` — this CLI module delegates to
the landed persistence and resolver primitives; it does not re-implement
credential resolution).

See Also:
    :class:`~adapters.outbound.google.GoogleCredentialSourceSelection`
        Persisted per-profile selection this CLI writes and reads.
    :class:`~adapters.outbound.google.GoogleImpersonationConfig`
        Service-account impersonation configuration validated for the
        non-default credential-source kind.
    :class:`~core.GoogleCredentialSourceKind`
        Closed credential-source taxonomy accepted by the CLI.
    :func:`~adapters.outbound.google.save_credential_source_selection`
        Persistence primitive used by ``set``.
    :func:`~adapters.outbound.google.load_credential_source_selection`
        Persistence primitive used by ``show``.
    :func:`~adapters.outbound.storage.build_google_credentials`
        Runtime factory that later consumes the stored selection.
    :mod:`~entrypoints.cli._config._google_credential_source_payloads`
        Typed JSON payload schemas emitted by this command group.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

from ....adapters.outbound.google import (
    GoogleAuthError,
    GoogleCredentialSourceSelection,
    GoogleImpersonationConfig,
    load_credential_source_selection,
    resolve_active_profile,
    save_credential_source_selection,
)
from ....core import GoogleCredentialSourceKind
from .._common import emit_envelope
from ._google_credential_source_payloads import (
    GoogleCredentialSourceSetResult,
    GoogleCredentialSourceViewResult,
)
from ._google_errors import _google_refusal

if TYPE_CHECKING:
    import typer


class _ImpersonationKwargs(TypedDict, total=False):
    """Optional-key constructor kwargs for :class:`GoogleImpersonationConfig`.

    Every key is conditionally populated below; omitted keys fall through to
    the model's own field defaults. A plain ``dict[str, object]`` would erase
    each field's real type at the ``**`` splat, so this mirrors the
    constructor's keyword types one-for-one instead.
    """

    target_principal: str
    target_scopes: tuple[str, ...]
    delegates: tuple[str, ...]
    subject: str | None
    lifetime_s: int


def _default_scopes(selection: GoogleCredentialSourceSelection) -> list[str]:
    if selection.impersonation is None:
        return []
    return list(selection.impersonation.target_scopes)


def google_credential_source_set(
    ctx: typer.Context,
    kind: GoogleCredentialSourceKind,
    target_principal: str | None = None,
    scopes: list[str] | None = None,
    delegates: list[str] | None = None,
    subject: str | None = None,
    lifetime_seconds: int | None = None,
) -> None:
    """Persist the active profile's Google credential-source selection.

    ``--kind service-account-impersonation`` requires ``--target-principal``
    and stores a :class:`~adapters.outbound.google.GoogleImpersonationConfig`;
    ``--kind oauth-desktop`` restores the interactive-consent default and
    rejects every impersonation-only option. Neither branch performs a live
    ADC discovery or IAM token exchange — that happens lazily the next time
    :func:`~adapters.outbound.storage.build_google_credentials` builds
    credentials for this profile.
    """
    scopes = scopes or []
    delegates = delegates or []
    try:
        active = resolve_active_profile()
    except GoogleAuthError as exc:
        raise _google_refusal(exc) from exc

    if kind is GoogleCredentialSourceKind.SERVICE_ACCOUNT_IMPERSONATION:
        if target_principal is None or not target_principal.strip():
            raise _google_refusal(
                GoogleAuthError(
                    "credential-source set --kind service-account-impersonation requires --target-principal",
                    translated_message="cli.config.google.credential_source.detail.target_principal_required",
                    context={"kind": kind.value},
                ),
            )
        impersonation_kwargs: _ImpersonationKwargs = {"target_principal": target_principal.strip()}
        if scopes:
            impersonation_kwargs["target_scopes"] = tuple(scopes)
        if delegates:
            impersonation_kwargs["delegates"] = tuple(delegates)
        if subject is not None:
            impersonation_kwargs["subject"] = subject
        if lifetime_seconds is not None:
            impersonation_kwargs["lifetime_s"] = lifetime_seconds
        try:
            impersonation = GoogleImpersonationConfig(**impersonation_kwargs)
            selection = GoogleCredentialSourceSelection(kind=kind, impersonation=impersonation)
        except ValueError as exc:
            raise _google_refusal(
                GoogleAuthError(
                    translated_message="cli.config.google.credential_source.detail.impersonation_config_invalid",
                    context={"error_type": type(exc).__name__},
                ),
            ) from exc
    else:
        if target_principal is not None or scopes or delegates or subject is not None or lifetime_seconds is not None:
            raise _google_refusal(
                GoogleAuthError(
                    "credential-source set --kind oauth-desktop accepts no impersonation options",
                    translated_message="cli.config.google.credential_source.detail.oauth_desktop_rejects_impersonation_options",
                    context={"kind": kind.value},
                ),
            )
        selection = GoogleCredentialSourceSelection(kind=kind)

    save_credential_source_selection(active, selection)

    impersonation = selection.impersonation
    typed = GoogleCredentialSourceSetResult(
        profile=active,
        kind=selection.kind,
        target_principal=impersonation.target_principal if impersonation is not None else None,
        target_scopes=_default_scopes(selection),
        delegates=list(impersonation.delegates) if impersonation is not None else [],
        subject=impersonation.subject if impersonation is not None else None,
        lifetime_s=impersonation.lifetime_s if impersonation is not None else None,
    )
    lines = [
        "operation\tconfig.google.credential_source.set",
        f"profile\t{active}",
        f"kind\t{selection.kind.value}",
    ]
    if impersonation is not None:
        lines.append(f"target_principal\t{impersonation.target_principal}")
        lines.extend(f"scope\t{scope}" for scope in impersonation.target_scopes)
        lines.extend(f"delegate\t{delegate}" for delegate in impersonation.delegates)
        if impersonation.subject is not None:
            lines.append(f"subject\t{impersonation.subject}")
        lines.append(f"lifetime_s\t{impersonation.lifetime_s}")
    emit_envelope(ctx, command="config.google.credential_source.set", result=typed, lines=tuple(lines))


def google_credential_source_view(
    ctx: typer.Context,
) -> None:
    """Report the active profile's persisted Google credential-source selection.

    A profile with no persisted selection reports the
    :attr:`~core.GoogleCredentialSourceKind.OAUTH_DESKTOP` default the
    factory dispatch (:func:`~adapters.outbound.storage.build_google_credentials`)
    applies — a missing record is a valid, expected state, never an error.
    """
    try:
        active = resolve_active_profile()
    except GoogleAuthError as exc:
        raise _google_refusal(exc) from exc

    selection = load_credential_source_selection(active)
    configured = selection is not None
    resolved = selection if selection is not None else GoogleCredentialSourceSelection()
    impersonation = resolved.impersonation

    typed = GoogleCredentialSourceViewResult(
        profile=active,
        configured=configured,
        kind=resolved.kind,
        target_principal=impersonation.target_principal if impersonation is not None else None,
        target_scopes=_default_scopes(resolved),
        delegates=list(impersonation.delegates) if impersonation is not None else [],
        subject=impersonation.subject if impersonation is not None else None,
        lifetime_s=impersonation.lifetime_s if impersonation is not None else None,
    )
    lines = [
        "operation\tconfig.google.credential_source.show",
        f"profile\t{active}",
        f"configured\t{configured}",
        f"kind\t{resolved.kind.value}",
    ]
    if impersonation is not None:
        lines.append(f"target_principal\t{impersonation.target_principal}")
        lines.extend(f"scope\t{scope}" for scope in impersonation.target_scopes)
        lines.extend(f"delegate\t{delegate}" for delegate in impersonation.delegates)
        if impersonation.subject is not None:
            lines.append(f"subject\t{impersonation.subject}")
        lines.append(f"lifetime_s\t{impersonation.lifetime_s}")
    emit_envelope(ctx, command="config.google.credential_source.show", result=typed, lines=tuple(lines))


__all__ = ["google_credential_source_set", "google_credential_source_view"]
