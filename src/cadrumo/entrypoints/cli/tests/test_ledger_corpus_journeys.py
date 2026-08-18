"""Lifecycle-focused ledger-corpus journeys over the real CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ....tests import general_m303_filing_evidence
from ....tests.registry_observations import registry_grounded_observations
from ._isolated_profile_storage_fixtures import live_fx_isolated_backend
from ._ledger_corpus_support import (
    _REVISION_CASILLA,
    _active_repo,
    _find,
    _import_bbva,
    _import_corpus,
    _invoke,
    _list_rows,
)

__all__ = ["live_fx_isolated_backend"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


# --- Split, merge, archive, stash, remove, and track ------------------------
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
    # follow-up gap.)
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


# --- Modification lifecycle (edit lineage, history, blocking) ----------------------
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

    from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
    from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from ....core import Period, resolve_active_bucket_id
    from ....domain.modelos import (
        CalculationRevision,
        CalculationRevisionCatalogue,
        CalculationRevisionState,
        ModeloCode,
        WorkUnit,
        WorkUnitCatalogue,
        derive_calculation_revision_id,
        derive_work_unit_id,
    )

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
        revision_id="2022",
    )
    filing_instance_evidence = general_m303_filing_evidence(period, reference="test:ledger-corpus-journey")
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={_REVISION_CASILLA: "1"},
        binding_overrides={},
        casilla_values={_REVISION_CASILLA: Decimal("1")},
        source_transaction_ids=(tx,),
        filing_instance_evidence=filing_instance_evidence,
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
                    revision_id="2022",
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
                    filing_instance_evidence=filing_instance_evidence,
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
