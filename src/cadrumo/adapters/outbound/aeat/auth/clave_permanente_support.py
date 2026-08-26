"""Shared support surface for :class:`~adapters.outbound.aeat.auth.ClavePermanenteAuthProvider`.

The helpers here keep the live Cl@ve Permanente form driver small: they
classify the configured DNI/NIE identity (reusing the shared
:func:`~adapters.outbound.aeat.auth.clave_movil_support.classify_identity`
format check, since DNI/NIE shape validation is not Móvil-specific) and attach
the closed
:class:`~adapters.outbound.aeat.auth.ClavePermanenteFailureMode` taxonomy to
provider errors.

Cl@ve Permanente login failures are raised as the existing registered
:class:`~adapters.outbound.aeat.auth.AuthConfigurationError` /
:class:`~adapters.outbound.aeat.auth.AuthError` classes (carrying a
``failure_mode`` key in ``context``) rather than new dedicated subclasses. Every
:class:`~core.errors.CadrumoError` subclass requires a declared
:class:`~core.errors.ErrorCode` registry row with a locale-backed
``message_key``; reusing the already-registered Cl@ve Móvil-sibling base
classes here avoids growing that registry (and its locale surface) as part of
this slice. A future pass may promote dedicated
``ClavePermanenteConfigurationError`` / ``ClavePermanenteLoginError`` classes
alongside their registry rows and locale strings.

See Also:
    :class:`~adapters.outbound.aeat.auth.ClavePermanenteAuthProvider`
        Live provider that uses these helpers to validate identity and report
        login-flow failures.
    :class:`~adapters.outbound.aeat.auth.ClavePermanenteFailureMode`
        Closed failure taxonomy carried in auth error context.
    :func:`~adapters.outbound.aeat.auth.clave_permanente_support.clave_permanente_auth_browser_action_policy`
        Remote-state guard policy builder for the headless login form.
    :class:`~domain.calculations.registry.RemoteStateGuardPolicy`
        Registry-authoritative policy carrier returned by the browser-action
        guard helper.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from .....core.errors import AuthError
from .....domain.calculations.registry.remote_state_guard import RemoteStateGuardPolicy
from .errors import AuthConfigurationError

if TYPE_CHECKING:
    from .....core.config import Settings


def clave_permanente_auth_browser_action_policy(settings: Settings) -> RemoteStateGuardPolicy:
    """Build the remote-state guard policy for Cl@ve Permanente browser actions.

    Mirrors the Cl@ve Móvil policy shape but scopes the allowed action
    patterns to the Permanente login form (username fill, password fill,
    authenticate) since there is no QR/push/representation-gate surface to allow.
    The final action is labelled ``authenticate`` rather than ``submit``: it is
    the Cl@ve IdP login-form submit (``#enviar_login``), an authentication step,
    not an AEAT tax filing, so the write-token block (which the label ``submit``
    lexically tripped) does not apply to it.

    Unlike Móvil — which stays on AEAT sede hosts throughout — the Permanente
    password form is submitted on Spain's Cl@ve national identity-provider page
    (``clave.gob.es``; the observed login host is ``se-pasarela.clave.gob.es``).
    The Cl@ve apex is therefore declared as a host SUFFIX under the explicit
    ``allows_gov_idp_hosts`` opt-in (a narrow, sanctioned government-IdP
    allowance, distinct from the AEAT-host predicate), alongside the AEAT apex
    suffix so a ``www{n}`` load-balancer sibling is tolerated like Móvil.
    """
    external = settings.external_constants()
    return RemoteStateGuardPolicy(
        id="aeat-clave-permanente-auth-browser-actions",
        evidence_tier="official_source_guidance",
        classification="authenticated_read_surface",
        allowed_hosts=(
            urlsplit(external.aeat.domains.sede).netloc,
            urlsplit(external.aeat.domains.www6).netloc,
        ),
        allowed_host_suffixes=(
            external.aeat.domains.host_suffix,
            urlsplit(external.aeat.domains.clave).netloc,
        ),
        allows_gov_idp_hosts=True,
        allowed_browser_action_patterns=(
            "clave-permanente-fill-username",
            "clave-permanente-fill-password",
            "clave-permanente-authenticate",
        ),
        synthetic_data_allowed=False,
        requires_authentication=True,
        requires_aeat_authorization=True,
    )


class ClavePermanenteFailureMode(StrEnum):
    """Closed failure taxonomy for Cl@ve Permanente login errors.

    Stored under the ``failure_mode`` key of the raised
    :class:`~adapters.outbound.aeat.auth.AuthConfigurationError` /
    :class:`~adapters.outbound.aeat.auth.AuthError` ``context`` mapping.
    """

    INITIAL_NAVIGATION_TIMEOUT = "initial_navigation_timeout"
    INVALID_CREDENTIALS = "invalid_credentials"
    ACCOUNT_LOCKED = "account_locked"
    PASSWORD_EXPIRED = "password_expired"
    ELEVATION_REQUIRED = "elevation_required"
    POST_AUTH_LANDING_TIMEOUT = "post_auth_landing_timeout"


def clave_permanente_configuration_error(
    message: str,
    *,
    failure_mode: ClavePermanenteFailureMode,
) -> AuthConfigurationError:
    """Build a registered :class:`~adapters.outbound.aeat.auth.AuthConfigurationError`.

    Used for local precondition faults (identity/password unset or
    malformed) raised before any browser work begins.
    """
    return AuthConfigurationError(message, context={"failure_mode": failure_mode.value})


def clave_permanente_login_error(
    message: str,
    *,
    failure_mode: ClavePermanenteFailureMode,
    context: dict[str, object] | None = None,
) -> AuthError:
    """Build a registered :class:`~adapters.outbound.aeat.auth.AuthError`.

    Used for live login-flow faults: the Cl@ve IdP rejected credentials,
    reported a locked account, an expired password, requested an SMS-OTP
    elevation the read-path flow cannot satisfy headlessly, or a navigation
    or post-auth landing wait timed out.
    """
    enriched_context = dict(context) if context is not None else {}
    enriched_context["failure_mode"] = failure_mode.value
    return AuthError(message, context=enriched_context)


__all__ = [
    "ClavePermanenteFailureMode",
    "clave_permanente_auth_browser_action_policy",
    "clave_permanente_configuration_error",
    "clave_permanente_login_error",
]
