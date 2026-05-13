"""Provider registry helpers for the ``aeat config auth`` CLI surface.

Hosts :mod:`aeat.entrypoints.cli.auth._registry` — the single source
of truth for auth provider ordering, default resolution, and
user-facing rendering used by the ``aeat config auth`` subapp.
Provider error classes (``NoConfiguredProviderError``,
``UnknownProviderError``, ``ProviderUnavailableError``) declared in
``_registry`` are registered in the central error-code registry.
"""
