"""Prorrata settlement filing writes definitive register state.

See Also:
    :func:`~application.modelo._revision_persistence.persist_filed_revision`
        Filing transition that co-emits the settlement register write.
    :class:`~adapters.persistence.profile.prorrata_register.ProrrataRegisterRepository`
        Encrypted profile repository receiving the definitive prorrata state.
    :class:`~domain.prorrata_register.ProrrataRegisterEntry`
        Per-ejercicio row updated with definitive percentage and annual volumes.
    :class:`~CalculationRevision`
        Verified Modelo 303 revision whose casilla observations supply the
        settlement values.
    :class:`~TransactionRevisionParticipationIndex`
        Sibling filing co-write whose atomicity pattern the prorrata writeback
        follows.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.participation_index import TransactionParticipationIndexRepository
from ....adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from ....core import Period, ProrrataActivityRowType, ProrrataProvisionalProvenance, ProrrataRegisterRegime
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.bindings import CasillaObservation
from ....domain.modelos.calculation_repository import upsert_calculation_revision
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.repository import upsert_work_unit
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.prorrata_register import ProrrataActivityRow, ProrrataRegister, ProrrataRegisterEntry
from ....tests import general_m303_filing_evidence
from ....tests.secure_sql import isolated_runtime_profile
from .._revision_persistence import persist_filed_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "a98e3d41-e45a-4616-a82b-d3e4bbe94e07"  # was 'prorrata-settlement-writeback'
_T0 = datetime(2026, 1, 1, 9, 0, 0, tzinfo=UTC)

_VOLUMEN_TOTAL: CasillaId = validated_casilla_id("iva.prorrata-volumen-total", surface="test casilla id")
_VOLUMEN_CON_DERECHO: CasillaId = validated_casilla_id(
    "iva.prorrata-volumen-con-derecho",
    surface="test casilla id",
)
_PORCENTAJE: CasillaId = validated_casilla_id("iva.prorrata-porcentaje", surface="test casilla id")

_SETTLEMENT_VALUES = {
    _VOLUMEN_TOTAL: Decimal("200000.00"),
    _VOLUMEN_CON_DERECHO: Decimal("150000.00"),
    _PORCENTAJE: Decimal("75"),
}


def _observation(casilla_id: CasillaId, value: Decimal) -> CasillaObservation:
    return CasillaObservation(
        casilla_id=casilla_id,
        value=value,
        legal_refs=("ley-37-1992:art-104", "ley-37-1992:art-105"),
        source_refs=("modelo-303-prorrata-settlement-test",),
    )


def _seed_verified_m303_revision(
    *,
    calculation_repository: CalculationRevisionCatalogueRepository,
    work_unit_repository: WorkUnitCatalogueRepository,
    period_code: str = "4T",
    casilla_values: dict[CasillaId, Decimal] | None = None,
) -> tuple[CalculationRevision, WorkUnit]:
    values = dict(_SETTLEMENT_VALUES if casilla_values is None else casilla_values)
    period = Period.from_year_and_code(2026, period_code)
    revision_id = bundled_authority().snapshot("303", filing_year=2026, period=period.registry_token).revision.id
    work_unit_id = derive_work_unit_id(
        bucket_id=_BUCKET_ID,
        modelo="303",
        filing_year=2026,
        period=period,
        revision_id=revision_id,
    )
    filing_instance_evidence = general_m303_filing_evidence(period, reference="test:prorrata-settlement-writeback")
    calculation_revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=values,
        filing_instance_evidence=filing_instance_evidence,
        source_provenance=(),
    )
    verified_at = _T0 + timedelta(hours=1)
    revision = CalculationRevision(
        calculation_revision_id=calculation_revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=values,
        observations=tuple(_observation(casilla_id, value) for casilla_id, value in values.items()),
        created_at=_T0,
        updated_at=verified_at,
        verified_at=verified_at,
        verified_by="aeat.test.modelo.verify",
        filing_instance_evidence=filing_instance_evidence,
        source_provenance=(),
    )
    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode("303"),
        filing_year=2026,
        period=period,
        revision_id=revision_id,
        name=f"303-2026-{period_code}",
        created_at=_T0,
        updated_at=verified_at,
        current_calculation_revision_id=calculation_revision_id,
    )
    calculation_repository.save(upsert_calculation_revision(calculation_repository.load(), revision))
    work_unit_repository.save(upsert_work_unit(work_unit_repository.load(), work_unit))
    return revision, work_unit


def _file_verified_revision(
    *,
    calculation_repository: CalculationRevisionCatalogueRepository,
    filing_repository: ModeloRecordCatalogueRepository,
    work_unit_repository: WorkUnitCatalogueRepository,
    prorrata_repository: ProrrataRegisterRepository,
    revision: CalculationRevision,
    work_unit: WorkUnit,
) -> None:
    persist_filed_revision(
        target=revision,
        work_unit=work_unit,
        work_units=work_unit_repository.load(),
        notes=None,
        actor="aeat.test.modelo.file",
        now=_T0 + timedelta(hours=2),
        calculation_repository=calculation_repository,
        filing_repository=filing_repository,
        work_unit_repository=work_unit_repository,
        bucket_event_repository=BucketEventHistoryRepository(),
        participation_index_repository=TransactionParticipationIndexRepository(bucket_id=_BUCKET_ID),
        prorrata_register_repository=prorrata_repository,
    )


def test_m303_settlement_creates_prorrata_register_entry_when_none_exists(tmp_path: Path) -> None:
    """Filing a settlement revision writes definitive percentage and volumes."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        calculation_repository = CalculationRevisionCatalogueRepository(bucket_id=_BUCKET_ID)
        filing_repository = ModeloRecordCatalogueRepository(bucket_id=_BUCKET_ID)
        work_unit_repository = WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID)
        prorrata_repository = ProrrataRegisterRepository(bucket_id=_BUCKET_ID)
        revision, work_unit = _seed_verified_m303_revision(
            calculation_repository=calculation_repository,
            work_unit_repository=work_unit_repository,
        )

        _file_verified_revision(
            calculation_repository=calculation_repository,
            filing_repository=filing_repository,
            work_unit_repository=work_unit_repository,
            prorrata_repository=prorrata_repository,
            revision=revision,
            work_unit=work_unit,
        )

        entry = prorrata_repository.load().entry_for(2026)
        filed_revision = calculation_repository.load().get(revision.calculation_revision_id)

    assert entry is not None
    assert entry.regime is ProrrataRegisterRegime.GENERAL
    assert entry.definitive_percentage == Decimal("75")
    assert entry.definitive_volume_con_derecho == Decimal("150000.00")
    assert entry.definitive_volume_sin_derecho == Decimal("50000.00")
    assert filed_revision is not None
    assert filed_revision.state is CalculationRevisionState.PRESENTADO


