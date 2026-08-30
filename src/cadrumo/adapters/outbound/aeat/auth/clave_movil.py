"""Cl@ve Móvil auth provider for AEAT Sede Electrónica.

Implements the :class:`AuthProvider` protocol for the human-in-the-loop
Cl@ve Móvil flow against the live portal. Captures the URL template,
form selectors, and polling endpoints needed to drive the AEAT QR page
to a successful login handshake.

The provider returns :class:`AeatSession` and :class:`AeatLoginAssertion`
records with Cl@ve-specific detail payloads. Fresh logins persist
:class:`ClaveMovilSessionMetadata` next to encrypted Playwright storage state;
resume and diagnostic probes rebuild :class:`ClaveMovilSessionDetail` from that
metadata without carrying credential material in the session record.

Design summary:

* Cl@ve Móvil is a human-in-the-loop flow. A browser that remains on the
  challenge page cannot reveal what happened on the phone. Conversely,
  AEAT's authenticated representation or target landing proves that the
  app request was accepted; diagnostics record that transition directly
  and never ask the operator to restate it.
* The provider opens a headed Playwright window on fresh login so the
  operator can scan the QR visually. Resume-from-storage-state runs
  headlessly because no human interaction is required.
* The persisted session stores Playwright state and provider metadata
  together in the encrypted session object. Kind-namespaced logical
  storage keys keep the Cl@ve and certificate sessions separate. Each
  persisted object is tagged with :class:`SensitivityClass` SESSION so
  the storage substrate applies the correct at-rest treatment.

See Also:
    :class:`ClaveMovilSessionMetadata` for the encrypted persistence contract,
    :class:`ClaveMovilSessionDetail` for the public session payload, and
    :class:`ClaveMovilApprovalTimeoutError` for operator-reportable live-flow
    failures.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Final, override
from urllib.parse import quote, urlsplit

from pydantic import ValidationError

from .....application.auth.protocols import (
    BrowserContextPort,
    BrowserPagePort,
    BrowserSessionFactoryPort,
    BrowserSessionPort,
)
from .....application.auth.session_types import (
    AeatLoginAssertion,
    AeatSession,
    ClaveMovilLoginAssertionDetail,
    ClaveMovilSessionDetail,
    is_exact_active_provider_session,
)
from .....core import AuthProviderDescription, AuthProviderKind
from .....core.config import Settings as _Settings
from .....core.config import unwrap_optional_secret
from .....core.errors.hierarchy import AeatLoginAssertionError, AuthError
from .....core.i18n import tr
from .....core.identity import same_tax_identifier, tax_id_identity_token
from .....core.logging import get_logger
from .....core.remote_authority import canonical_remote_hostname
from .....core.time import now
from .....domain.user_profile.errors import UserProfileError
from .._playwright import PlaywrightTimeoutError
from . import session_store as session_store
from ._clave_movil_page_flow import _ClaveMovilPageFlowMixin
from ._clave_movil_salvage import _ClaveMovilSessionSalvageMixin
from ._clave_provider_common import (
    close_clave_browser_session,
    close_clave_context,
    default_sede_target_url,
    verification_probe_url,
)
from ._session_probe import run_authenticated_landing_probe
from .authenticator import AEAT_SESSION_IDLE_TTL
from .browser_lifecycle import _CloseIntentBarrier
from .clave_movil_metadata import ClaveMovilSessionMetadata
from .clave_movil_support import (
    ClaveMovilApprovalTimeoutError,
    ClaveMovilConfigurationError,
    ClaveMovilFailureMode,
)
from .clave_movil_support import (
    classify_identity as _classify_identity,
)
from .clave_movil_support import (
    diagnostic_fingerprint as _diagnostic_fingerprint,
)
from .clave_movil_support import (
    render_progress_banner as _render_progress_banner,
)
from .clave_movil_support import (
    url_diagnostic as _url_diagnostic,
)
from .errors import AuthProviderCleanupError

if TYPE_CHECKING:
    from .....core.config import Settings


log = get_logger(__name__)

_NAVIGATION_TIMEOUT_MS_DEFAULT: Final[int] = int(
    _Settings.model_fields["cadrumo_browser_navigation_timeout_ms"].default,
)
# Environment variable name referenced in operator-facing error messages.
# Named constant so grepping for the env-var name surfaces every usage site.
_CLAVE_MOVIL_DNI_NIE_ENV: Final[str] = "CADRUMO_CLAVE_MOVIL_DNI_NIE"


class ClaveMovilAuthProvider(_ClaveMovilPageFlowMixin, _ClaveMovilSessionSalvageMixin):
    """Cl@ve Móvil implementation of the :class:`AuthProvider` protocol.

    Constructed by :func:`adapters.outbound.aeat.auth.select_provider` when
    ``kind == AuthProviderKind.CLAVE_MOVIL``. Fresh login can run the
    configured non-QR confirmation flow or the alternate QR flow;
    resume runs headlessly because the stored cookies are sufficient.

    The provider owns the lifecycle contract; :class:`_ClaveMovilPageFlowMixin`
    supplies page-driving helpers, :class:`_ClaveMovilSessionSalvageMixin`
    supplies the post-failure session-salvage helpers, and this class turns
    those browser outcomes into :class:`AeatSession`, :class:`AeatLoginAssertion`,
    and :class:`AuthProviderDescription` records.
    """

    kind: AuthProviderKind = AuthProviderKind.CLAVE_MOVIL

    def __init__(
        self,
        settings: Settings,
        *,
        browser_session_factory: BrowserSessionFactoryPort | None = None,
        navigation_timeout_ms: int = _NAVIGATION_TIMEOUT_MS_DEFAULT,
    ) -> None:
        """Initialize one provider with its settings and browser boundary."""
        self._settings = settings
        self._browser_session_factory = browser_session_factory
        self._navigation_timeout_ms = navigation_timeout_ms
        self._lifecycle = _CloseIntentBarrier()
        self._browser_session: BrowserSessionPort | None = None
        self._context: BrowserContextPort | None = None
        self._active_session: AeatSession | None = None

    # ── Protocol surface ────────────────────────────────────────────────────

    async def authenticate(self) -> AeatSession:
        """Run the provider-neutral Cl@ve Móvil login flow."""
        return await self.authenticate_for_target(target_url=None)

    async def authenticate_for_target(
        self,
        *,
        target_url: str | None = None,
    ) -> AeatSession:
        """Run the Cl@ve Móvil login flow and return an :class:`AeatSession`.

        Attempts to resume a cached session first. Falls back to the
        human-in-the-loop QR-scan flow (or the non-QR DNI/NIE +
        contraste fallback, when
        ``CADRUMO_CLAVE_PREFER_NON_QR=true``). Fresh success writes
        :class:`ClaveMovilSessionMetadata` and returns a session whose
        provider detail is :class:`ClaveMovilSessionDetail`.
        """
        async with self._lifecycle.work():
            if self._active_session is not None:
                raise AeatLoginAssertionError(
                    "ClaveMovilAuthProvider already has an active session; call close() before authenticating again",
                    translated_message="adapters.auth.clave_movil.errors.already_active",
                )
            if self._context is not None or self._browser_session is not None:
                raise AuthProviderCleanupError(
                    "ClaveMovilAuthProvider retained browser resources after close",
                    translated_message="errors.auth.auth_auth_provider_cleanup",
                )
            dni_nie = self._require_identity()
            resume_path = self._storage_state_path()
            if session_store.exists(resume_path):
                try:
                    return await self._resume_locked(
                        resume_path,
                        target_url=target_url,
                    )
                except AeatLoginAssertionError as exc:
                    log.info(
                        "ClaveMovilAuthProvider: persisted session unusable; falling back to fresh login (%s)",
                        exc,
                    )
                    self._invalidate_persisted(resume_path)

            return await self._fresh_login_locked(
                dni_nie=dni_nie,
                storage_state_path=resume_path,
                target_url=target_url,
            )

    async def probe_persisted_session(
        self,
        *,
        target_url: str | None = None,
    ) -> tuple[AeatSession, AeatLoginAssertion]:
        """Probe the encrypted persisted session without side effects.

        Unlike :meth:`authenticate`, this method NEVER falls back to a
        fresh login and NEVER deletes the persisted session, even when
        the probe fails. Callers can therefore use it as a pure diagnostic
        without accidentally triggering a fresh operator-mediated Cl@ve request.
        A successful probe refreshes the stored idle deadline using the
        returned :class:`AeatLoginAssertion` timestamp.

        Returns:
            A 2-tuple of (:class:`AeatSession`, :class:`AeatLoginAssertion`).
        """
        async with self._lifecycle.work():
            if self._active_session is not None:
                raise AeatLoginAssertionError(
                    "ClaveMovilAuthProvider already has an active session; call close() first",
                )
            if self._context is not None or self._browser_session is not None:
                raise AuthProviderCleanupError(
                    "ClaveMovilAuthProvider retained browser resources after close",
                    translated_message="errors.auth.auth_auth_provider_cleanup",
                )
            storage_state_path = self._storage_state_path()
            if not session_store.exists(storage_state_path):
                raise AeatLoginAssertionError(
                    "no persisted Cl@ve Móvil session; run `aeat config auth status` first",
                    translated_message="adapters.auth.clave_movil.errors.no_persisted_session",
                )

            persisted = self._load_persisted(storage_state_path)
            metadata = self._load_metadata(storage_state_path, persisted)
            if metadata.idle_deadline <= now():
                raise AeatLoginAssertionError(
                    "Cl@ve Móvil session past idle deadline",
                    translated_message="adapters.auth.clave_movil.errors.session_expired",
                )

            session_like = await self._resolve_browser_session()
            self._browser_session = session_like
            context: BrowserContextPort | None = None
            try:
                context = await session_like.create_context(storage_state=persisted.storage_state)
                self._context = context
                session = AeatSession(
                    authenticated_at=metadata.authenticated_at,
                    idle_deadline=metadata.idle_deadline,
                    storage_state_path=storage_state_path,
                    identity_nif=metadata.identity_nif,
                    provider_detail=ClaveMovilSessionDetail(
                        dni_nie=metadata.identity_nif,
                        used_non_qr_fallback=metadata.used_non_qr_fallback,
                        verification_code=metadata.verification_code,
                        landing_url=metadata.landing_url,
                    ),
                )
                self._browser_session = session_like
                self._context = context
                self._active_session = session
                # Explicit caller targets need selector dispatch; recorded
                # landing metadata is already carried by the session detail
                # and remains a direct probe.
                # Persisted-session probes must never turn into a fresh
                # Cl@ve dispatch. Explicit target probes use AEAT's selector
                # URL, which can issue a new phone request when the stored
                # cookies are not accepted for that target. Verify the stored
                # landing/default authenticated page here; the downstream
                # read surface will use the session and fail as a read error
                # if AEAT rejects it for the target application.
                del target_url
                assertion = await self._verify_in_work(session, target_url=None)
                return self._finalize_probe_result(
                    session,
                    metadata,
                    storage_state_path,
                    storage_state=persisted.storage_state,
                    assertion=assertion,
                )
            except Exception:  # cleanup on verify error then re-raise; Playwright+CadrumoError undocumented
                context_closed = await self._close_context(context, reason="verify cleanup")
                closed = await self._close_browser_session(session_like)
                self._browser_session = None if closed else session_like
                self._context = None if context_closed else context
                self._active_session = None
                raise

    def _finalize_probe_result(
        self,
        session: AeatSession,
        metadata: ClaveMovilSessionMetadata,
        storage_state_path: Path,
        *,
        storage_state: Mapping[str, object],
        assertion: AeatLoginAssertion,
    ) -> tuple[AeatSession, AeatLoginAssertion]:
        """Refresh the idle TTL on a valid probe, else return the session as-is."""
        # Refresh idle TTL on successful probe so long-running
        # discovery sessions stay alive without re-auth. AEAT's
        # own 18-minute idle window resets on every authenticated
        # hit to the sede — our persisted deadline should too.
        if not assertion.is_valid:
            log.warning(
                "ClaveMovilAuthProvider: live probe returned invalid assertion status=%s error=%r",
                assertion.status_code,
                assertion.error_message,
            )
            return session, assertion
        refreshed = session.model_copy(
            update={
                "authenticated_at": assertion.attempted_at,
                "idle_deadline": assertion.attempted_at + AEAT_SESSION_IDLE_TTL,
            },
        )
        self._active_session = refreshed
        refreshed_metadata = metadata.model_copy(
            update={
                "authenticated_at": refreshed.authenticated_at,
                "idle_deadline": refreshed.idle_deadline,
            },
        )
        try:
            self._persist_session(
                storage_state_path,
                storage_state=storage_state,
                metadata=refreshed_metadata,
            )
        except (OSError, AuthError):
            log.warning(
                "ClaveMovilAuthProvider: encrypted session refresh write failed;"
                " session valid but deadline not persisted",
                exc_info=True,
            )
        return refreshed, assertion

    async def verify(self, session: AeatSession) -> AeatLoginAssertion:
        """Run the provider-neutral verification flow for ``session``."""
        return await self.verify_for_target(session, target_url=None)

    async def verify_for_target(
        self,
        session: AeatSession,
        *,
        target_url: str | None = None,
    ) -> AeatLoginAssertion:
        """Re-probe that ``session``'s cookies still unlock a Sede page.

        Explicit ``target_url`` probes go through AEAT's selector dispatcher,
        because some Cl@ve-backed apps only establish target-local state when
        dispatched from the selector. When no explicit target is supplied and
        the session metadata has a concrete post-auth landing URL, the probe
        can navigate there directly.

        The returned :class:`AeatLoginAssertion` carries
        :class:`ClaveMovilLoginAssertionDetail`, including the observed landing
        URL and whether the probe reached an authenticated AEAT page.

        Returns:
            An :class:`AeatLoginAssertion` describing the probe outcome.
        """
        async with self._lifecycle.work():
            return await self._verify_in_work(session, target_url=target_url)

    async def _verify_in_work(
        self,
        session: AeatSession,
        *,
        target_url: str | None,
    ) -> AeatLoginAssertion:
        """Verify a session while the caller holds the provider work lease."""
        context = self._context
        if context is None:
            raise AeatLoginAssertionError(
                "ClaveMovilAuthProvider.verify() requires an active browser context; call authenticate() first",
                translated_message="adapters.auth.clave_movil.errors.verify_requires_active_context",
            )
        if not is_exact_active_provider_session(
            session,
            self._active_session,
            provider_kind=AuthProviderKind.CLAVE_MOVIL,
            detail_type=ClaveMovilSessionDetail,
        ):
            raise AeatLoginAssertionError(
                "ClaveMovilAuthProvider.verify() requires the exact active Cl@ve Móvil session",
            )
        session_landing_url = (
            session.provider_detail.landing_url
            if isinstance(session.provider_detail, ClaveMovilSessionDetail)
            else None
        )
        resolved_target_url = target_url or session_landing_url
        target_path = (
            self._target_path_from_url(resolved_target_url)
            if resolved_target_url
            else self._settings.aeat_sede_expedientes_path
        )
        probe_url = self._probe_url_for_verification(
            explicit_target_url=target_url,
            resolved_target_url=resolved_target_url,
            target_path=target_path,
        )
        attempted_at = now()
        outcome = await run_authenticated_landing_probe(
            context,
            probe_url=probe_url,
            target_path=target_path,
            navigation_timeout_ms=self._navigation_timeout_ms,
            is_authenticated_landing=self._authenticated_landing_predicate,
            on_landing=self._dispatch_clave_selector_on_landing,
            log_label="ClaveMovilAuthProvider.verify",
        )
        is_valid = outcome.session_cookie_present and bool(session.identity_nif)
        return AeatLoginAssertion(
            target_url=probe_url,
            is_valid=is_valid,
            identity_nif=session.identity_nif,
            status_code=outcome.status_code,
            elapsed_ms=outcome.elapsed_ms,
            attempted_at=attempted_at,
            error_message=outcome.error_message,
            assertion_detail=ClaveMovilLoginAssertionDetail(
                session_cookie_present=outcome.session_cookie_present,
                landing_url=outcome.landing_url,
            ),
        )

    def _authenticated_landing_predicate(self, landing_url: str, target_path: str) -> bool:
        return self._is_authenticated_aeat_landing(landing_url=landing_url, target_path=target_path)

    async def _dispatch_clave_selector_on_landing(
        self,
        page: BrowserPagePort,
        landing_url: str,
        target_path: str,
    ) -> bool:
        """Click through the Cl@ve selector page when the probe lands on it."""
        if self._clave_surface().selector_access_path_marker not in landing_url:
            return False
        await self._click_clave_movil_button(page)
        await self._wait_for_post_auth_landing(page, target_path, self._navigation_timeout_ms)
        return True

    def describe(self) -> AuthProviderDescription:
        """Return an :class:`AuthProviderDescription` for the Cl@ve Móvil provider state.

        Severity is set explicitly here so a normal pending state — Cl@ve
        Móvil completion requires an operator-mediated tap on the phone —
        is paired with ``info``, never the loudest ``error`` token
        (round-5 M5). A malformed identity is a real configuration
        fault and surfaces as ``warning``; the no-identity case is an
        undeclared state and surfaces as ``info``. Identity validation is
        delegated to :func:`classify_identity`, which raises
        :class:`ClaveMovilConfigurationError` for unsupported DNI/NIE shapes.
        """
        dni_nie = unwrap_optional_secret(self._settings.cadrumo_clave_movil_dni_nie).strip()
        if not dni_nie:
            return AuthProviderDescription(
                kind=self.kind,
                label="Cl@ve Móvil",
                configured=False,
                available=False,
                health_severity="info",
                health_summary=tr("application.auth.clave_movil.health.identity_unset"),
            )
        try:
            _classify_identity(dni_nie)
        except ClaveMovilConfigurationError as exc:
            return AuthProviderDescription(
                kind=self.kind,
                label="Cl@ve Móvil",
                configured=True,
                available=False,
                identity_nif=dni_nie.upper(),
                health_severity="warning",
                health_summary=str(exc),
            )
        # Cl@ve Móvil requires operator-mediated live auth, so availability
        # means the provider is configured to start that AEAT flow.
        return AuthProviderDescription(
            kind=self.kind,
            label="Cl@ve Móvil",
            configured=True,
            available=True,
            identity_nif=dni_nie.upper(),
            health_severity="info",
            health_summary=tr("application.auth.clave_movil.health.operator_completion_required"),
        )

    async def close(self) -> None:
        """Tear down any retained :class:`BrowserContextPort` and browser session."""
        async with self._lifecycle.close():
            context_closed = await self._drop_context()
            browser_session_closed = await self._close_browser_session(self._browser_session)
            if browser_session_closed:
                self._browser_session = None
            self._active_session = None
        if not context_closed or not browser_session_closed:
            raise AuthProviderCleanupError(
                "ClaveMovilAuthProvider retained browser resources after close",
                translated_message="errors.auth.auth_auth_provider_cleanup",
            )

    # ── Identity + target helpers ───────────────────────────────────────────

    def _require_identity(self) -> str:
        raw = unwrap_optional_secret(self._settings.cadrumo_clave_movil_dni_nie)
        if not raw:
            raise ClaveMovilConfigurationError(
                f"{_CLAVE_MOVIL_DNI_NIE_ENV} is not set; set it to your DNI or NIE "
                "before running `aeat config auth configure --provider clave_movil`.",
                translated_message="adapters.auth.clave_movil.errors.dni_nie_not_set",
            )
        _classify_identity(raw)
        return raw.strip().upper()

    def _default_target_url(self) -> str:
        return default_sede_target_url(self._settings)

    def _selector_url(self, target_path: str) -> str:
        template = self._settings.aeat_clave_sede_access_url_template
        return template.format(target=quote(target_path, safe=""))

    @override
    def _clave_surface(self):
        return self._settings.external_constants().aeat.clave_movil

    def _probe_url_for_verification(
        self,
        *,
        explicit_target_url: str | None,
        resolved_target_url: str | None,
        target_path: str,
    ) -> str:
        return verification_probe_url(
            explicit_target_url=explicit_target_url,
            resolved_target_url=resolved_target_url,
            target_path=target_path,
            selector_url_for=self._selector_url,
        )

    @override
    def _is_authenticated_aeat_landing(self, *, landing_url: str, target_path: str) -> bool:
        """Return True for a protected AEAT page reached after Cl@ve dispatch."""
        external = self._settings.external_constants()
        surface = external.aeat.clave_movil
        try:
            parsed = urlsplit(landing_url)
        except ValueError:
            return False
        # The authority is decided by the one canonical helper, never by
        # ``parsed.netloc``: that string still ends in the AEAT suffix when a
        # credential prefix rides in front of it, so
        # ``https://evil@www6.agenciatributaria.gob.es/`` was read as a
        # protected AEAT landing.
        host = canonical_remote_hostname(landing_url)
        if host is None:
            return False
        host_suffix = external.aeat.domains.host_suffix.casefold()
        if host != host_suffix and not host.endswith(f".{host_suffix}"):
            return False
        path = parsed.path.casefold()
        if external.aeat.sede_paths.auth_gate_4033.casefold() in path:
            return False
        clave_path_markers = (
            surface.selector_access_path_marker,
            surface.dialogo_representacion_path_marker,
            surface.obtener_clave_movil_path_marker,
            surface.obtener_clave_movil_qr_path_marker,
            surface.cancelar_clave_movil_path_marker,
        )
        if any(marker.casefold() in path for marker in clave_path_markers):
            return False
        if target_path in landing_url:
            return True
        return self._same_aeat_application_path(landing_path=path, target_path=target_path)

    @staticmethod
    def _same_aeat_application_path(*, landing_path: str, target_path: str) -> bool:
        target_path_only = urlsplit(target_path).path.casefold()
        landing_parts = tuple(part for part in landing_path.split("/") if part)
        target_parts = tuple(part for part in target_path_only.split("/") if part)
        if len(landing_parts) < 2 or len(target_parts) < 2:
            return False
        if target_parts[0] == "wlpl":
            return landing_parts[:2] == target_parts[:2]
        if target_parts[0] == "sede":
            return landing_parts[:2] == target_parts[:2]
        return False

    @override
    def _attempt_context(self) -> dict[str, object]:
        fresh_login_settings = self._fresh_login_settings()
        identity = unwrap_optional_secret(self._settings.cadrumo_clave_movil_dni_nie).strip()
        try:
            identity_kind = _classify_identity(identity)
        except ClaveMovilConfigurationError:
            identity_kind = "invalid_or_missing"
        auth_mode = "non_qr" if self._settings.cadrumo_clave_prefer_non_qr else "qr"
        auth_route = (
            "clave_movil_non_qr_request" if self._settings.cadrumo_clave_prefer_non_qr else "clave_movil_qr_request"
        )
        context: dict[str, object] = {
            "auth_mode": auth_mode,
            "auth_route": auth_route,
            "identity_kind": identity_kind,
            "clave_identity_configured": bool(identity),
            "clave_identity_fingerprint": _diagnostic_fingerprint(identity),
            "dni_fecha_configured": bool((self._settings.cadrumo_clave_movil_dni_fecha or "").strip()),
            "dni_fecha_fingerprint": _diagnostic_fingerprint(self._settings.cadrumo_clave_movil_dni_fecha),
            "nie_soporte_configured": bool(
                unwrap_optional_secret(self._settings.cadrumo_clave_movil_nie_soporte).strip(),
            ),
            "nie_soporte_fingerprint": _diagnostic_fingerprint(self._settings.cadrumo_clave_movil_nie_soporte),
            "prefer_non_qr": self._settings.cadrumo_clave_prefer_non_qr,
            "headless": fresh_login_settings.cadrumo_browser_headless,
            "timeout_ms": self._settings.cadrumo_clave_movil_timeout_ms,
        }
        context.update(self._active_profile_diagnostic_context(identity))
        return context

    def _active_profile_diagnostic_context(self, provider_identity: str) -> dict[str, object]:
        try:
            from .....adapters.persistence.storage import active_bucket_session_serves
            from .....application.user_profile.profile_record_repository import ProfileRecordRepository
            from .....application.user_profile.projections import record_to_path_values, record_to_values
            from .....application.workflow.profile_bucket_scan import read_profile_bucket_by_id
            from .....core.bucket_pointer import resolve_active_bucket_id
            from .....domain.user_profile.errors import ProfileNotFoundError

            bucket_id = resolve_active_bucket_id()
            pointer = read_profile_bucket_by_id(bucket_id) if bucket_id else None
            context: dict[str, object] = {
                "active_profile_id": "",
                "active_profile_ref": _diagnostic_fingerprint(bucket_id),
                "active_profile_label": "",
                "active_profile_label_present": bool(pointer is not None and pointer.label),
                "active_profile_registered": pointer is not None,
                "profile_record_present": False,
                "profile_tax_id_present": False,
                "profile_tax_id_fingerprint": "",
                "identity_alignment": "profile_tax_id_missing",
            }
            if bucket_id is None:
                context["identity_alignment"] = "no_active_profile"
                return context
            # Only this bucket's own session may serve the read; a foreign
            # session would decrypt under the wrong key.  Without one the record
            # stays sealed: it is encrypted under the profile's own DEK, which
            # exists only inside the session its password envelope unwrapped.
            #
            # The locked case reports itself rather than borrowing the
            # absent-identity token.  This context is read by an operator
            # debugging a Cl@ve identity mismatch, and "the profile carries no
            # tax id" and "the profile's tax id could not be read" call for
            # opposite next steps -- re-enrol the identity, or unlock the
            # profile and re-run.
            if not active_bucket_session_serves(bucket_id):
                context["identity_alignment"] = "profile_record_locked"
                return context
            try:
                record = ProfileRecordRepository.for_current_session(bucket_id).load(bucket_id)
            except ProfileNotFoundError:
                return context

            path_values = record_to_path_values(record)
            profile_identity = tax_id_identity_token(str(path_values.get("identity.tax_id") or ""))
            if not profile_identity:
                selector_values = record_to_values(record)
                profile_identity = str(selector_values.get("tax.id") or "").strip().upper()
            context["profile_record_present"] = True
            context["profile_tax_id_present"] = bool(profile_identity)
            context["profile_tax_id_fingerprint"] = _diagnostic_fingerprint(profile_identity)
            if not provider_identity:
                context["identity_alignment"] = "clave_identity_missing"
            elif not profile_identity:
                context["identity_alignment"] = "profile_tax_id_missing"
            elif same_tax_identifier(profile_identity, provider_identity):
                context["identity_alignment"] = "matches"
            else:
                context["identity_alignment"] = "mismatch"
            return context
        except (ImportError, KeyError, AttributeError, UserProfileError) as exc:
            log.debug("ClaveMovilAuthProvider: profile diagnostic context unavailable: %s", exc, exc_info=True)
            return {
                "active_profile_id": "",
                "active_profile_ref": "",
                "active_profile_label": "",
                "active_profile_label_present": False,
                "active_profile_registered": False,
                "profile_record_present": False,
                "profile_tax_id_present": False,
                "profile_tax_id_fingerprint": "",
                "identity_alignment": "profile_context_unavailable",
            }

    # ── Lifecycle helpers ───────────────────────────────────────────────────

    def _fresh_login_settings(self) -> Settings:
        """Return browser settings suitable for operator-mediated authentication.

        The shared browser default is headless because most AEAT reads consume
        persisted session state.  A fresh Cl@ve Movil login is different: its
        QR branch requires the operator to see and scan the browser page.  Keep
        that interaction contract local to the provider instead of making every
        unrelated browser-backed read headed.
        """
        if not self._settings.cadrumo_browser_headless:
            return self._settings
        return self._settings.model_copy(update={"cadrumo_browser_headless": False})

    async def _resolve_browser_session(self, *, settings: Settings | None = None) -> BrowserSessionPort:
        if self._browser_session_factory is None:
            raise AeatLoginAssertionError(
                "ClaveMovilAuthProvider was constructed without a browser "
                "session factory; pass one via select_provider(..., "
                "browser_session_factory=...).",
            )
        return await self._browser_session_factory(settings or self._settings)

    async def _drop_context(self) -> bool:
        context = self._context
        closed = await self._close_context(context, reason="_drop_context")
        if closed:
            self._context = None
        return closed

    async def _close_context(self, context: BrowserContextPort | None, *, reason: str) -> bool:
        return await close_clave_context(
            context,
            settings=self._settings,
            logger=log,
            owner=f"ClaveMovilAuthProvider:{reason}",
        )

    async def _close_browser_session(self, session: BrowserSessionPort | None) -> bool:
        return await close_clave_browser_session(
            session,
            settings=self._settings,
            logger=log,
            owner="ClaveMovilAuthProvider",
        )

    # ── Encrypted session state ────────────────────────────────────────────

    def _storage_state_path(self) -> Path:
        from .....core.auth_session_keys import aeat_auth_session_storage_state_path
        from .....core.bucket_pointer import require_active_bucket_id

        profile = require_active_bucket_id()
        return aeat_auth_session_storage_state_path(profile, "clave-movil-storage")

    @override
    def _persist_session(
        self,
        storage_state_path: Path,
        *,
        storage_state: Mapping[str, object],
        metadata: ClaveMovilSessionMetadata,
    ) -> None:
        session_store.save(
            storage_state_path,
            storage_state=storage_state,
            metadata=metadata.model_dump(mode="json"),
        )

    def _load_persisted(self, storage_state_path: Path) -> session_store.PersistedBrowserSession:
        persisted = session_store.load(storage_state_path)
        if persisted is None:
            raise AeatLoginAssertionError(
                "no persisted Cl@ve Móvil session; run `aeat config auth status` first",
                translated_message="adapters.auth.clave_movil.errors.no_persisted_session",
            )
        return persisted

    @staticmethod
    def _load_metadata(
        storage_state_path: Path,
        persisted: session_store.PersistedBrowserSession,
    ) -> ClaveMovilSessionMetadata:
        try:
            return ClaveMovilSessionMetadata.model_validate_json(json.dumps(persisted.metadata, default=str))
        except (ValueError, ValidationError) as exc:
            raise AeatLoginAssertionError(
                f"Cl@ve Móvil metadata invalid for {storage_state_path}: {exc}",
                translated_message="adapters.auth.clave_movil.errors.metadata_invalid",
            ) from exc

    def _invalidate_persisted(self, storage_state_path: Path) -> None:
        session_store.delete(storage_state_path)

    def _fresh_login_session(
        self,
        *,
        dni_nie: str,
        authenticated_at: datetime,
        idle_deadline: datetime,
        storage_state_path: Path,
        verification_code: str | None,
        landing_url: str | None,
    ) -> AeatSession:
        return AeatSession(
            authenticated_at=authenticated_at,
            idle_deadline=idle_deadline,
            storage_state_path=storage_state_path,
            identity_nif=dni_nie,
            provider_detail=ClaveMovilSessionDetail(
                dni_nie=dni_nie,
                used_non_qr_fallback=self._settings.cadrumo_clave_prefer_non_qr,
                verification_code=verification_code,
                landing_url=landing_url,
            ),
        )

    # ── Flow ────────────────────────────────────────────────────────────────

    async def _fresh_login_locked(
        self,
        *,
        dni_nie: str,
        storage_state_path: Path,
        target_url: str | None,
    ) -> AeatSession:
        target = target_url or self._default_target_url()
        target_path = self._target_path_from_url(target)
        selector_url = self._selector_url(target_path)
        attempt_context = self._attempt_context()

        session_like = await self._resolve_browser_session(settings=self._fresh_login_settings())
        self._browser_session = session_like
        context, storage_state, landing_url, verification_code = await self._capture_fresh_login_state(
            session_like,
            dni_nie=dni_nie,
            target_path=target_path,
            selector_url=selector_url,
            attempt_context=attempt_context,
            storage_state_path=storage_state_path,
        )

        authenticated_at = now()
        idle_deadline = authenticated_at + AEAT_SESSION_IDLE_TTL
        await self._persist_fresh_session(
            storage_state_path,
            context=context,
            session_like=session_like,
            storage_state=storage_state,
            dni_nie=dni_nie,
            authenticated_at=authenticated_at,
            idle_deadline=idle_deadline,
            verification_code=verification_code,
            landing_url=landing_url,
        )

        session = self._fresh_login_session(
            dni_nie=dni_nie,
            authenticated_at=authenticated_at,
            idle_deadline=idle_deadline,
            storage_state_path=storage_state_path,
            verification_code=verification_code,
            landing_url=landing_url,
        )
        self._browser_session = session_like
        self._context = context
        self._active_session = session
        log.info(
            "ClaveMovilAuthProvider: authenticated non_qr=%s landing=%s",
            self._settings.cadrumo_clave_prefer_non_qr,
            landing_url,
        )
        return session

    async def _capture_fresh_login_state(
        self,
        session_like: BrowserSessionPort,
        *,
        dni_nie: str,
        target_path: str,
        selector_url: str,
        attempt_context: dict[str, object],
        storage_state_path: Path,
    ) -> tuple[BrowserContextPort, Mapping[str, object], str | None, str | None]:
        """Drive the fresh Cl@ve Móvil login page to a captured storage state.

        On failure the context is salvaged before it is closed. AEAT
        presents its representation dialogue only after Cl@ve has
        authenticated, so a failure at that point means the operator's
        approval already succeeded and the context holds a live session -
        and closing it unread was spending a second factor to recover from
        a navigation error. The same is true of a landing wait that times
        out after an approval AEAT has already processed.
        """
        context: BrowserContextPort | None = None
        page: BrowserPagePort | None = None
        try:
            context = await session_like.create_context()
            self._context = context
            page = await context.new_page()
            self._attach_dialog_autodismiss(page)
            await self._navigate_to_selector(
                page,
                selector_url=selector_url,
                target_path=target_path,
                attempt_context=attempt_context,
            )
            verification_code = await self._run_clave_challenge(
                page,
                dni_nie=dni_nie,
                target_path=target_path,
                attempt_context=attempt_context,
            )
            storage_state = await context.storage_state()
            landing_url = getattr(page, "url", None)
            await page.close()
        except Exception as exc:
            if page is not None and not self._exception_already_has_diagnostic(exc):
                try:
                    await self._dump_diagnostic(page, reason=f"fresh-login-exception:{type(exc).__name__}")
                except Exception as _exc:
                    log.debug("ClaveMovilAuthProvider: diagnostic dump suppressed: %s", _exc, exc_info=True)
            await self._salvage_session_before_teardown(
                context,
                storage_state_path=storage_state_path,
                dni_nie=dni_nie,
                page=page,
                target_path=target_path,
            )
            context_closed = await self._close_context(context, reason="fresh-login cleanup")
            self._context = None if context_closed else context
            session_closed = await self._close_browser_session(session_like)
            self._browser_session = None if session_closed else session_like
            raise
        return context, storage_state, landing_url, verification_code

    async def _navigate_to_selector(
        self,
        page: BrowserPagePort,
        *,
        selector_url: str,
        target_path: str,
        attempt_context: dict[str, object],
    ) -> None:
        """Navigate to the AEAT selector page, mapping timeout to a typed error."""
        try:
            await page.goto(selector_url, timeout=self._navigation_timeout_ms)
        except (TimeoutError, PlaywrightTimeoutError) as exc:
            raise ClaveMovilApprovalTimeoutError(
                f"Cl@ve Móvil initial navigation did not reach the AEAT selector within "
                f"{self._navigation_timeout_ms // 1000} seconds.",
                translated_message="adapters.auth.clave_movil.errors.initial_navigation_timeout",
                failure_mode=ClaveMovilFailureMode.INITIAL_NAVIGATION_TIMEOUT,
                context={
                    "timeout_ms": self._navigation_timeout_ms,
                    "target_path": target_path,
                    "selector_url": _url_diagnostic(selector_url),
                    **attempt_context,
                },
            ) from exc

    async def _run_clave_challenge(
        self,
        page: BrowserPagePort,
        *,
        dni_nie: str,
        target_path: str,
        attempt_context: dict[str, object],
    ) -> str | None:
        """Drive the QR / non-QR challenge and wait for the post-auth landing."""
        use_non_qr = self._settings.cadrumo_clave_prefer_non_qr
        log.info(
            "ClaveMovilAuthProvider: starting fresh login mode=%s route=%s identity_kind=%s "
            "identity_alignment=%s profile_present=%s headless=%s",
            attempt_context["auth_mode"],
            attempt_context["auth_route"],
            attempt_context["identity_kind"],
            attempt_context["identity_alignment"],
            attempt_context["profile_tax_id_present"],
            attempt_context["headless"],
        )

        if use_non_qr:
            await self._drive_non_qr_fallback(page, dni_nie)
        else:
            await self._click_clave_movil_button(page)
            await self._raise_if_pending_request_error(page)
        verification_code = await self._extract_verification_code(page)
        await self._assert_push_wait_state(
            page,
            target_path=target_path,
            verification_code=verification_code,
            used_non_qr_fallback=use_non_qr,
        )

        timeout_ms = int(self._settings.cadrumo_clave_movil_timeout_ms)
        _render_progress_banner(
            verification_code=verification_code,
            timeout_seconds=timeout_ms // 1000,
            used_non_qr_fallback=use_non_qr,
        )

        try:
            await self._wait_for_post_auth_landing(page, target_path, timeout_ms)
        except (TimeoutError, PlaywrightTimeoutError) as exc:
            diagnostic_id = await self._dump_diagnostic(page, reason="post-auth-landing-timeout")
            await self._cancel_pending_auth_request(page)
            current_url = getattr(page, "url", "") or ""
            raise ClaveMovilApprovalTimeoutError(
                f"Cl@ve Móvil browser authentication did not complete after {timeout_ms // 1000} seconds. "
                "The driver observed the AEAT browser page but cannot infer the phone/app state.",
                translated_message="adapters.auth.clave_movil.errors.approval_timeout",
                failure_mode=ClaveMovilFailureMode.AUTH_COMPLETION_TIMEOUT,
                context={
                    "timeout_ms": timeout_ms,
                    "current_url": _url_diagnostic(current_url),
                    "target_path": target_path,
                    "diagnostic_id": diagnostic_id,
                    "phone_state": "unknown",
                    "operator_report_required": True,
                    "operator_report_options": (
                        "app_prompted_and_accepted",
                        "app_prompted_not_accepted",
                        "app_did_not_prompt",
                        "operator_did_not_check",
                    ),
                    **attempt_context,
                    "verification_code_present": bool(verification_code),
                },
            ) from exc
        return verification_code

    async def _persist_fresh_session(
        self,
        storage_state_path: Path,
        *,
        context: BrowserContextPort,
        session_like: BrowserSessionPort,
        storage_state: Mapping[str, object],
        dni_nie: str,
        authenticated_at: datetime,
        idle_deadline: datetime,
        verification_code: str | None,
        landing_url: str | None,
    ) -> None:
        """Persist the captured session, cleaning up owned resources on failure."""
        try:
            metadata = ClaveMovilSessionMetadata(
                identity_nif=dni_nie,
                authenticated_at=authenticated_at,
                idle_deadline=idle_deadline,
                storage_state_sha256=session_store.storage_state_sha256(storage_state),
                used_non_qr_fallback=self._settings.cadrumo_clave_prefer_non_qr,
                verification_code=verification_code,
                landing_url=landing_url,
            )
            self._persist_session(
                storage_state_path,
                storage_state=storage_state,
                metadata=metadata,
            )
        except Exception:
            # If the encrypted save fails, remove any partial object so the
            # next authenticate() call sees a clean slate and runs fresh.
            # The cleanup is wrapped so a secondary failure does not mask the
            # original persist exception (mirrors the teardown pattern above).
            try:
                self._invalidate_persisted(storage_state_path)
            except Exception as _cleanup_exc:
                log.debug(
                    "ClaveMovilAuthProvider: _invalidate_persisted during persist-failure cleanup suppressed: %s",
                    _cleanup_exc,
                    exc_info=True,
                )
            context_closed = await self._close_context(context, reason="persist-failure cleanup")
            self._context = None if context_closed else context
            session_closed = await self._close_browser_session(session_like)
            self._browser_session = None if session_closed else session_like
            raise

    async def _resume_locked(
        self,
        storage_state_path: Path,
        *,
        target_url: str | None,
    ) -> AeatSession:
        persisted = self._load_persisted(storage_state_path)
        metadata = self._load_metadata(storage_state_path, persisted)
        if metadata.idle_deadline <= now():
            raise AeatLoginAssertionError(
                "Cl@ve Móvil session past idle deadline",
                translated_message="adapters.auth.clave_movil.errors.session_expired",
            )
        observed_sha256 = persisted.storage_state_sha256
        if observed_sha256 != metadata.storage_state_sha256:
            raise AeatLoginAssertionError(
                "Cl@ve Móvil storage-state hash mismatch",
                translated_message="adapters.auth.clave_movil.errors.storage_state_hash_mismatch",
            )

        session_like = await self._resolve_browser_session()
        self._browser_session = session_like
        context: BrowserContextPort | None = None
        try:
            context = await session_like.create_context(
                storage_state=persisted.storage_state,
            )
            self._context = context
            session = AeatSession(
                authenticated_at=metadata.authenticated_at,
                idle_deadline=metadata.idle_deadline,
                storage_state_path=storage_state_path,
                identity_nif=metadata.identity_nif,
                provider_detail=ClaveMovilSessionDetail(
                    dni_nie=metadata.identity_nif,
                    used_non_qr_fallback=metadata.used_non_qr_fallback,
                    verification_code=metadata.verification_code,
                    landing_url=metadata.landing_url,
                ),
            )
            self._browser_session = session_like
            self._context = context
            self._active_session = session

            assertion = await self._verify_in_work(session, target_url=target_url)
            if not assertion.is_valid:
                raise AeatLoginAssertionError(
                    "Cl@ve Móvil resume failed live verification: "
                    f"status={assertion.status_code} error={assertion.error_message!r}",
                )
            refreshed = session.model_copy(
                update={
                    "authenticated_at": assertion.attempted_at,
                    "idle_deadline": assertion.attempted_at + AEAT_SESSION_IDLE_TTL,
                },
            )
            self._active_session = refreshed
            refreshed_metadata = metadata.model_copy(
                update={
                    "authenticated_at": refreshed.authenticated_at,
                    "idle_deadline": refreshed.idle_deadline,
                },
            )
            self._persist_session(
                storage_state_path,
                storage_state=persisted.storage_state,
                metadata=refreshed_metadata,
            )
            log.info(
                "ClaveMovilAuthProvider: resumed landing=%s",
                assertion.assertion_detail.landing_url
                if isinstance(assertion.assertion_detail, ClaveMovilLoginAssertionDetail)
                else None,
            )
            return refreshed
        except Exception:  # cleanup on resume error then re-raise; Playwright+CadrumoError undocumented
            context_closed = await self._close_context(context, reason="resume cleanup")
            self._browser_session = None
            self._context = None if context_closed else context
            self._active_session = None
            if not await self._close_browser_session(session_like):
                self._browser_session = session_like
            raise


__all__ = [
    "ClaveMovilAuthProvider",
]
