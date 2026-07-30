"""SQLite FTS5 query-fragment construction shared across search indexes."""

from __future__ import annotations

from collections.abc import Iterable


def fts_or_group(terms: Iterable[str]) -> str:
    """Build a SQLite FTS5 ``OR`` group from ``terms``.

    Each non-empty term is stripped, de-duplicated preserving first-seen order,
    quoted, and joined with the separator ``" OR "``. An all-empty or empty
    input yields the empty string. The quoting keeps a term with
    FTS5-significant characters a single match token.
    """
    unique: list[str] = []
    seen: set[str] = set()
    for term in terms:
        cleaned = term.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            unique.append(cleaned)
    return " OR ".join(f'"{term}"' for term in unique)
