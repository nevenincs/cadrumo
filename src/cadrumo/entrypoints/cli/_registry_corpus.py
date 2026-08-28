"""Read-only ``aeat app registry`` exposure of legal citations and manuals."""

from __future__ import annotations

import typer

from ...application.registry.corpus import (
    RegistryCitationReferenceProjection,
    RegistryCitationShowCommand,
    RegistryCitationShowReport,
    RegistryCitationsListCommand,
    RegistryCitationsListReport,
    RegistryCitationsVerificationReport,
    RegistryManualId,
    RegistryManualRulesCommand,
    RegistryManualRulesReport,
    RegistryManualShowCommand,
    RegistryManualShowReport,
    RegistryManualsListCommand,
    RegistryManualsListReport,
    RegistryManualVerificationReport,
    RegistryManualVerifyCommand,
    list_registry_citations,
    list_registry_manual_rules,
    list_registry_manuals,
    show_registry_citation,
    show_registry_manual,
    verify_registry_citations,
    verify_registry_manual,
)
from ...core.json_contract import strict_round_trip
from ...domain.manuals import ManualPart
from ._common import emit_envelope
from ._registry_corpus_payloads import (
    CitationListResult,
    CitationShowResult,
    CitationVerifyResult,
    ManualListResult,
    ManualRulesListResult,
    ManualShowResult,
    ManualVerifyResult,
)


def list_citations_cmd(
    ctx: typer.Context,
    tag: str | None = None,
) -> None:
    """List the legal authorities codified in the project's legal corpus."""
    report = list_registry_citations(RegistryCitationsListCommand(tag=tag))
    typed = CitationListResult.model_validate_json(report.model_dump_json())
    emit_envelope(ctx, command="registry.citations.list", result=typed, lines=_citation_list_lines(report))


def show_citation_cmd(
    ctx: typer.Context,
    legal_id: str,
    articulo: str | None = None,
) -> None:
    """View one legal authority and, optionally, one cited article."""
    report = show_registry_citation(RegistryCitationShowCommand(legal_id=legal_id, articulo=articulo))
    typed = CitationShowResult.model_validate_json(report.model_dump_json())
    emit_envelope(ctx, command="registry.citations.view", result=typed, lines=_citation_show_lines(report))


def verify_citations_cmd(ctx: typer.Context) -> None:
    """Verify the legal corpus against its own schema invariants."""
    report = verify_registry_citations()
    typed = CitationVerifyResult.model_validate_json(report.model_dump_json())
    emit_envelope(ctx, command="registry.citations.verify", result=typed, lines=_citation_verification_lines(report))
    if not report.passed:
        raise typer.Exit(code=1)


def list_manuals_cmd(
    ctx: typer.Context,
    manual: RegistryManualId | None = None,
    year: int | None = None,
) -> None:
    """List AEAT Manual práctico records available on disk."""
    report = list_registry_manuals(RegistryManualsListCommand(manual=manual, year=year))
    typed = strict_round_trip(ManualListResult, report)
    emit_envelope(ctx, command="registry.manuals.list", result=typed, lines=_manuals_list_lines(report))


def show_manual_cmd(
    ctx: typer.Context,
    manual: RegistryManualId,
    year: int,
    part: ManualPart = ManualPart.SINGLE,
    section: str | None = None,
) -> None:
    """View one manual's metadata and, optionally, one section by id."""
    report = show_registry_manual(RegistryManualShowCommand(manual=manual, year=year, part=part, section=section))
    typed = strict_round_trip(ManualShowResult, report)
    emit_envelope(ctx, command="registry.manuals.view", result=typed, lines=_manual_show_lines(report))


def list_manual_rules_cmd(
    ctx: typer.Context,
    manual: RegistryManualId,
    year: int,
    part: ManualPart = ManualPart.SINGLE,
    kind: str | None = None,
) -> None:
    """List AEAT rule decisions for one manual / year / part."""
    report = list_registry_manual_rules(RegistryManualRulesCommand(manual=manual, year=year, part=part, kind=kind))
    typed = strict_round_trip(ManualRulesListResult, report)
    emit_envelope(ctx, command="registry.manuals.rules", result=typed, lines=_manual_rules_lines(report))


def verify_manual_cmd(
    ctx: typer.Context,
    manual: RegistryManualId,
    year: int,
    part: ManualPart = ManualPart.SINGLE,
) -> None:
    """Verify one manual part against its schema and cross-reference contracts."""
    report = verify_registry_manual(RegistryManualVerifyCommand(manual=manual, year=year, part=part))
    typed = strict_round_trip(ManualVerifyResult, report)
    emit_envelope(ctx, command="registry.manuals.verify", result=typed, lines=_manual_verification_lines(report))
    if not report.passed:
        raise typer.Exit(code=1)


