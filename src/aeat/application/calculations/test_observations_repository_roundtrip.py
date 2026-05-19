"""Strict roundtrip across the CalculationObservationRepository boundary.

Persists :class:`RegistryModeloObservation` records at
``SensitivityClass.AUDIT`` keyed by ``(modelo, filing_year, period)``.

Anti-tautology: the populated observation carries two
``CasillaObservation`` entries with full provenance (formula_id,
operand_refs, operand_values, legal_refs, source_refs). A
save-drops-grounding regression would surface as inequality on the
loaded observation tuple.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ...adapters.persistence.storage import (
    EphemeralMasterKeyProvider,
)
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...adapters.persistence.storage.sql._orm import Base
from ...adapters.persistence.storage.sql.engine import create_engine_from_settings
from ...core.config import Settings
from ...domain.calculations.registry._bindings import (
    CasillaObservation,
    RegistryModeloObservation,
)
from ._iva_wallet_reconciliation import IvaCompensationReconciliationDecision
from ._observations_repository import CalculationObservationRepository

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


def _populated_observation() -> RegistryModeloObservation:
    return RegistryModeloObservation(
        modelo="303",
        filing_year=2025,
        period="1T",
        observations=(
            CasillaObservation(
                casilla_id="iva.devengado",
                value=Decimal("20000.00"),
                formula_id=None,  # input casilla — no formula
                operand_refs=(),
                operand_values=(),
                legal_refs=("liva.art-21",),
                source_refs=("aeat.iva.2025",),
            ),
            CasillaObservation(
                casilla_id="iva.resultado",
                value=Decimal("12345.67"),
                formula_id="iva.formula.resultado",
                operand_refs=("iva.devengado", "iva.deducible"),
                operand_values=(Decimal("20000.00"), Decimal("7654.33")),
                legal_refs=("liva.art-94",),
                source_refs=("aeat.iva.2025",),
            ),
        ),
    )


def test_calculation_observation_survives_encrypted_storage_roundtrip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A RegistryModeloObservation roundtrips through the encrypted observation repo."""

    provider = EphemeralMasterKeyProvider()
    with provider:
        db_path = tmp_path / "observations-roundtrip.db"
        monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
        engine = create_engine_from_settings(
            Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"),
        )
        Base.metadata.create_all(engine)
        try:
            SecureObjectRepository(engine=engine)

            original = _populated_observation()
            # Non-default source_kind: the audit-sink path that pulls
            # from the AEAT justificante.
            captured_at = datetime.now(UTC).replace(microsecond=0)
            repo = CalculationObservationRepository()
            repo.save(
                original,
                source_kind="aeat_sede_justificante",
                captured_at=captured_at,
            )
            loaded = repo.load("303", 2025, "1T")

            assert loaded is not None
            # The envelope carries observation + metadata; pin both layers.
            assert loaded.observation == original
            assert loaded.source_kind == "aeat_sede_justificante"
            assert loaded.captured_at == captured_at
            # Per-field witnesses on the typed observation tuple:
            # formula_id on the computed casilla, operand_refs +
            # operand_values, legal_refs + source_refs.
            assert len(loaded.observation.observations) == 2
            loaded_computed = loaded.observation.observations[1]
            assert loaded_computed.formula_id == "iva.formula.resultado"
            assert loaded_computed.operand_refs == ("iva.devengado", "iva.deducible")
            assert loaded_computed.operand_values == (
                Decimal("20000.00"),
                Decimal("7654.33"),
            )
            assert loaded_computed.legal_refs == ("liva.art-94",)
        finally:
            engine.dispose()


