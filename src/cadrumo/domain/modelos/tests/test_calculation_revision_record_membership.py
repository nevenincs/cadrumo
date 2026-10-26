"""Closed-row evidence survives secure serialization and participates in identity."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ....core.aggregation import BindingSourceKind
from ...calculations.record_row_membership import ClosedRecordRowSet, RecordRowMembership
from ...calculations.registry.schema_references import RegistrySnapshotRef
from ..calculation_revision import CalculationRevision, CalculationRevisionState, derive_calculation_revision_id

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]

_SECURE = {"secure_calculation_revision": True}
_SNAPSHOT = RegistrySnapshotRef(modelo="369", revision_id="esquema-exterior", modelo_year=2025, period="EXT-1T")


def _closed() -> ClosedRecordRowSet:
    return ClosedRecordRowSet(
        record_id="services",
        bucket_id="fictional-profile",
        work_unit_id="a" * 64,
        registry_snapshot_ref=_SNAPSHOT,
        authority_generation="b" * 64,
        source_kind=BindingSourceKind.LEDGER_OSS_AGGREGATION,
        source_ref="private-collection-reference",
        source_fingerprint="c" * 64,
        rows=(RecordRowMembership(row_index=1, binding_ids=("country", "quota"), occupied=False),),
    )


def _revision(row_sets: tuple[ClosedRecordRowSet, ...]) -> CalculationRevision:
    created = datetime(2026, 10, 6, tzinfo=UTC)
    return CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id="a" * 64,
            input_values_by_casilla_id={},
            binding_overrides={},
            closed_record_row_sets=row_sets,
            casilla_values={},
            source_provenance=(),
            filing_instance_evidence=None,
        ),
        work_unit_id="a" * 64,
        registry_snapshot_ref=_SNAPSHOT,
        state=CalculationRevisionState.BORRADOR,
        closed_record_row_sets=row_sets,
        source_provenance=(),
        filing_instance_evidence=None,
        created_at=created,
        updated_at=created,
    )


def test_unknown_and_complete_empty_have_different_revision_ids() -> None:
    assert _revision(()).calculation_revision_id != _revision((_closed(),)).calculation_revision_id


def test_membership_is_private_but_survives_secure_python_and_json_roundtrips() -> None:
    revision = _revision((_closed(),))
    assert "closed_record_row_sets" not in revision.model_dump(mode="json")
    assert "private-collection-reference" not in repr(revision)
    assert "private-collection-reference" not in revision.model_dump_json()
    payload = revision.model_dump(mode="python", context=_SECURE)
    assert CalculationRevision.model_validate(payload, context=_SECURE) == revision
    assert (
        CalculationRevision.model_validate_json(revision.model_dump_json(context=_SECURE), context=_SECURE) == revision
    )


@pytest.mark.parametrize("change", ["remove", "unused", "fingerprint", "scope"])
def test_altered_membership_cannot_retain_the_saved_revision_identity(change: str) -> None:
    revision = _revision((_closed(),))
    payload = dict(revision)
    original = _closed()
    if change == "remove":
        changed = ()
    elif change == "unused":
        changed = (
            original.model_copy(
                update={"rows": (RecordRowMembership(row_index=1, binding_ids=("country", "quota"), occupied=True),)}
            ),
        )
    elif change == "fingerprint":
        changed = (original.model_copy(update={"source_fingerprint": "d" * 64}),)
    else:
        changed = (original.model_copy(update={"work_unit_id": "e" * 64}),)
    payload["closed_record_row_sets"] = changed
    with pytest.raises(ValidationError):
        CalculationRevision.model_validate(payload)


def test_saved_binding_values_cannot_populate_a_claimed_unused_row() -> None:
    revision = _revision((_closed(),))
    payload = {**dict(revision), "binding_overrides": {"quota": "0"}}
    payload["calculation_revision_id"] = derive_calculation_revision_id(
        work_unit_id=revision.work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={"quota": "0"},
        closed_record_row_sets=revision.closed_record_row_sets,
        casilla_values={},
        source_provenance=(),
        filing_instance_evidence=None,
    )
    with pytest.raises(ValidationError, match="closed record rows disagree"):
        CalculationRevision.model_validate(payload)
