"""Inbound adapter namespace for external artefact import.

This package root exports no parser classes. Focused child packages own the
actual import contracts: :mod:`declaracion` for filed declaration PDFs,
:mod:`borrador` for Renta draft PDFs, :mod:`justificante` for receipt metadata,
:mod:`pdf` for shared PDF helpers, :mod:`financial` for bank-statement providers,
:mod:`identity` for Spanish identity inputs, and :mod:`sanitizer` for
deterministic fixture hygiene.

Inbound adapters translate outside artefacts into strict records consumed by
:mod:`application` and :mod:`domain`. They observe and normalize source files;
they do not own application workflow, persistence policy, tax-law
classification, or CLI presentation.

See Also:
    :mod:`adapters`
        Parent infrastructure boundary that explains the adapter layer's place
        in the architecture.
    :mod:`financial.providers`
        Provider registry for CSV, OFX, XLSX, and N26 PDF bank statements.
    :mod:`sanitizer`
        PDF sanitisation pipeline used to prepare committed regression
        artefacts without leaking operator PII.
    :mod:`domain.justificante`
        Domain receipt metadata records populated by the justificante parser.
    :mod:`application.filing`
        Application import workflows that decide how parsed filing evidence
        participates in local drafts and audit baselines.
    :mod:`application.ledger`
        Ledger import surface that consumes financial-provider transactions and
        evidence references.
    :mod:`domain.transactions`
        Domain transaction records populated by financial import providers.
"""
