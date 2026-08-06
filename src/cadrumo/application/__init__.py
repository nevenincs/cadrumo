"""Application layer orchestration boundary.

Application services coordinate :mod:`domain` authorities with
:mod:`adapters` infrastructure and :mod:`core` primitives. This layer
is allowed to wire concrete persistence, inbound, and outbound adapters; domain
and core code must not depend back on it, and entrypoint modules should stay
thin transports over the public application facades.

Regulatory formulas, schema authority, and legal classification stay in domain
packages (especially :mod:`domain.calculations.registry`). Application
services assemble inputs, persistence, readiness checks, and operator workflows
around those authorities; they should not become parallel tax-law engines.

Public subpackage boundaries such as :mod:`modelo` and
:mod:`user_profile` are the preferred import surfaces for
cross-package consumers. Import from those package facades, not private
``_...`` implementation modules; the facade ``__all__`` contract is the
service boundary. The root package intentionally stays import-light so
state-free CLI paths do not pay for registry, storage, browser, or workflow
subtrees unless a specific command asks for them.

Operator state and readiness converge through
:mod:`state_projection`: the
:class:`OperatorStateProjection` built by
:func:`build_operator_state_projection`
feeds overview status, auth status/test, and modelo readiness without giving
those facades separate store-reading paths. Workflow orchestration remains in
:mod:`workflow`; live AEAT access stays read-only under
:mod:`live`; and diagnostics / repair surfaces stay in
:mod:`diagnostics` and
:mod:`repair_integrity` so operator health checks do not leak
into domain authorities.

See Also:
    :mod:`modelo`:
        Modelo work-unit, calculation, verification, filing, export, and
        reconciliation facade.
    :mod:`filing`:
        Registry-backed local filing draft construction, review, export, and
        justificante import facade.
    :mod:`user_profile`:
        Lazy profile lifecycle, validation, storage-session, and projection
        facade.
    :mod:`workflow`:
        Workflow run, active-profile, bucket-discovery, and resume facade.
    :mod:`auth`:
        Operator auth configuration, status/test, session, and preflight
        facade.
    :mod:`overview`:
        Read-only operator dashboard projections built from state, deadlines,
        and filing evidence.
    :mod:`aggregation`:
        Calculation source mesh that supplies registry binding values from
        ledger, invoice, profile, relation, and carry inputs.
    :mod:`registry`:
        Read-only registry tree, corpus, manual, and filed-state verification
        services over validated registry authority.
    :mod:`operator_surface`:
        Backend-owned operator capability contract consumed by CLI adapters and
        automation surfaces.
    :mod:`ledger`:
        Bucket-scoped transaction lifecycle and ledger preflight facade used by
        modelo calculation readiness.
"""
