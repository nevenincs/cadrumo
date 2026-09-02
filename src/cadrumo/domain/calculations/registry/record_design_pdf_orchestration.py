"""Orchestrate text and visual PDF record-design extraction."""

from __future__ import annotations

from functools import lru_cache
from io import BufferedReader, BytesIO
from pathlib import Path

from .errors import RegistryValidationError
from .record_design_pdf_repairs import (
    collapse_doubled_coordinate_rows,
    collapse_stuttered_row_prefix,
    join_wrapped_row_descriptions,
    reattach_stranded_casilla_tags,
    recover_coordinate_stutter_rows,
    rejoin_bare_coordinate_rows,
    rejoin_reversed_column_rows,
    repair_truncated_offset_rows,
    split_fused_ordinal_offset_rows,
    split_fused_ordinal_position_prefix,
    split_glued_naturaleza_rows,
    split_row_from_wrapped_content,
    split_tail_from_leading_fragment,
    undouble_struck_rows,
)
from .record_design_pdf_state import PdfParseState, contiguity_failure, extract_pdf_lines
from .record_design_pdf_visual import (
    extract_pdf_text_lines,
    extract_pdfplumber_text_lines,
    extract_visual_record_design_chart,
    snapshot_pdf_page,
    uses_page_record_layout,
)
from .record_design_schema import RecordDesignExtraction, RecordDesignSkippedSheet
from .record_design_sources import EMPTY_CORRECTIONS, CorrectionIndex, load_corrections


@lru_cache(maxsize=256)
def extract_record_design_pdf_cached(
    path: str,
    byte_count: int,
    modified_ns: int,
) -> RecordDesignExtraction:
    """Extract and cache one record-design PDF's parsed sheets, keyed on its identity.

    ``byte_count`` and ``modified_ns`` are cache-key components only, invalidating
    the cache when the file changes on disk; the extraction itself reads the file
    fresh from ``path``.
    """
    del byte_count, modified_ns
    source_path = Path(path)
    corrections = load_corrections(source_path)
    with source_path.open("rb") as pdf_file:
        return extract_record_design_pdf_stream(
            pdf_file,
            source_label=str(source_path),
            corrections=corrections,
        )


def extract_record_design_pdf_stream(
    stream: BufferedReader | BytesIO,
    *,
    source_label: str,
    corrections: CorrectionIndex = EMPTY_CORRECTIONS,
) -> RecordDesignExtraction:
    """Read a record-design PDF's sheets from an open stream, trying repairs and visual fallback in turn.

    Raises:
        RegistryValidationError: When no text can be extracted, or every text
            and visual reading strategy fails to produce a usable extraction.
    """
    import pdfplumber

    pdf_bytes = stream.read()
    base_lines = extract_pdf_text_lines(pdf_bytes, source_label=source_label)
    lines = reattach_stranded_casilla_tags(
        split_row_from_wrapped_content(
            split_fused_ordinal_offset_rows(
                collapse_doubled_coordinate_rows(
                    collapse_stuttered_row_prefix(join_wrapped_row_descriptions(base_lines)),
                ),
            ),
        ),
    )
    if uses_page_record_layout(base_lines):
        page_lines = reattach_stranded_casilla_tags(
            collapse_stuttered_row_prefix(
                join_wrapped_row_descriptions(
                    extract_pdfplumber_text_lines(pdf_bytes, source_label=source_label),
                ),
            ),
        )
        lines = _better_page_record_lines(
            page_lines,
            lines,
            source_label=source_label,
            corrections=corrections,
        )
    if not any(line.strip() for line in lines):
        raise RegistryValidationError(f"no text extracted from record-design PDF {source_label}")
    try:
        return _read_with_reversed_column_repair(lines, source_label=source_label, corrections=corrections)
    except ValueError as pdfium_exc:
        text_fallback_error = pdfium_exc
        try:
            fallback_lines = extract_pdfplumber_text_lines(pdf_bytes, source_label=source_label)
            return extract_pdf_lines(fallback_lines, source_label=source_label, corrections=corrections)
        except ValueError as fallback_exc:
            text_fallback_error = fallback_exc
        if "did not contain parseable field rows" not in str(text_fallback_error):
            raise text_fallback_error from pdfium_exc
        try:
            with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
                pages = tuple(snapshot_pdf_page(page) for page in pdf.pages)
        except Exception as pdf_exc:  # pragma: no cover - defensive; pdfplumber surface
            raise RegistryValidationError(
                f"pdfplumber could not open record-design PDF {source_label}: {pdf_exc}",
            ) from pdf_exc
        visual_chart = extract_visual_record_design_chart(pages, source_label=source_label)
        if visual_chart:
            # The geometry reader was documented as "complete by construction",
            # and it is not: modelo 349's 2002 edition and modelo 180's 2000
            # edition both reconstruct here with 40-to-65-byte runs missing from
            # every record, and reported ``is_complete`` because nothing checked.
            # It is a READER like any other, so it answers to the same contiguity
            # question -- a sheet whose rows do not tile its declared extent is
            # reported as skipped rather than handed over as whole.
            broken = {sheet.name: reason for sheet in visual_chart if (reason := contiguity_failure(sheet)) is not None}
            return RecordDesignExtraction(
                source=source_label,
                sheets=tuple(sheet for sheet in visual_chart if sheet.name not in broken),
                skipped=tuple(RecordDesignSkippedSheet(name=name, reason=reason) for name, reason in broken.items()),
            )
        raise


