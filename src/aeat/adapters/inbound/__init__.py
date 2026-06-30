"""Inbound adapter namespace for external artefact import.

This package root exports no parser classes. Focused child packages own the
actual import contracts: :mod:`aeat.adapters.inbound.declaracion` for filed
declaration PDFs, :mod:`aeat.adapters.inbound.borrador` for Renta draft PDFs,
:mod:`aeat.adapters.inbound.justificante` for receipt metadata,
:mod:`aeat.adapters.inbound.pdf` for shared PDF helpers,
:mod:`aeat.adapters.inbound.financial` for bank-statement providers,
:mod:`aeat.adapters.inbound.identity` for Spanish identity inputs, and
:mod:`aeat.adapters.inbound.sanitizer` for deterministic fixture hygiene.

Inbound adapters translate outside artefacts into strict records consumed by
:mod:`aeat.application` and :mod:`aeat.domain`. They observe and normalize
source files; they do not own application workflow, persistence policy, tax-law
classification, or CLI presentation.

See Also:
    :mod:`aeat.adapters`
        Parent infrastructure boundary that explains the adapter layer's place
        in the architecture.
    :mod:`aeat.adapters.inbound.financial.providers`
        Provider registry for CSV, OFX, XLSX, and N26 PDF bank statements.
    :mod:`aeat.adapters.inbound.sanitizer`
        PDF sanitisation pipeline used to prepare committed regression
        artefacts without leaking operator PII.
    :mod:`aeat.domain.transactions`
        Domain transaction records populated by financial import providers.
"""