def test_m303_settlement_preserves_existing_register_facts(tmp_path: Path) -> None:
    """Settlement write-back replaces only the whole-entity settlement fields."""
    existing = ProrrataRegisterEntry(
        ejercicio=2026,
        regime=ProrrataRegisterRegime.GENERAL,
        especial_transition=None,
        provisional_percentage=Decimal("80"),
        provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
        source_observation_ref="303:2025:4T",
    )
    sector_entry = ProrrataRegisterEntry(
        ejercicio=2026,
        regime=ProrrataRegisterRegime.ESPECIAL,
        especial_transition=None,
        sector_id="arrendamiento",
        provisional_percentage=Decimal("60"),
        provisional_provenance=ProrrataProvisionalProvenance.AEAT_AUTORIZADA,
        authorisation_reference="AEAT-AUTH-2026-001",
    )

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        calculation_repository = CalculationRevisionCatalogueRepository(bucket_id=_BUCKET_ID)
        filing_repository = ModeloRecordCatalogueRepository(bucket_id=_BUCKET_ID)
        work_unit_repository = WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID)
        prorrata_repository = ProrrataRegisterRepository(bucket_id=_BUCKET_ID)
        prorrata_repository.save(ProrrataRegister(entries=(existing, sector_entry)))
        revision, work_unit = _seed_verified_m303_revision(
            calculation_repository=calculation_repository,
            work_unit_repository=work_unit_repository,
        )

        _file_verified_revision(
            calculation_repository=calculation_repository,
            filing_repository=filing_repository,
            work_unit_repository=work_unit_repository,
            prorrata_repository=prorrata_repository,
            revision=revision,
            work_unit=work_unit,
        )

        register = prorrata_repository.load()

    carried = register.entry_for(2026)
    retained_sector = register.entry_for(2026, sector_id="arrendamiento")
    assert carried is not None
    assert carried.regime is ProrrataRegisterRegime.GENERAL
    assert carried.provisional_percentage == Decimal("80")
    assert carried.provisional_provenance is ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA
    assert carried.source_observation_ref == "303:2025:4T"
    assert carried.definitive_percentage == Decimal("75")
    assert carried.definitive_volume_con_derecho == Decimal("150000.00")
    assert carried.definitive_volume_sin_derecho == Decimal("50000.00")
    assert retained_sector == sector_entry


