"""Dynamic-surface strip for :mod:`aeat.adapters.inbound.sanitizer`.

Dynamic surfaces are the parts of a PDF that can rewrite content at
view time: embedded JavaScript, AcroForm field values, annotations,
optional content groups, attachments. The Manafort, NSA Russia
memo and AstraZeneca redaction-failure post-mortems all share the
same root cause — these surfaces must be removed *before*
content-stream rewriting so a JS action, layer toggle, or
hierarchical AcroForm field cannot re-inject PII the sanitiser
just stripped.

Each function in this module is a single-surface scrubber. They
record their work as :class:`ScrubbedSurface` rows so the
:class:`SanitizationResult` audit log carries one row per surface
that was either present-and-cleared or absent (count zero).
"""

from __future__ import annotations

import pikepdf
from pikepdf import Pdf

from ._records import SanitizationWarning, ScrubbedSurface


def strip_attachments(pdf: Pdf) -> ScrubbedSurface:
    """Remove every embedded file attachment from ``pdf``.

    Args:
        pdf: An open PDF whose attachment table should be wiped.

    Returns:
        A :class:`ScrubbedSurface` counter recording how many
        attachments were removed.
    """
    count = len(list(pdf.attachments))
    if count == 0:
        return ScrubbedSurface(surface="attachments", count=0)
    keys = list(pdf.attachments)
    for key in keys:
        del pdf.attachments[key]
    return ScrubbedSurface(surface="attachments", count=count)


def strip_javascript(pdf: Pdf) -> tuple[ScrubbedSurface, ScrubbedSurface, ScrubbedSurface]:
    """Remove embedded JavaScript from the Names tree and document actions.

    Args:
        pdf: An open PDF whose JavaScript surfaces should be wiped.

    Returns:
        A 3-tuple of :class:`ScrubbedSurface` counters
        ``(javascript, open_action, additional_actions)``. ``javascript``
        covers the ``Root.Names.JavaScript`` name tree; ``open_action``
        covers ``Root.OpenAction``; ``additional_actions`` covers ``Root.AA``
        plus per-page ``AA``.
    """
    js_count = 0
    names = pdf.Root.get("/Names")
    if names is not None and "/JavaScript" in names:
        del names["/JavaScript"]
        js_count = 1

    open_action_count = 0
    if "/OpenAction" in pdf.Root:
        del pdf.Root["/OpenAction"]
        open_action_count = 1

    aa_count = 0
    if "/AA" in pdf.Root:
        del pdf.Root["/AA"]
        aa_count += 1
    for page in pdf.pages:
        if "/AA" in page.obj:
            del page.obj["/AA"]
            aa_count += 1

    return (
        ScrubbedSurface(surface="javascript", count=js_count),
        ScrubbedSurface(surface="open_action", count=open_action_count),
        ScrubbedSurface(surface="additional_actions", count=aa_count),
    )


def strip_annotations(pdf: Pdf) -> ScrubbedSurface:
    """Drop every page annotation from ``pdf``.

    Annotations can carry PII via their ``/Contents`` strings,
    embedded files, or JavaScript actions. The sanitiser drops
    them entirely rather than scrubbing them per-key, since their
    only role in a justificante PDF is decoration.

    Args:
        pdf: An open PDF whose annotation arrays should be wiped.

    Returns:
        A :class:`ScrubbedSurface` counter of annotations removed
        across all pages.
    """
    total = 0
    for page in pdf.pages:
        annots = page.obj.get("/Annots")
        if annots is None:
            continue
        total += len(annots)
        del page.obj["/Annots"]
    return ScrubbedSurface(surface="annotation_drop", count=total)


def strip_optional_content_groups(pdf: Pdf) -> ScrubbedSurface:
    """Remove any Optional Content (layer) properties from ``pdf``.

    OCG layers can selectively show or hide content at view time —
    a redaction that hides content with a layer toggle is not a
    redaction. The sanitiser drops the layers wholesale so any
    associated content streams are visible to the body rewriter.

    Args:
        pdf: An open PDF whose ``Root.OCProperties`` should be wiped.

    Returns:
        A :class:`ScrubbedSurface` counter of OCG entries removed
        (zero or one).
    """
    if "/OCProperties" not in pdf.Root:
        return ScrubbedSurface(surface="optional_content_groups", count=0)
    del pdf.Root["/OCProperties"]
    return ScrubbedSurface(surface="optional_content_groups", count=1)


