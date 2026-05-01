"""``aeat manual`` sub-app — AEAT *Manual práctico* corpus CLI.

Provides the full seven-subcommand shape from issue ``#25``. Four
commands (``fetch``, ``verify``, ``list``, ``show``) are fully
functional in v1. Three commands (``structure``, ``extract-rules``,
``translate``) are defined to lock the public CLI surface but raise
:class:`RuleExtractionError` until ``aeat.adapters.outbound.llm`` (``#21``) lands. The
exact error message names ``#21`` so callers know exactly which
sibling issue unblocks them.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from ...core.i18n import get_translation
from ...domain.manuals import (
    ManualError,
    ManualId,
    ManualNotFoundError,
    ManualPart,
    RuleExtractionError,
    RuleKind,
    VerificationReport,
    fetch_manual_part,
    find_rules,
    load_catalogue,
    load_manual,
    raise_on_errors,
    verify_manual_dir,
)
from ._i18n import output_language

app = typer.Typer(name="manual", no_args_is_help=True, help="AEAT Manual práctico corpus helpers (#25).")

_console = Console()

_PENDING_21_MESSAGE = (
    "pending #21 (aeat.adapters.outbound.llm): LLM-assisted extraction is not yet implemented on this branch. "
    "Re-run this command after #21 merges and the LLM client + translator surfaces land."
)


def _parse_part(part: str) -> ManualPart:
    """Convert a CLI string into :class:`ManualPart`, failing loud."""
    try:
        return ManualPart(part)
    except ValueError as exc:
        valid = ", ".join(member.value for member in ManualPart)
        raise typer.BadParameter(f"unknown part {part!r}; valid values: {valid}") from exc


def _parse_manual_id(manual: str) -> ManualId:
    """Convert a CLI string into :class:`ManualId`, failing loud."""
    try:
        return ManualId(manual)
    except ValueError as exc:
        valid = ", ".join(member.value for member in ManualId)
        raise typer.BadParameter(f"unknown manual {manual!r}; valid values: {valid}") from exc


def _parse_kind(kind: str | None) -> RuleKind | None:
    """Convert a CLI string into :class:`RuleKind` or return ``None``."""
    if kind is None:
        return None
    try:
        return RuleKind(kind)
    except ValueError as exc:
        valid = ", ".join(member.value for member in RuleKind)
        raise typer.BadParameter(f"unknown kind {kind!r}; valid values: {valid}") from exc


@app.command(name="fetch", help="Download the raw manual PDF and write its sha256 manifest.")
def fetch(
    manual: str = typer.Option(..., "--manual", "-m", help="Manual identifier (e.g. 'renta')."),
    year: int = typer.Option(..., "--year", "-y", help="Tax year, e.g. 2025."),
    part: str = typer.Option(
        ManualPart.SINGLE.value,
        "--part",
        "-p",
        help="Volume split: 'single', 'parte1', or 'parte2-deducciones-autonomicas'.",
    ),
) -> None:
    """Materialise a raw manual part and commit its manifest."""
    manual_id = _parse_manual_id(manual)
    part_enum = _parse_part(part)
    try:
        result = fetch_manual_part(manual_id=manual_id, year=year, part=part_enum)
    except ManualError as exc:
        typer.secho(f"fetch failed: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc
    typer.echo(f"fetched {result.pdf_path} ({result.manifest.content_length} bytes, sha256={result.manifest.sha256})")
    typer.echo(f"wrote manifest {result.manifest_path}")


@app.command(name="structure", help="(pending #21) LLM-assisted chapter/section tree extraction.")
def structure(
    manual: str = typer.Option(..., "--manual", "-m"),
    year: int = typer.Option(..., "--year", "-y"),
    part: str = typer.Option(ManualPart.SINGLE.value, "--part", "-p"),
) -> None:
    """Pending LLM-assisted chapter-tree extraction workflow."""
    _ = (_parse_manual_id(manual), year, _parse_part(part))
    raise RuleExtractionError(_PENDING_21_MESSAGE)


@app.command(name="extract-rules", help="(pending #21) LLM-assisted per-section rule extraction.")
def extract_rules(
    manual: str = typer.Option(..., "--manual", "-m"),
    year: int = typer.Option(..., "--year", "-y"),
    part: str = typer.Option(ManualPart.SINGLE.value, "--part", "-p"),
    section: str = typer.Option(..., "--section", "-s", help="Section identifier to extract."),
) -> None:
    """Pending LLM-assisted rule extraction workflow."""
    _ = (_parse_manual_id(manual), year, _parse_part(part), section)
    raise RuleExtractionError(_PENDING_21_MESSAGE)


@app.command(name="translate", help="(pending #21) Bulk translation of section titles / summaries / rules.")
def translate(
    manual: str = typer.Option(..., "--manual", "-m"),
    year: int = typer.Option(..., "--year", "-y"),
    part: str = typer.Option(ManualPart.SINGLE.value, "--part", "-p"),
    section: str = typer.Option(..., "--section", "-s"),
) -> None:
    """Pending bulk-translation workflow."""
    _ = (_parse_manual_id(manual), year, _parse_part(part), section)
    raise RuleExtractionError(_PENDING_21_MESSAGE)


def _render_report(report: VerificationReport) -> None:
    """Render a :class:`VerificationReport` as a rich table."""
    if not report.issues:
        typer.secho(
            f"✓ verify clean: {report.manual_id.value}/{report.year}/{report.part.value}",
            fg=typer.colors.GREEN,
        )
        return
    table = Table(
        title=f"verify {report.manual_id.value}/{report.year}/{report.part.value}",
        header_style="bold",
    )
    table.add_column("level", style="white")
    table.add_column("code", style="cyan")
    table.add_column("message", style="white")
    for issue in report.issues:
        colour = "red" if issue.level == "error" else "yellow"
        table.add_row(f"[{colour}]{issue.level}[/{colour}]", issue.code, issue.message)
    _console.print(table)


@app.command(name="verify", help="Validate a manual part against the schema and review gate.")
def verify(
    manual: str = typer.Option(..., "--manual", "-m"),
    year: int = typer.Option(..., "--year", "-y"),
    part: str = typer.Option(ManualPart.SINGLE.value, "--part", "-p"),
    review_required: bool | None = typer.Option(
        None,
        "--review-required/--no-review-required",
        help="Override AEAT_MANUALS_REVIEW_REQUIRED for this run.",
    ),
) -> None:
    """Run the verification pipeline and exit non-zero on errors."""
    manual_id = _parse_manual_id(manual)
    part_enum = _parse_part(part)
    try:
        report = verify_manual_dir(
            manual_id=manual_id,
            year=year,
            part=part_enum,
            review_required=review_required,
        )
    except ManualNotFoundError as exc:
        typer.secho(f"verify failed: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc
    _render_report(report)
    try:
        raise_on_errors(report)
    except ManualError as exc:
        typer.secho(str(exc), fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc


@app.command(name="list", help="List rules in a loaded manual part, optionally filtered by kind.")
def list_rules(
    manual: str = typer.Option(..., "--manual", "-m"),
    year: int = typer.Option(..., "--year", "-y"),
    part: str = typer.Option(ManualPart.SINGLE.value, "--part", "-p"),
    kind: str | None = typer.Option(None, "--kind", "-k", help="Filter by RuleKind value."),
) -> None:
    """List every rule in the requested manual part."""
    manual_id = _parse_manual_id(manual)
    part_enum = _parse_part(part)
    kind_enum = _parse_kind(kind)
    try:
        catalogue = load_catalogue([(manual_id, year, part_enum)])
    except ManualNotFoundError as exc:
        typer.secho(
            f"no structured content for {manual_id.value}/{year}/{part_enum.value}: {exc}",
            fg=typer.colors.YELLOW,
        )
        raise typer.Exit(code=0) from exc
    table = Table(title=f"{manual_id.value}/{year}/{part_enum.value} rules", header_style="bold")
    table.add_column("rule_id", style="cyan")
    table.add_column("kind", style="white")
    table.add_column("chapter", style="dim")
    table.add_column("section", style="dim")
    count = 0
    for rule in find_rules(catalogue, kind=kind_enum):
        table.add_row(rule.rule_id, rule.kind.value, rule.chapter_id, rule.section_id)
        count += 1
    _console.print(table)
    typer.echo(f"{count} rule(s)")


@app.command(name="show", help="Show a single manual's metadata from the on-disk structure/.")
def show(
    manual: str = typer.Option(..., "--manual", "-m"),
    year: int = typer.Option(..., "--year", "-y"),
    part: str = typer.Option(ManualPart.SINGLE.value, "--part", "-p"),
) -> None:
    """Print the manual metadata (title, summary, chapter count, reviewer)."""
    manual_id = _parse_manual_id(manual)
    part_enum = _parse_part(part)
    try:
        record = load_manual(manual_id, year, part_enum)
    except ManualNotFoundError as exc:
        typer.secho(
            f"no structured content for {manual_id.value}/{year}/{part_enum.value}: {exc}",
            fg=typer.colors.YELLOW,
        )
        raise typer.Exit(code=0) from exc
    lang = output_language()
    typer.echo(f"manual: {record.manual_id.value}/{record.year}/{record.part.value}")
    typer.echo(f"title: {get_translation(record.title, lang) if record.title else ''}")
    typer.echo(f"summary: {get_translation(record.summary, lang) if record.summary else ''}")
    typer.echo(f"chapters: {len(record.chapters)}")
    typer.echo(f"definition_reviewed_by: {record.definition_reviewed_by}")
    typer.echo(f"definition_reviewed_at: {record.definition_reviewed_at.isoformat()}")


__all__ = ["app"]
