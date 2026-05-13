"""Read-only ``aeat app registry`` exposure of normatives + manuals.

* ``aeat app registry citations list`` — list every normative codified
  in the project's legal corpus, with an optional tag filter.
* ``aeat app registry citations show NORMATIVE_ID`` — show one
  normative's metadata and, optionally, one cited article.
* ``aeat app registry citations verify`` — verify the legal corpus
  against its own schema invariants.
* ``aeat app registry manuals list`` — list AEAT Manual práctico
  records available on disk.
* ``aeat app registry manuals show`` — show one manual and, optionally,
  one section by id.
* ``aeat app registry manuals rules`` — list AEAT rule decisions for
  one manual / year / part, optionally filtered by rule kind.
* ``aeat app registry manuals verify`` — verify one manual part on
  disk against its own schema and cross-reference contracts.

The commands are thin Typer adapters over the domain APIs
:mod:`aeat.domain.normatives` and :mod:`aeat.domain.manuals`. They
inspect local reference catalogues only and emit no bucket events.
Every command honours the root ``--format json|text`` contract.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import typer

from ...core.config import load_settings
from ...core.logging import get_logger
from ...domain.manuals import (
    ManualId,
    ManualPart,
    find_rules,
    iter_sections,
    load_catalogue as load_manual_catalogue,
    load_manual,
    raise_on_errors,
    verify_manual_dir,
)
from ...domain.manuals._schema import RuleKind
from ...domain.manuals._verify import ManualVerificationReport
from ...domain.normatives import (
    NormativeReference,
    cite,
    find_articulo,
    find_reference,
    load_catalogue as load_normative_catalogue,
    short_title,
    verify_catalogue as verify_normative_catalogue,
)
from ...domain.normatives.errors import NormativeParseError
from ._common import _emit
from ._i18n import tr

_LOGGER = get_logger(__name__)


# ---------------------------------------------------------------------------
# Citations Typer
# ---------------------------------------------------------------------------


citations_app = typer.Typer(
    name="citations",
    help=tr("cli.registry.citations.app_help"),
    no_args_is_help=True,
    add_completion=False,
)


def _normative_payload(reference: NormativeReference) -> dict[str, Any]:
    return {
        "id": reference.id,
        "kind": reference.kind.value,
        "number": reference.number,
        "title": reference.title,
        "published_at": reference.published_at.isoformat(),
        "boe_id": reference.boe_id,
        "boe_url": str(reference.boe_url),
        "tags": list(reference.tags),
        "articulo_count": len(reference.articulos),
    }


def _normative_lines(reference: NormativeReference) -> list[str]:
    return [
        f"id\t{reference.id}",
        f"kind\t{reference.kind.value}",
        f"number\t{reference.number}",
        f"title\t{reference.title}",
        f"published_at\t{reference.published_at.isoformat()}",
        f"boe_id\t{reference.boe_id}",
        f"boe_url\t{reference.boe_url}",
        f"tags\t{','.join(reference.tags)}",
        f"articulo_count\t{len(reference.articulos)}",
    ]


@citations_app.command("list", help=tr("cli.registry.citations.list_help"))
def list_citations_cmd(
    ctx: typer.Context,
    tag: Annotated[
        str | None,
        typer.Option("--tag", help=tr("cli.registry.citations.tag_help")),
    ] = None,
) -> None:
    """List the normatives codified in the project's legal corpus."""

    catalogue = load_normative_catalogue()
    references = tuple(catalogue.references.values())
    if tag is not None:
        needle = tag.strip().lower()
        references = tuple(ref for ref in references if needle in tuple(t.lower() for t in ref.tags))
    references = tuple(sorted(references, key=lambda ref: ref.id))
    payload = {
        "operation": "registry.citations.list",
        "reference_count": len(references),
        "tag_filter": tag,
        "references": [_normative_payload(ref) for ref in references],
    }
    lines = [
        f"operation\tregistry.citations.list",
        f"reference_count\t{len(references)}",
        f"tag_filter\t{tag or ''}",
    ]
    for reference in references:
        lines.append(
            "\t".join(
                (
                    "ref",
                    reference.id,
                    reference.kind.value,
                    reference.number,
                    reference.boe_id,
                    short_title(reference),
                )
            )
        )
    _emit(ctx, payload, lines)