def _better_page_record_lines(
    page_lines: tuple[str, ...],
    base_lines: tuple[str, ...],
    *,
    source_label: str,
    corrections: CorrectionIndex,
) -> tuple[str, ...]:
    """Return whichever text extraction reads a page-record design more completely.

    A design that names its records by page is read through pdfplumber, because
    the plain text extractor does not recover those headings. That switch was
    unconditional, and it is not free: pdfplumber emits some rows' columns in an
    order the line repairs cannot reassemble, and where a row's tail is lost the
    damage is not only a hole. Modelo 390's 2015 edition is the worked case --
    under pdfplumber its ``Pág. 7`` loses the row at ``@132`` AND mis-pairs the
    surviving tail onto ``@115``, so that position carried casilla ``[654]``
    where five sibling editions (2016, 2017, 2018, 2019-2020 and 2025, all read
    cleanly) agree it is ``[523]``. The plain extraction reads the same design
    whole, all nine records, with both descriptions matching those siblings.

    So the choice is MEASURED per design rather than decided by the heading
    heuristic alone, in the idiom :func:`_read_with_reversed_column_repair`
    already uses: the page-record read stands unless the alternative is strictly
    better, so a design the switch serves today cannot be perturbed. "Better" is
    fewer skipped records first -- a skipped record is a whole record nobody can
    read -- and fewer uncovered positions only as a tie-break.

    The wrong-pairing half of that damage is worth stating plainly, because the
    reversed-column repair's own docstring says a wrong pairing "cannot pass
    quietly: it would place a field at a position some other row already
    covers". Here it did pass quietly: the mis-paired tail tiled exactly, and
    only the orphaned head left a hole for :func:`contiguity_failure` to find.
    A pairing that tiles is invisible to that check.
    """

    def read(candidate: tuple[str, ...]) -> RecordDesignExtraction | None:
        try:
            return _read_with_reversed_column_repair(
                candidate,
                source_label=source_label,
                corrections=corrections,
            )
        except (ValueError, RegistryValidationError):
            return None

    page_read = read(page_lines)
    if page_read is not None and not page_read.skipped:
        return page_lines
    base_read = read(base_lines)
    if base_read is None:
        return page_lines
    if page_read is None:
        return base_lines
    if len(base_read.skipped) != len(page_read.skipped):
        return base_lines if len(base_read.skipped) < len(page_read.skipped) else page_lines
    page_unread = _unread_positions_over_lines(
        page_lines,
        source_label=source_label,
        corrections=corrections,
    )
    base_unread = _unread_positions_over_lines(
        base_lines,
        source_label=source_label,
        corrections=corrections,
    )
    return base_lines if base_unread < page_unread else page_lines