def test_m303_settlement_preserves_existing_activity_rows(tmp_path: Path) -> None:
    """Filing 4T cannot erase the canonical DP30305 activity evidence."""
    general_entry = ProrrataRegisterEntry(
        ejercicio=2026,
        regime=ProrrataRegisterRegime.GENERAL,
        especial_transition=None,
    )
    activity_row = ProrrataActivityRow(
        ejercicio=2026,
        activity_id="retail-general",
        slot=1,
        cnae_code="471",
        operaciones_total=Decimal("200000.00"),
        operaciones_con_derecho=Decimal("150000.00"),
        prorrata_type=ProrrataActivityRowType.GENERAL,
        percentage=Decimal("75"),
        evidence_reference="evidence:dp30305:retail-general:2026",
    )
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        calculation_repository = CalculationRevisionCatalogueRepository(bucket_id=_BUCKET_ID)
        filing_repository = ModeloRecordCatalogueRepository(bucket_id=_BUCKET_ID)
        work_unit_repository = WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID)
        prorrata_repository = ProrrataRegisterRepository(bucket_id=_BUCKET_ID)
        prorrata_repository.save(ProrrataRegister(entries=(general_entry,), activity_rows=(activity_row,)))
        revision, work_unit = _seed_verified_m303_revision(
            calculation_repository=calculation_repository,
            work_unit_repository=work_unit_repository,
        )

        _file_verified_revision(
            calculation_repository=calculation_repository,
            filing_repository=filing_repository,
            work_unit_repository=work_unit_repository,
            prorrata_repository=prorrata_repository,
            revision=revision,
            work_unit=work_unit,
        )

        persisted = prorrata_repository.load()

    assert persisted.activity_rows == (activity_row,)
    settled_entry = persisted.entry_for(2026)
    assert settled_entry is not None
    assert settled_entry.definitive_percentage == Decimal("75")


@pytest.mark.parametrize("period_code", ("1T", "2T", "3T"))
def test_non_settlement_period_does_not_write_prorrata_register(tmp_path: Path, period_code: str) -> None:
    """Only annual close periods seed the definitive prorrata register fields."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        calculation_repository = CalculationRevisionCatalogueRepository(bucket_id=_BUCKET_ID)
        filing_repository = ModeloRecordCatalogueRepository(bucket_id=_BUCKET_ID)
        work_unit_repository = WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID)
        prorrata_repository = ProrrataRegisterRepository(bucket_id=_BUCKET_ID)
        revision, work_unit = _seed_verified_m303_revision(
            calculation_repository=calculation_repository,
            work_unit_repository=work_unit_repository,
            period_code=period_code,
        )

        _file_verified_revision(
            calculation_repository=calculation_repository,
            filing_repository=filing_repository,
            work_unit_repository=work_unit_repository,
            prorrata_repository=prorrata_repository,
            revision=revision,
            work_unit=work_unit,
        )

        register = prorrata_repository.load()

    assert register.entries == ()
