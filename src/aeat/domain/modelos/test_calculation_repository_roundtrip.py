"""Strict roundtrip across the encrypted CalculationRevisionCatalogueRepository.

Persists :class:`CalculationRevisionCatalogue` under
``aeat.domain.modelos.calculation_revisions`` at
``SensitivityClass.FINANCIAL``.

The calculation-revision catalogue is the FINANCIAL-class encrypted
boundary that carries formula provenance. ``CalculationRevision.observations``
defaults to ``()``; a save-drops-field regression on that typed envelope
is invisible unless a roundtrip fixture populates it with real
:class:`CasillaObservation` entries carrying ``legal_refs`` / ``source_refs``.

The fixture below populates EVERY defaultable field with a non-default
value: a non-default lifecycle state (``VERIFICADO_COMPLETO`` with the
required audit triple), populated ``inputs_snapshot`` / ``binding_overrides``
/ ``casilla_values``, populated ``source_transaction_ids``, and a populated
``observations`` tuple. The anti-tautology proof mutates the on-disk
encrypted JSON to drop the ``observations`` field and asserts the boundary
surfaces the regression rather than silently re-defaulting to ``()``.
"""

from __future__ import annotations

import json as _json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select

from ...adapters.persistence.storage import EphemeralMasterKeyProvider
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...adapters.persistence.storage.sql._orm import Base, SecureObjectRow
from ...adapters.persistence.storage.sql.engine import create_engine_from_settings
from ...adapters.persistence.storage.sql.session import session_scope
from ...core.config import Settings
from ..calculations.registry._bindings import CasillaObservation
from ._calculation_repository import (
    _CALCULATION_NAMESPACE,
    _CALCULATION_OBJECT_KEY,
    CalculationRevisionCatalogueRepository,
)
from ._calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    derive_calculation_revision_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


def _hex(seed: str) -> str:
    """Return a stable 64-char hex blob for typed-id fixture values."""

    base = seed * 64
    return base[:64]


def _populated_catalogue() -> CalculationRevisionCatalogue:
    """Build a catalogue whose every defaultable field is non-default.

    The single revision is in ``VERIFICADO_COMPLETO`` state (not the
    default ``BORRADOR``), carries populated inputs / overrides /
    casilla values / source transactions, and a populated
    ``observations`` tuple with two :class:`CasillaObservation`
    entries carrying real ``legal_refs`` / ``source_refs`` provenance.
    """

    work_unit_id = _hex("a")
    created_at = datetime(2024, 7, 1, 9, 0, 0, tzinfo=UTC)
    verified_at = created_at + timedelta(hours=3)

    inputs_snapshot = {"iva.base-imponible": "1000.00"}
    binding_overrides = {"modelo-303-compensacion-pendiente-anteriores": "50.00"}
    casilla_values = {"casilla-01": Decimal("1000.00"), "casilla-12": Decimal("210.00")}
    source_transaction_ids = (_hex("d"), _hex("e"))

    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        inputs_snapshot=inputs_snapshot,
        binding_overrides=binding_overrides,
        casilla_values=casilla_values,
        source_transaction_ids=source_transaction_ids,
    )

    observations = (
        CasillaObservation(
            casilla_id="casilla-01",
            value=Decimal("1000.00"),
            formula_id=None,
            operand_refs=(),
            operand_values=(),
            legal_refs=("Ley 37/1992 art. 78",),
            source_refs=("aeat-modelo-303-instrucciones-2024",),
        ),
        CasillaObservation(
            casilla_id="casilla-12",
            value=Decimal("210.00"),
            formula_id="iva-cuota-devengada-general",
            operand_refs=("casilla-01",),
            operand_values=(Decimal("1000.00"),),
            legal_refs=("Ley 37/1992 art. 90",),
            source_refs=("aeat-modelo-303-instrucciones-2024",),
        ),
    )

    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        inputs_snapshot=inputs_snapshot,
        binding_overrides=binding_overrides,
        source_transaction_ids=source_transaction_ids,
        casilla_values=casilla_values,
        observations=observations,
        created_at=created_at,
        updated_at=verified_at,
        verified_at=verified_at,
        verified_by="aeat.cli.modelo.verify",
    )
    return CalculationRevisionCatalogue(revisions={revision_id: revision})