def _read_with_reversed_column_repair(
    lines: tuple[str, ...],
    *,
    source_label: str,
    corrections: CorrectionIndex,
) -> RecordDesignExtraction:
    """Read the design, retrying with the reversed-column repair only where it can help.

    The repair reassembles a row whose PDF columns were emitted out of order. It
    recovers a great deal -- roughly 8,800 positions across modelo 200's three
    oldest editions -- but a design may emit the SAME row both split and intact,
    and a line-level view cannot tell those apart. Applied unconditionally it
    added twelve duplicate importe fields to each of modelo 200's 2012-2014
    editions, which had no unread positions at all, and contiguity permits that
    as containment, so it would have been silent.

    So the decision is made at DESIGN level, on two exact quantities rather than
    on a judgement about any line. A design that reports nothing skipped has
    nothing for this repair to recover and is never offered one -- its first
    read is what it returns, so a clean design cannot be perturbed. Where
    something IS skipped, the repaired read is kept only if it skips no more
    sheets and leaves strictly fewer positions uncovered -- counted across every
    record the lines produce, including the ones that stay reported, because
    that is where this repair does its work.
    """
    first = extract_pdf_lines(lines, source_label=source_label, corrections=corrections)
    if not first.skipped:
        return first
    repaired_lines = recover_coordinate_stutter_rows(
        repair_truncated_offset_rows(
            rejoin_bare_coordinate_rows(
                split_glued_naturaleza_rows(
                    split_fused_ordinal_position_prefix(
                        reattach_stranded_casilla_tags(
                            collapse_stuttered_row_prefix(
                                join_wrapped_row_descriptions(
                                    rejoin_reversed_column_rows(
                                        split_tail_from_leading_fragment(undouble_struck_rows(lines)),
                                    ),
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )
    try:
        repaired = extract_pdf_lines(
            repaired_lines,
            source_label=source_label,
            corrections=corrections,
            repair_glued_rows=True,
        )
    except ValueError:
        return first
    if len(repaired.skipped) > len(first.skipped):
        return first
    before = _unread_positions_over_lines(lines, source_label=source_label, corrections=corrections)
    after = _unread_positions_over_lines(
        repaired_lines,
        source_label=source_label,
        corrections=corrections,
        repair_glued_rows=True,
    )
    return repaired if after < before else first


def _unread_positions_over_lines(
    lines: tuple[str, ...],
    *,
    source_label: str,
    corrections: CorrectionIndex,
    repair_glued_rows: bool = False,
) -> int:
    """Positions no row covers, counted over EVERY record these lines produce.

    Deliberately measured on the parse state rather than on the finished
    extraction, and that is the whole reason this function exists. A record
    whose rows do not tile its extent is reported instead of handed over, so it
    is absent from ``sheets`` -- and the reversed-column repair recovers rows
    precisely inside such records, which stay incomplete for other reasons.
    Every quantity the extraction exposes is therefore identical either side of
    the repair while thousands of positions differ, which is what made two
    earlier decision rules read as "no improvement" and leave the repair dead.
    """
    state = PdfParseState(
        source_label=source_label,
        corrections=corrections,
        repair_glued_rows=repair_glued_rows,
    )
    for number, line in enumerate(lines, start=1):
        state.feed(line, number)
    state.close_current_body()
    total = 0
    for result in state.results:
        sheet = result.sheet
        if sheet.total_positions is None or not sheet.fields:
            continue
        covered: set[int] = set()
        for parsed_field in sheet.fields:
            covered.update(range(parsed_field.offset, parsed_field.offset + parsed_field.length))
        total += len(set(range(1, sheet.total_positions + 1)) - covered)
    return total
