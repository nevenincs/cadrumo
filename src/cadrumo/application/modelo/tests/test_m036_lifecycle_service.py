"""Inward M036 lifecycle policy tests.

The application owns profile/bucket validation, lifecycle sequencing, event
derivation, and the required capability bundle. These tests keep those rules
at the application seam with protocol-shaped in-memory repositories. Real
encrypted snapshot and bucket-event persistence is covered under the profile
adapter test package.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime

import pytest

from ....core.classification.policies import SensitivityClass
from ....core.secure_object_write import SecureObjectWrite
from ....domain.buckets.event import BucketEventHistoryCatalogue, BucketEventType
from ....domain.calculations.registry.censo_modelos import CensoModeloEventKind
from ....domain.modelos.errors import Modelo036PriorAltaRequiredError
from ...live.errors import LiveApplicationInputError
from ..m036_lifecycle import M036DeclarationCommand, M036DeclarationResult, record_m036_declaration
from ..m036_lifecycle_ports import M036LifecyclePorts

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = "32323232-3232-4232-8232-323232323232"


class _PreparedEventWrite(SecureObjectWrite):
    catalogue: BucketEventHistoryCatalogue


class _EventRepository:
    """Minimal revisioned bucket-event capability for inward policy tests."""

    def __init__(self) -> None:
        self.catalogue = BucketEventHistoryCatalogue()
        self.revision = "0" * 64

    def exists(self) -> bool:
        return bool(self.catalogue.events)

    def load(self) -> BucketEventHistoryCatalogue:
        return self.catalogue

    def save(self, catalogue: BucketEventHistoryCatalogue) -> None:
        self.catalogue = catalogue
        self.revision = hashlib.sha256(self.revision.encode()).hexdigest()

    def load_revisioned(self) -> tuple[BucketEventHistoryCatalogue, str]:
        return self.catalogue, self.revision

    def to_secure_object_write(
        self,
        catalogue: BucketEventHistoryCatalogue,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        return _PreparedEventWrite(
            namespace="test",
            object_key="m036-event-history",
            classification=SensitivityClass.AUDIT,
            schema_version=1,
            written_at=datetime(2026, 6, 4, tzinfo=UTC),
            payload=b"m036-event-history",
            expected_revision_id=expected_revision_id,
            catalogue=catalogue,
        )

    def commit(self, write: SecureObjectWrite) -> None:
        if not isinstance(write, _PreparedEventWrite):
            raise TypeError("m036 fake received an unexpected secure-object write")
        if write.expected_revision_id != self.revision:
            raise AssertionError("stale fake event write")
        self.save(write.catalogue)


class _DeclarationRepository:
    """In-memory declaration capability that co-commits event writes."""

    def __init__(self, events: _EventRepository) -> None:
        self.events = events
        self.records: dict[str, M036DeclarationResult] = {}

    def exists(self, declaration_id: str) -> bool:
        return declaration_id in self.records

    def load(self, declaration_id: str) -> M036DeclarationResult:
        return self.records[declaration_id]

    def list_snapshots(self) -> tuple[M036DeclarationResult, ...]:
        return tuple(self.records.values())

    def resolve(self, declaration_id: str) -> M036DeclarationResult:
        matches = tuple(record for key, record in self.records.items() if key.startswith(declaration_id))
        if len(matches) != 1:
            raise KeyError(declaration_id)
        return matches[0]

    def save(self, declaration: M036DeclarationResult) -> None:
        self.records[declaration.declaration_id] = declaration

    def save_with_secure_object_writes(
        self,
        declaration: M036DeclarationResult,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        if not extra_writes:
            raise AssertionError("m036 declaration requires one event write")
        self.events.commit(extra_writes[0])
        self.save(declaration)


def _ports() -> M036LifecyclePorts:
    events = _EventRepository()
    return M036LifecyclePorts(
        declaration_repository=_DeclarationRepository(events),
        bucket_event_repository=events,
    )


def _command(event_kind: CensoModeloEventKind = CensoModeloEventKind.ALTA) -> M036DeclarationCommand:
    return M036DeclarationCommand(
        profile_id=_PROFILE_ID,
        event_kind=event_kind,
        declared_on=date(2026, 6, 4),
    )


def test_record_uses_required_ports_to_store_declaration_and_event() -> None:
    ports = _ports()

    result = record_m036_declaration(_command(), bucket_id=_PROFILE_ID, ports=ports)

    declarations = ports.declaration_repository.list_snapshots()
    events = ports.bucket_event_repository.load()
    assert declarations == (result,)
    assert len(events.events) == 1
    assert next(iter(events.events.values())).event_type is BucketEventType.CENSO_DECLARATION_ALTA


def test_profile_mismatch_is_rejected_before_capabilities_are_used() -> None:
    ports = _ports()

    with pytest.raises(LiveApplicationInputError):
        record_m036_declaration(_command(), bucket_id="39393939-3939-4939-8939-393939393939", ports=ports)

    assert ports.declaration_repository.list_snapshots() == ()
    assert ports.bucket_event_repository.load().events == {}


def test_modificacion_requires_a_prior_alta_on_the_bound_capabilities() -> None:
    ports = _ports()

    with pytest.raises(Modelo036PriorAltaRequiredError):
        record_m036_declaration(
            _command(CensoModeloEventKind.MODIFICACION),
            bucket_id=_PROFILE_ID,
            ports=ports,
        )

    alta = record_m036_declaration(_command(), bucket_id=_PROFILE_ID, ports=ports)
    modificacion = record_m036_declaration(
        _command(CensoModeloEventKind.MODIFICACION),
        bucket_id=_PROFILE_ID,
        ports=ports,
    )

    assert alta.event_kind is CensoModeloEventKind.ALTA
    assert modificacion.event_kind is CensoModeloEventKind.MODIFICACION
    assert len(ports.declaration_repository.list_snapshots()) == 2
