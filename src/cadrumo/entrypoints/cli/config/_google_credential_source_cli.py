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
- ``show`` — report the persisted selection for the active profile, reading
  :attr:`~adapters.outbound.google.GoogleImpersonationConfig.target_principal`
  directly to render the exact SA email an operator would grant IAM roles to,
  and falling back to reporting the
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
    :mod:`~entrypoints.cli.config._google_credential_source_payloads`
        Typed JSON payload schemas emitted by this command group.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

from ....adapters.outbound.google.active_profile import resolve_active_profile
from ....adapters.outbound.google.errors import GoogleAuthError
from ....adapters.outbound.google.impersonation import GoogleCredentialSourceSelection, GoogleImpersonationConfig
from ....adapters.outbound.google.session_store import (
    load_credential_source_selection,
    save_credential_source_selection,
)
from ....core.google_credential_source import GoogleCredentialSourceKind
from .._common import emit_envelope
from ._google_credential_source_payloads import (
    GoogleCredentialSourceSetResult,
    GoogleCredentialSourceViewResult,
)
from .google_errors import google_refusal

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


def _resolve_active_profile_or_refuse() -> str:
    """Resolve the active profile through the canonical profile authority."""
    try:
        return resolve_active_profile()
    except GoogleAuthError as exc:
        raise google_refusal(exc) from exc


def _impersonation_kwargs(
    *,
    target_principal: str,
    scopes: list[str],
    delegates: list[str],
    subject: str | None,
    lifetime_seconds: int | None,
) -> _ImpersonationKwargs:
    """Translate CLI option values into the config model's optional kwargs."""
    kwargs: _ImpersonationKwargs = {"target_principal": target_principal.strip()}
    if scopes:
        kwargs["target_scopes"] = tuple(scopes)
    if delegates:
        kwargs["delegates"] = tuple(delegates)
    if subject is not None:
        kwargs["subject"] = subject
    if lifetime_seconds is not None:
        kwargs["lifetime_s"] = lifetime_seconds
    return kwargs


def _impersonation_selection(
    *,
    kind: GoogleCredentialSourceKind,
    target_principal: str | None,
    scopes: list[str],
    delegates: list[str],
    subject: str | None,
    lifetime_seconds: int | None,
) -> GoogleCredentialSourceSelection:
    """Validate and construct the service-account selection."""
    if target_principal is None or not target_principal.strip():
        raise google_refusal(
            GoogleAuthError(
                "credential-source set --kind service-account-impersonation requires --target-principal",
                translated_message="cli.config.google.credential_source.detail.target_principal_required",
                context={"kind": kind.value},
            ),
        )
    try:
        impersonation = GoogleImpersonationConfig(
            **_impersonation_kwargs(
                target_principal=target_principal,
                scopes=scopes,
                delegates=delegates,
                subject=subject,
                lifetime_seconds=lifetime_seconds,
            ),
        )
        return GoogleCredentialSourceSelection(kind=kind, impersonation=impersonation)
    except ValueError as exc:
        raise google_refusal(
            GoogleAuthError(
                translated_message="cli.config.google.credential_source.detail.impersonation_config_invalid",
                context={"error_type": type(exc).__name__},
            ),
        ) from exc


def _reject_oauth_desktop_options(
    *,
    kind: GoogleCredentialSourceKind,
    target_principal: str | None,
    scopes: list[str],
    delegates: list[str],
    subject: str | None,
    lifetime_seconds: int | None,
) -> None:
    """Reject options that have meaning only for impersonation."""
    if any(
        (
            target_principal is not None,
            bool(scopes),
            bool(delegates),
            subject is not None,
            lifetime_seconds is not None,
        ),
    ):
        raise google_refusal(
            GoogleAuthError(
                "credential-source set --kind oauth-desktop accepts no impersonation options",
                translated_message="cli.config.google.credential_source.detail.oauth_desktop_rejects_impersonation_options",
                context={"kind": kind.value},
            ),
        )