def test_calculation_observation_dropped_legal_refs_surfaces_at_load(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Anti-tautology proof: deleting ``legal_refs`` on a casilla must surface.

    The whole point of persisting :class:`RegistryModeloObservation` is
    the regulatory grounding (legal_refs, source_refs, formula_id) it
    carries through the AUDIT-class boundary. A save-drops-grounding
    drift is the highest-stakes regression this codebase can have: a
    persisted observation with no legal_refs would silently feed
    unsupported numbers into amendment / verification flows.

    Persists a populated observation, reaches into ``SecureObjectRow``
    via ``session_scope``, surgically deletes the ``legal_refs`` tuple
    from one casilla in the encrypted JSON envelope, and asserts the
    load path catches the drift (either ValidationError on the typed
    record's min_length=1 invariant, or strict inequality on the
    loaded observation).
    """

    import json as _json

    from sqlalchemy import select

    from ...adapters.persistence.storage.sql._orm import SecureObjectRow
    from ...adapters.persistence.storage.sql.session import session_scope
    from ._observations_repository import _OBSERVATION_NAMESPACE, observation_key

    provider = EphemeralMasterKeyProvider()
    with provider:
        db_path = tmp_path / "observations-anti-tautology.db"
        monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
        engine = create_engine_from_settings(
            Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"),
        )
        Base.metadata.create_all(engine)
        try:
            SecureObjectRepository(engine=engine)

            original = _populated_observation()
            captured_at = datetime.now(UTC).replace(microsecond=0)
            repo = CalculationObservationRepository()
            repo.save(
                original,
                source_kind="aeat_sede_justificante",
                captured_at=captured_at,
            )

            object_key = observation_key("303", 2025, "1T")
            with session_scope(engine) as session:
                stmt = select(SecureObjectRow).where(
                    SecureObjectRow.namespace == _OBSERVATION_NAMESPACE,
                    SecureObjectRow.object_key == object_key,
                )
                row = session.execute(stmt).scalar_one()
                envelope = _json.loads(row.payload.decode("utf-8"))
                # The envelope wraps the observation under "payload"; the
                # observation itself nests the casillas under
                # "observation" -> "observations".
                casillas = envelope["payload"]["observation"]["observations"]
                assert casillas and casillas[1]["legal_refs"], (
                    "fixture must serialise legal_refs onto the computed "
                    "casilla for this proof test to be meaningful"
                )
                casillas[1]["legal_refs"] = []
                row.payload = _json.dumps(envelope).encode("utf-8")

            # Reload. Whether the model_validator on CasillaObservation
            # tolerates an empty legal_refs tuple or the load path surfaces
            # the dropped grounding as inequality, the boundary must catch
            # the drift somewhere.
            loaded = repo.load("303", 2025, "1T")
            assert loaded is not None
            assert loaded.observation != original, (
                "anti-tautology proof failed: deleting legal_refs from a "
                "persisted casilla did NOT surface as strict inequality "
                "on the loaded observation. The grounding boundary is "
                "tautological and every observation roundtrip in the "
                "suite is suspect."
            )
        finally:
            engine.dispose()


def test_iva_wallet_reconciliation_decision_survives_encrypted_storage_roundtrip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An IVA wallet reconciliation decision round-trips as AUDIT state."""

    provider = EphemeralMasterKeyProvider()
    with provider:
        db_path = tmp_path / "iva-wallet-decision-roundtrip.db"
        monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
        engine = create_engine_from_settings(
            Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"),
        )
        Base.metadata.create_all(engine)
        try:
            SecureObjectRepository(engine=engine)
            repo = CalculationObservationRepository()
            decided_at = datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC)
            decision = IvaCompensationReconciliationDecision(
                taxpayer_nif="12345678Z",
                target_year=2026,
                target_period="2T",
                selected_authority="aeat_wallet",
                selected_amount=Decimal("1200"),
                wallet_amount=Decimal("1200"),
                local_recurrence_amount=Decimal("1200"),
                override_amount=None,
                divergence="match",
                blocked=False,
                stale_wallet=False,
                reason="Using latest valid AEAT wallet observation for Modelo 303 prior compensation.",
                wallet_captured_at=decided_at,
                decided_at=decided_at,
            )

            repo.save_iva_wallet_decision(decision)
            loaded = repo.load_iva_wallet_decision("12345678Z", 2026, "2T")

            assert loaded == decision
            assert loaded is not None
            assert loaded.selected_authority == "aeat_wallet"
            assert loaded.selected_amount == Decimal("1200")
            assert loaded.blocked is False
        finally:
            engine.dispose()
