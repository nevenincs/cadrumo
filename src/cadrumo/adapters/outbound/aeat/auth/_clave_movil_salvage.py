"""Post-failure session-salvage mixin for the Cl@ve Móvil auth provider.

A fresh Cl@ve Móvil login is a human-in-the-loop, single-use second factor:
once the operator approves the phone prompt, AEAT will not reissue a fresh
challenge for the same identity until the pending request expires or is
explicitly cancelled. When the browser driver fails *after* that approval —
a navigation error on the representation dialogue, a landing wait that times
out on an already-processed approval — closing the context unread would
throw away the approval the operator already gave and force a second,
avoidable Cl@ve prompt.

:class:`_ClaveMovilSessionSalvageMixin` supplies the best-effort repair:
persist whatever authenticated state the failing context holds before it is
torn down, so the next resume attempt can probe it rather than starting a
fresh login outright. This is safety code, not an optimisation — its
behaviour must not change when moved, only its module.
"""

from __future__ import annotations

import abc
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING

from .....application.auth.protocols import BrowserContextPort, BrowserPagePort
from .....core.logging import get_logger
from .....core.time.clock import now
from . import session_store as session_store
from .authenticator import AEAT_SESSION_IDLE_TTL
from .clave_movil_metadata import ClaveMovilSessionMetadata

if TYPE_CHECKING:
    from .....core.config import Settings

log = get_logger(__name__)


class _ClaveMovilSessionSalvageMixin(abc.ABC):
    """Abstract contract consumed by the Cl@ve Móvil post-failure salvage helpers.

    Concrete subclasses (:class:`ClaveMovilAuthProvider`) supply the
    configured :class:`Settings` and the landing-authentication predicate and
    encrypted-persistence primitive the salvage path reuses rather than
    re-implementing.
    """

    # ── Abstract contract consumed by the salvage helpers ───────────────────
    # Instance-variable annotation: concrete subclasses assign this in
    # ``__init__``. Declared here so type checkers resolve ``self._settings``
    # without reaching into the subclass, mirroring ``_ClaveMovilPageFlowMixin``.

    _settings: Settings

    @abc.abstractmethod
    def _is_authenticated_aeat_landing(self, *, landing_url: str, target_path: str) -> bool:
        """Return True for a protected AEAT page reached after Cl@ve dispatch."""

    @abc.abstractmethod
    def _persist_session(
        self,
        storage_state_path: Path,
        *,
        storage_state: Mapping[str, object],
        metadata: ClaveMovilSessionMetadata,
    ) -> None:
        """Persist the captured storage state and metadata to the encrypted session store."""

    # ── Salvage helpers ──────────────────────────────────────────────────────

    def _salvageable_landing_url(self, observed_url: str | None, *, target_path: str) -> str | None:
        """Return ``observed_url`` when it is a landing a later probe may reuse, else ``None``.

        A salvaged session's recorded landing URL is not decoration: it
        becomes :attr:`ClaveMovilSessionDetail.landing_url`, which
        :meth:`_verify_in_work` resolves as the probe target when the caller
        names none. So whatever is recorded here is navigated to on the next
        resume.

        A failing fresh login is, by construction, still somewhere in the
        Cl@ve flow — the access selector, the representation dialogue, or the
        push-wait page. Recording one of those makes the salvaged session
        probe back into the flow it was salvaged out of, and
        :meth:`_is_authenticated_aeat_landing` refuses every Cl@ve marker, so
        that probe cannot report a valid session however live the cookies
        are. A salvaged session recorded that way is therefore rejected on
        every resume: the repair persists a session the reuse path is
        guaranteed to refuse.

        Recording ``None`` does not promise the resume succeeds. It gives the
        salvaged session the ordinary persisted-session route — the selector
        URL for the default target, which AEAT dispatches through when the
        cookies are still good — rather than a target whose refusal is
        settled before the navigation runs.

        Args:
            observed_url: The URL the failing page was on, if any.
            target_path: The path the login was navigating toward.

        Returns:
            The observed URL when it is an authenticated AEAT landing, else ``None``.
        """
        if not observed_url:
            return None
        if not self._is_authenticated_aeat_landing(landing_url=observed_url, target_path=target_path):
            return None
        return observed_url

    async def _salvage_session_before_teardown(
        self,
        context: BrowserContextPort | None,
        *,
        storage_state_path: Path,
        dni_nie: str,
        page: BrowserPagePort | None,
        target_path: str,
    ) -> None:
        """Persist whatever session the failing context holds, if any.

        Best-effort by construction: every failure here is logged and
        swallowed so the original login error stays the one the caller
        sees. Salvaging must never turn a diagnosable failure into a
        confusing one.

        A state carrying no cookies is not saved. That is a fact about the
        capture rather than a guess about the operator: a context that
        never reached an authenticated page has nothing to reuse, and
        writing it would leave a record the reuse probe rejects at the
        cost of a browser launch.

        A salvaged session is NOT assumed usable. It is persisted so the
        reuse path can judge it, and that path already probes before
        trusting - an unusable one is rejected and the caller falls
        through to a fresh login, which is exactly what happens today.
        The upside is asymmetric: at worst a wasted probe, at best the
        operator keeps the approval they already gave.

        The landing URL is recorded only when a later probe may reuse it;
        :meth:`_salvageable_landing_url` states why a Cl@ve-flow URL is
        dropped rather than stored.

        Args:
            context: The failing browser context, if one was created.
            storage_state_path: Encrypted session path to write.
            dni_nie: The identity the login was run for.
            page: The failing page, if one was opened.
            target_path: The path the login was navigating toward.
        """
        if context is None:
            return
        try:
            storage_state = await context.storage_state()
            cookies = storage_state.get("cookies") if isinstance(storage_state, Mapping) else None
            if not cookies:
                log.debug("ClaveMovilAuthProvider: nothing to salvage, captured state carries no cookies")
                return
            authenticated_at = now()
            metadata = ClaveMovilSessionMetadata(
                identity_nif=dni_nie,
                authenticated_at=authenticated_at,
                idle_deadline=authenticated_at + AEAT_SESSION_IDLE_TTL,
                storage_state_sha256=session_store.storage_state_sha256(storage_state),
                used_non_qr_fallback=self._settings.cadrumo_clave_prefer_non_qr,
                verification_code=None,
                landing_url=self._salvageable_landing_url(
                    getattr(page, "url", None),
                    target_path=target_path,
                ),
            )
            self._persist_session(storage_state_path, storage_state=storage_state, metadata=metadata)
        except Exception as exc:
            log.debug(
                "ClaveMovilAuthProvider: post-auth session salvage suppressed: %s",
                exc,
                exc_info=True,
            )
            return
        log.info("ClaveMovilAuthProvider: salvaged the authenticated session from a failed post-auth navigation")


__all__ = ["_ClaveMovilSessionSalvageMixin"]