def test_calculation_revision_catalogue_survives_encrypted_storage_roundtrip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fully-populated calculation revision round-trips through encrypted SQL."""

    provider = EphemeralMasterKeyProvider()
    with provider:
        db_path = tmp_path / "calculation-revisions-roundtrip.db"
        monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
        engine = create_engine_from_settings(
            Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"),
        )
        Base.metadata.create_all(engine)
        try:
            SecureObjectRepository(engine=engine)

            repo = CalculationRevisionCatalogueRepository()
            original = _populated_catalogue()
            repo.save(original)
            loaded = repo.load()

            assert loaded == original
            assert len(loaded.revisions) == 1
            (revision,) = loaded.values()
            assert revision.state is CalculationRevisionState.VERIFICADO_COMPLETO
            # The typed observations envelope must survive the boundary
            # with its full formula provenance intact.
            assert len(revision.observations) == 2
            computed = next(o for o in revision.observations if o.formula_id is not None)
            assert computed.formula_id == "iva-cuota-devengada-general"
            assert computed.operand_refs == ("casilla-01",)
            assert computed.legal_refs == ("Ley 37/1992 art. 90",)
            assert computed.source_refs == ("aeat-modelo-303-instrucciones-2024",)
        finally:
            engine.dispose()


def test_calculation_revision_catalogue_dropped_observations_surfaces_at_load(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Anti-tautology proof: dropping ``observations`` on disk must surface.

    Persists a revision carrying two :class:`CasillaObservation`
    entries, then surgically deletes the ``observations`` key from the
    encrypted JSON envelope. ``observations`` defaults to ``()`` on the
    model, so a naive load would silently re-default and return a
    catalogue that compares unequal to the original. The proof asserts
    the regression surfaces either as a ValidationError or as strict
    inequality on the loaded catalogue.

    If this test passes silently with the field dropped, the
    calculation-revision boundary is tautological and every roundtrip
    in the suite is suspect.
    """

    provider = EphemeralMasterKeyProvider()
    with provider:
        db_path = tmp_path / "calculation-revisions-anti-tautology.db"
        monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
        engine = create_engine_from_settings(
            Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"),
        )
        Base.metadata.create_all(engine)
        try:
            SecureObjectRepository(engine=engine)

            repo = CalculationRevisionCatalogueRepository()
            original = _populated_catalogue()
            repo.save(original)

            with session_scope(engine) as session:
                stmt = select(SecureObjectRow).where(
                    SecureObjectRow.namespace == _CALCULATION_NAMESPACE,
                    SecureObjectRow.object_key == _CALCULATION_OBJECT_KEY,
                )
                row = session.execute(stmt).scalar_one()
                envelope = _json.loads(row.payload.decode("utf-8"))
                revisions = envelope["payload"]["revisions"]
                ((_revision_id, record),) = revisions.items()
                # Drop the typed provenance envelope from the on-disk
                # payload. A save-drops-field regression looks exactly
                # like this: the key is simply absent on reload.
                assert "observations" in record, (
                    "fixture must persist observations for the proof to be meaningful"
                )
                del record["observations"]
                row.payload = _json.dumps(envelope).encode("utf-8")

            regression_caught = False
            try:
                mutated = repo.load()
            except Exception:  # noqa: BLE001 - boundary may raise different types
                regression_caught = True
            else:
                if mutated != original:
                    regression_caught = True
            assert regression_caught, (
                "anti-tautology proof failed: dropping the observations "
                "envelope did NOT surface on load. The calculation-revision "
                "boundary is tautological and every roundtrip in the suite "
                "is suspect."
            )
        finally:
            engine.dispose()
