"""Source evidence for complete membership of fixed binding-backed record rows.

:class:`RegistrySnapshot` pins the registry declarations used by the projection.
"""

from collections.abc import Mapping, Sequence, Set

from pydantic import BaseModel, Field, field_validator

from ...core.aggregation import BindingSourceKind
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.identity.bucket import BucketId
from ...core.identity.digest import ContentDigest
from ...core.identity.hex_ids import WorkUnitId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from .registry.errors import RegistryValidationError
from .registry.ids import BindingId, RecordId
from .registry.manual_input_selector import ManualInputProvider
from .registry.schema import RegistrySnapshot
from .registry.schema_references import RegistrySnapshotRef


class RecordRowMembership(BaseModel):
    """One declared row, including every binding whose value would occupy it.

    Occupied does not mean financially complete: required values can still be
    missing. An unused row is a positive source assertion, never a blank-cell
    inference. The owning resolver must verify these slots against its registry
    projection before issuing a closed row set.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    row_index: int = Field(ge=1)
    binding_ids: tuple[BindingId, ...] = Field(min_length=1)
    occupied: bool

    @field_validator("binding_ids")
    @classmethod
    @pydantic_validation_boundary
    def _canonical_bindings(cls, value: tuple[BindingId, ...]) -> tuple[BindingId, ...]:
        if len(value) != len(set(value)):
            raise ValueError("record row repeats a binding")
        return tuple(sorted(value))


class ClosedRecordRowSet(BaseModel):
    """An admitted source's complete enumeration for one fixed record table.

    The fingerprint covers the source collection, including membership and
    calculation-relevant contents. A hash-shaped string is not admission: the
    resolver owns enumeration, source validation and exact registry coverage.
    Consumers must also match all scope coordinates before using this evidence.
    Absence of this carrier means unknown membership, including an empty table.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    record_id: RecordId
    bucket_id: BucketId = Field(repr=False)
    work_unit_id: WorkUnitId = Field(repr=False)
    registry_snapshot_ref: RegistrySnapshotRef
    authority_generation: ContentDigest = Field(repr=False)
    source_kind: BindingSourceKind
    source_ref: str = Field(min_length=1, max_length=256, repr=False)
    source_fingerprint: ContentDigest = Field(repr=False)
    rows: tuple[RecordRowMembership, ...] = Field(min_length=1, repr=False)

    @field_validator("source_ref")
    @classmethod
    @pydantic_validation_boundary
    def _canonical_source_ref(cls, value: str) -> str:
        if value != value.strip() or any(ord(character) < 32 for character in value):
            raise ValueError("record row set source reference is not canonical")
        return value

    @field_validator("rows")
    @classmethod
    @pydantic_validation_boundary
    def _complete_unique_rows(cls, value: tuple[RecordRowMembership, ...]) -> tuple[RecordRowMembership, ...]:
        rows = tuple(sorted(value, key=lambda row: row.row_index))
        if tuple(row.row_index for row in rows) != tuple(range(1, len(rows) + 1)):
            raise ValueError("closed record rows must enumerate every slot exactly once")
        bindings = [binding for row in rows for binding in row.binding_ids]
        if len(bindings) != len(set(bindings)):
            raise ValueError("closed record rows assign one binding to multiple slots")
        return rows

    @property
    def binding_ids(self) -> frozenset[BindingId]:
        """All binding slots covered by this complete enumeration."""
        return frozenset(binding for row in self.rows for binding in row.binding_ids)

    @property
    def unused_binding_ids(self) -> frozenset[BindingId]:
        """Slots positively known to belong to unused rows."""
        return frozenset(binding for row in self.rows if not row.occupied for binding in row.binding_ids)


def validate_closed_record_row_sets(
    row_sets: Sequence[ClosedRecordRowSet], *, supplied_binding_ids: Set[BindingId]
) -> None:
    """Refuse ambiguous scope, overlapping ownership and populated unused rows."""
    records: set[RecordId] = set()
    bindings: set[BindingId] = set()
    scope = None
    for row_set in row_sets:
        current_scope = (
            row_set.bucket_id,
            row_set.work_unit_id,
            row_set.registry_snapshot_ref,
            row_set.authority_generation,
        )
        if scope is not None and current_scope != scope:
            raise ValueError("closed record row sets have different calculation scopes")
        scope = current_scope
        if row_set.record_id in records or bindings.intersection(row_set.binding_ids):
            raise ValueError("closed record row sets have ambiguous ownership")
        if row_set.unused_binding_ids.intersection(supplied_binding_ids):
            raise ValueError("an unused record row contains supplied values")
        records.add(row_set.record_id)
        bindings.update(row_set.binding_ids)


def resolve_closed_record_rows(
    snapshot: RegistrySnapshot,
    row_sets: Sequence[ClosedRecordRowSet],
    *,
    supplied_binding_ids: Set[BindingId],
) -> Mapping[BindingId, RecordRowMembership]:
    """Validate admitted evidence against the snapshot consumed by a calculation.

    The source resolver owns exact table enumeration and content fingerprints;
    the application owns profile, work-unit and authority admission. Both local
    arithmetic and workbook compilation must additionally check snapshot scope,
    declared record slots and consistency with the supplied values.

    The ``snapshot`` parameter uses :class:`RegistrySnapshot`, which pins
    the registry declarations used by the projection.
    """
    try:
        validate_closed_record_row_sets(row_sets, supplied_binding_ids=supplied_binding_ids)
    except ValueError as exc:
        raise RegistryValidationError("record row membership conflicts with calculation inputs") from exc
    providers = {binding.id: binding.provider for binding in snapshot.revision.bindings}
    rows: dict[BindingId, RecordRowMembership] = {}
    for row_set in row_sets:
        if row_set.registry_snapshot_ref != snapshot.snapshot_ref:
            raise RegistryValidationError("record row membership belongs to a different registry snapshot")
        for row in row_set.rows:
            for binding_id in row.binding_ids:
                provider = providers.get(binding_id)
                if not isinstance(provider, ManualInputProvider) or provider.record != row_set.record_id:
                    raise RegistryValidationError("record row membership does not address a declared fixed record slot")
                rows[binding_id] = row
    return rows