def _selection_for_set(
    *,
    kind: GoogleCredentialSourceKind,
    target_principal: str | None,
    scopes: list[str],
    delegates: list[str],
    subject: str | None,
    lifetime_seconds: int | None,
) -> GoogleCredentialSourceSelection:
    """Build the canonical selection while retaining CLI refusal ordering."""
    if kind is GoogleCredentialSourceKind.SERVICE_ACCOUNT_IMPERSONATION:
        return _impersonation_selection(
            kind=kind,
            target_principal=target_principal,
            scopes=scopes,
            delegates=delegates,
            subject=subject,
            lifetime_seconds=lifetime_seconds,
        )
    _reject_oauth_desktop_options(
        kind=kind,
        target_principal=target_principal,
        scopes=scopes,
        delegates=delegates,
        subject=subject,
        lifetime_seconds=lifetime_seconds,
    )
    return GoogleCredentialSourceSelection(kind=kind)


def _selection_fields(
    selection: GoogleCredentialSourceSelection,
) -> tuple[str | None, list[str], list[str], str | None, int | None]:
    """Flatten canonical selection fields for the two typed CLI schemas."""
    impersonation = selection.impersonation
    if impersonation is None:
        return None, [], [], None, None
    return (
        impersonation.target_principal,
        _default_scopes(selection),
        list(impersonation.delegates),
        impersonation.subject,
        impersonation.lifetime_s,
    )


def _set_result(profile: str, selection: GoogleCredentialSourceSelection) -> GoogleCredentialSourceSetResult:
    """Project a saved selection onto the set command's typed result."""
    target_principal, target_scopes, delegates, subject, lifetime_s = _selection_fields(selection)
    return GoogleCredentialSourceSetResult(
        profile=profile,
        kind=selection.kind,
        target_principal=target_principal,
        target_scopes=target_scopes,
        delegates=delegates,
        subject=subject,
        lifetime_s=lifetime_s,
    )


def _view_result(
    profile: str,
    configured: bool,
    selection: GoogleCredentialSourceSelection,
) -> GoogleCredentialSourceViewResult:
    """Project a loaded selection onto the view command's typed result."""
    target_principal, target_scopes, delegates, subject, lifetime_s = _selection_fields(selection)
    return GoogleCredentialSourceViewResult(
        profile=profile,
        configured=configured,
        kind=selection.kind,
        target_principal=target_principal,
        target_scopes=target_scopes,
        delegates=delegates,
        subject=subject,
        lifetime_s=lifetime_s,
    )


def _selection_lines(
    operation: str,
    profile: str,
    selection: GoogleCredentialSourceSelection,
) -> list[str]:
    """Render the stable tabular projection shared by set and view."""
    lines = [
        f"operation\t{operation}",
        f"profile\t{profile}",
        f"kind\t{selection.kind.value}",
    ]
    impersonation = selection.impersonation
    if impersonation is None:
        return lines
    lines.append(f"target_principal\t{impersonation.target_principal}")
    lines.extend(f"scope\t{scope}" for scope in impersonation.target_scopes)
    lines.extend(f"delegate\t{delegate}" for delegate in impersonation.delegates)
    if impersonation.subject is not None:
        lines.append(f"subject\t{impersonation.subject}")
    lines.append(f"lifetime_s\t{impersonation.lifetime_s}")
    return lines


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
    active = _resolve_active_profile_or_refuse()
    selection = _selection_for_set(
        kind=kind,
        target_principal=target_principal,
        scopes=scopes,
        delegates=delegates,
        subject=subject,
        lifetime_seconds=lifetime_seconds,
    )

    save_credential_source_selection(active, selection)

    emit_envelope(
        ctx,
        command="config.google.credential_source.set",
        result=_set_result(active, selection),
        lines=tuple(_selection_lines("config.google.credential_source.set", active, selection)),
    )


def google_credential_source_view(
    ctx: typer.Context,
) -> None:
    """Report the active profile's persisted Google credential-source selection.

    A profile with no persisted selection reports the
    :attr:`~core.GoogleCredentialSourceKind.OAUTH_DESKTOP` default the
    factory dispatch (:func:`~adapters.outbound.storage.build_google_credentials`)
    applies — a missing record is a valid, expected state, never an error.
    """
    active = _resolve_active_profile_or_refuse()

    selection = load_credential_source_selection(active)
    configured = selection is not None
    resolved = selection if selection is not None else GoogleCredentialSourceSelection()
    emit_envelope(
        ctx,
        command="config.google.credential_source.show",
        result=_view_result(active, configured, resolved),
        lines=tuple(_selection_lines("config.google.credential_source.show", active, resolved)),
    )


__all__ = ["google_credential_source_set", "google_credential_source_view"]
