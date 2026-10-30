"""The timeline words every fact an operator states, and leaves out the identities the system keeps."""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.application.actividad_asset.activity_asset_read_models import (
    TIMELINE_FIELD_PATHS,
    TIMELINE_INTERNAL_FIELDS,
    timeline_field_key,
    timeline_field_word_key,
)
from cadrumo.application.actividad_asset.fact_wording import CLAIM_AMOUNT_PATH
from cadrumo.core.external_constants import SUPPORTED_OUTPUT_LANGUAGES
from cadrumo.core.i18n.render import I18N_STRICT_MISSING_KEYS, tr
from cadrumo.domain.renta.actividad_asset.fact_leaves import fact_leaves
from cadrumo.domain.renta.actividad_asset.lifecycle import (
    AcquisitionLineageReference,
    ActivityAssetRevision,
)
from cadrumo.domain.renta.actividad_asset.register_records import ActivityAssetDescriptorFacts

from .operations_support import ACQUISITION, build_operations, build_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_INTERNAL = frozenset(
    {
        "asset_id",
        "revision_number",
        "supersedes_revision_id",
        "acquisition.observed_transaction_id",
        "acquisition.observed_lineage_event_id",
        "acquisition.evidence_fingerprint",
        "further_acquisitions[].lineage.observed_transaction_id",
        "further_acquisitions[].lineage.observed_lineage_event_id",
        "further_acquisitions[].lineage.evidence_fingerprint",
    }
)
"""Written out so a mark added to or dropped from a model shows up here as a decision."""


def test_the_fields_marked_internal_are_the_identities_and_chain_links() -> None:
    assert TIMELINE_INTERNAL_FIELDS == _INTERNAL


def test_every_record_field_is_either_internal_or_a_fact_the_timeline_words() -> None:
    every = {
        leaf.dotted for model in (ActivityAssetRevision, ActivityAssetDescriptorFacts) for leaf in fact_leaves(model)
    }

    assert set(TIMELINE_FIELD_PATHS) | TIMELINE_INTERNAL_FIELDS == every | {CLAIM_AMOUNT_PATH}
    assert not set(TIMELINE_FIELD_PATHS) & TIMELINE_INTERNAL_FIELDS


@pytest.mark.parametrize("locale", SUPPORTED_OUTPUT_LANGUAGES)
def test_every_fact_the_timeline_shows_has_a_word_in_every_locale(locale: str) -> None:
    token = I18N_STRICT_MISSING_KEYS.set(True)
    try:
        words = {path: tr(timeline_field_word_key(path), locale=locale) for path in TIMELINE_FIELD_PATHS}
    finally:
        I18N_STRICT_MISSING_KEYS.reset(token)

    assert all(word.strip() for word in words.values())
    assert len(words) == len(TIMELINE_FIELD_PATHS)


def test_a_path_that_is_no_fact_of_the_timeline_has_no_key() -> None:
    assert (
        timeline_field_key("further_acquisitions[3].shape") == "ledger.actividad_asset.field.further_acquisitions.shape"
    )
    assert timeline_field_key("asset_id") is None
    assert timeline_field_key("no.such.fact") is None


def test_the_timeline_states_the_key_of_each_change_and_never_shows_an_identity() -> None:
    operations = build_operations()
    first = operations.inspect("laptop-1")[0]
    corrected = build_revision(number=2, supersedes=first.revision_id, basis="1500").model_copy(
        update={
            "acquisition": AcquisitionLineageReference(
                observed_transaction_id=ACQUISITION.transaction_id,
                invoice_evidence_id="invoice-2",
                evidence_fingerprint="c" * 64,
            )
        }
    )
    operations.correct(corrected, origin="test.correct")

    events = operations.timeline("laptop-1")
    changed = {change.field: change for event in events for change in event.changes}

    assert not set(changed) & _INTERNAL
    assert changed["basis.basis_amount"].field_key == "ledger.actividad_asset.field.basis.basis_amount"
    assert (
        changed["acquisition.invoice_evidence_id"].field_key
        == "ledger.actividad_asset.field.acquisition.invoice_evidence_id"
    )
    assert all(change.field_key is not None for event in events for change in event.changes)
    created = events[0]
    assert {change.field for change in created.changes} >= {
        "in_service_date",
        "basis.basis_amount",
        "amortization.method",
    }


def test_a_claim_states_the_key_of_its_amount() -> None:
    operations = build_operations()
    operations.record_claim(
        operations.forecast(
            asset_id="laptop-1",
            covered_from=date(2025, 1, 1),
            covered_until=date(2026, 1, 1),
        ),
        creating_operation="test.words",
    )

    claim_event = operations.timeline("laptop-1")[-1]

    assert [change.field_key for change in claim_event.changes] == ["ledger.actividad_asset.field.amount"]
