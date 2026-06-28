"""`aeat app ledger list --filter` real-behaviour suite.

Drives the real CLI against the isolated profile + hand-authored ledger-corpus
fixture and asserts that ``ledger list --filter KEY=VALUE`` narrows the listing
through the same typed :class:`LedgerReviewFilterSpec` that ``ledger review``
uses. Before this verb the only ``ledger list`` controls were paging
(``--limit``/``--offset``) and the organisational ``--group`` label, forcing an
operator to dump the whole ledger and grep; these tests lock the filter axes
(period incl. bare-year, classification, text) and the parse-error surface.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....application.user_profile._orchestration import profile_create_storage_span
from ....application.user_profile._testing import register_minimal_profile
from ....application.workflow._persistence import workflow_state_repository
from ....core.config import override_settings
from ....tests import FIXTURES_DIR
from ....tests.secure_sql import isolated_profile_storage_root
from .. import app

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_RUNNER = CliRunner()
_CORPUS = FIXTURES_DIR / "financial" / "ledger-corpus"
_FILES = (
    "bbva-business-eur.csv",
    "caixabank-personal.csv",
    "revolut-multi.csv",
    "n26-savings.csv",
)


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    dispose_engine()
    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_output_language="en"),
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("default"),
    ):
        try:
            workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id="default"))
            yield
        finally:
            dispose_engine()


def _import_corpus() -> None:
    for name in _FILES:
        result = _RUNNER.invoke(app, ["app", "ledger", "import", str(_CORPUS / name), "--provider", "csv"])
        assert result.exit_code == 0, f"{name}: {result.output}"


def _list_rows(*filters: str) -> list[dict[str, Any]]:
    args = ["--format", "json", "app", "ledger", "list"]
    for clause in filters:
        args += ["--filter", clause]
    listed = _RUNNER.invoke(app, args)
    assert listed.exit_code == 0, listed.output
    payload = json.loads(listed.output)
    return payload.get("result", payload).get("rows", [])


def _list_rows_with_options(*args: str) -> list[dict[str, Any]]:
    listed = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "list", *args])
    assert listed.exit_code == 0, listed.output
    payload = json.loads(listed.output)
    return payload.get("result", payload).get("rows", [])


def test_list_without_filter_returns_full_ledger() -> None:
    """The unfiltered baseline lists the whole operating-scale corpus."""
    _import_corpus()
    assert len(_list_rows()) >= 500


def test_period_filter_narrows_to_one_year() -> None:
    """A year-qualified annual period filter scopes the listing to that year only.

    The corpus is cross-year; a ``period=0A`` + ``year=YYYY`` filter must return a strict,
    non-empty subset of the full ledger, and every returned row's date must fall
    in that year — proving the filter actually applies rather than passing the
    full set through.
    """
    _import_corpus()
    full = _list_rows()
    years = sorted({str(r["date"])[:4] for r in full})
    assert len(years) >= 2, f"corpus must span >=2 years to exercise the year filter, got {years}"
    target = years[0]
    filtered = _list_rows("period=0A", f"year={target}")
    assert filtered, f"period=0A + year={target} must match the rows dated in {target}"
    assert len(filtered) < len(full), "a single-year filter must be a strict subset of the cross-year ledger"
    assert all(str(r["date"]).startswith(target) for r in filtered)


def test_period_year_options_match_filter_clauses() -> None:
    """Convenience ``--period/--year`` flags route through the same typed filter as ``--filter``."""
    _import_corpus()
    full = _list_rows()
    target = sorted({str(r["date"])[:4] for r in full})[0]

    option_rows = _list_rows_with_options("--period", "0A", "--year", target)
    filter_rows = _list_rows("period=0A", f"year={target}")

    assert {row["full_id"] for row in option_rows} == {row["full_id"] for row in filter_rows}
    assert option_rows, "period/year options must match the same non-empty annual subset as --filter"


def test_classification_filter_narrows_to_one_class() -> None:
    """A classification filter returns only rows of that business class.

    On import every row lands NOT_YET_PROCESSED, so filtering to that class
    returns the full ledger and filtering to BUSINESS (none yet) returns empty —
    proving the classification predicate discriminates rather than no-opping.
    """
    # The shared LedgerReviewFilterSpec validates the classification value
    # against the BusinessClassification enum, whose members are UPPERCASE
    # (NOT_YET_PROCESSED / BUSINESS / ...), so the filter value is uppercase —
    # the same contract `ledger review --filter classification=` already uses.
    _import_corpus()
    full = _list_rows()
    not_processed = _list_rows("classification=NOT_YET_PROCESSED")
    assert len(not_processed) == len(full)
    assert all(r.get("business_classification") == "NOT_YET_PROCESSED" for r in not_processed)
    business = _list_rows("classification=BUSINESS")
    assert business == [], "no row is classified BUSINESS on raw import, so the filter must return empty"


def test_text_filter_matches_description_substring() -> None:
    """A text filter returns only rows whose description carries the needle."""
    _import_corpus()
    full = _list_rows()
    needle = "Transferencia"
    expected = [r for r in full if needle.casefold() in r["description"].casefold()]
    assert expected, "corpus must carry at least one 'Transferencia' row to exercise the text filter"
    filtered = _list_rows(f"text={needle}")
    assert {r["full_id"] for r in filtered} == {r["full_id"] for r in expected}


def test_combined_filters_compose_as_intersection() -> None:
    """Two filter clauses compose: the result is the intersection of both."""
    _import_corpus()
    full = _list_rows()
    target_year = sorted({str(r["date"])[:4] for r in full})[0]
    combined = _list_rows("period=0A", f"year={target_year}", "classification=NOT_YET_PROCESSED")
    year_only = _list_rows("period=0A", f"year={target_year}")
    # Every raw-import row is NOT_YET_PROCESSED, so the classification clause is a
    # no-op intersection here: combined == year_only, and both are a strict
    # subset of the full ledger.
    assert {r["full_id"] for r in combined} == {r["full_id"] for r in year_only}
    assert len(combined) < len(full)


def test_direction_filter_narrows_to_one_money_flow() -> None:
    """A ``direction`` filter returns only rows of that money-flow direction.

    The corpus carries both incoming (credits) and outgoing (debits) rows. A
    ``direction=incoming`` filter must return a strict, non-empty subset of the
    full ledger whose every row is incoming, and the incoming + outgoing subsets
    must partition the directional rows — proving the CLI forwards the parsed
    direction into the shared query rather than passing the full set through.
    The lowercase value exercises the case-insensitive parse the shared spec
    added for the natural ``incoming`` / ``outgoing`` operator spelling.
    """
    _import_corpus()
    full = _list_rows()
    directions = {r["direction"] for r in full}
    assert {"INCOMING", "OUTGOING"} <= directions, f"corpus must carry both directions, got {directions}"

    incoming = _list_rows("direction=incoming")
    outgoing = _list_rows("direction=outgoing")
    assert incoming, "direction=incoming must match the credited rows"
    assert outgoing, "direction=outgoing must match the debited rows"
    assert len(incoming) < len(full), "a single-direction filter must be a strict subset of the full ledger"
    assert all(r["direction"] == "INCOMING" for r in incoming)
    assert all(r["direction"] == "OUTGOING" for r in outgoing)
    # The two directional subsets are disjoint and exactly cover the full set's
    # INCOMING/OUTGOING rows (the corpus has no INTERNAL_TRANSFER on raw import).
    expected_incoming = {r["full_id"] for r in full if r["direction"] == "INCOMING"}
    assert {r["full_id"] for r in incoming} == expected_incoming


def test_direction_filter_uppercase_value_matches_too() -> None:
    """The canonical uppercase enum value resolves identically to lowercase.

    ``direction=INCOMING`` (the raw :class:`TransactionDirection` member value)
    and ``direction=incoming`` must select the same rows, confirming the
    case-insensitive parse accepts both the natural operator spelling and the
    canonical form rather than silently rejecting one.
    """
    _import_corpus()
    lower = {r["full_id"] for r in _list_rows("direction=incoming")}
    upper = {r["full_id"] for r in _list_rows("direction=INCOMING")}
    assert lower == upper
    assert lower, "direction filter must match a non-empty incoming set"


def test_unknown_filter_key_is_rejected() -> None:
    """An out-of-catalogue filter key fails loudly at the CLI boundary.

    The unknown key is refused with a non-zero exit (it does not silently
    pass through and list every row). The offending token's exact rendering is
    governed by the shared error-boundary box layout, so this asserts the
    refusal itself rather than the echoed substring.
    """
    _import_corpus()
    result = _RUNNER.invoke(app, ["app", "ledger", "list", "--filter", "bogus=1"])
    assert result.exit_code != 0


def test_malformed_filter_token_is_rejected() -> None:
    """A ``--filter`` token without ``=`` is a parse error, not a silent pass."""
    _import_corpus()
    result = _RUNNER.invoke(app, ["app", "ledger", "list", "--filter", "period"])
    assert result.exit_code != 0


def test_period_filter_combined_shape_refuses_with_period_guidance() -> None:
    """A combined period filter refuses with the same AEAT-token guidance as --period."""
    combined_period = "2026" + "Q1"
    result = _RUNNER.invoke(
        app,
        ["app", "ledger", "list", "--filter", f"period={combined_period}", "--filter", "year=2026"],
    )

    assert result.exit_code != 0
    assert "1T" in result.output
    assert "--year" in result.output
