"""Real-behavior suite for the stable ledger lineage handle.

A ledger transaction id is a content hash, so editing an id-affecting fact
(amount, narrative, ...) via ``ledger update`` re-derives the id and the old
handle is removed from the catalogue. The content-addressed id stays authoritative
for storage and audit, while the operator read verbs (``history`` / ``view`` /
``track``) resolve any id in a row's edit-lineage chain, so a handle written
down before a correction keeps answering afterwards.

Every test here drives the real ``aeat app ledger`` CLI against an isolated
profile bucket through the real persistence stack — no mocks, no stubs, no
skips. The lineage chain, the content-address invariant, and the per-verb
resolution behaviour are all asserted against real catalogue state.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest
from click.testing import Result

from ....domain.transactions.models import derive_transaction_id
from ....tests.cli_envelope import unwrap_cli_result as _json_result
from ....tests.cli_runner import invoke_cached_cli
from ._ledger_seeded_profile_fixture import _isolated_backend

__all__ = ["_isolated_backend"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _invoke(args: Sequence[str]) -> Result:
    return invoke_cached_cli(args)


def _add_row(*, amount: str, description: str, idempotency_key: str) -> str:
    """Create one manual ledger row and return its content-addressed id."""
    result = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "add",
            "--date",
            "2026-05-02",
            "--amount",
            amount,
            "--direction",
            "OUTGOING",
            "--description",
            description,
            "--counterparty",
            "Proveedor SL",
            "--idempotency-key",
            idempotency_key,
        ],
    )
    assert result.exit_code == 0, result.output
    payload = _json_result(result)
    transaction_id = payload["transaction_id"]
    assert isinstance(transaction_id, str) and len(transaction_id) == 64
    return transaction_id


def _active_repo() -> Any:
    from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
    from ....core.bucket_pointer import resolve_active_bucket_id

    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    return TransactionCatalogueRepository(bucket_id=bucket_id)


def _list_rows() -> list[dict[str, Any]]:
    listed = _invoke(["--format", "json", "app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    return _json_result(listed)["rows"]


def _update_description(transaction_id: str, new_description: str) -> str:
    """Edit the narrative (an id-affecting fact) and return the heir's new id."""
    result = _invoke(
        ["--format", "json", "app", "ledger", "update", transaction_id, "--description", new_description],
    )
    assert result.exit_code == 0, result.output
    raw_transaction_id: object = _json_result(result).get("transaction_id")
    assert isinstance(raw_transaction_id, str), result.output
    return raw_transaction_id


# --- update: the old handle keeps answering across all three read verbs -------
def test_update_changes_the_content_addressed_id() -> None:
    """Sanity anchor: editing the narrative really does re-mint the id, and the
    new id is the content hash of the edited raw row (content-addressing is
    unchanged by D3 — the read-side resolver does not freeze the id).
    """
    old_id = _add_row(amount="100.00", description="Material oficina", idempotency_key="row-1")
    new_id = _update_description(old_id, "Material oficina (corregido)")
    assert new_id != old_id, "an id-affecting edit must re-derive the content-addressed id"

    catalogue = _active_repo().load()
    heir = catalogue.get(new_id)
    assert heir is not None
    # The new id is still the SHA-256 of the heir's raw row — the content
    # address remains authoritative; lineage resolution is a read-side layer.
    assert derive_transaction_id(heir.raw) == new_id
    assert old_id not in {t.transaction_id for t in catalogue.values()}
    # The old id survives only as a lineage back-pointer on the heir.
    assert heir.edit_lineage[-1].previous_transaction_id == old_id