def _citation_list_lines(report: RegistryCitationsListReport) -> list[str]:
    lines = [
        "operation\tregistry.citations.list",
        f"reference_count\t{report.reference_count}",
        f"tag_filter\t{report.tag_filter or ''}",
        f"topic_count\t{report.topic_count}",
    ]
    for reference in report.references:
        lines.append(_citation_reference_line(reference))
    return lines


def _citation_show_lines(report: RegistryCitationShowReport) -> list[str]:
    lines = ["operation\tregistry.citations.show", _citation_reference_line(report.reference)]
    if report.articulo is not None:
        lines.extend(
            [
                f"articulo.numero\t{report.articulo.numero}",
                f"articulo.titulo\t{report.articulo.titulo}",
                f"articulo.permalink\t{report.articulo.permalink}",
                f"articulo.cite\t{report.articulo.cite}",
            ],
        )
    lines.append(f"related_topic_count\t{len(report.related_topics)}")
    return lines


def _citation_verification_lines(report: RegistryCitationsVerificationReport) -> list[str]:
    lines = [
        "operation\tregistry.citations.verify",
        f"reference_count\t{report.reference_count}",
        f"issue_count\t{report.issue_count}",
        f"passed\t{report.passed}",
        f"topic_count\t{report.topic_count}",
    ]
    for issue in report.issues:
        lines.append("\t".join(("issue", issue.level.value, issue.code, issue.reference_id or "", issue.message)))
    return lines


def _citation_reference_line(reference: RegistryCitationReferenceProjection) -> str:
    return "\t".join(
        (
            "ref",
            reference.id,
            reference.kind,
            reference.number,
            reference.boe_id,
            reference.short_title,
        ),
    )


def _manuals_list_lines(report: RegistryManualsListReport) -> list[str]:
    lines = [
        "operation\tregistry.manuals.list",
        f"manual_filter\t{report.manual_filter or ''}",
        f"year_filter\t{report.year_filter if report.year_filter is not None else ''}",
        f"part_count\t{report.part_count}",
        f"topic_count\t{report.topic_count}",
    ]
    for part in report.parts:
        lines.append("\t".join(("part", part.manual_id, str(part.year), part.part, part.root)))
    return lines


def _manual_show_lines(report: RegistryManualShowReport) -> list[str]:
    lines = [
        "operation\tregistry.manuals.show",
        f"manual_id\t{report.manual_id}",
        f"year\t{report.year}",
        f"part\t{report.part}",
        f"title\t{report.title or ''}",
        f"source_pdf_url\t{report.source_pdf_url}",
        f"chapter_count\t{report.chapter_count}",
        f"section_count\t{report.section_count}",
        f"structure_available\t{report.structure_available}",
        f"topic_count\t{report.topic_count}",
    ]
    if report.section is not None:
        lines.extend(
            [
                f"section.section_id\t{report.section.section_id}",
                f"section.title\t{report.section.title}",
                f"section.rule_count\t{report.section.rule_count}",
                f"section.paragraph_count\t{report.section.paragraph_count}",
            ],
        )
    return lines


def _manual_rules_lines(report: RegistryManualRulesReport) -> list[str]:
    lines = [
        "operation\tregistry.manuals.rules",
        f"manual_id\t{report.manual_id}",
        f"year\t{report.year}",
        f"part\t{report.part}",
        f"kind_filter\t{report.kind_filter or ''}",
        f"structure_available\t{report.structure_available}",
        f"rule_count\t{report.rule_count}",
        f"topic_count\t{report.topic_count}",
    ]
    for rule in report.rules:
        lines.append("\t".join(("rule", rule.rule_id, rule.kind, rule.section_id)))
        for reference in rule.references_casillas:
            lines.append("\t".join(("rule_casilla", rule.rule_id, reference.modelo_id, reference.casilla_id)))
    return lines


def _manual_verification_lines(report: RegistryManualVerificationReport) -> list[str]:
    lines = [
        "operation\tregistry.manuals.verify",
        f"manual_id\t{report.manual_id}",
        f"year\t{report.year}",
        f"part\t{report.part}",
        f"issue_count\t{report.issue_count}",
        f"error_count\t{report.error_count}",
        f"warning_count\t{report.warning_count}",
        f"passed\t{report.passed}",
        f"topic_count\t{report.topic_count}",
    ]
    for issue in report.issues:
        lines.append("\t".join(("issue", issue.level.value, issue.code, issue.reference_id or "", issue.message)))
    return lines


__all__ = [
    "list_citations_cmd",
    "list_manual_rules_cmd",
    "list_manuals_cmd",
    "show_citation_cmd",
    "show_manual_cmd",
    "verify_citations_cmd",
    "verify_manual_cmd",
]
