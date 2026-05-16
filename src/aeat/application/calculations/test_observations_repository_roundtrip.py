"""Strict roundtrip across the CalculationObservationRepository boundary.

Persists :class:`RegistryFilingObservation` records at
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
    override_master_key_provider,
)
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...adapters.persistence.storage.sql._orm import Base
from ...adapters.persistence.storage.sql.engine import create_engine_from_settings
from ...core.config import Settings
from ...domain.calculations.registry._bindings import (
    CasillaObservation,
    RegistryFilingObservation,
)
from ._observations_repository import CalculationObservationRepository

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


def _populated_observation() -> RegistryFilingObservation:
    return RegistryFilingObservation(
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
    """A RegistryFilingObservation roundtrips through the encrypted observation repo."""

    provider = EphemeralMasterKeyProvider()
    override_master_key_provider(provider)
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
        override_master_key_provider(None)
