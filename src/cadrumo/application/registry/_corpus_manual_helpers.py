"""Manual-corpus helpers that cross-check casillas through the registry authority.

Manual verification uses a :class:`ValidatedRegistryAuthority` to confirm that
manual casilla references resolve to the same modelo revision surface consumed
by runtime registry workflows.
"""

from __future__ import annotations

from typing import get_args

from ...core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from ...core.config import Settings
from ...core.errors.severity import BaseSeverity
from ...core.logging import get_logger
from ...domain.calculations.registry.authority import (
    ValidatedRegistryAuthority,
    bundled_authority,
)
from ...domain.calculations.registry.errors import RegistrySnapshotError
from ...domain.manuals.fetch import load_manifest
from ...domain.manuals.loader import iter_sections, load_manual, resolve_part_root
from ...domain.manuals.schema import ManualCasillaReference, ManualId, ManualPart, RuleKind
from ...domain.manuals.verify import ManualVerificationIssue, ManualVerificationReport
from .errors import RegistryPreconditionCondition, registry_terminal_refusal

_LOGGER = get_logger(__name__)


def manual_report_with_registry_casilla_issues(
    report: ManualVerificationReport,
    *,
    settings: Settings | None,
    registry_authority: ValidatedRegistryAuthority | None,
) -> ManualVerificationReport:
    issues = _manual_registry_casilla_reference_issues(
        report,
        settings=settings,
        registry_authority=registry_authority,
    )
    if not issues:
        return report
    return report.model_copy(update={"issues": (*report.issues, *issues)})


def _manual_registry_casilla_reference_issues(
    report: ManualVerificationReport,
    *,
    settings: Settings | None,
    registry_authority: ValidatedRegistryAuthority | None,
) -> tuple[ManualVerificationIssue, ...]:
    if any(issue.code == "load-failed" for issue in report.errors):
        return ()
    part_root = resolve_part_root(
        manual_id=report.manual_id,
        year=report.year,
        part=report.part,
        settings=settings,
    )
    if not (part_root / "structure" / "manual.json").exists():
        return ()

    manual = load_manual(report.manual_id, report.year, report.part, settings=settings)
    authority = registry_authority or bundled_authority()

    issues: list[ManualVerificationIssue] = []
    for section in iter_sections(manual, settings=settings):
        for rule in section.rules:
            for reference in rule.references_casillas:
                issues.extend(
                    _manual_registry_casilla_reference_rule_issues(
                        reference,
                        authority=authority,
                        manual_year=report.year,
                        rule_id=rule.rule_id,
                    ),
                )
    return tuple(issues)


def _manual_registry_casilla_reference_rule_issues(
    reference: ManualCasillaReference,
    *,
    authority: ValidatedRegistryAuthority,
    manual_year: int,
    rule_id: str,
) -> tuple[ManualVerificationIssue, ...]:
    try:
        modelo = authority.modelo(reference.modelo_id)
    except RegistrySnapshotError:
        return (
            ManualVerificationIssue(
                level=BaseSeverity.ERROR,
                code="unknown-casilla-modelo-ref",
                message=(
                    f"rule {rule_id} references modelo {reference.modelo_id!r} casilla "
                    f"{reference.casilla_id!r}, but the modelo is absent from the registry"
                ),
            ),
        )

    covering_revisions = tuple(
        sorted(
            (revision for revision in modelo.revisions.values() if revision.period_selector.includes_year(manual_year)),
            key=lambda revision: (revision.valid_from, str(revision.id)),
        ),
    )
    if not covering_revisions:
        return (
            ManualVerificationIssue(
                level=BaseSeverity.ERROR,
                code="no-casilla-revision-ref",
                message=(
                    f"rule {rule_id} references modelo {reference.modelo_id!r} casilla "
                    f"{reference.casilla_id!r}, but no registry revision covers year {manual_year}"
                ),
            ),
        )

    issues: list[ManualVerificationIssue] = []
    missing_revisions: list[str] = []
    resolved_signatures: dict[tuple[str | None, str, str, tuple[str, ...], str], list[str]] = {}
    for revision in covering_revisions:
        matches = tuple(casilla for casilla in revision.casillas if casilla.id == reference.casilla_id)
        if len(matches) > 1:
            issues.append(
                ManualVerificationIssue(
                    level=BaseSeverity.ERROR,
                    code="ambiguous-casilla-ref",
                    message=(
                        f"rule {rule_id} references modelo {reference.modelo_id!r} casilla "
                        f"{reference.casilla_id!r}, but revision {revision.id!r} declares "
                        f"{len(matches)} matching casilla ids"
                    ),
                ),
            )
            continue
        if not matches:
            missing_revisions.append(str(revision.id))
            continue
        casilla = matches[0]
        signature = (casilla.segmento, casilla.number, casilla.label, casilla.section, casilla.data_type)
        resolved_signatures.setdefault(signature, []).append(str(revision.id))

    if missing_revisions:
        issues.append(
            ManualVerificationIssue(
                level=BaseSeverity.ERROR,
                code="dangling-casilla-ref",
                message=(
                    f"rule {rule_id} references modelo {reference.modelo_id!r} casilla "
                    f"{reference.casilla_id!r}, but that casilla.id is missing from "
                    f"revision(s) {tuple(missing_revisions)!r} for year {manual_year}"
                ),
            ),
        )
    if len(resolved_signatures) > 1:
        signature_revisions = tuple(tuple(revisions) for revisions in resolved_signatures.values())
        issues.append(
            ManualVerificationIssue(
                level=BaseSeverity.ERROR,
                code="ambiguous-casilla-ref",
                message=(
                    f"rule {rule_id} references modelo {reference.modelo_id!r} casilla "
                    f"{reference.casilla_id!r}, but year {manual_year} resolves to divergent "
                    f"casilla definitions across revision groups {signature_revisions!r}"
                ),
            ),
        )
    return tuple(issues)


def manual_rule_kind(kind: str | None) -> RuleKind | None:
    if kind is None:
        return None
    match kind:
        case "computation":
            return "computation"
        case "applicability":
            return "applicability"
        case "valuation":
            return "valuation"
        case "deductibility":
            return "deductibility"
        case "formal_obligation":
            return "formal_obligation"
        case "procedural":
            return "procedural"
        case "other":
            return "other"
        case _:
            pass
    allowed = tuple(str(value) for value in get_args(RuleKind))
    _LOGGER.warning(
        "registry.manuals.rules refused unknown rule kind",
        extra={
            "registry_service": "registry.manuals.rules",
            "registry_rule_kind": kind,
            "registry_allowed_rule_kinds": allowed,
        },
    )
    raise registry_terminal_refusal(
        condition=RegistryPreconditionCondition.MANUAL_RULE_KIND_SUPPORTED,
        translated_message="application.registry.errors.invalid_manual_rule_kind",
        context={
            "registry_service": "registry.manuals.rules",
            "rule_kind": kind,
            "allowed_rule_kinds": allowed,
        },
        facts={"manual_rule_kind_supported": False},
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


def load_manual_manifest(
    *,
    manual_id: ManualId,
    year: int,
    part: ManualPart,
    settings: Settings | None,
):
    part_root = resolve_part_root(manual_id=manual_id, year=year, part=part, settings=settings)
    return load_manifest(part_root / "manifest.json"), part_root
