"""Application layer orchestration boundary.

Application services coordinate :mod:`aeat.domain` authorities with
:mod:`aeat.adapters` infrastructure and :mod:`aeat.core` primitives. This layer
is allowed to wire concrete persistence, inbound, and outbound adapters; domain
and core code must not depend back on it, and entrypoint modules should stay
thin transports over the public application facades.

Public subpackage boundaries such as :mod:`aeat.application.modelo` and
:mod:`aeat.application.user_profile` are the preferred import surfaces for
cross-package consumers. Import from those package facades, not private
``_...`` implementation modules; the facade ``__all__`` contract is the
service boundary. The root package intentionally stays import-light so
state-free CLI paths do not pay for registry, storage, browser, or workflow
subtrees unless a specific command asks for them.

See Also:
    :mod:`aeat.application.modelo`:
        Modelo work-unit, calculation, verification, filing, export, and
        reconciliation facade.
    :mod:`aeat.application.filing`:
        Registry-backed local filing draft construction, review, export, and
        justificante import facade.
    :mod:`aeat.application.user_profile`:
        Lazy profile lifecycle, validation, storage-session, and projection
        facade.
"""
