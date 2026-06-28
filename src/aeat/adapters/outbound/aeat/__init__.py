"""Outbound adapter package for AEAT integrations.

This package is the adapter-layer entry point for code that talks to the
Agencia Tributaria. Subpackages keep external concerns separated:

* :mod:`aeat.adapters.outbound.aeat.auth` owns certificate and Cl@ve Móvil
  authentication plus the :class:`~aeat.adapters.outbound.aeat.auth.AeatSession`
  records consumed by live readers.
* :mod:`aeat.adapters.outbound.aeat.browser` owns Playwright session creation,
  site-health classification, and browser failure envelopes.
* :mod:`aeat.adapters.outbound.aeat.sede` owns authenticated, read-only Sede
  navigation, downloads, parsing, and observation records.
* :mod:`aeat.adapters.outbound.aeat.verify` owns public CSV verification through
  the reviewed read-only Sede verifier.
* :mod:`aeat.adapters.outbound.aeat.export` owns read-only export and preflight
  helpers.

See Also:
    :mod:`aeat.adapters.outbound.aeat._playwright`
        Import-safe Playwright exception aliases shared by browser and Sede
        modules when the optional ``browser`` extra is absent.
    :mod:`aeat.adapters.outbound`
        Parent outbound adapter layer for all external counterparts.
"""
