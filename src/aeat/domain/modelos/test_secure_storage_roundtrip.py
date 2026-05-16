"""Strict roundtrip across the encrypted Modelo work-unit + calculation catalogues.

Two repositories share the modelo-domain encrypted persistence
boundary and were flagged as untested in the persistence-boundary
identity audit:

  * ``WorkUnitCatalogueRepository`` persists
    :class:`WorkUnitCatalogue`, a keyed mapping of :class:`WorkUnit`
    records at ``SensitivityClass.FINANCIAL``.
  * (``CalculationRevisionCatalogueRepository`` is already covered
    by ``domain/filing/test_secure_storage_roundtrip.py`` —
    keep the focus here on the work-unit half.)
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ...adapters.persistence.storage import (
    EphemeralMasterKeyProvider,
    override_master_key_provider,
)
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...adapters.persistence.storage.sql._orm import Base
from ...adapters.persistence.storage.sql.engine import create_engine_from_settings
from ...core.config import Settings
from ._repository import WorkUnitCatalogueRepository
from ._work_unit import (
    WorkUnit,
    WorkUnitCatalogue,
    WorkUnitState,
    derive_work_unit_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


def _populated_work_unit(*, name_suffix: str = "default") -> WorkUnit:
    """Build a typed WorkUnit with deterministic id."""

    now = datetime.now(UTC).replace(microsecond=0)
    bucket_id = "b" * 32
    modelo = "303"
    filing_year = 2025
    period = "1T"
    revision_id = "2025-y-siguientes"
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=bucket_id,
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            revision_id=revision_id,
        ),
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
        name=f"IVA-{filing_year}-{period}-{name_suffix}",
        created_at=now,
        updated_at=now,
        state=WorkUnitState.DRAFT,
    )


def test_work_unit_catalogue_survives_encrypted_storage_roundtrip(
    tmp_path: Path,
) -> None:
    """A WorkUnitCatalogue with one typed WorkUnit roundtrips strictly."""

    provider = EphemeralMasterKeyProvider()
    override_master_key_provider(provider)
    db_path = tmp_path / "work-unit-catalogue-roundtrip.db"
    engine = create_engine_from_settings(
        Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"),
    )
    Base.metadata.create_all(engine)
    try:
        SecureObjectRepository(engine=engine)

        work_unit = _populated_work_unit()
        original = WorkUnitCatalogue(work_units={work_unit.work_unit_id: work_unit})

        repo = WorkUnitCatalogueRepository()
        repo.save(original)
        loaded = repo.load()

        assert loaded == original
        loaded_unit = loaded.work_units[work_unit.work_unit_id]
        # Per-field witnesses: ModeloCode preservation, year/period
        # round-trip, state enum identity, and the content-addressed
        # work_unit_id all survive the encrypted-storage cycle.
        assert loaded_unit.modelo == "303"
        assert loaded_unit.filing_year == 2025
        assert loaded_unit.period == "1T"
        assert loaded_unit.revision_id == "2025-y-siguientes"
        assert loaded_unit.state is WorkUnitState.DRAFT
        assert loaded_unit.work_unit_id == work_unit.work_unit_id
    finally:
        engine.dispose()
        override_master_key_provider(None)
