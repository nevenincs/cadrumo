"""Adapter-layer namespace for external and persistence infrastructure.

This root package is intentionally import-light and exports no concrete adapter
classes. Import focused child facades instead: :mod:`aeat.adapters.inbound` for
parsers and import pipelines, :mod:`aeat.adapters.outbound` for integrations
with external services, and :mod:`aeat.adapters.persistence` for profile and
secure-storage adapters.

Application services own orchestration and domain authorities own business
semantics. Adapter packages translate between those internal contracts and
external artefacts such as PDFs, financial statements, AEAT Sede pages, browser
sessions, Google services, LLM providers, and encrypted local storage.
"""