def strip_acroform(
    pdf: Pdf,
    *,
    drop_entirely: bool = False,
) -> tuple[ScrubbedSurface, tuple[SanitizationWarning, ...]]:
    """Clear AcroForm field values, optionally dropping the form structure.

    Args:
        pdf: An open PDF whose form values should be cleared.
        drop_entirely: When True, deletes ``Root.AcroForm`` outright;
            otherwise clears the ``/V`` (value) and ``/DV`` (default
            value) entries on every field while preserving the form.

    Returns:
        A 2-tuple ``(counter, warnings)``. The counter is a :class:`ScrubbedSurface`
        recording the number of fields whose values were cleared (or 1 when the
        form was dropped wholesale). The warnings tuple contains
        :class:`SanitizationWarning` entries, including ``unknown_surface_present``
        when a hierarchical form (``/Kids`` chains) is detected.
    """
    acroform = pdf.Root.get("/AcroForm")
    if acroform is None:
        if drop_entirely:
            return ScrubbedSurface(surface="acroform_dropped", count=0), ()
        return ScrubbedSurface(surface="acroform_field_value", count=0), ()

    if drop_entirely:
        del pdf.Root["/AcroForm"]
        return ScrubbedSurface(surface="acroform_dropped", count=1), ()

    fields = acroform.get("/Fields")
    if fields is None:
        return ScrubbedSurface(surface="acroform_field_value", count=0), ()
    cleared = 0
    has_kids = False
    # `Object` is the base pikepdf type and ty's metadata doesn't
    # advertise iteration on it directly; the runtime exposes a
    # numeric index. Loop with an explicit range to keep both the
    # type checker and pikepdf happy.
    for index in range(len(fields)):
        field = fields[index]
        if "/V" in field:
            del field["/V"]
            cleared += 1
        if "/DV" in field:
            del field["/DV"]
        if "/Kids" in field:
            has_kids = True

    warnings: tuple[SanitizationWarning, ...] = ()
    if has_kids:
        warnings = (
            SanitizationWarning(
                code="unknown_surface_present",
                detail=(
                    "AcroForm carries hierarchical /Kids chains; child fields' /V "
                    "values may survive the in-place clear. Pass drop_acroform=True "
                    "to wipe the form structure entirely, or extend the sanitiser "
                    "to recurse into /Kids before re-running."
                ),
            ),
        )
    return ScrubbedSurface(surface="acroform_field_value", count=cleared), warnings


def strip_thumbnails(pdf: Pdf) -> ScrubbedSurface:
    """Drop every page-level rasterised thumbnail.

    Thumbnails can carry PII visible at a glance even after body
    sanitisation — a renderer that ignores the body but renders the
    thumbnail would still leak the original.

    Args:
        pdf: An open PDF whose page thumbnails should be wiped.

    Returns:
        A :class:`ScrubbedSurface` counter of thumbnails removed
        across all pages.
    """
    count = 0
    for page in pdf.pages:
        if "/Thumb" in page.obj:
            del page.obj["/Thumb"]
            count += 1
    return ScrubbedSurface(surface="page_thumbnail", count=count)


def strip_outlines(pdf: Pdf) -> ScrubbedSurface:
    """Remove the document outline (bookmarks) tree.

    Bookmarks have historically retained the redacted term in the
    AstraZeneca contract failure case. The sanitiser drops them.

    Args:
        pdf: An open PDF whose outline should be wiped.

    Returns:
        A :class:`ScrubbedSurface` counter (zero or one).
    """
    if "/Outlines" not in pdf.Root:
        return ScrubbedSurface(surface="outlines", count=0)
    del pdf.Root["/Outlines"]
    return ScrubbedSurface(surface="outlines", count=1)


def strip_page_labels(pdf: Pdf) -> ScrubbedSurface:
    """Remove per-page label dictionaries.

    Args:
        pdf: An open PDF whose ``Root.PageLabels`` should be wiped.

    Returns:
        A :class:`ScrubbedSurface` counter (zero or one).
    """
    if "/PageLabels" not in pdf.Root:
        return ScrubbedSurface(surface="page_labels", count=0)
    del pdf.Root["/PageLabels"]
    return ScrubbedSurface(surface="page_labels", count=1)


# Keep the module pikepdf import resolvable even if the type
# checker does not see :func:`strip_javascript` calling it
# transitively — `pikepdf` is the only runtime dep here.
_ = pikepdf  # silence "unused import" complaint without losing the dep edge
