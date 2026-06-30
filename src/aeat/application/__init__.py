"""Application layer orchestration boundary.

Application services coordinate :mod:`aeat.domain` authorities with
:mod:`aeat.adapters` infrastructure and :mod:`aeat.core` primitives. This layer
is allowed to wire concrete persistence, inbound, and outbound adapters; domain
and core code must not depend back on it, and entrypoint modules should stay
thin transports over the public application facades.

Regulatory formulas, schema authority, and legal classification stay in domain
packages (especially :mod:`aeat.domain.calculations.registry`). Application
services assemble inputs, persistence, readiness checks, and operator workflows
around those authorities; they should not become parallel tax-law engines.

Public subpackage boundaries such as :mod:`aeat.application.modelo` and
:mod:`aeat.application.user_profile` are the preferred import surfaces for
cross-package consumers. Import from those package facades, not private
``_...`` implementation modules; the facade ``__all__`` contract is the
service boundary. The root package intentionally stays import-light so
state-free CLI paths do not pay for registry, storage, browser, or workflow
subtrees unless a specific command asks for them.

Operator state and readiness converge through
:mod:`aeat.application.state_projection`: the
:class:`~aeat.application.state_projection.OperatorStateProjection` built by
:func:`~aeat.application.state_projection.build_operator_state_projection`
feeds overview status, auth status/test, and modelo readiness without giving
those facades separate store-reading paths. Workflow orchestration remains in
:mod:`aeat.application.workflow`; live AEAT access stays read-only under
:mod:`aeat.application.live`; and diagnostics / repair surfaces stay in
:mod:`aeat.application.diagnostics` and
:mod:`aeat.application.repair_integrity` so operator health checks do not leak
into domain authorities.

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
    :mod:`aeat.application.workflow`:
        Workflow run, active-profile, bucket-discovery, and resume facade.
    :mod:`aeat.application.auth`:
        Operator auth configuration, status/test, session, and preflight
        facade.
    :mod:`aeat.application.overview`:
        Read-only operator dashboard projections built from state, deadlines,
        and filing evidence.
    :mod:`aeat.application.aggregation`:
        Calculation source mesh that supplies registry binding values from
        ledger, invoice, profile, relation, and carry inputs.
    :mod:`aeat.application.ledger`:
        Bucket-scoped transaction lifecycle and ledger preflight facade used by
        modelo calculation readiness.
"""
