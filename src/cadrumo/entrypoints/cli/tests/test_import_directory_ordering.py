"""Regression: the ledger-import directory scan feeds sorted, deterministic order.

A directory scan that feeds
ordered output (here, the order statement files are imported, which affects
created-row order) must be sorted at the boundary rather than left in
OS-dependent ``iterdir`` order. ``_resolve_import_paths`` already sorts; this gate
pins that invariant so a future edit cannot silently regress it to raw scan
order.

The sibling output-ordering site — the profile inventory scan in
``CommittedProfileRepository.list`` — is deliberately NOT sorted at the scan: it feeds
no ordered output. Its consumer is the order-independent duplicate-tax-id
uniqueness guard, and the operator-facing profile listing is a separate
bucket-directory scan (``list_profile_buckets``) that never reads it. Sorting
this scan would be the misleading noise Decision 3 rejects.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .._ledger_import_cli import _resolve_import_paths

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_directory_import_returns_files_in_sorted_order(tmp_path: Path) -> None:
    # Create files in deliberately non-sorted creation order.
    for name in ("c.csv", "a.csv", "b.csv"):
        (tmp_path / name).write_text("date,amount\n", encoding="utf-8")
    # A non-importable extension is excluded regardless of order.
    (tmp_path / "notes.txt").write_text("ignore me", encoding="utf-8")

    resolved = _resolve_import_paths(tmp_path)

    assert [p.name for p in resolved] == ["a.csv", "b.csv", "c.csv"]


def test_single_file_path_is_returned_as_is(tmp_path: Path) -> None:
    statement = tmp_path / "statement.csv"
    statement.write_text("date,amount\n", encoding="utf-8")
    # A tuple since the plan moved to the application layer: the resolved
    # sources are a fixed plan, not a list the caller may amend.
    assert _resolve_import_paths(statement) == (statement,)
