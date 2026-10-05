"""Apply verified reviewer quotes to generated official form headings."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from cadrumo.domain.calculations.registry.schema_form_layouts import (
    FormBlockDefinition,
    FormGridBlock,
    FormGridColumn,
    FormPageDefinition,
    FormRepeatingColumn,
    FormRepeatingGroupBlock,
    FormSectionDefinition,
)
from cadrumo.domain.calculations.registry.schema_references import SourceReference

from .column_vocabulary import shared_column_key
from .generation_models import _Build
from .official_headings import OfficialHeadingRefusedError, QuotedHeading, verify_quote
from .official_text import node_slug
from .page_sections import _column_heading_key, _heading_key


def _quoted_column[C: (FormGridColumn, FormRepeatingColumn)](build: _Build, column: C, quote: QuotedHeading) -> C:
    if column.official_heading is not None:
        raise OfficialHeadingRefusedError(f"{quote.describe()}: the design already names this column")
    key = shared_column_key(quote.text) or column.key
    return column.model_copy(
        update={"official_heading": quote.text, "heading_key": _column_heading_key(build.modelo_id, key)}
    )


def _quoted_block(build: _Build, block: FormBlockDefinition, quotes: dict[str, QuotedHeading]) -> FormBlockDefinition:
    if isinstance(block, FormGridBlock):
        grid = tuple(
            _quoted_column(build, column, quotes.pop(column.key)) if column.key in quotes else column
            for column in block.columns
        )
        return block.model_copy(update={"columns": grid})
    if isinstance(block, FormRepeatingGroupBlock):
        repeating = tuple(
            _quoted_column(build, column, quotes.pop(column.key)) if column.key in quotes else column
            for column in block.columns
        )
        return block.model_copy(update={"columns": repeating})
    return block


def _quoted_section(
    build: _Build, section: FormSectionDefinition, quote: QuotedHeading | None, columns: dict[str, QuotedHeading]
) -> FormSectionDefinition:
    update: dict[str, object] = {"blocks": tuple(_quoted_block(build, block, columns) for block in section.blocks)}
    if quote is not None:
        if section.official_heading is not None:
            raise OfficialHeadingRefusedError(f"{quote.describe()}: the design already names this section")
        update["official_heading"] = quote.text
        update["heading_key"] = _heading_key(build.modelo_id, "section", node_slug(quote.text))
    return section.model_copy(update=update)


def _pin_quote_sources(
    build: _Build,
    quotes: Sequence[QuotedHeading],
    *,
    sources: Mapping[str, SourceReference],
    data_root: Path,
) -> None:
    cited = tuple(str(ref) for ref in build.revision.source_refs)
    for quote in quotes:
        pinned = verify_quote(quote, cited=cited, sources=sources, data_root=data_root)
        if all(item.source_ref != pinned.source_ref for item in build.design_sources):
            build.design_sources.append(pinned)


def _section_quote_parts(
    page_id: str,
    section_id: str,
    pending: dict[tuple[str, str | None, str | None], QuotedHeading],
) -> tuple[dict[str, QuotedHeading], QuotedHeading | None]:
    columns = {
        column: quote
        for (quote_page, quote_section, column), quote in pending.items()
        if quote_page == page_id and quote_section == section_id and column is not None
    }
    for column in columns:
        del pending[(page_id, section_id, column)]
    heading = pending.pop((page_id, section_id, None), None)
    return columns, heading


def _quoted_page_sections(
    build: _Build,
    page: FormPageDefinition,
    pending: dict[tuple[str, str | None, str | None], QuotedHeading],
) -> tuple[FormSectionDefinition, ...]:
    sections = []
    for section in page.sections:
        columns, heading = _section_quote_parts(page.id, section.id, pending)
        sections.append(_quoted_section(build, section, heading, columns))
        if columns:
            unknown = ", ".join(sorted(columns))
            raise OfficialHeadingRefusedError(f"{build.modelo_id} {build.revision.id}: no column {unknown}")
    return tuple(sections)


def _quoted_page(
    build: _Build,
    page: FormPageDefinition,
    pending: dict[tuple[str, str | None, str | None], QuotedHeading],
) -> FormPageDefinition:
    update: dict[str, object] = {"sections": _quoted_page_sections(build, page, pending)}
    page_quote = pending.pop((page.id, None, None), None)
    if page_quote is not None:
        if page.official_heading is not None:
            raise OfficialHeadingRefusedError(f"{page_quote.describe()}: the design already names this page")
        update["official_heading"] = page_quote.text
    return page.model_copy(update=update)


def _quoted_pages(
    build: _Build,
    pages: Sequence[FormPageDefinition],
    quotes: Sequence[QuotedHeading],
    *,
    sources: Mapping[str, SourceReference],
    data_root: Path,
) -> list[FormPageDefinition]:
    """Head each quoted part with the reviewer's verified quote, and pin the sources quoted from.

    A quote is refused when it is not grounded, when it names a part the layout
    does not have, or when the design already names that part: the design's
    own words always win, so a quote can only fill a gap.
    """
    if not quotes:
        return list(pages)
    _pin_quote_sources(build, quotes, sources=sources, data_root=data_root)
    pending = {(quote.page, quote.section, quote.column): quote for quote in quotes}
    if len(pending) != len(quotes):
        raise OfficialHeadingRefusedError(f"{build.modelo_id} {build.revision.id}: a part is quoted twice")
    out = [_quoted_page(build, page, pending) for page in pages]
    if pending:
        missing = ", ".join(quote.describe() for quote in pending.values())
        raise OfficialHeadingRefusedError(f"quoted parts the layout does not have: {missing}")
    return out
