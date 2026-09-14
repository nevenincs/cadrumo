"""Rebuild the participation index from finalized-revision catalogues.

The application service is exercised through inward repository fakes.  Adapter
round-trips belong to the persistence adapter tests; these cases cover the
application projection and its replacement semantics without importing storage.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

import pytest

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.modelos.calculation_repository import upsert_calculation_revision
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.filing_record import (
    ModeloRecord,
    ModeloRecordCatalogue,
    ModeloRecordStatus,
    derive_filing_record_id,
)
from ....domain.modelos.filing_repository import upsert_filing_record
from ....domain.modelos.participation_index import (
    TransactionRevisionParticipation,
    TransactionRevisionParticipationIndex,
    upsert_transaction_participation,
)
from ....domain.modelos.repository import upsert_work_unit
from ....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from ..participation_index_rebuild import rebuild_participation_index
from ..participation_index_rebuild_ports import ParticipationIndexRebuildPorts

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "1cfbce2c-6cf7-43fe-a1a0-60c2e44cd95b"  # was 'modelo-participation-rebuild'
_T0 = datetime(2024, 7, 1, 9, 0, 0, tzinfo=UTC)

_TX_FILED = "1" * 64
_TX_VERIFIED = "2" * 64
_TX_BORRADOR = "3" * 64
_TX_SHARED = "4" * 64  # touched by both the filed and the verified revision
_IVA_BASE_IMPONIBLE_CASILLA: CasillaId = validated_casilla_id(
    "iva.base-imponible",
    surface="_IVA_BASE_IMPONIBLE_CASILLA",
)


class _CalculationRepository:
    """Inward fake for the calculation-revision catalogue capability."""

    def __init__(self) -> None:
        self._catalogue = CalculationRevisionCatalogue()

    def load(self) -> CalculationRevisionCatalogue:
        """Return the current in-memory calculation catalogue."""
        return self._catalogue

    def save(self, catalogue: CalculationRevisionCatalogue) -> None:
        """Replace the in-memory calculation catalogue."""
        self._catalogue = catalogue


class _WorkUnitRepository:
    """Inward fake for the work-unit catalogue capability."""

    def __init__(self) -> None:
        self._catalogue = WorkUnitCatalogue()

    def load(self) -> WorkUnitCatalogue:
        """Return the current in-memory work-unit catalogue."""
        return self._catalogue

    def save(self, catalogue: WorkUnitCatalogue) -> None:
        """Replace the in-memory work-unit catalogue."""
        self._catalogue = catalogue


class _FilingRepository:
    """Inward fake for the filing-record catalogue capability."""

    def __init__(self) -> None:
        self._catalogue = ModeloRecordCatalogue()

    def load(self) -> ModeloRecordCatalogue:
        """Return the current in-memory filing-record catalogue."""
        return self._catalogue

    def save(self, catalogue: ModeloRecordCatalogue) -> None:
        """Replace the in-memory filing-record catalogue."""
        self._catalogue = catalogue


class _ParticipationIndexRepository:
    """Inward fake for the derived index replacement capability."""

    def __init__(self) -> None:
        self._indexes: dict[str, TransactionRevisionParticipationIndex] = {}

    def exists(self, transaction_id: str) -> bool:
        """Report whether an index exists for ``transaction_id``."""
        return transaction_id in self._indexes

    def load(self, transaction_id: str) -> TransactionRevisionParticipationIndex:
        """Return an index or the empty index for ``transaction_id``."""
        return self._indexes.get(
            transaction_id,
            TransactionRevisionParticipationIndex(transaction_id=transaction_id),
        )

    def save(self, index: TransactionRevisionParticipationIndex) -> None:
        """Persist one in-memory index."""
        self._indexes[index.transaction_id] = index

    def replace_all(self, indexes: Iterable[TransactionRevisionParticipationIndex]) -> int:
        """Replace every in-memory index and return the stale-row count."""
        replacement = {index.transaction_id: index for index in indexes}
        stale_count = len(self._indexes.keys() - replacement.keys())
        self._indexes = replacement
        return stale_count


def _work_unit(*, modelo: str, period: str, revision_seed: str) -> WorkUnit:
    typed_period = Period.from_year_and_code(2024, period)
    work_unit_id = derive_work_unit_id(
        bucket_id=_BUCKET_ID,
        modelo=modelo,
        filing_year=2024,
        period=typed_period,
        revision_id=revision_seed,
    )
    return WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode(modelo),
        filing_year=2024,
        period=typed_period,
        revision_id=revision_seed,
        name=f"{modelo}-2024-{period}",
        created_at=_T0,
        updated_at=_T0,
    )


def _revision(*, work_unit: WorkUnit, state: CalculationRevisionState, txids: tuple[str, ...]) -> CalculationRevision:
    inputs = {_IVA_BASE_IMPONIBLE_CASILLA: "1000.00"}
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id=inputs,
        binding_overrides={},
        casilla_values={},
        source_transaction_ids=txids,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    verified_at: datetime | None = None
    verified_by: str | None = None
    filed_at: datetime | None = None
    filed_by: str | None = None
    if state in {CalculationRevisionState.VERIFICADO_COMPLETO, CalculationRevisionState.PRESENTADO}:
        verified_at = _T0 + timedelta(hours=1)
        verified_by = "aeat.cli.modelo.verify"
    if state is CalculationRevisionState.PRESENTADO:
        filed_at = _T0 + timedelta(hours=2)
        filed_by = "aeat.cli.modelo.file"
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit.work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo=work_unit.modelo,
            revision_id=work_unit.revision_id,
            modelo_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
        ),
        state=state,
        input_values_by_casilla_id=inputs,
        source_transaction_ids=txids,
        created_at=_T0,
        updated_at=_T0 + timedelta(hours=2),
        verified_at=verified_at,
        verified_by=verified_by,
        filed_at=filed_at,
        filed_by=filed_by,
        filing_instance_evidence=None,
        source_provenance=(),
    )


def test_rebuild_includes_finalized_excludes_borrador_and_carries_filing_record() -> None:
    """Rebuild folds every finalized revision in, drops borrador, carries filing_record_id."""
    cr_repo = _CalculationRepository()
    wu_repo = _WorkUnitRepository()
    fr_repo = _FilingRepository()
    participation_repo = _ParticipationIndexRepository()
    ports = ParticipationIndexRebuildPorts(
        calculation_repository=cr_repo,
        work_unit_repository=wu_repo,
        filing_repository=fr_repo,
        participation_index_repository=participation_repo,
    )

    filed_wu = _work_unit(modelo="303", period="1T", revision_seed="303")
    verified_wu = _work_unit(modelo="130", period="2T", revision_seed="130")
    borrador_wu = _work_unit(modelo="303", period="3T", revision_seed="303b")

    filed_rev = _revision(
        work_unit=filed_wu,
        state=CalculationRevisionState.PRESENTADO,
        txids=(_TX_FILED, _TX_SHARED),
    )
    verified_rev = _revision(
        work_unit=verified_wu,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        txids=(_TX_VERIFIED, _TX_SHARED),
    )
    borrador_rev = _revision(
        work_unit=borrador_wu,
        state=CalculationRevisionState.BORRADOR,
        txids=(_TX_BORRADOR,),
    )

    work_units = wu_repo.load()
    for wu in (filed_wu, verified_wu, borrador_wu):
        work_units = upsert_work_unit(work_units, wu)
    wu_repo.save(work_units)

    revisions = cr_repo.load()
    for rev in (filed_rev, verified_rev, borrador_rev):
        revisions = upsert_calculation_revision(revisions, rev)
    cr_repo.save(revisions)

    # A filing record bound to the filed revision so rebuild can attach filing_record_id.
    filing_id = derive_filing_record_id(
        work_unit_id=filed_wu.work_unit_id,
        calculation_revision_id=filed_rev.calculation_revision_id,
        filed_by="aeat.cli.modelo.file",
    )
    filing_record = ModeloRecord(
        filing_record_id=filing_id,
        work_unit_id=filed_wu.work_unit_id,
        calculation_revision_id=filed_rev.calculation_revision_id,
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode("303"),
        filing_year=2024,
        period=Period.from_year_and_code(2024, "1T"),
        filed_at=_T0 + timedelta(hours=2),
        filed_by="aeat.cli.modelo.file",
        status=ModeloRecordStatus.VIGENTE,
    )
    fr_repo.save(upsert_filing_record(fr_repo.load(), filing_record))

    stats = rebuild_participation_index(ports=ports)

    index_filed = participation_repo.load(_TX_FILED)
    index_verified = participation_repo.load(_TX_VERIFIED)
    index_borrador = participation_repo.load(_TX_BORRADOR)
    index_shared = participation_repo.load(_TX_SHARED)

    # Two finalized revisions folded in (borrador excluded).
    assert stats.revision_count == 2
    # Four transaction objects gained at least one entry: filed, verified, shared (borrador excluded).
    assert stats.transaction_count == 3
    # filed(2 tx) + verified(2 tx) = 4 participation entries.
    assert stats.participation_count == 4

    # Borrador transaction has no entry.
    assert index_borrador.participations == ()

    # Filed revision entry carries filing_record_id.
    (filed_entry,) = index_filed.participations
    assert filed_entry.revision_state == "presentado"
    assert filed_entry.filing_record_id == filing_id

    # Verified revision entry has no filing_record_id.
    (verified_entry,) = index_verified.participations
    assert verified_entry.revision_state == "verificado_completo"
    assert verified_entry.filing_record_id is None

    # Shared transaction carries BOTH revisions' participations.
    shared_revisions = {p.calculation_revision_id for p in index_shared.participations}
    assert shared_revisions == {filed_rev.calculation_revision_id, verified_rev.calculation_revision_id}


def test_rebuild_on_empty_catalogue_writes_nothing() -> None:
    """An empty revision catalogue rebuilds to zero participations."""
    stats = rebuild_participation_index(
        ports=ParticipationIndexRebuildPorts(
            calculation_repository=_CalculationRepository(),
            work_unit_repository=_WorkUnitRepository(),
            filing_repository=_FilingRepository(),
            participation_index_repository=_ParticipationIndexRepository(),
        ),
    )

    assert stats.revision_count == 0
    assert stats.transaction_count == 0
    assert stats.participation_count == 0
    assert stats.stale_removed_count == 0


def test_rebuild_prunes_participation_absent_from_the_regenerated_catalogue() -> None:
    """A persisted entry the catalogue no longer records is removed, not left readable.

    The index is a derived cache over the finalized-revision catalogue, so a
    rebuild must REPLACE rather than upsert: an entry whose revision has since
    been discarded has no regenerated row, and leaving its secure object in place
    would keep surfacing a participation the authority dropped.
    """
    participation_repo = _ParticipationIndexRepository()
    ports = ParticipationIndexRebuildPorts(
        calculation_repository=_CalculationRepository(),
        work_unit_repository=_WorkUnitRepository(),
        filing_repository=_FilingRepository(),
        participation_index_repository=participation_repo,
    )

    # A genuine persisted participation whose revision is absent from the
    # (empty) catalogue the rebuild will read.
    stale_wu = _work_unit(modelo="303", period="4T", revision_seed="303stale")
    stale_rev = _revision(
        work_unit=stale_wu,
        state=CalculationRevisionState.PRESENTADO,
        txids=(_TX_BORRADOR,),
    )
    participation_repo.save(
        upsert_transaction_participation(
            TransactionRevisionParticipationIndex(transaction_id=_TX_BORRADOR),
            TransactionRevisionParticipation(
                calculation_revision_id=stale_rev.calculation_revision_id,
                work_unit_id=stale_wu.work_unit_id,
                modelo=stale_wu.modelo,
                filing_year=stale_wu.filing_year,
                period=stale_wu.period,
                revision_state=CalculationRevisionState.PRESENTADO.value,
            ),
        ),
    )
    assert participation_repo.exists(_TX_BORRADOR)

    stats = rebuild_participation_index(ports=ports)

    pruned_exists = participation_repo.exists(_TX_BORRADOR)
    pruned_index = participation_repo.load(_TX_BORRADOR)

    assert stats.stale_removed_count == 1
    assert pruned_exists is False
    assert pruned_index.participations == ()


def test_rebuild_prunes_only_transactions_the_catalogue_dropped() -> None:
    """Pruning is scoped to absent keys: a still-finalized transaction round-trips intact."""
    cr_repo = _CalculationRepository()
    wu_repo = _WorkUnitRepository()
    participation_repo = _ParticipationIndexRepository()
    ports = ParticipationIndexRebuildPorts(
        calculation_repository=cr_repo,
        work_unit_repository=wu_repo,
        filing_repository=_FilingRepository(),
        participation_index_repository=participation_repo,
    )

    kept_wu = _work_unit(modelo="130", period="2T", revision_seed="130keep")
    kept_rev = _revision(
        work_unit=kept_wu,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        txids=(_TX_VERIFIED,),
    )
    wu_repo.save(upsert_work_unit(wu_repo.load(), kept_wu))
    cr_repo.save(upsert_calculation_revision(cr_repo.load(), kept_rev))

    # A stale object for a transaction no revision references any more.
    participation_repo.save(TransactionRevisionParticipationIndex(transaction_id=_TX_BORRADOR))

    stats = rebuild_participation_index(ports=ports)

    kept_index = participation_repo.load(_TX_VERIFIED)
    dropped_exists = participation_repo.exists(_TX_BORRADOR)

    assert stats.stale_removed_count == 1
    assert dropped_exists is False

    # The retained transaction survives the replace with its real participation.
    (kept_entry,) = kept_index.participations
    assert kept_entry.calculation_revision_id == kept_rev.calculation_revision_id
    assert kept_entry.work_unit_id == kept_wu.work_unit_id
    assert kept_entry.revision_state == CalculationRevisionState.VERIFICADO_COMPLETO.value
    assert kept_entry.filing_record_id is None
