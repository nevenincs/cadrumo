"""Modelo registry conformance governance surface (not shipped in the wheel).

Answers "what is the state of modelo X, what drifted, what is unreviewed" for
every modelo revision the registry declares, by rendering the shipped
conformance fact libraries rather than recomputing them. Review and engineering
provenance is the one axis nothing can derive, so it is DECLARED per revision
and written from here; every other signal is derived and therefore never staler
than the tree.

Run via ``python -m dev.registry.conformance``:

* ``report [--json]`` — every conformance axis, one row per modelo revision.
* ``coverage [--json]`` — per-axis measured counts against real populations.
* ``audit [--check]`` — the ratchet comparison.
* ``closure [--check]`` — the derived temporal, source, and filing release
  predicate; its check exit blocks an incomplete shipped-registry claim.
* ``stamp`` — write a revision's declared governance scalars.

``report`` and ``coverage`` always exit 0, deliberately: they show a picture
that is currently bad, and a report that refused to render would leave the
backlog unread. A fact earns gate teeth when its worklist empties, not before.

Major declarations:

* :class:`~dev.registry.conformance.manager.ConformanceReport` — the rendered
  per-revision report.
* :class:`~dev.registry.conformance.manager.CoverageReport` — per-axis coverage.
* :class:`~dev.registry.conformance.manager.ConformanceAuditResult` — the
  ratchet comparison against the committed baseline.
* :func:`~dev.registry.conformance.manager.load_conformance_report` — composes
  the bundled registry's report, validated or degraded.

See Also:
    :func:`~application.registry.audit_bundled_registry_conformance`
        Shipped composer this package renders.
    :mod:`~dev.registry.conformance.cli`
        Typer surface for the five governance verbs.
    :func:`~domain.calculations.registry.build_support_matrix`
        Shipped per-modelo capability authority the report's support probe reads.
"""

from __future__ import annotations

from .authorities import RegistryClosureAuthorities, canonical_live_registry_closure_authorities
from .closure import (
    RegistryClosureJoinDisagreement,
    RegistryClosurePredicateRefusal,
    RegistryClosureReleaseResult,
    RegistryClosureReport,
    RegistryClosureRevisionReport,
    build_registry_closure_report,
    check_registry_closure_release,
    load_registry_closure_report,
    render_registry_closure_report,
)
from .manager import (
    AUDITED_LOCALES,
    NOT_MEASURED,
    ConformanceAuditResult,
    ConformanceReport,
    CoverageReport,
    build_conformance_report,
    build_coverage_report,
    load_conformance_report,
    render_audit,
    render_coverage,
    render_report,
    reset_conformance_cache,
)

__all__ = [
    "AUDITED_LOCALES",
    "NOT_MEASURED",
    "ConformanceAuditResult",
    "ConformanceReport",
    "CoverageReport",
    "RegistryClosureAuthorities",
    "RegistryClosureJoinDisagreement",
    "RegistryClosurePredicateRefusal",
    "RegistryClosureReleaseResult",
    "RegistryClosureReport",
    "RegistryClosureRevisionReport",
    "build_conformance_report",
    "build_coverage_report",
    "build_registry_closure_report",
    "canonical_live_registry_closure_authorities",
    "check_registry_closure_release",
    "load_conformance_report",
    "load_registry_closure_report",
    "render_audit",
    "render_coverage",
    "render_registry_closure_report",
    "render_report",
    "reset_conformance_cache",
]
