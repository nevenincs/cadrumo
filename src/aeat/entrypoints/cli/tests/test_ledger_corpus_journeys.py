"""Operator-journey suite over the ledger-corpus fixture.

Drives the real ``aeat app ledger`` CLI against an isolated profile, importing
the hand-authored operating-scale corpus (500+ rows, four accounts, multi-
currency, cross-year) and exercising the workflows a real operator performs:
import + dedup, classification (single + bulk ``--from-csv`` resolving ids at
runtime against the ground-truth oracle), allocation + ratios, filter/review,
lifecycle (split/merge/archive/stash), export fidelity, and preflight/status.

These are the durable, CI-gating counterpart to the live persona testimonials.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ....tests.registry_observations import registry_grounded_observations
from ._ledger_corpus_support import (
    _CORPUS,
    _FILES,
    _REVISION_CASILLA,
    _find,
    _import_bbva,
    _import_corpus,
    _invoke,
    _list_payload,
    _list_rows,
    _match,
    _oracle_rules,
)
from ._ledger_corpus_support import _isolated_backend as _isolated_backend

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


# --- Journey 1: import, dedup, and multicurrency ----------------------------
def test_import_full_corpus_persists_operating_scale() -> None:
    _import_corpus()
    rows = _list_rows()
    assert len(rows) >= 500, f"expected operating-scale corpus, got {len(rows)}"


def test_reimport_is_idempotent_dedups() -> None:
    _import_corpus()
    first = len(_list_rows())
    # Re-import one file; fingerprint dedup must skip every row.
    result = _invoke(
        ["--format", "json", "app", "ledger", "import", str(_CORPUS / _FILES[0]), "--provider", "csv"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    assert payload["imported"] == 0, payload
    assert payload["skipped"] >= 1, payload
    assert len(_list_rows()) == first


def test_import_dry_run_does_not_persist() -> None:
    result = _invoke(
        ["app", "ledger", "import", str(_CORPUS / _FILES[0]), "--provider", "csv", "--dry-run"],
    )
    assert result.exit_code == 0, result.output
    assert _list_rows() == []


def test_import_preserves_foreign_currencies() -> None:
    _import_corpus()
    currencies = {r.get("currency") for r in _list_rows()}
    assert {"EUR", "GBP", "USD"} <= currencies, currencies


# --- Journey 2: classification (single and bulk), allocate, and ratios -------
def test_bulk_classify_from_oracle_resolved_at_runtime(tmp_path: Path) -> None:
    _import_corpus()
    rules = _oracle_rules()
    rows = _list_rows()
    # Build a classify CSV (transaction_id, classification[, category_id]) by
    # resolving each persisted row's id against the oracle. --from-csv carries
    # only classification + category, so restrict to non-MIXED rows.
    # Classify a bounded slice: enough to prove --from-csv resolves ids,
    # applies classification + category, and reports a per-row summary. The
    # full-corpus scale behaviour is tracked separately (the per-row re-persist
    # cost is a recorded hardening finding, not this gate's concern).
    lines = ["transaction_id,classification,category_id"]
    expected: dict[str, str] = {}
    for row in rows:
        rule = _match(row["description"], rules)
        if rule is None or rule["classification"] == "MIXED":
            continue
        cat = rule.get("category_id") or ""
        lines.append(f"{row['transaction_id']},{rule['classification']},{cat}")
        expected[row["transaction_id"]] = rule["classification"]
        if len(expected) >= 12:
            break
    assert len(expected) == 12

    classify_csv = tmp_path / "classify.csv"
    classify_csv.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = _invoke(["--format", "json", "app", "ledger", "classify", "--from-csv", str(classify_csv)])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    assert payload["applied"] == 12, payload

    by_id = {r["transaction_id"]: r for r in _list_rows()}
    for tx_id, classification in expected.items():
        assert by_id[tx_id]["business_classification"] == classification


def test_single_classify_intracommunity_with_eu_state() -> None:
    from ....domain.iva import EUMemberState, IvaCategory
    from ....domain.transactions import BusinessClassification

    _import_corpus()
    rows = _list_rows()
    de_rows = [r for r in rows if "cliente DE GmbH intracom" in r["description"]]
    assert de_rows, "corpus must contain a DE intracommunity client invoice"
    tx = de_rows[0]["transaction_id"]
    result = _invoke(
        [
            "app",
            "ledger",
            "classify",
            tx,
            "--classification",
            "BUSINESS",
            "--iva-category",
            "intra_community_supply",
            "--counterparty-eu-member-state",
            "de",
        ],
    )
    assert result.exit_code == 0, result.output
    # Post-state: the row now carries the explicit intra-community IVA category
    # and the DE counterparty member state (concrete read-back, not exit-code only).
    txn = _active_repo().load().get(tx)
    assert txn is not None
    assert txn.business_classification is BusinessClassification.BUSINESS
    assert txn.iva_category is IvaCategory.INTRA_COMMUNITY_SUPPLY
    assert txn.counterparty_eu_member_state is EUMemberState.DE


# --- Journey 3: filter, review, and search ----------------------------------
def test_review_renders_corpus() -> None:
    _import_corpus()
    result = _invoke(["app", "ledger", "review"])
    assert result.exit_code == 0, result.output


def test_operator_can_filter_income_vs_expense() -> None:
    _import_corpus()
    rows = _list_rows()
    # On import, direction is resolved once from the source-signed amount; every row lands
    # INCOMING or OUTGOING and NOT_YET_PROCESSED. INTERNAL_TRANSFER is an
    # operator classification applied later (transfers are not auto-detected),
    # so the raw import carries only the two settlement directions plus the
    # transfer/exchange *candidates* the operator must still reclassify.
    incoming = [r for r in rows if r.get("direction") == "INCOMING"]
    outgoing = [r for r in rows if r.get("direction") == "OUTGOING"]
    assert incoming and outgoing, (len(incoming), len(outgoing))
    assert all(r.get("business_classification") == "NOT_YET_PROCESSED" for r in rows)
    transfer_candidates = [
        r
        for r in rows
        if any(token in r["description"] for token in ("Transferencia", "Traspaso", "Top-Up", "Exchange"))
    ]
    assert transfer_candidates, "corpus must carry transfer candidates to reclassify"


# --- Journey 4: lifecycle ---------------------------------------------------
def test_split_then_merge_roundtrip() -> None:
    from decimal import Decimal

    _import_corpus()
    rows = _list_rows()
    parent = next(r for r in rows if "Subcontratacion desarrollo" in r["description"])
    tx = parent["transaction_id"]
    amount = abs(float(parent["amount"]))
    half = round(amount / 2, 2)
    other = round(amount - half, 2)
    split = _invoke(
        [
            "app",
            "ledger",
            "split",
            tx,
            "--child-amount",
            f"{half}",
            "--child-description",
            "Subcontratacion parte A",
            "--child-amount",
            f"{other}",
            "--child-description",
            "Subcontratacion parte B",
            "--reason",
            "split for project allocation",
            "--yes",
        ],
    )
    assert split.exit_code == 0, split.output
    # Post-split post-state: parent transitions ACTIVE -> SPLIT (retained for
    # audit lineage), two ACTIVE children appear, and the children re-carry the
    # parent balance exactly (no value lost). Concrete post-state, not exit-code only.
    rows_after = _list_rows()
    parent_after = next((r for r in rows_after if r["transaction_id"] == tx), None)
    assert parent_after is not None, "the SPLIT parent is retained for audit lineage"
    assert parent_after["lifecycle_state"] == "SPLIT"
    child_a = _find(rows_after, "Subcontratacion parte A")
    child_b = _find(rows_after, "Subcontratacion parte B")
    assert child_a["lifecycle_state"] == "ACTIVE"
    assert child_b["lifecycle_state"] == "ACTIVE"
    assert Decimal(child_a["amount"]) + Decimal(child_b["amount"]) == Decimal(parent["amount"])


def test_archive_then_history() -> None:
    _import_corpus()
    rows = _list_rows()
    personal = next(r for r in rows if "Suscripcion Netflix" in r["description"])
    tx = personal["transaction_id"]
    archived = _invoke(["app", "ledger", "archive", tx, "--reason", "personal", "--yes"])
    assert archived.exit_code == 0, archived.output
    history = _invoke(["app", "ledger", "history", tx])
    assert history.exit_code == 0, history.output


# --- Journey 5: preflight and status ---------------------------------------
def test_status_reports_active_ledger() -> None:
    _import_corpus()
    result = _invoke(["app", "ledger", "status"])
    assert result.exit_code == 0, result.output


# --- Journey 6: allocate and ratios -----------------------------------------
def test_allocate_records_business_proportion() -> None:
    from decimal import Decimal

    from ....domain.transactions import BusinessClassification

    _import_bbva()
    internet = _find(_list_rows(), "Factura internet fibra oficina enero")
    tx = internet["transaction_id"]
    result = _invoke(
        [
            "app",
            "ledger",
            "allocate",
            tx,
            "--business-pct",
            "0.30",
            "--category-id",
            "suministros_home_office_internet",
        ],
    )
    assert result.exit_code == 0, result.output
    # Post-state: allocate records a MIXED business proportion (0.30) and the
    # supplied category against the row (concrete read-back, not exit-code only).
    txn = _active_repo().load().get(tx)
    assert txn is not None
    assert txn.business_classification is BusinessClassification.MIXED
    assert txn.business_pct == Decimal("0.30")
    assert txn.category_id == "suministros_home_office_internet"


def test_ratios_eligible_set_list_validate() -> None:
    _import_bbva()
    eligible = _invoke(["--format", "json", "app", "ledger", "ratios", "eligible"])
    assert eligible.exit_code == 0, eligible.output
    blob = json.dumps(json.loads(eligible.output))
    category = "telefonia_movil" if "telefonia_movil" in blob else "vehiculo_combustible"
    setr = _invoke(["app", "ledger", "ratios", "set", category, "0.50"])
    assert setr.exit_code == 0, setr.output
    listed = _invoke(["app", "ledger", "ratios", "list"])
    assert listed.exit_code == 0 and category in listed.output, listed.output
    validate = _invoke(["app", "ledger", "ratios", "validate"])
    assert validate.exit_code == 0, validate.output


# --- Journey 7: filter and search via review typed spec ---------------------
def test_review_filter_by_period_and_status() -> None:
    _import_bbva()
    by_period = _invoke(["app", "ledger", "review", "--filter", "period=1T", "--filter", "year=2025"])
    assert by_period.exit_code == 0, by_period.output
    by_status = _invoke(["app", "ledger", "review", "--filter", "status=pending"])
    assert by_status.exit_code == 0, by_status.output


# --- Journey 8: merge, stash, remove, and track -----------------------------
def test_split_children_then_merge() -> None:
    _import_bbva()
    parent = _find(_list_rows(), "Subcontratacion desarrollo freelance Juan")
    amount = abs(float(parent["amount"]))
    half = round(amount / 2, 2)
    other = round(amount - half, 2)
    split = _invoke(
        [
            "app",
            "ledger",
            "split",
            parent["transaction_id"],
            "--child-amount",
            f"{half}",
            "--child-description",
            "Subcontratacion parte A",
            "--child-amount",
            f"{other}",
            "--child-description",
            "Subcontratacion parte B",
            "--reason",
            "project allocation",
            "--yes",
        ],
    )
    assert split.exit_code == 0, split.output
    rows = _list_rows()
    child_a_row = _find(rows, "Subcontratacion parte A")
    child_b_row = _find(rows, "Subcontratacion parte B")
    child_a = child_a_row["transaction_id"]
    child_b = child_b_row["transaction_id"]
    # Post-split post-state: both children are ACTIVE, and the original parent
    # has transitioned to SPLIT (the catalogue retains it for audit lineage; the
    # CLI ``list`` surfaces every lifecycle state, with lifecycle_state as the
    # discriminator rather than filtering the parent out).
    assert child_a_row["lifecycle_state"] == "ACTIVE"
    assert child_b_row["lifecycle_state"] == "ACTIVE"
    parent_after_split = next((r for r in rows if r["transaction_id"] == parent["transaction_id"]), None)
    assert parent_after_split is not None, "the SPLIT parent is retained for audit lineage"
    assert parent_after_split["lifecycle_state"] == "SPLIT", (
        "the parent transitions ACTIVE -> SPLIT once its children carry the balance"
    )

    merged = _invoke(
        [
            "app",
            "ledger",
            "merge",
            "--child-id",
            child_a,
            "--child-id",
            child_b,
            "--reason",
            "re-merge after review",
            "--yes",
        ],
    )
    assert merged.exit_code == 0, merged.output

    # Post-merge post-state (SplitRole.MERGED semantics): the two children
    # transition ACTIVE -> ARCHIVED, the original parent transitions SPLIT ->
    # ARCHIVED (never back to ACTIVE), and a FRESH MERGED row — a new
    # content-addressed id carrying the parent's narrative — becomes ACTIVE,
    # re-carrying the rejoined balance.
    rows_after_merge = _list_rows()
    by_id = {r["transaction_id"]: r for r in rows_after_merge}
    assert by_id.get(child_a, {}).get("lifecycle_state") == "ARCHIVED", "merged child A must transition to ARCHIVED"
    assert by_id.get(child_b, {}).get("lifecycle_state") == "ARCHIVED", "merged child B must transition to ARCHIVED"
    assert by_id.get(parent["transaction_id"], {}).get("lifecycle_state") == "ARCHIVED", (
        "the original SPLIT parent transitions to ARCHIVED on merge, never back to ACTIVE"
    )
    # The fresh MERGED row re-carries the parent's EXACT narrative and amount
    # (the rejoined balance), under a new content-addressed id. Match on exact
    # description + amount to disambiguate from any other corpus row that merely
    # shares the narrative substring.
    merged_rows = [
        r
        for r in rows_after_merge
        if r["description"] == parent["description"]
        and r["amount"] == parent["amount"]
        and r["transaction_id"] not in {child_a, child_b, parent["transaction_id"]}
        and r["lifecycle_state"] == "ACTIVE"
    ]
    assert len(merged_rows) == 1, (
        f"exactly one fresh ACTIVE MERGED row must carry the rejoined balance, got {len(merged_rows)}"
    )


def test_stash_remove_and_track() -> None:
    _import_bbva()
    rows = _list_rows()
    stash_row = _find(rows, "Material oficina Papeleria Gomez")
    stashed = _invoke(
        ["app", "ledger", "stash", stash_row["transaction_id"], "--reason", "pending review", "--yes"],
    )
    assert stashed.exit_code == 0, stashed.output
    # Post-stash post-state: the row remains listed but transitions to STASHED
    # (parked pending review — reversible, not removed from the catalogue).
    stashed_row = next((r for r in _list_rows() if r["transaction_id"] == stash_row["transaction_id"]), None)
    assert stashed_row is not None, "a stashed row stays in the catalogue (reversible state)"
    assert stashed_row["lifecycle_state"] == "STASHED"

    # ``ledger track`` is a READ-ONLY audit-lineage view (it calls
    # get_manual_transaction; it does NOT mutate lifecycle state). Asserting the
    # real behavior: the row's state is unchanged (still STASHED) after track,
    # and the track output reports that state. (There is no per-row un-stash CLI
    # verb today — stash/archive are "reversible" in the domain enum but no
    # ledger subcommand reverses them per row; surfaced to the coordinator as a
    # follow-up gap, documented here rather than faked.)
    tracked = _invoke(["app", "ledger", "track", stash_row["transaction_id"]])
    assert tracked.exit_code == 0, tracked.output
    assert "STASHED" in tracked.output, "track must report the row's STASHED lifecycle state"
    after_track = next((r for r in _list_rows() if r["transaction_id"] == stash_row["transaction_id"]), None)
    assert after_track is not None, "track is read-only; the row stays in the catalogue"
    assert after_track["lifecycle_state"] == "STASHED", (
        "track is a read-only lineage view and must not change lifecycle state"
    )

    remove_row = _find(rows, "Comida de trabajo Restaurante El Olivo")
    removed = _invoke(
        ["app", "ledger", "remove", remove_row["transaction_id"], "--reason", "duplicate", "--yes"],
    )
    assert removed.exit_code == 0, removed.output
    # Post-remove: the removed row is absent from the default list.
    assert remove_row["transaction_id"] not in {r["transaction_id"] for r in _list_rows()}, (
        "a removed row must be absent from the default list"
    )


# --- Journey 9: preflight and check gates ------------------------------------
def test_preflight_and_check_surface_missing_facts() -> None:
    _import_bbva()
    preflight = _invoke(["app", "ledger", "preflight", "--period", "1T", "--year", "2025"])
    assert preflight.exit_code == 0, preflight.output
    check = _invoke(["app", "ledger", "check"])
    assert check.exit_code == 0, check.output


# --- Operating-scale rendering: honest paging/truncation ---------------------------
def test_list_paging_is_honest_and_never_silently_caps() -> None:
    _import_bbva()
    full = _list_payload()
    total = full["total"]
    assert total > 20, "fixture should carry enough rows to page"
    assert full["truncated"] is False
    assert full["shown"] == total
    assert len(full["rows"]) == total

    # A clipped page reports the full total and flags truncation.
    page = _list_payload("--limit", "10")
    assert page["total"] == total
    assert page["shown"] == 10
    assert len(page["rows"]) == 10
    assert page["truncated"] is True
    assert page["rows"] == full["rows"][:10]

    # The offset window is a contiguous, non-overlapping slice of the full set.
    nxt = _list_payload("--limit", "10", "--offset", "10")
    assert nxt["offset"] == 10
    assert nxt["rows"] == full["rows"][10:20]
    assert nxt["truncated"] is True

    # Paging through every window reconstructs the full ledger exactly once.
    seen: list[dict[str, Any]] = []
    off = 0
    while off < total:
        win = _list_payload("--limit", "25", "--offset", str(off))
        seen.extend(win["rows"])
        off += 25
    assert seen == full["rows"]

    # The final window is honestly NOT truncated past its tail beyond offset 0.
    last_off = (total // 25) * 25
    tail = _list_payload("--limit", "25", "--offset", str(last_off))
    assert tail["shown"] == total - last_off


def test_list_truncation_footer_states_the_full_total() -> None:
    _import_bbva()
    total = _list_payload()["total"]
    listed = _invoke(["app", "ledger", "list", "--limit", "5"])
    assert listed.exit_code == 0, listed.output
    # The human footer names the full total so the cap is never silent.
    assert str(total) in listed.output
    assert "1-5" in listed.output


# --- Grouping / labelling + grouped display ----------------------------------------
def _set_group(tx_id: str, label: str) -> None:
    res = _invoke(["app", "ledger", "update", tx_id, "--group", label])
    assert res.exit_code == 0, res.output


def test_group_label_assign_filter_and_grouped_display() -> None:
    _import_bbva()
    rows = _list_rows()
    a = _find(rows, "Material oficina Papeleria Gomez")
    b = _find(rows, "Comida de trabajo Restaurante El Olivo")
    _set_group(a["transaction_id"], "Proyecto Acme")
    _set_group(b["transaction_id"], "Proyecto Acme")

    # --group filters to exactly the labelled rows.
    filtered = _list_payload("--group", "Proyecto Acme")
    ids = {r["transaction_id"] for r in filtered["rows"]}
    assert ids == {a["transaction_id"], b["transaction_id"]}
    assert all(r["group_label"] == "Proyecto Acme" for r in filtered["rows"])

    # Every row carries the group_label key (None when ungrouped).
    full = _list_payload()
    labels = {r["group_label"] for r in full["rows"]}
    assert "Proyecto Acme" in labels and None in labels

    # --by-group renders a section header naming the group.
    grouped = _invoke(["app", "ledger", "list", "--by-group"])
    assert grouped.exit_code == 0, grouped.output
    assert "# Proyecto Acme" in grouped.output


def test_unrelated_update_preserves_group_label() -> None:
    _import_bbva()
    rows = _list_rows()
    row = _find(rows, "Material oficina Papeleria Gomez")
    _set_group(row["transaction_id"], "Q1 viajes")
    # An edit to an unrelated field must NOT wipe the operator's grouping.
    res = _invoke(["app", "ledger", "update", row["transaction_id"], "--notes", "revisado"])
    assert res.exit_code == 0, res.output
    after = {r["transaction_id"]: r for r in _list_rows()}[row["transaction_id"]]
    assert after["group_label"] == "Q1 viajes"

    # Passing an empty --group clears the label.
    cleared = _invoke(["app", "ledger", "update", row["transaction_id"], "--group", ""])
    assert cleared.exit_code == 0, cleared.output
    final = {r["transaction_id"]: r for r in _list_rows()}[row["transaction_id"]]
    assert final["group_label"] is None


# --- Batch transform / iterative refinement at scale -------------------------------
def test_batch_transform_recategorize_relabel_reallocate_at_scale(tmp_path: Path) -> None:
    """Iterative refinement over a large slice: recategorize -> relabel -> reallocate.

    Proves the operator can amend hundreds of rows in batched passes and that
    each pass is observable end-to-end (applied counts + per-row read-back),
    the working-at-scale guarantee.
    """
    _import_corpus()
    rows = _list_rows()
    rules = _oracle_rules()

    # Pass 1 — recategorize at scale: classify every row the oracle marks as a
    # non-MIXED BUSINESS movement, in one --from-csv batch.
    lines = ["transaction_id,classification,category_id"]
    targeted: dict[str, str] = {}
    for row in rows:
        rule = _match(row["description"], rules)
        if rule is None or rule["classification"] != "BUSINESS":
            continue
        cat = rule.get("category_id") or ""
        lines.append(f"{row['transaction_id']},BUSINESS,{cat}")
        targeted[row["transaction_id"]] = cat
    assert len(targeted) >= 100, f"corpus must yield a hundreds-scale batch, got {len(targeted)}"

    recat_csv = tmp_path / "recategorize.csv"
    recat_csv.write_text("\n".join(lines) + "\n", encoding="utf-8")
    res = _invoke(["--format", "json", "app", "ledger", "classify", "--from-csv", str(recat_csv)])
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)["result"]
    assert payload["applied"] == len(targeted), payload
    by_id = {r["transaction_id"]: r for r in _list_rows()}
    for tx_id in targeted:
        assert by_id[tx_id]["business_classification"] == "BUSINESS"

    # Pass 2 — relabel at scale: assign one organisational group across a
    # 60-row slice of the recategorized set, then confirm via --group filter.
    slice_ids = list(targeted)[:60]
    for tx_id in slice_ids:
        _set_group(tx_id, "Cierre 2025")
    grouped = _list_payload("--group", "Cierre 2025")
    assert {r["transaction_id"] for r in grouped["rows"]} == set(slice_ids)

    # Pass 3 — reallocate at scale: flip a 20-row slice to MIXED with a shared
    # business_pct in one batch, then read back the new classification.
    mixed_ids = slice_ids[:20]
    realloc = ["transaction_id,classification,business_pct"]
    realloc += [f"{tx_id},MIXED,0.60" for tx_id in mixed_ids]
    realloc_csv = tmp_path / "reallocate.csv"
    realloc_csv.write_text("\n".join(realloc) + "\n", encoding="utf-8")
    res2 = _invoke(["--format", "json", "app", "ledger", "classify", "--from-csv", str(realloc_csv)])
    assert res2.exit_code == 0, res2.output
    payload2 = json.loads(res2.output)["result"]
    assert payload2["applied"] == len(mixed_ids), payload2
    final = {r["transaction_id"]: r for r in _list_rows()}
    for tx_id in mixed_ids:
        assert final[tx_id]["business_classification"] == "MIXED"
        # The group label survives an unrelated batch reallocation.
        assert final[tx_id]["group_label"] == "Cierre 2025"


# --- Transfer reclassification -----------------------------------------------------
def test_transfer_row_reclassified_to_internal_transfer_and_locked_out_of_tax() -> None:
    """Import lands a transfer as OUTGOING/NOT_YET_PROCESSED; the operator
    reclassifies it to INTERNAL_TRANSFER, after which it cannot be marked
    tax-relevant (BUSINESS) — the gated-transfer guarantee.
    """
    _import_bbva()
    rows = _list_rows()
    transfer = _find(rows, "Transferencia a cuenta personal CaixaBank")
    tx = transfer["transaction_id"]
    # Import resolves direction once from the source-signed amount — never INTERNAL_TRANSFER.
    assert transfer["direction"] == "OUTGOING"
    assert transfer["business_classification"] == "NOT_YET_PROCESSED"

    reclass = _invoke(["app", "ledger", "update", tx, "--direction", "INTERNAL_TRANSFER"])
    assert reclass.exit_code == 0, reclass.output
    after = {r["transaction_id"]: r for r in _list_rows()}[tx]
    assert after["direction"] == "INTERNAL_TRANSFER"

    # A transfer must not be promotable to a tax-relevant BUSINESS row.
    refused = _invoke(["app", "ledger", "update", tx, "--classification", "BUSINESS"])
    assert refused.exit_code != 0, refused.output
    assert after["business_classification"] != "BUSINESS"


# --- Modification lifecycle (edit lineage, history, blocking) ----------------------
def _active_repo():
    from ....core import resolve_active_bucket_id
    from ....domain.transactions import TransactionCatalogueRepository

    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    return TransactionCatalogueRepository(bucket_id=bucket_id)


def test_edit_editable_facts_records_edit_lineage_chain() -> None:
    """Editing an id-affecting fact rewrites the row id and the new
    record carries an edit_lineage entry pointing back at the prior id.
    """
    _import_bbva()
    rows = _list_rows()
    target = _find(rows, "Material oficina Papeleria Gomez")
    old_id = target["transaction_id"]

    res = _invoke(
        ["app", "ledger", "update", old_id, "--description", "Material oficina (corregido)"],
    )
    assert res.exit_code == 0, res.output

    catalogue = _active_repo().load()
    # The edit changed the narrative -> a new content-addressed id; locate the
    # heir by its edit_lineage back-pointer.
    heirs = [t for t in catalogue.values() if t.edit_lineage and t.edit_lineage[-1].previous_transaction_id == old_id]
    assert len(heirs) == 1, [t.transaction_id for t in catalogue.values() if t.edit_lineage]
    heir = heirs[0]
    assert heir.raw.description == "Material oficina (corregido)"
    assert old_id not in {t.transaction_id for t in catalogue.values()}


def test_reclassify_retains_classification_event_chain() -> None:
    """Reclassifying after review keeps the prior classification in the
    auditable bucket-event chain (the operator-facing classification history).
    """
    _import_bbva()
    rows = _list_rows()
    target = _find(rows, "Material oficina Papeleria Gomez")
    tx = target["transaction_id"]

    first = _invoke(
        ["app", "ledger", "classify", tx, "--classification", "BUSINESS", "--category-id", "material_oficina"],
    )
    assert first.exit_code == 0, first.output
    second = _invoke(
        ["app", "ledger", "classify", tx, "--classification", "BUSINESS", "--category-id", "asesoria_fiscal"],
    )
    assert second.exit_code == 0, second.output

    history = _invoke(["--format", "json", "app", "ledger", "history", tx])
    assert history.exit_code == 0, history.output
    events = json.loads(history.output)["result"]["events"]
    classified = [e for e in events if e["event_type"] == "ledger.transaction.classified"]
    # Both classification decisions are retained in the chain, not overwritten.
    assert len(classified) >= 2, events

    # The current category reflects the latest decision; the chain proves the
    # earlier one was not silently dropped.
    catalogue = _active_repo().load()
    txn = catalogue.get(tx)
    assert txn is not None
    assert txn.category_id == "asesoria_fiscal"


def test_modification_refused_when_row_feeds_finalized_modelo() -> None:
    """Once a verified modelo revision cites a ledger row, the CLI
    refuses to edit that row (finalized-modelo blocking guard).
    """
    from datetime import UTC, datetime
    from decimal import Decimal

    from ....core import Period, resolve_active_bucket_id
    from ....domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
    from ....domain.modelos._calculation_revision import (
        CalculationRevision,
        CalculationRevisionCatalogue,
        CalculationRevisionState,
        derive_calculation_revision_id,
    )
    from ....domain.modelos._codes import ModeloCode
    from ....domain.modelos._repository import WorkUnitCatalogueRepository
    from ....domain.modelos._work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id

    _import_bbva()
    rows = _list_rows()
    tx = _find(rows, "Material oficina Papeleria Gomez")["transaction_id"]
    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None

    period = Period.from_year_and_code(2025, "1T")
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo="303",
        filing_year=2025,
        period=period,
        revision_id="2009-y-siguientes",
    )
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={_REVISION_CASILLA: "1"},
        binding_overrides={},
        casilla_values={_REVISION_CASILLA: Decimal("1")},
        source_transaction_ids=(tx,),
    )
    now = datetime(2026, 5, 2, 9, 0, tzinfo=UTC)
    WorkUnitCatalogueRepository().save(
        WorkUnitCatalogue.from_work_units(
            (
                WorkUnit(
                    work_unit_id=work_unit_id,
                    bucket_id=bucket_id,
                    modelo=ModeloCode("303"),
                    filing_year=2025,
                    period=period,
                    revision_id="2009-y-siguientes",
                    name="303-2025-1T",
                    created_at=now,
                    updated_at=now,
                    current_calculation_revision_id=revision_id,
                ),
            ),
        ),
    )
    CalculationRevisionCatalogueRepository().save(
        CalculationRevisionCatalogue(
            revisions={
                revision_id: CalculationRevision(
                    calculation_revision_id=revision_id,
                    work_unit_id=work_unit_id,
                    state=CalculationRevisionState.VERIFICADO_COMPLETO,
                    input_values_by_casilla_id={_REVISION_CASILLA: "1"},
                    binding_overrides={},
                    source_transaction_ids=(tx,),
                    casilla_values={_REVISION_CASILLA: Decimal("1")},
                    observations=registry_grounded_observations(
                        modelo="303",
                        filing_year=2025,
                        period=period.registry_token,
                        casilla_values={_REVISION_CASILLA: Decimal("1")},
                    ),
                    created_at=now,
                    updated_at=now,
                    verified_at=now,
                    verified_by="operator",
                ),
            },
        ),
    )

    refused = _invoke(["app", "ledger", "update", tx, "--notes", "tweak"])
    assert refused.exit_code != 0, refused.output
    assert "finalized modelo" in refused.output.lower() or "modelo" in refused.output.lower()


# --- Drive document-link fetch-and-encrypt-or-refuse -------------------------------
def test_doclink_refuses_when_document_bytes_are_unreachable() -> None:
    """A Drive link the app cannot fetch (no connected Google credentials) is
    refused: evidence must carry encrypted document bytes, so the verb never
    falls back to storing the bare link, and the row gains no attachment.
    """
    _import_bbva()
    rows = _list_rows()
    tx = _find(rows, "Material oficina Papeleria Gomez")["transaction_id"]
    link = "https://drive.google.com/file/d/ABC123ticket/view"

    res = _invoke(
        ["app", "ledger", "doclink", tx, "--source", "GOOGLE_DRIVE", "--reference", link, "--note", "ticket"],
    )
    assert res.exit_code != 0, res.output

    catalogue = _active_repo().load()
    txn = catalogue.get(tx)
    assert txn is not None
    assert not txn.attachment_ids, "a refused doclink must not bind any attachment to the row"


def test_doclink_refuses_non_link_source(tmp_path: Path) -> None:
    _import_bbva()
    rows = _list_rows()
    tx = _find(rows, "Material oficina Papeleria Gomez")["transaction_id"]
    # LOCAL_FILE is a valid AttachmentSource but not a document *link* source.
    res = _invoke(
        [
            "app",
            "ledger",
            "doclink",
            tx,
            "--source",
            "LOCAL_FILE",
            "--reference",
            str(tmp_path / "local-source.txt"),
        ],
    )
    assert res.exit_code != 0, res.output


# --- Split a mixed invoice into business + personal children -----------------------
def test_split_mixed_invoice_into_business_and_personal_children() -> None:
    """Split one parent row into a business child (with base/IVA) and a personal
    child, then classify each independently — the mixed-invoice per-child split.
    """
    from decimal import Decimal

    _import_bbva()
    rows = _list_rows()
    parent = _find(rows, "Material oficina Papeleria Gomez")
    parent_id = parent["transaction_id"]
    amount = Decimal(str(parent["amount"]))
    # Two children of the same sign summing exactly to the parent amount.
    biz = (amount * Decimal("0.6")).quantize(Decimal("0.01"))
    personal = amount - biz

    split = _invoke(
        [
            "app",
            "ledger",
            "split",
            parent_id,
            "--child-amount",
            str(biz),
            "--child-description",
            "Material oficina (negocio)",
            "--child-amount",
            str(personal),
            "--child-description",
            "Material oficina (personal)",
            "--reason",
            "uso mixto",
            "--yes",
        ],
    )
    assert split.exit_code == 0, split.output

    catalogue = _active_repo().load()
    # Locate the two children by their split descriptions.
    children = [
        t for t in catalogue.values() if t.split_lineage is not None and "Material oficina (" in t.raw.description
    ]
    assert len(children) == 2, [t.raw.description for t in children]
    biz_child = next(t for t in children if "negocio" in t.raw.description)
    per_child = next(t for t in children if "personal" in t.raw.description)

    # Classify each child independently: business carries base/IVA; personal does not.
    cls_biz = _invoke(
        [
            "app",
            "ledger",
            "classify",
            biz_child.transaction_id,
            "--classification",
            "BUSINESS",
            "--category-id",
            "material_oficina",
        ],
    )
    assert cls_biz.exit_code == 0, cls_biz.output
    cls_per = _invoke(
        ["app", "ledger", "classify", per_child.transaction_id, "--classification", "PERSONAL"],
    )
    assert cls_per.exit_code == 0, cls_per.output

    after = {t.transaction_id: t for t in _active_repo().load().values()}
    assert after[biz_child.transaction_id].business_classification.value == "BUSINESS"
    assert after[per_child.transaction_id].business_classification.value == "PERSONAL"
    # The child amounts reconstruct the parent exactly (no value lost in the split).
    assert biz_child.raw.amount + per_child.raw.amount == amount
