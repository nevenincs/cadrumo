"""The summary lines of the frontend column: the Frontend sentence and the trees folded.

Both read a finished :class:`.frontend.FrontendComparison`; the grading itself stays in :mod:`.frontend`.
"""

from __future__ import annotations

from .frontend import SURFACE_LABELS, SURFACES, FrontendComparison


def _unmatched_suffix(comparison: FrontendComparison) -> str:
    """``; not matched: window differs 3, not run 2``: a row a surface differs on apart from one it did not run."""
    groups = []
    for surface in SURFACES:
        if unmatched := comparison.unmatched(surface):
            groups.append(
                f"{SURFACE_LABELS[surface]} " + ", ".join(f"{word} {count}" for word, count in unmatched.items())
            )
    return "; not matched: " + "; ".join(groups) if groups else ""


def frontend_line(comparison: FrontendComparison) -> str:
    """The summary sentence, ``Frontend: TUI matched a / N, window matched b / N, CLI matched c / N (N rows)``.

    After the total it lists, per surface, the rows not matched by why (differs apart from not run), then the rows
    matched on redacted casillas and, aged by the tree of the surface line, the filed rows whose surface states no
    file stage, when there are any.
    """
    total = len(comparison.rows)
    matched = ", ".join(
        f"{SURFACE_LABELS[surface]} matched {comparison.matched(surface)} / {total}" for surface in SURFACES
    )
    redacted = ", ".join(
        f"{SURFACE_LABELS[surface]} {count}"
        for surface in SURFACES
        if (count := comparison.matched_on_redacted(surface))
    )
    suffix = (
        f"; rows matched on redacted casillas (by presence, against the backend row's text value): {redacted}"
        if redacted
        else ""
    )
    unmatched = _unmatched_suffix(comparison)
    return f"Frontend: {matched} ({total} rows){unmatched}{suffix}{_file_not_measured_suffix(comparison)}"


def _file_not_measured_suffix(comparison: FrontendComparison) -> str:
    """``; file not measured (filed rows whose surface line states no file stage): TUI 12 (tree abc 7, def 5)``."""
    groups = []
    for surface in SURFACES:
        unmeasured = comparison.file_not_measured(surface)
        if unmeasured:
            ages = ", ".join(f"{tree} {count}" for tree, count in sorted(unmeasured.items()))
            groups.append(f"{SURFACE_LABELS[surface]} {sum(unmeasured.values())} (trees {ages})")
    if not groups:
        return ""
    return (
        "; file not measured (filed rows whose surface line states no file stage, neither matched nor different): "
        + ", ".join(groups)
    )


def trees_line(comparison: FrontendComparison) -> str:
    """``Trees folded: tui abc (5), def (2); window abc (3)``: per surface, each tree and the table rows it covers.

    A surface with no result is omitted; ``none`` stands when no surface has one.
    """
    groups = []
    for surface in SURFACES:
        folded = comparison.trees_folded(surface)
        if folded:
            groups.append(f"{surface} " + ", ".join(f"{tree} ({count})" for tree, count in sorted(folded.items())))
    return "Trees folded: " + ("; ".join(groups) or "none")
