"""Adapter-layer namespace for infrastructure-facing integrations.

This package is the outer infrastructure layer in the hexagonal layout. It is
intentionally import-light and exports no concrete adapter classes; callers
should import focused child facades such as :mod:`inbound` for
document and statement ingestion, :mod:`outbound` for external
service integrations, and :mod:`persistence` for profile and
secure-storage adapters.

Application services own orchestration through :mod:`application`, and
domain authorities own business semantics through :mod:`domain`. Adapter
packages translate between those internal contracts and external artefacts:
PDFs, financial statements, AEAT Sede pages, browser sessions, Google services,
LLM providers, local profile stores, and encrypted storage. They may depend on
core primitives from :mod:`core`, but lower layers must not import adapter
internals to recover persistence or transport behavior.

See Also:
    :mod:`inbound`
        Parser and import-pipeline boundary for external files entering the
        application.
    :mod:`outbound`
        Remote-service and export boundary for integrations leaving the
        application.
    :mod:`persistence`
        Concrete persistence boundary for profile, storage, SQL, blob, and
        secure-object infrastructure.
    :mod:`application`
        Use-case orchestration layer that wires adapters to domain authorities.
    :mod:`domain`
        Business authority layer whose records adapters populate or persist.
    :mod:`core`
        Layer-neutral primitives and policies adapters may consume without
        depending inward on application workflows.
"""
