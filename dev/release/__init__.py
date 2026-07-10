"""Developer release-readiness gates for `aeat-cli` (RC soak, audit-state, rollback).

See Also:
    :mod:`~dev.release.readiness`
        Audit-state gate implementation invoked before release apply.
    :func:`~dev.release.readiness.build_report`
        Programmatic entrypoint that evaluates every readiness check.
    :class:`~dev.release.readiness.ReadinessReport`
        Machine-readable aggregate returned by the release gate.
"""
