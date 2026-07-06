"""Application-service tests for the cross-period prorrata register."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from aeat.adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from aeat.application.prorrata_register import ProrrataRegisterService
from aeat.core import ProrrataProvisionalProvenance, ProrrataRegisterRegime
from aeat.domain.prorrata_register import ProrrataRegisterEntry
from aeat.tests.secure_sql import isolated_runtime_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_record_aeat_autorizada_persists_authorised_override(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repository = ProrrataRegisterRepository(objects=profile.repository)
        service = ProrrataRegisterService(repository=repository)
        service.declare(
            ProrrataRegisterEntry(
                ejercicio=2026,
                regime=ProrrataRegisterRegime.GENERAL,
                provisional_percentage=Decimal("80"),
                provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
                source_observation_ref="303:2025:4T",
            ),
        )

        updated = service.record_aeat_autorizada(
            ejercicio=2026,
            provisional_percentage=Decimal("63.5"),
            authorisation_reference="AEAT-AUTH-2026-0007",
        )
        loaded = repository.load()

    assert updated == loaded
    assert len(loaded.entries) == 1
    entry = loaded.entry_for(2026)
    assert entry is not None
    assert entry.regime is ProrrataRegisterRegime.GENERAL
    assert entry.provisional_percentage == Decimal("63.5")
    assert entry.provisional_provenance is ProrrataProvisionalProvenance.AEAT_AUTORIZADA
    assert entry.authorisation_reference == "AEAT-AUTH-2026-0007"
    assert entry.source_observation_ref is None


def test_record_aeat_autorizada_preserves_sector_and_regime(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repository = ProrrataRegisterRepository(objects=profile.repository)
        service = ProrrataRegisterService(repository=repository)

        updated = service.record_aeat_autorizada(
            ejercicio=2026,
            provisional_percentage=Decimal("58"),
            authorisation_reference="AEAT-AUTH-2026-SECTOR-02",
            sector_id="arrendamiento",
            regime=ProrrataRegisterRegime.ESPECIAL,
        )

    entry = updated.entry_for(2026, sector_id="arrendamiento")
    assert entry is not None
    assert entry.regime is ProrrataRegisterRegime.ESPECIAL
    assert entry.provisional_percentage == Decimal("58")
    assert entry.provisional_provenance is ProrrataProvisionalProvenance.AEAT_AUTORIZADA
    assert entry.authorisation_reference == "AEAT-AUTH-2026-SECTOR-02"