@citations_app.command("show", help=tr("cli.registry.citations.show_help"))
def show_citation_cmd(
    ctx: typer.Context,
    normative_id: Annotated[
        str,
        typer.Argument(help=tr("cli.registry.citations.normative_id_help")),
    ],
    articulo: Annotated[
        str | None,
        typer.Option("--articulo", help=tr("cli.registry.citations.articulo_help")),
    ] = None,
) -> None:
    """Show one normative and, optionally, one cited article."""

    catalogue = load_normative_catalogue()
    reference = find_reference(catalogue, normative_id)
    payload: dict[str, Any] = {
        "operation": "registry.citations.show",
        "reference": _normative_payload(reference),
    }
    lines = ["operation\tregistry.citations.show"]
    lines.extend(_normative_lines(reference))
    if articulo is not None:
        record = find_articulo(catalogue, reference.id, articulo)
        payload["articulo"] = {
            "numero": record.numero,
            "titulo": record.titulo,
            "summary": record.summary,
            "permalink": str(record.permalink),
        }
        payload["cite"] = cite(reference, record)
        lines.extend(
            [
                f"articulo.numero\t{record.numero}",
                f"articulo.titulo\t{record.titulo}",
                f"articulo.permalink\t{record.permalink}",
                f"cite\t{payload['cite']}",
            ]
        )
    _emit(ctx, payload, lines)


@citations_app.command("verify", help=tr("cli.registry.citations.verify_help"))
def verify_citations_cmd(ctx: typer.Context) -> None:
    """Verify the legal corpus against its own schema invariants.

    The verifier is resilient: a strict-schema load failure on any
    corpus file is captured as a structured ``parse_error`` issue
    rather than crashing the command. The CLI still emits a complete
    payload and signals a non-zero exit so callers can act on the
    issue list.
    """

    # ``verify_normative_catalogue`` already owns the resilient
    # disk-load path: it catches ``NormativeParseError`` internally
    # and surfaces it as a ``parse_error`` issue on the report. The
    # second load below is a separate, narrow attempt strictly for
    # populating ``reference_count`` when the corpus is healthy. If
    # that second load fails with the same error, we log a structured
    # warning and let ``reference_count`` stay at ``0`` — the report
    # itself is the authoritative diagnostic for the operator.
    report = verify_normative_catalogue()
    reference_count = 0
    try:
        catalogue = load_normative_catalogue()
    except NormativeParseError as exc:
        _LOGGER.warning(
            "citations.verify: corpus load failed; verifier owns the diagnostic surface",
            extra={"error_type": type(exc).__name__, "error_message": str(exc)},
        )
    else:
        reference_count = len(catalogue.references)
    payload = {
        "operation": "registry.citations.verify",
        "reference_count": reference_count,
        "issue_count": len(report.issues),
        "issues": [issue.model_dump(mode="json") for issue in report.issues],
        "passed": report.clean,
    }
    lines = [
        "operation\tregistry.citations.verify",
        f"reference_count\t{reference_count}",
        f"issue_count\t{len(report.issues)}",
        f"passed\t{report.clean}",
    ]
    for issue in report.issues:
        lines.append(
            "\t".join(
                (
                    "issue",
                    issue.level,
                    issue.code,
                    issue.reference_id or "",
                    issue.message,
                )
            )
        )
    _emit(ctx, payload, lines)
    if not report.clean:
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# Manuals Typer
# ---------------------------------------------------------------------------


manuals_app = typer.Typer(
    name="manuals",
    help=tr("cli.registry.manuals.app_help"),
    no_args_is_help=True,
    add_completion=False,
)


def _discover_manual_parts() -> tuple[tuple[ManualId, int, ManualPart, Path], ...]:
    """Walk the manuals corpus root and yield every part on disk.

    The discovery is read-only: it inspects directory structure under
    the configured ``aeat_manuals_root`` and returns a tuple of
    ``(manual_id, year, part, part_root)`` for every directory that
    contains a ``structure/manual.json`` or a ``manifest.json``.
    """

    settings = load_settings()
    root = settings.aeat_manuals_root
    if not root.exists():
        return ()
    discovered: list[tuple[ManualId, int, ManualPart, Path]] = []
    for manual_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        try:
            manual_id = ManualId(manual_dir.name)
        except ValueError:
            continue
        for year_dir in sorted(p for p in manual_dir.iterdir() if p.is_dir() and p.name.isdigit()):
            year = int(year_dir.name)
            for part_dir in sorted(p for p in year_dir.iterdir() if p.is_dir()):
                try:
                    part = ManualPart(part_dir.name)
                except ValueError:
                    continue
                discovered.append((manual_id, year, part, part_dir))
    return tuple(discovered)


