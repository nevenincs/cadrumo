"""Audit registry test enrollment literals against declared law-selectable revisions."""

from __future__ import annotations

from pathlib import Path

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from dev._paths import REPO_ROOT

from ..temporal_coverage import compose_temporal_coverage
from .temporal_enrollment_findings import ENROLLMENT_EXCLUSION_PINS, _declaration_finding
from .temporal_enrollment_models import (
    REGISTRY_TEST_ROOT,
    LiteralEnrollmentAudit,
    LiteralEnrollmentDeclaration,
    LiteralEnrollmentFinding,
    RegistryRevisionSubject,
    TemporalEnrollmentExclusionPin,
)
from .temporal_enrollment_source import _literal_enrollment_declarations

__all__ = [
    "audit_registry_test_enrollment_literals",
    "audit_temporal_enrollment_source",
    "law_selectable_revision_subjects",
]


def law_selectable_revision_subjects(
    authority: ValidatedRegistryAuthority,
) -> frozenset[RegistryRevisionSubject]:
    """Derive the complete law-selectable registered-revision denominator."""
    report = compose_temporal_coverage(authority=authority)
    return frozenset(RegistryRevisionSubject(summary.modelo, summary.revision) for summary in report.revision_summaries)


def audit_registry_test_enrollment_literals(
    authority: ValidatedRegistryAuthority,
    *,
    root: Path = REGISTRY_TEST_ROOT,
    pins: tuple[TemporalEnrollmentExclusionPin, ...] = ENROLLMENT_EXCLUSION_PINS,
) -> LiteralEnrollmentAudit:
    """Audit every literal revision enumeration declared under registry tests.

    The sweep asks what it can establish about a collection it did not author:
    that every identity it names still exists in the registry, and that none is
    named twice. Completeness is a claim only the owning test can make - the
    registry tests legitimately enumerate deliberate subsets, such as the
    revisions that split inside one year - so the denominator is supplied by
    that caller through :func:`audit_temporal_enrollment_source` rather than
    imposed on every collection here.
    """
    declarations: list[LiteralEnrollmentDeclaration] = []
    findings: list[LiteralEnrollmentFinding] = []
    for path in sorted(root.rglob("*.py")):
        relative = path.relative_to(REPO_ROOT).as_posix() if path.is_relative_to(REPO_ROOT) else path.as_posix()
        audit = audit_temporal_enrollment_source(
            path.read_text(encoding="utf-8"),
            path=relative,
            expected=None,
            authority=authority,
            pins=pins,
        )
        declarations.extend(audit.declarations)
        findings.extend(audit.findings)
    declaration_keys = {(declaration.path, declaration.symbol) for declaration in declarations}
    for pin in pins:
        if (pin.path, pin.symbol) not in declaration_keys:
            findings.append(
                LiteralEnrollmentFinding(
                    path=pin.path,
                    symbol=pin.symbol,
                    missing=(),
                    extra=(),
                    duplicates=(),
                    duplicate_pins=(),
                    dormant_pins=(),
                    unnecessary_pins=(pin.subject,),
                )
            )
    return LiteralEnrollmentAudit(tuple(declarations), tuple(findings))


def audit_temporal_enrollment_source(
    source: str,
    *,
    path: str,
    expected: frozenset[RegistryRevisionSubject] | None,
    authority: ValidatedRegistryAuthority,
    pins: tuple[TemporalEnrollmentExclusionPin, ...] = (),
) -> LiteralEnrollmentAudit:
    """Audit module-level literal revision collections in one Python source.

    ``expected`` is the denominator this caller claims the collection enumerates.
    ``None`` means no completeness is claimed, and only the identities the rows
    name are checked.
    """
    declarations = _literal_enrollment_declarations(source, path=path, authority=authority)
    findings = tuple(
        finding
        for declaration in declarations
        if (
            finding := _declaration_finding(
                declaration,
                expected=expected,
                authority=authority,
                pins=pins,
            )
        )
        is not None
    )
    return LiteralEnrollmentAudit(declarations, findings)
