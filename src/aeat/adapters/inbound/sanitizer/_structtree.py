"""StructTree drop for :mod:`aeat.adapters.inbound.sanitizer`.

The Tagged-PDF structure tree (``Root.StructTreeRoot``) carries
accessibility text via ``/ActualText``, ``/Alt``, and ``/E``
entries. Scrubbing the body Tj operands does not automatically
catch these — the structure tree is a parallel surface. The
AstraZeneca contract redaction failure was rooted in this gap.

The sanitiser drops the entire StructTreeRoot rather than walking
it. Drop > scrub: a missed key is a leak; lost accessibility
metadata in a regression-test fixture is harmless. The
:class:`SanitizationWarning` ``structtree_dropped_lossy`` records
the trade-off so callers know the fixture is no longer
screen-reader-equivalent to the source.
"""

from __future__ import annotations

from pikepdf import Pdf

from ._records import SanitizationWarning, ScrubbedSurface


def drop_struct_tree(pdf: Pdf) -> tuple[ScrubbedSurface, tuple[SanitizationWarning, ...]]:
    """Removes ``Root.StructTreeRoot`` if present.

    Args:
        pdf: An open PDF whose StructTree should be wiped.

    Returns:
        A 2-tuple of (counter, warnings). The counter is a :class:`ScrubbedSurface`
        that is zero when the tree was absent and one when it was dropped. Warnings
        carry :class:`SanitizationWarning` ``structtree_dropped_lossy`` when the tree
        was present so callers see the lossy step in the audit log.
    """
    warnings: tuple[SanitizationWarning, ...] = ()
    if "/StructTreeRoot" not in pdf.Root:
        return ScrubbedSurface(surface="structtree_dropped", count=0), warnings

    del pdf.Root["/StructTreeRoot"]
    # MarkInfo declares the document is structured; lying about it
    # after dropping the tree is dishonest, so wipe the marker too.
    if "/MarkInfo" in pdf.Root:
        del pdf.Root["/MarkInfo"]

    warnings = (
        SanitizationWarning(
            code="structtree_dropped_lossy",
            detail="Source PDF carried a Tagged-PDF structure tree; the sanitiser "
            "dropped it wholesale to avoid leaking accessibility text.",
        ),
    )
    return ScrubbedSurface(surface="structtree_dropped", count=1), warnings
