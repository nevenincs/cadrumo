"""Read-only CSV verification against AEAT's Sede electrónica.

The :func:`verify_csv` helper is opt-in: it only runs when the caller supplies
or constructs a :class:`adapters.outbound.aeat.browser.DefaultBrowserSession`.
It is guarded by :class:`domain.calculations.registry.RemoteStateGuardPolicy`
and never mutates AEAT-side state. The contract is:

* open the CSV-keyed Sede viewer,
* read back the server response,
* return ``True`` iff AEAT confirms the document as valid.

The function degrades gracefully when a browser cannot be
constructed and surfaces the underlying error to the caller via
:class:`domain.justificante.JustificanteVerificationError`.

Public surface: :func:`verify_csv` plus the Playwright protocol types
(:class:`VerifyBrowserPageLike`, :class:`VerifyBrowserContextLike`,
:class:`VerifyBrowserSessionLike`, and :class:`VerifyBrowserSessionFactory`)
shared by the concrete browser adapters.

See Also:
    :func:`adapters.outbound.aeat.browser.default_browser_session_factory`
        Production factory used by :data:`DEFAULT_BROWSER_SESSION_FACTORY`.
    :class:`adapters.outbound.aeat.browser.BrowserSession`
        Concrete browser session whose context/page surface these protocols
        mirror.
    :func:`domain.calculations.registry.assert_remote_operation_allowed`
        Guard used to allow only the reviewed read-only CSV verification URL.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