def test_history_resolves_a_superseded_old_id() -> None:
    """``history OLD-ID`` answers after an update re-derived the id, surfacing
    the lineage chain rather than failing id-not-found.
    """
    old_id = _add_row(amount="100.00", description="Material oficina", idempotency_key="row-1")
    new_id = _update_description(old_id, "Material oficina (corregido)")

    by_old = _invoke(["--format", "json", "app", "ledger", "history", old_id])
    assert by_old.exit_code == 0, by_old.output
    old_payload = _json_result(by_old)
    # The old handle resolves to the current (heir) row.
    assert old_payload["transaction_id"] == new_id

    by_new = _invoke(["--format", "json", "app", "ledger", "history", new_id])
    assert by_new.exit_code == 0, by_new.output
    new_payload = _json_result(by_new)

    # Both handles surface the same lineage chain: the pre-edit create event
    # (anchored on the old id) AND the post-edit update event (anchored on the
    # new id) are present whichever handle the operator typed.
    old_event_types = {event["event_type"] for event in old_payload["events"]}
    new_event_types = {event["event_type"] for event in new_payload["events"]}
    assert old_payload["event_count"] == new_payload["event_count"]
    assert "ledger.transaction.created" in old_event_types
    assert any(t.endswith("updated") or t.endswith("correction") for t in old_event_types | new_event_types)
    assert old_event_types == new_event_types


def test_view_resolves_a_superseded_old_id_to_the_current_row() -> None:
    """``view OLD-ID`` resolves the pre-edit handle to the corrected row.

    Per the resolver design: an ``update`` removes the
    old id from the catalogue, so there is no superseded *record* to show; the
    most guessable behaviour, matching ``view``'s live-record semantics, is to
    resolve the old handle to the heir and show the corrected record.
    """
    old_id = _add_row(amount="100.00", description="Material oficina", idempotency_key="row-1")
    new_id = _update_description(old_id, "Material oficina (corregido)")

    by_old = _invoke(["--format", "json", "app", "ledger", "view", old_id])
    assert by_old.exit_code == 0, by_old.output
    payload = _json_result(by_old)
    assert payload["transaction_id"] == new_id
    assert payload["transaction"]["description"] == "Material oficina (corregido)"


def test_track_resolves_a_superseded_old_id() -> None:
    """``track OLD-ID`` resolves the pre-edit handle to the corrected row."""
    old_id = _add_row(amount="100.00", description="Material oficina", idempotency_key="row-1")
    new_id = _update_description(old_id, "Material oficina (corregido)")

    by_old = _invoke(["--format", "json", "app", "ledger", "track", old_id])
    assert by_old.exit_code == 0, by_old.output
    payload = _json_result(by_old)
    assert payload["transaction"]["transaction_id"] == new_id


def test_multi_edit_chain_resolves_the_oldest_handle() -> None:
    """A handle from two edits ago still resolves through the whole chain."""
    id_0 = _add_row(amount="100.00", description="v0", idempotency_key="row-1")
    id_1 = _update_description(id_0, "v1")
    id_2 = _update_description(id_1, "v2")
    assert len({id_0, id_1, id_2}) == 3

    for handle in (id_0, id_1, id_2):
        view = _invoke(["--format", "json", "app", "ledger", "view", handle])
        assert view.exit_code == 0, f"{handle}: {view.output}"
        assert _json_result(view)["transaction_id"] == id_2

    history = _invoke(["--format", "json", "app", "ledger", "history", id_0])
    assert history.exit_code == 0, history.output
    assert _json_result(history)["transaction_id"] == id_2


def test_current_id_still_resolves_unchanged() -> None:
    """The live-id path is unchanged: a current id resolves directly."""
    tx = _add_row(amount="100.00", description="Material oficina", idempotency_key="row-1")
    for verb in ("history", "view", "track"):
        result = _invoke(["--format", "json", "app", "ledger", verb, tx])
        assert result.exit_code == 0, f"{verb}: {result.output}"


def test_unknown_id_with_no_lineage_still_refuses() -> None:
    """An id that names neither a live row nor any lineage handle is refused."""
    _add_row(amount="100.00", description="Material oficina", idempotency_key="row-1")
    absent = "f" * 64
    result = _invoke(["app", "ledger", "view", absent])
    assert result.exit_code != 0, result.output