@manuals_app.command("list", help=tr("cli.registry.manuals.list_help"))
def list_manuals_cmd(
    ctx: typer.Context,
    manual: Annotated[
        ManualId | None,
        typer.Option("--manual", help=tr("cli.registry.manuals.manual_help")),
    ] = None,
    year: Annotated[
        int | None,
        typer.Option("--year", help=tr("cli.registry.manuals.year_help")),
    ] = None,
) -> None:
    """List AEAT Manual práctico records available on disk."""

    parts = _discover_manual_parts()
    if manual is not None:
        parts = tuple(entry for entry in parts if entry[0] == manual)
    if year is not None:
        parts = tuple(entry for entry in parts if entry[1] == year)
    payload = {
        "operation": "registry.manuals.list",
        "manual_filter": manual.value if manual is not None else None,
        "year_filter": year,
        "part_count": len(parts),
        "parts": [
            {
                "manual_id": entry[0].value,
                "year": entry[1],
                "part": entry[2].value,
                "root": entry[3].as_posix(),
            }
            for entry in parts
        ],
    }
    lines = [
        "operation\tregistry.manuals.list",
        f"manual_filter\t{manual.value if manual is not None else ''}",
        f"year_filter\t{year if year is not None else ''}",
        f"part_count\t{len(parts)}",
    ]
    for entry in parts:
        lines.append(
            "\t".join(
                (
                    "part",
                    entry[0].value,
                    str(entry[1]),
                    entry[2].value,
                    entry[3].as_posix(),
                )
            )
        )
    _emit(ctx, payload, lines)


@manuals_app.command("show", help=tr("cli.registry.manuals.show_help"))
def show_manual_cmd(
    ctx: typer.Context,
    manual: Annotated[
        ManualId,
        typer.Option("--manual", help=tr("cli.registry.manuals.manual_help")),
    ],
    year: Annotated[
        int,
        typer.Option("--year", help=tr("cli.registry.manuals.year_help")),
    ],
    part: Annotated[
        ManualPart,
        typer.Option("--part", help=tr("cli.registry.manuals.part_help")),
    ] = ManualPart.SINGLE,
    section: Annotated[
        str | None,
        typer.Option("--section", help=tr("cli.registry.manuals.section_help")),
    ] = None,
) -> None:
    """Show one manual's metadata and, optionally, one section by id."""

    manual_obj = load_manual(manual, year, part)
    section_count = sum(len(chapter.sections) for chapter in manual_obj.chapters)
    payload: dict[str, Any] = {
        "operation": "registry.manuals.show",
        "manual_id": manual_obj.manual_id.value,
        "year": manual_obj.year,
        "part": manual_obj.part.value,
        "title": manual_obj.title,
        "source_pdf_url": str(manual_obj.source_pdf_url),
        "chapter_count": len(manual_obj.chapters),
        "section_count": section_count,
    }
    lines = [
        "operation\tregistry.manuals.show",
        f"manual_id\t{manual_obj.manual_id.value}",
        f"year\t{manual_obj.year}",
        f"part\t{manual_obj.part.value}",
        f"title\t{manual_obj.title}",
        f"source_pdf_url\t{manual_obj.source_pdf_url}",
        f"chapter_count\t{len(manual_obj.chapters)}",
        f"section_count\t{section_count}",
    ]
    if section is not None:
        matched = next(
            (sec for sec in iter_sections(manual_obj) if sec.section_id == section),
            None,
        )
        if matched is None:
            raise typer.BadParameter(
                tr("cli.registry.manuals.errors.unknown_section", section=section)
            )
        payload["section"] = {
            "section_id": matched.section_id,
            "title": matched.title,
            "rule_count": len(matched.rules),
            "paragraph_count": len(matched.prose),
        }
        lines.extend(
            [
                f"section.section_id\t{matched.section_id}",
                f"section.title\t{matched.title}",
                f"section.rule_count\t{len(matched.rules)}",
                f"section.paragraph_count\t{len(matched.prose)}",
            ]
        )
    _emit(ctx, payload, lines)


