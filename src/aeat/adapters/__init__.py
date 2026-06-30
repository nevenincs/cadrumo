"""Adapter-layer namespace for infrastructure-facing integrations.

This package is the outer infrastructure layer in the hexagonal layout. It is
intentionally import-light and exports no concrete adapter classes; callers
should import focused child facades such as :mod:`aeat.adapters.inbound` for
document and statement ingestion, :mod:`aeat.adapters.outbound` for external
service integrations, and :mod:`aeat.adapters.persistence` for profile and
secure-storage adapters.

Application services own orchestration through :mod:`aeat.application`, and
domain authorities own business semantics through :mod:`aeat.domain`. Adapter
packages translate between those internal contracts and external artefacts:
PDFs, financial statements, AEAT Sede pages, browser sessions, Google services,
LLM providers, local profile stores, and encrypted storage. They may depend on
core primitives from :mod:`aeat.core`, but lower layers must not import adapter
internals to recover persistence or transport behavior.

See Also:
    :mod:`aeat.adapters.inbound`
        Parser and import-pipeline boundary for external files entering the
        application.
    :mod:`aeat.adapters.outbound`
        Remote-service and export boundary for integrations leaving the
        application.
    :mod:`aeat.adapters.persistence`
        Concrete persistence boundary for profile, storage, SQL, blob, and
        secure-object infrastructure.
    :mod:`aeat.application`
        Use-case orchestration layer that wires adapters to domain authorities.
"""