# --- split: parent -> children lineage ----------------------------------------
def test_split_parent_id_still_resolves_after_split() -> None:
    """The SPLIT parent stays in the catalogue, so its id keeps resolving and
    its lineage (the split children) is visible through ``history``.
    """
    parent = _add_row(amount="100.00", description="Subcontratacion", idempotency_key="row-1")
    split = _invoke(
        [
            "app",
            "ledger",
            "split",
            parent,
            "--child-amount",
            "40.00",
            "--child-description",
            "Subcontratacion parte A",
            "--child-amount",
            "60.00",
            "--child-description",
            "Subcontratacion parte B",
            "--reason",
            "project allocation",
            "--yes",
        ],
    )
    assert split.exit_code == 0, split.output

    rows = _list_rows()
    parent_row = next((r for r in rows if r["transaction_id"] == parent), None)
    assert parent_row is not None and parent_row["lifecycle_state"] == "SPLIT"
    child_a = next(r for r in rows if "parte A" in r["description"])["transaction_id"]

    # The parent handle still answers (it was never removed).
    parent_view = _invoke(["--format", "json", "app", "ledger", "view", parent])
    assert parent_view.exit_code == 0, parent_view.output
    assert _json_result(parent_view)["transaction_id"] == parent

    # The split siblings (parent -> children) surface when opted in.
    history = _invoke(["--format", "json", "app", "ledger", "history", parent, "--include-split-siblings"])
    assert history.exit_code == 0, history.output
    events = _json_result(history)["events"]
    assert any(e["event_type"] == "ledger.transaction.split" for e in events)
    # The child id is independently addressable.
    child_view = _invoke(["--format", "json", "app", "ledger", "view", child_a])
    assert child_view.exit_code == 0, child_view.output


# --- merge: children -> merged lineage ----------------------------------------
def test_merged_children_ids_still_resolve_after_merge() -> None:
    """After a merge the archived children stay in the catalogue, so their ids
    keep resolving, and the fresh merged row carries a new content-addressed id.
    """
    parent = _add_row(amount="100.00", description="Subcontratacion", idempotency_key="row-1")
    split = _invoke(
        [
            "app",
            "ledger",
            "split",
            parent,
            "--child-amount",
            "40.00",
            "--child-description",
            "Subcontratacion parte A",
            "--child-amount",
            "60.00",
            "--child-description",
            "Subcontratacion parte B",
            "--reason",
            "project allocation",
            "--yes",
        ],
    )
    assert split.exit_code == 0, split.output
    rows = _list_rows()
    child_a = next(r for r in rows if "parte A" in r["description"])["transaction_id"]
    child_b = next(r for r in rows if "parte B" in r["description"])["transaction_id"]

    merged = _invoke(
        [
            "--format",
            "json",
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
    merged_id = _json_result(merged)["merged_transaction_id"]
    assert merged_id not in {child_a, child_b, parent}

    # The archived child ids still resolve to their own (ARCHIVED) records.
    for child in (child_a, child_b):
        view = _invoke(["--format", "json", "app", "ledger", "view", child])
        assert view.exit_code == 0, f"{child}: {view.output}"
        assert _json_result(view)["transaction_id"] == child

    # The merge event chain is reachable from the parent handle.
    history = _invoke(["--format", "json", "app", "ledger", "history", parent])
    assert history.exit_code == 0, history.output
    events = _json_result(history)["events"]
    assert any(e["event_type"] == "ledger.transaction.merged" for e in events)

    # The fresh merged row's id is its own content hash (content-addressing
    # unchanged) and is independently addressable.
    merged_view = _invoke(["--format", "json", "app", "ledger", "view", merged_id])
    assert merged_view.exit_code == 0, merged_view.output
    catalogue = _active_repo().load()
    merged_tx = catalogue.get(merged_id)
    assert merged_tx is not None
    assert derive_transaction_id(merged_tx.raw) == merged_id
