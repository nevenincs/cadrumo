"""Outbound adapter package for AEAT integrations.

This package is the adapter-layer entry point for code that talks to the
Agencia Tributaria. Subpackages keep external concerns separated:

* :mod:`adapters.outbound.aeat.auth` owns certificate and Cl@ve Móvil
  authentication plus the :class:`adapters.outbound.aeat.auth.AeatSession`
  records consumed by live readers.
* :mod:`adapters.outbound.aeat.browser` owns Playwright session creation,
  site-health classification, and browser failure envelopes.
* :mod:`adapters.outbound.aeat.sede` owns authenticated, read-only Sede
  navigation, downloads, parsing, and observation records.
* :mod:`adapters.outbound.aeat.verify` owns public CSV verification through
  the reviewed read-only Sede verifier.
* :mod:`adapters.outbound.aeat.export` owns read-only export and preflight
  helpers.

See Also:
    :mod:`adapters.outbound.aeat._playwright`
        Import-safe Playwright exception aliases shared by browser and Sede
        modules when the optional ``browser`` extra is absent.
    :mod:`application.auth`
        Application facade that selects auth providers and owns operator-facing
        session lifecycle commands.
    :mod:`application.live`
        Read-only acquisition facade that consumes Sede, browser, and
        verification adapters.
    :mod:`core.access_gate`
        Core live-read gate and permanent live-write refusal applied before
        authenticated AEAT access proceeds.
    :mod:`adapters.outbound`
        Parent outbound adapter layer for all external counterparts.
"""

from __future__ import annotations

from ._operator_progress import emit_operator_progress, operator_progress_sink

__all__ = ["emit_operator_progress", "operator_progress_sink"]