@manuals_app.command("rules", help=tr("cli.registry.manuals.rules_help"))
def list_manual_rules_cmd(
    ctx: typer.Context,
    manual: Annotated[
        ManualId,
        typer.Option("--manual", help=tr("cli.registry.manuals.manual_help")),
    ],
    year: Annotated[
        int,
        typer.Option("--year", help=tr("cli.registry.manuals.year_help")),
    ],
    part: Annotated[
        ManualPart,
        typer.Option("--part", help=tr("cli.registry.manuals.part_help")),
    ] = ManualPart.SINGLE,
    kind: Annotated[
        str | None,
        typer.Option("--kind", help=tr("cli.registry.manuals.kind_help")),
    ] = None,
) -> None:
    """List AEAT rule decisions for one manual / year / part."""

    catalogue = load_manual_catalogue([(manual, year, part)])
    rule_kind: RuleKind | None = None
    if kind is not None:
        allowed = (
            "computation",
            "applicability",
            "valuation",
            "deductibility",
            "formal_obligation",
            "procedural",
            "other",
        )
        if kind not in allowed:
            raise typer.BadParameter(
                f"--kind must be one of {allowed!r}; got {kind!r}"
            )
        # The runtime guard above narrows ``kind`` to one of the
        # ``RuleKind`` Literal members. ty cannot infer the narrowing
        # from a tuple-membership test against an arbitrary tuple, so
        # the assignment carries a single suppressed Literal-narrowing
        # diagnostic with an explicit reason code.
        rule_kind = kind  # ty: ignore[invalid-assignment]
    rules = tuple(find_rules(catalogue, kind=rule_kind))
    payload = {
        "operation": "registry.manuals.rules",
        "manual_id": manual.value,
        "year": year,
        "part": part.value,
        "kind_filter": kind,
        "rule_count": len(rules),
        "rules": [
            {
                "rule_id": rule.rule_id,
                "kind": rule.kind,
                "section_id": rule.section_id,
                "references_casillas": list(rule.references_casillas),
            }
            for rule in rules
        ],
    }
    lines = [
        "operation\tregistry.manuals.rules",
        f"manual_id\t{manual.value}",
        f"year\t{year}",
        f"part\t{part.value}",
        f"kind_filter\t{kind or ''}",
        f"rule_count\t{len(rules)}",
    ]
    for rule in rules:
        lines.append(
            "\t".join(
                (
                    "rule",
                    rule.rule_id,
                    rule.kind,
                    rule.section_id,
                    ",".join(rule.references_casillas),
                )
            )
        )
    _emit(ctx, payload, lines)


@manuals_app.command("verify", help=tr("cli.registry.manuals.verify_help"))
def verify_manual_cmd(
    ctx: typer.Context,
    manual: Annotated[
        ManualId,
        typer.Option("--manual", help=tr("cli.registry.manuals.manual_help")),
    ],
    year: Annotated[
        int,
        typer.Option("--year", help=tr("cli.registry.manuals.year_help")),
    ],
    part: Annotated[
        ManualPart,
        typer.Option("--part", help=tr("cli.registry.manuals.part_help")),
    ] = ManualPart.SINGLE,
) -> None:
    """Verify one manual part against its schema and cross-reference contracts."""

    report: ManualVerificationReport = verify_manual_dir(
        manual_id=manual, year=year, part=part
    )
    error_issues = report.errors
    warning_issues = report.warnings
    payload = {
        "operation": "registry.manuals.verify",
        "manual_id": manual.value,
        "year": year,
        "part": part.value,
        "issue_count": len(report.issues),
        "error_count": len(error_issues),
        "warning_count": len(warning_issues),
        "passed": not error_issues,
        "issues": [issue.model_dump(mode="json") for issue in report.issues],
    }
    lines = [
        "operation\tregistry.manuals.verify",
        f"manual_id\t{manual.value}",
        f"year\t{year}",
        f"part\t{part.value}",
        f"issue_count\t{len(report.issues)}",
        f"error_count\t{len(error_issues)}",
        f"warning_count\t{len(warning_issues)}",
        f"passed\t{payload['passed']}",
    ]
    for issue in report.issues:
        lines.append(
            "\t".join(
                (
                    "issue",
                    issue.level,
                    issue.code,
                    issue.message,
                )
            )
        )
    _emit(ctx, payload, lines)
    if error_issues:
        raise_on_errors(report)


__all__ = ["citations_app", "manuals_app"]
