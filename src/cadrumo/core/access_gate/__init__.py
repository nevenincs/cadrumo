"""Unified access gate for live AEAT reads and permanent write refusal.

The gate consolidates live-test preconditions for pytest-driven live
reads while keeping operator-facing live reads as operational surfaces.
Live AEAT writes are permanently forbidden, so the write-side helper
always raises a typed refusal. The gate is consumed by the repair CLI
for surfacing a "Live access gate" row and by every live-read module
(filing history, missing-filing detection, AEAT messages, IVA balance
tracking) that needs a typed precondition rather than per-call-site
``if os.environ[...] != "1"`` boilerplate in tests.

The gate is always constructed inline from a
:class:`core.config.Settings` instance at the call site. It is
never injected via a constructor, never stored as state on engines,
and never passed as a kwarg that could make a write path
substitutable. That anti-injection stance preserves the
"no substitutable dependency on the write-gate" property: tests
cannot swap the gate for a no-op because there is no seam to swap
through.

See Also:
    :class:`AeatAccessGate`
        Inline gate object used by read-only live surfaces and permanent
        write-refusal checks.
    :class:`AuthorizationManifest`
        Directory-mode modelo authorization manifest re-exported by this
        package for registry capability derivation.
    :mod:`application.live`
        Read-only application-live facade that calls the read gate before
        opening AEAT remote surfaces.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
