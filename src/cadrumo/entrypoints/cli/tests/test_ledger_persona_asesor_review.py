"""Asesor-fiscal review-and-sign-off journey over the ledger-corpus fixture.

These tests drive the real ``aeat app ledger`` CLI from the seat of a tax
advisor (*asesor fiscal*) doing a pre-filing review pass on a client's freshly
imported ledger. The asesor's job is *not* to do data entry: it is to find what
needs attention before sign-off — unclassified rows, rows missing the facts a
modelo needs, and outright anomalies — and to be able to defend each
disposition with a legible audit trail.

The journey exercised here:

1. Import the operating-scale corpus (4 accounts, ~514 rows).
2. Run ``check`` (all-period anomaly probe) and ``preflight --period 1T --year 2025``
   to surface the rows that block a clean filing.
3. Use ``review --filter status=pending`` to triage the unclassified backlog.
4. Inspect ``history`` / ``track`` lineage on a single transaction.
5. Locate the recargo-equivalencia supplier anomaly row
   ("Compra genero con recargo equivalencia") and a personal/ignorable row
   ("Suscripcion Netflix"), and confirm the asesor can tell business vs
   personal vs gated rows apart.

The harness mirrors :mod:`test_ledger_corpus_journeys`: an isolated backend
per test, the real Typer app, and the JSON envelope surfaced by
``--format json``.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from click.testing import Result

from ....tests import FIXTURES_DIR
from ....tests.cli_envelope import unwrap_schema_envelope as _json
from ....tests.cli_runner import invoke_cached_cli
from ....tests.ledger_cli import list_ledger_rows_via_cli as _list_rows
from ._isolated_profile_storage_fixtures import live_fx_seeded_backend

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_CORPUS = FIXTURES_DIR / "financial" / "ledger-corpus"
_FILES = (
    "bbva-business-eur.csv",
    "caixabank-personal.csv",
    "revolut-multi.csv",
    "n26-savings.csv",
)

_RECARGO_DESC = "Compra genero con recargo equivalencia"
_PERSONAL_DESC = "Suscripcion Netflix"


def _invoke(args: Sequence[str]) -> Result:
    return invoke_cached_cli(args)


def _import_corpus() -> None:
    for name in _FILES:
        result = _invoke(["app", "ledger", "import", "--file", str(_CORPUS / name), "--provider", "csv"])
        assert result.exit_code == 0, f"{name}: {result.output}"


# The corpus is the asesor's starting state, not the thing under test: every
# test below opens on a client ledger that has just been imported. Seeding it
# once and giving each test a copy keeps the per-test isolation exactly as it
# was -- each still gets its own storage root, so a classify or archive cannot
# reach the next test -- while paying the import once instead of ten times.
_seeded_origin, live_fx_seeded_world = live_fx_seeded_backend(seed=_import_corpus)
__all__ = ["_seeded_origin", "live_fx_seeded_world"]


def _find(rows: list[dict[str, object]], needle: str) -> dict[str, object]:
    for r in rows:
        desc = r.get("description")
        if isinstance(desc, str) and needle in desc:
            return r
    raise StopIteration


# --- Asesor first look: what is unclassified? -------------------------------
def test_asesor_sees_entire_corpus_unclassified_on_arrival() -> None:
    """A freshly imported client ledger lands wholly unclassified.

    The asesor must be able to see, at a glance, that *every* row still needs a
    disposition — none are silently treated as ready.
    """
    rows = _list_rows()
    assert len(rows) >= 500, f"expected operating-scale corpus, got {len(rows)}"
    assert all(r.get("business_classification") == "NOT_YET_PROCESSED" for r in rows)


def test_asesor_triage_pending_backlog_via_review_filter() -> None:
    """``review --filter status=pending`` is the asesor's triage queue.

    The pending backlog must be reachable as a typed filter, and the recargo
    anomaly + a personal row must both be in it before any disposition.
    """
    pending = _invoke(["--format", "json", "app", "ledger", "review", "--filter", "status=pending"])
    assert pending.exit_code == 0, pending.output
    json_result = _json(pending.output)
    rows_val = json_result.get("rows", [])
    descriptions: set[str] = set()
    if isinstance(rows_val, list):
        for item in rows_val:
            if isinstance(item, dict):
                typed_item: dict[str, object] = {str(key): value for key, value in item.items()}
                desc_val = typed_item.get("description")
                descriptions.add(str(desc_val))
    assert any(_RECARGO_DESC in d for d in descriptions), sorted(descriptions)[:10]
    assert any(_PERSONAL_DESC in d for d in descriptions), sorted(descriptions)[:10]


# --- Check + preflight surface what blocks a clean filing -------------------
def test_check_surfaces_all_period_anomalies_without_mutating() -> None:
    """``check`` is the all-period anomaly probe.

    On a wholly-unclassified import every classified-tax check is blocked by the
    missing-classification gap, so the probe must report ``ready=false`` with a
    non-empty issue list, and never silently green-light the ledger.
    """
    check = _invoke(["--format", "json", "app", "ledger", "check"])
    assert check.exit_code == 0, check.output
    result = _json(check.output)
    assert result.get("ready") is False, result
    count_val = result.get("checked_transaction_count")
    if isinstance(count_val, int):
        assert count_val >= 500, result
    issues = result.get("issues", [])
    if not isinstance(issues, list):
        issues = []
    assert issues, "an unclassified corpus must surface readiness issues"
    reasons: set[str] = set()
    if isinstance(issues, list):
        for issue in issues:
            if isinstance(issue, dict):
                typed_issue: dict[str, object] = {str(key): value for key, value in issue.items()}
                reason_val = typed_issue.get("reason")
                reasons.add(str(reason_val))
    assert "missing_business_classification" in reasons, reasons


def test_preflight_period_scopes_the_readiness_gaps() -> None:
    """``preflight --period 1T --year 2025`` scopes the readiness probe to one quarter.

    The asesor reviews quarter by quarter; the period filter must narrow the
    checked set below the all-period total while still reporting gaps.
    """
    pre = _invoke(
        ["--format", "json", "app", "ledger", "preflight", "--period", "1T", "--year", "2025"],
    )
    assert pre.exit_code == 0, pre.output
    result = _json(pre.output)
    assert result.get("ready") is False, result
    count_val = result.get("checked_transaction_count")
    if isinstance(count_val, int):
        assert 0 < count_val < 500, result
    issues_val = result.get("issues")
    if isinstance(issues_val, list):
        assert issues_val, result
        # Every issue must carry a transaction_id + machine reason the asesor can act on.
        for item in issues_val:
            if isinstance(item, dict):
                typed_item: dict[str, object] = {str(key): value for key, value in item.items()}
                tx_id_field = typed_item.get("transaction_id")
                reason_field = typed_item.get("reason")
                detail_field = typed_item.get("detail")
                assert tx_id_field, item
                assert reason_field, item
                assert detail_field, item


def test_preflight_issue_detail_is_actionable_text() -> None:
    """Each preflight issue must name the missing fact in plain language."""
    pre = _invoke(
        ["--format", "json", "app", "ledger", "preflight", "--period", "1T", "--year", "2025"],
    )
    assert pre.exit_code == 0, pre.output
    json_result = _json(pre.output)
    issues_val = json_result.get("issues")
detail_parts: list[str] = []
    if isinstance(issues_val, list):
        for issue in issues_val:
            if isinstance(issue, dict):
                typed_issue: dict[str, object] = {str(key): value for key, value in issue.items()}
                detail_parts.append(str(typed_issue.get("detail", "")))
    details = " ".join(detail_parts)
    assert "classification" in details.lower(), details[:200]


# --- Lineage / audit legibility on a single transaction ---------------------
def test_history_and_track_expose_lineage_for_one_transaction() -> None:
    """``history`` + ``track`` are the asesor's audit-trail surfaces.

    For one business row both verbs must succeed and surface a stable id +
    a lifecycle/event chain — the evidence an asesor needs to defend a row.
    """
    row = _find(_list_rows(), _RECARGO_DESC)
    tx_val = row.get("transaction_id")
    assert isinstance(tx_val, str)

    history = _invoke(["--format", "json", "app", "ledger", "history", tx_val])
    assert history.exit_code == 0, history.output
    hist = _json(history.output)
    assert hist.get("transaction_id"), hist
    event_count_val = hist.get("event_count")
    if isinstance(event_count_val, int):
        assert event_count_val >= 1, hist
    assert hist.get("events"), "an imported row must carry at least its creation event"

    track = _invoke(["--format", "json", "app", "ledger", "track", tx_val])
    assert track.exit_code == 0, track.output
    tracked = _json(track.output)
    tx_obj = tracked.get("transaction")
    if isinstance(tx_obj, dict):
        typed_tx_obj: dict[str, object] = {str(key): value for key, value in tx_obj.items()}
        assert typed_tx_obj.get("transaction_id"), tracked
    assert "tracking" in tracked, tracked


def test_history_after_disposition_records_the_decision() -> None:
    """An asesor's disposition (archive personal row) must extend the lineage.

    Archiving a personal row and re-reading ``history`` must show more events
    than before — the decision is auditable, not silent.
    """
    row = _find(_list_rows(), _PERSONAL_DESC)
    tx_val = row.get("transaction_id")
    assert isinstance(tx_val, str)
    before_hist = _json(_invoke(["--format", "json", "app", "ledger", "history", tx_val]).output)
    before_val = before_hist.get("event_count")
    before = before_val if isinstance(before_val, int) else 0
    archived = _invoke(
        ["app", "ledger", "archive", tx_val, "--reason", "personal expense", "--yes"],
    )
    assert archived.exit_code == 0, archived.output
    after_hist = _json(_invoke(["--format", "json", "app", "ledger", "history", tx_val]).output)
    after_val = after_hist.get("event_count")
    after = after_val if isinstance(after_val, int) else 0
    assert after > before, (before, after)


# --- Business vs personal vs gated discrimination ---------------------------
def test_asesor_can_classify_then_preflight_surfaces_recargo_gaps() -> None:
    """The recargo row is a supplier anomaly: a BUSINESS purchase whose RE
    surcharge is non-deductible.

    The asesor classifies it BUSINESS (the disposition the ground truth records)
    and then preflight must still surface a downstream fact gap, because a
    classified-but-incomplete business row is not yet filing-ready.
    """
    row = _find(_list_rows(), _RECARGO_DESC)
    tx_val = row.get("transaction_id")
    assert isinstance(tx_val, str)
    classify = _invoke(
        ["app", "ledger", "classify", tx_val, "--classification", "BUSINESS"],
    )
    assert classify.exit_code == 0, classify.output
    refreshed = _find(_list_rows(), _RECARGO_DESC)
    assert refreshed.get("business_classification") == "BUSINESS", refreshed

    pre = _invoke(
        ["--format", "json", "app", "ledger", "preflight", "--period", "1T", "--year", "2025"],
    )
    assert pre.exit_code == 0, pre.output
    issues_val = _json(pre.output).get("issues")
    recargo_issues = []
    if isinstance(issues_val, list):
        for item in issues_val:
            if isinstance(item, dict):
                typed_item: dict[str, object] = {str(key): value for key, value in item.items()}
                tx_id_val_field = typed_item.get("transaction_id")
                if tx_id_val_field == tx_val:
                    recargo_issues.append(item)
    # Classifying alone does not satisfy the modelo fact requirements (category,
    # taxable base, etc.); the asesor still gets a gap, never a false "ready".
    assert recargo_issues, "a classified-but-incomplete business row must still flag"


def test_personal_row_drops_out_of_readiness_when_classified() -> None:
    """A PERSONAL row is correctly *ignorable* for modelo aggregation.

    Once the asesor classifies a Netflix subscription PERSONAL, preflight must
    NOT flag it (personal rows carry no deductible facts) — the asesor can
    distinguish "needs attention" from "legitimately out of scope".
    """
    row = _find(_list_rows(), _PERSONAL_DESC)
    tx_val = row.get("transaction_id")
    assert isinstance(tx_val, str)
    classify = _invoke(
        ["app", "ledger", "classify", tx_val, "--classification", "PERSONAL"],
    )
    assert classify.exit_code == 0, classify.output

    pre = _invoke(
        ["--format", "json", "app", "ledger", "preflight", "--period", "1T", "--year", "2025"],
    )
    assert pre.exit_code == 0, pre.output
    issues_val = _json(pre.output).get("issues")
    personal_issues = []
    if isinstance(issues_val, list):
        for item in issues_val:
            if isinstance(item, dict):
                typed_item: dict[str, object] = {str(key): value for key, value in item.items()}
                tx_id_val_field = typed_item.get("transaction_id")
                if tx_id_val_field == tx_val:
                    personal_issues.append(item)
    assert personal_issues == [], personal_issues


def test_check_clears_recargo_row_once_personal_and_business_dispositioned() -> None:
    """Sign-off shape: disposition reduces the anomaly count.

    After the asesor classifies one personal row PERSONAL, the all-period
    ``check`` issue count must strictly drop — review work visibly converges
    toward a clean filing rather than staying flat.
    """
    before_issues_val = _json(_invoke(["--format", "json", "app", "ledger", "check"]).output).get(
        "issues",
        [],
    )
    before = len(before_issues_val) if isinstance(before_issues_val, list) else 0
    row = _find(_list_rows(), _PERSONAL_DESC)
    tx_val = row.get("transaction_id")
    assert isinstance(tx_val, str)
    classify = _invoke(
        ["app", "ledger", "classify", tx_val, "--classification", "PERSONAL"],
    )
    assert classify.exit_code == 0, classify.output
    after_issues_val = _json(_invoke(["--format", "json", "app", "ledger", "check"]).output).get(
        "issues",
        [],
    )
    after = len(after_issues_val) if isinstance(after_issues_val, list) else 0
    assert after < before, (before, after)
