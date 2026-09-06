"""Which files a folder import reads, and in what order.

Two properties matter and neither is presentation. The extension filter decides
what gets handed to a statement parser — a stray note or an exported PDF beside
the statements must not be — and the order decides what the aggregated result
means, because several files fold into one answer. A filesystem-dependent order
would make the same folder import differently on two machines.

Refusing an empty directory is the third: the alternative is an import that
reports success having read nothing, which reads to an operator as "your
statements contained no transactions".
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ....domain.transactions.errors import TransactionValidationError
from ..actions_import import IMPORTABLE_SOURCE_EXTENSIONS, plan_ledger_import_sources

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_a_single_file_resolves_to_itself_whatever_its_extension() -> None:
    """A named file is the operator's explicit choice, not a candidate to filter.

    The extension filter exists to pick statements out of a mixed folder; a
    file named directly has already been chosen, and second-guessing it would
    refuse a validly-named statement with an unusual suffix.
    """
    named = Path("statement.dat")

    assert plan_ledger_import_sources(named) == (named,)


def test_a_directory_yields_only_importable_extensions(tmp_path: Path) -> None:
    """A note or an invoice PDF beside the statements must not reach a parser."""
    (tmp_path / "march.csv").write_text("x", encoding="utf-8")
    (tmp_path / "april.ofx").write_text("x", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("x", encoding="utf-8")
    (tmp_path / "invoice.pdf").write_text("x", encoding="utf-8")

    planned = plan_ledger_import_sources(tmp_path)

    assert sorted(item.name for item in planned) == ["april.ofx", "march.csv"]


def test_the_extension_match_ignores_case(tmp_path: Path) -> None:
    """An uppercase suffix is the same statement; exports capitalise freely."""
    (tmp_path / "MARCH.CSV").write_text("x", encoding="utf-8")

    assert [item.name for item in plan_ledger_import_sources(tmp_path)] == ["MARCH.CSV"]


def test_the_plan_is_deterministically_ordered(tmp_path: Path) -> None:
    """Order is part of the contract: the files fold into one aggregated result."""
    for name in ("c.csv", "a.csv", "b.csv"):
        (tmp_path / name).write_text("x", encoding="utf-8")

    first = plan_ledger_import_sources(tmp_path)
    second = plan_ledger_import_sources(tmp_path)

    assert [item.name for item in first] == ["a.csv", "b.csv", "c.csv"]
    assert first == second


def test_a_directory_holding_no_statement_is_refused(tmp_path: Path) -> None:
    """Silence here would read as 'your statements were empty'."""
    (tmp_path / "notes.txt").write_text("x", encoding="utf-8")

    with pytest.raises(TransactionValidationError):
        plan_ledger_import_sources(tmp_path)


def test_an_entirely_empty_directory_is_refused(tmp_path: Path) -> None:
    """The same refusal, with nothing at all to filter."""
    with pytest.raises(TransactionValidationError):
        plan_ledger_import_sources(tmp_path)


def test_the_refusal_names_what_would_have_been_accepted() -> None:
    """An operator told only 'nothing found' cannot tell what to rename."""
    with pytest.raises(TransactionValidationError) as excinfo:
        plan_ledger_import_sources(Path(__file__).parent)

    context = getattr(excinfo.value, "context", None) or {}
    assert "accepted_extensions" in context
    assert ".csv" in str(context["accepted_extensions"])


def test_subdirectories_are_not_descended_into(tmp_path: Path) -> None:
    """A folder import reads that folder; recursion would surprise an operator.

    Nested statements are commonly archives of already-imported periods, so
    descending would silently re-import them.
    """
    (tmp_path / "march.csv").write_text("x", encoding="utf-8")
    nested = tmp_path / "archive"
    nested.mkdir()
    (nested / "old.csv").write_text("x", encoding="utf-8")

    assert [item.name for item in plan_ledger_import_sources(tmp_path)] == ["march.csv"]


def test_the_accepted_set_covers_the_shipped_statement_formats() -> None:
    """A silently narrowed set would refuse formats the parsers still read."""
    assert {".csv", ".tsv", ".ofx", ".qfx", ".xls", ".xlsx"} <= IMPORTABLE_SOURCE_EXTENSIONS
