"""Application-policy tests for the cross-period prorrata register service.

These tests exercise the service facade through its application-owned repository
protocol.  The fake keeps register state in memory so the assertions cover
override construction, sector selection, and the domain precedence ladder
without reaching encrypted persistence.  Repository round-trip behavior lives
with the profile-persistence adapter tests.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from dev.registry.compiler.authority import compiled_bundled_authority

from cadrumo.core.modelo import Modelo
from cadrumo.core.prorrata_register import ProrrataProvisionalProvenance, ProrrataRegisterRegime
from cadrumo.domain.calculations.registry.schema_references import RegistrySnapshotRef
from cadrumo.domain.prorrata_register.register import ProrrataRegister, ProrrataRegisterEntry

from ..service import ProrrataRegisterService

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _InMemoryProrrataRegisterRepository:
    """Deterministic inward fake for the required register capability."""

    def __init__(self) -> None:
        self._register = ProrrataRegister()

    @property
    def bucket_id(self) -> str:
        return "prorrata-register-policy-test"

    def load(self) -> ProrrataRegister:
        return self._register

    def upsert_entry(self, entry: ProrrataRegisterEntry) -> ProrrataRegister:
        retained = tuple(
            existing
            for existing in self._register.entries
            if (existing.ejercicio, existing.sector_id) != (entry.ejercicio, entry.sector_id)
        )
        self._register = ProrrataRegister(
            entries=(*retained, entry),
            sector_definitions=self._register.sector_definitions,
            activity_rows=self._register.activity_rows,
        )
        return self._register


def _service() -> ProrrataRegisterService:
    return ProrrataRegisterService(repository=_InMemoryProrrataRegisterRepository())


def _prior_registry_snapshot_ref() -> RegistrySnapshotRef:
    return compiled_bundled_authority().snapshot(Modelo("303").value, filing_year=2025, period="4T").snapshot_ref


def test_record_aeat_autorizada_preserves_sector_and_regime() -> None:
    service = _service()

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


def test_record_inicio_actividad_preserves_sector_and_regime() -> None:
    service = _service()

    updated = service.record_inicio_actividad(
        ejercicio=2026,
        provisional_percentage=Decimal("52"),
        proposal_reference="INICIO-036-2026-SECTOR-04",
        sector_id="formacion",
        regime=ProrrataRegisterRegime.ESPECIAL,
    )

    entry = updated.entry_for(2026, sector_id="formacion")
    assert entry is not None
    assert entry.regime is ProrrataRegisterRegime.ESPECIAL
    assert entry.provisional_percentage == Decimal("52")
    assert entry.provisional_provenance is ProrrataProvisionalProvenance.INICIO_ACTIVIDAD
    assert entry.authorisation_reference == "INICIO-036-2026-SECTOR-04"


def test_resolve_provisional_uses_ladder_for_authorised_candidate() -> None:
    service = _service()
    service.declare(
        ProrrataRegisterEntry(
            ejercicio=2026,
            regime=ProrrataRegisterRegime.GENERAL,
            especial_transition=None,
            provisional_percentage=Decimal("80"),
            provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
            source_observation_ref="303:2025:4T",
            source_registry_snapshot_refs=(_prior_registry_snapshot_ref(),),
        ),
    )
    authorised = ProrrataRegisterEntry(
        ejercicio=2026,
        regime=ProrrataRegisterRegime.GENERAL,
        especial_transition=None,
        provisional_percentage=Decimal("63"),
        provisional_provenance=ProrrataProvisionalProvenance.AEAT_AUTORIZADA,
        authorisation_reference="AEAT-AUTH-2026-0009",
        source_registry_snapshot_refs=(),
    )

    resolution = service.resolve_provisional(2026, candidate_entries=(authorised,))

    assert resolution.resolved
    assert resolution.percentage == Decimal("63")
    assert resolution.provenance is ProrrataProvisionalProvenance.AEAT_AUTORIZADA


def test_resolve_provisional_uses_ladder_for_inicio_candidate() -> None:
    service = _service()
    service.declare(
        ProrrataRegisterEntry(
            ejercicio=2026,
            regime=ProrrataRegisterRegime.GENERAL,
            especial_transition=None,
            provisional_percentage=Decimal("80"),
            provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
            source_observation_ref="303:2025:4T",
            source_registry_snapshot_refs=(_prior_registry_snapshot_ref(),),
        ),
    )
    inicio = ProrrataRegisterEntry(
        ejercicio=2026,
        regime=ProrrataRegisterRegime.GENERAL,
        especial_transition=None,
        provisional_percentage=Decimal("55"),
        provisional_provenance=ProrrataProvisionalProvenance.INICIO_ACTIVIDAD,
        authorisation_reference="INICIO-036-2026-0005",
        source_registry_snapshot_refs=(),
    )

    resolution = service.resolve_provisional(2026, candidate_entries=(inicio,))

    assert resolution.resolved
    assert resolution.percentage == Decimal("55")
    assert resolution.provenance is ProrrataProvisionalProvenance.INICIO_ACTIVIDAD


def test_resolve_provisional_filters_candidates_to_requested_sector() -> None:
    service = _service()
    service.declare(
        ProrrataRegisterEntry(
            ejercicio=2026,
            regime=ProrrataRegisterRegime.GENERAL,
            especial_transition=None,
            sector_id="comercio",
            provisional_percentage=Decimal("80"),
            provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
            source_observation_ref="303:2025:4T",
            source_registry_snapshot_refs=(_prior_registry_snapshot_ref(),),
        ),
    )
    other_sector = ProrrataRegisterEntry(
        ejercicio=2026,
        regime=ProrrataRegisterRegime.GENERAL,
        especial_transition=None,
        sector_id="arrendamiento",
        provisional_percentage=Decimal("63"),
        provisional_provenance=ProrrataProvisionalProvenance.AEAT_AUTORIZADA,
        authorisation_reference="AEAT-AUTH-2026-0010",
        source_registry_snapshot_refs=(),
    )

    resolution = service.resolve_provisional(
        2026,
        sector_id="comercio",
        candidate_entries=(other_sector,),
    )

    assert resolution.resolved
    assert resolution.percentage == Decimal("80")
    assert resolution.provenance is ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA
