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
    """Build a typed WorkUnit using **non-default** values everywhere possible.

    Every field defaulting to a value (state=DRAFT, discarded_at=None,
    discarded_by=None, discard_reason=None) is overridden with a real
    non-default value. This is the anti-tautology safeguard: if any
    boundary silently drops a field and the load side re-defaults it,
    the roundtrip equality would still hold under default-only
    fixtures. Forcing every defaultable field to a distinct sentinel
    makes a drop-and-redefault regression visible.
    """

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
        # Non-default lifecycle state so a save-drops-state regression
        # would surface as state mismatch on load (default is DRAFT).
        state=WorkUnitState.DISCARDED,
        # Discard metadata is required when state is DISCARDED;
        # populating it covers all three defaultable optional fields
        # at once.
        discarded_at=now,
        discarded_by="cli/aeat",
        discard_reason="superseded by amended revision for roundtrip test fixture",
        # Census-stale marker pair — defaults to (None, None). Without
        # non-default fixture values, a save-drops-field regression on
        # either side would still pass strict equality. Stamp at
        # created_at so the validator's not-before invariant holds.
        census_stamped_stale_at=now,
        census_stale_reason="census apply snapshot abc123 superseded prior facts",
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
        # round-trip, state enum identity, content-addressed
        # work_unit_id, and the discard metadata triple (which were
        # the test's main anti-tautology guard — every defaultable
        # field carries a real non-default value).
        assert loaded_unit.modelo == "303"
        assert loaded_unit.filing_year == 2025
        assert loaded_unit.period == "1T"
        assert loaded_unit.revision_id == "2025-y-siguientes"
        assert loaded_unit.state is WorkUnitState.DISCARDED
        assert loaded_unit.work_unit_id == work_unit.work_unit_id
        # Discard metadata survives the cycle; a regression that
        # dropped any of these three on save would leave them as
        # None on load and fail the strict-equality check above,
        # but also fail these explicit witnesses.
        assert loaded_unit.discarded_at == work_unit.discarded_at
        assert loaded_unit.discarded_by == "cli/aeat"
        assert loaded_unit.discard_reason is not None
        assert "superseded" in loaded_unit.discard_reason
        # Census-stale marker pair survives — protects against the
        # save-drops / load-re-defaults regression on either field.
        assert loaded_unit.census_stamped_stale_at == work_unit.census_stamped_stale_at
        assert loaded_unit.census_stale_reason is not None
        assert "snapshot abc123" in loaded_unit.census_stale_reason
    finally:
        engine.dispose()
        override_master_key_provider(None)


def test_work_unit_catalogue_lifecycle_drift_surfaces_at_load(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Anti-tautology proof: flipping DISCARDED to DRAFT while retaining metadata must surface.

    :class:`WorkUnit` enforces a lifecycle invariant:
    DRAFT work units must NOT carry discard metadata; DISCARDED ones
    MUST. The catalogue also enforces that the dict key equals the
    work unit's content-addressed work_unit_id.

    Persists a DISCARDED work unit (with discard metadata populated),
    reaches into ``SecureObjectRow`` via ``session_scope``, surgically
    flips the persisted ``state`` from ``"discarded"`` back to
    ``"draft"`` without clearing the discard metadata, and asserts
    the load path catches the drift via the model_validator's
    DRAFT-must-not-carry-discard-metadata check.

    If this test ever passes silently with the flipped state, the
    work-unit catalogue boundary is tautological and the lifecycle
    state machine is not actually enforced post-persistence.
    """

    import json as _json

    from sqlalchemy import select

    from ...adapters.persistence.storage.sql._orm import SecureObjectRow
    from ...adapters.persistence.storage.sql.session import session_scope
    from ._repository import _WORK_UNIT_NAMESPACE, _WORK_UNIT_OBJECT_KEY

    provider = EphemeralMasterKeyProvider()
    override_master_key_provider(provider)
    db_path = tmp_path / "work-unit-anti-tautology.db"
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    engine = create_engine_from_settings(
        Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"),
    )
    Base.metadata.create_all(engine)
    try:
        SecureObjectRepository(engine=engine)
        work_unit = _populated_work_unit()
        catalogue = WorkUnitCatalogue(work_units={work_unit.work_unit_id: work_unit})
        repo = WorkUnitCatalogueRepository()
        repo.save(catalogue)

        with session_scope(engine) as session:
            stmt = select(SecureObjectRow).where(
                SecureObjectRow.namespace == _WORK_UNIT_NAMESPACE,
                SecureObjectRow.object_key == _WORK_UNIT_OBJECT_KEY,
            )
            row = session.execute(stmt).scalar_one()
            envelope = _json.loads(row.payload.decode("utf-8"))
            work_units = envelope["payload"]["work_units"]
            unit_dict = work_units[work_unit.work_unit_id]
            assert unit_dict["state"] == "discarded", (
                "fixture must serialise state as 'discarded' for this "
                "proof test to be meaningful"
            )
            # Flip state back to draft while leaving discard metadata
            # in place. The DRAFT invariant must trip on load.
            unit_dict["state"] = "draft"
            row.payload = _json.dumps(envelope).encode("utf-8")

        regression_caught = False
        try:
            repo.load()
        except Exception:  # noqa: BLE001 - boundary may raise different types
            regression_caught = True
        assert regression_caught, (
            "anti-tautology proof failed: flipping state from "
            "DISCARDED to DRAFT while retaining discard metadata did "
            "NOT surface on load. The work-unit catalogue boundary "
            "is tautological and the lifecycle state machine is not "
            "actually enforced post-persistence."
        )
    finally:
        engine.dispose()
        override_master_key_provider(None)
