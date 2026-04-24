"""Factory wiring a live :class:`aeat.status.StatusReader` from CLI settings.

Loads a persisted auth session (certificate or Cl@ve) from disk and
yields an authenticated :class:`StatusReader` for the CLI
``--from-aeat`` code paths (#170, #272). Deep auth-stack integration
is kept narrow by deferring ``BrowserSession`` and ``CertificateBackend``
wiring to a pluggable hook — the live factory is therefore
test-friendly: tests substitute a fake reader via monkeypatch, and
production wiring of ``aeat.browser.BrowserSession`` +
``aeat.auth.preload_into_browser_context`` lands in a dedicated
follow-up.

Charter #116 (no-write mandate): the yielded :class:`StatusReader`
inherits the safety contract of its module — all navigations are safe
``page.goto(..., wait_until="domcontentloaded")`` GETs, and the
reader's public surface contains no write verbs.
"""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator

from ..auth import AuthProviderKind
from ..config import Settings
from ..errors import AeatError
from ..status import StatusReader
from .auth import _session as auth_session


class LiveSessionUnavailableError(AeatError):
    """Raised when ``--from-aeat`` is invoked without a usable live session."""


async def _resolve_live_reader(
    settings: Settings,
    provider_kind: AuthProviderKind | None,
) -> StatusReader:
    """Resolve a live :class:`StatusReader` or raise with a clear message.

    Currently the production path is gated on the deeper auth-stack
    integration work and raises a :class:`LiveSessionUnavailableError`
    that Kent-facing commands surface as a ``typer.BadParameter``.
    Tests reach the success branch by monkeypatching
    :func:`build_live_status_reader` rather than this helper.
    """
    persisted = auth_session.load(settings, provider_kind)
    if persisted is None:
        raise LiveSessionUnavailableError(
            "No authenticated AEAT session found. Run `aeat auth login` first, then retry with `--from-aeat`.",
        )
    raise LiveSessionUnavailableError(
        "Live ``--from-aeat`` wiring is pending follow-up. "
        "Use the file-backed source or monkeypatch build_live_status_reader in tests.",
    )


@contextlib.asynccontextmanager
async def build_live_status_reader(
    settings: Settings,
    *,
    provider_kind: AuthProviderKind | None = None,
) -> AsyncIterator[StatusReader]:
    """Yield an authenticated :class:`StatusReader` against the live Sede.

    Args:
        settings: The resolved :class:`Settings`.
        provider_kind: Optional pin of the auth provider; when omitted
            the first persisted sidecar is used in the order declared
            by :func:`aeat.cli.auth._session.load`.

    Yields:
        A ready-to-use :class:`StatusReader`.

    Raises:
        LiveSessionUnavailableError: No persisted session available,
            or the auth-stack wiring hook is not yet implemented in
            this build.
    """
    reader = await _resolve_live_reader(settings, provider_kind)
    try:
        yield reader
    finally:
        await reader.close()


__all__ = ["LiveSessionUnavailableError", "build_live_status_reader"]
