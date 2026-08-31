"""Application-service tests for the cross-period prorrata register.

See Also:
    :class:`~application.prorrata_register.ProrrataRegisterService`
        Facade under test for recording art. 105.Dos/Tres overrides and
        resolving the in-force provisional percentage.
    :class:`~adapters.persistence.profile.prorrata_register.ProrrataRegisterRepository`
        Real encrypted register repository used by the service tests.
    :class:`~domain.prorrata_register.ProrrataRegisterEntry`
        Strict register row type persisted for carried, authorised, and inicio
        provenance paths.
    :func:`~domain.prorrata_register.resolve_provisional_percentage`
        Single domain precedence ladder delegated to by the service resolver.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from ....core.prorrata_register import (
    ProrrataEspecialTransitionKind,
    ProrrataProvisionalProvenance,
    ProrrataRegisterRegime,
)
from ....domain.prorrata_register import ProrrataEspecialTransitionEvidence, ProrrataRegisterEntry
from ....tests.secure_sql import isolated_runtime_profile
from .. import ProrrataRegisterService

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_declare_especial_transition_persists_typed_option(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repository = ProrrataRegisterRepository(objects=profile.repository)
        service = ProrrataRegisterService(repository=repository)
        entry = ProrrataRegisterEntry(
            ejercicio=2026,
            regime=ProrrataRegisterRegime.ESPECIAL,
            provisional_percentage=Decimal("60"),
            provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
            especial_transition=ProrrataEspecialTransitionEvidence(
                kind=ProrrataEspecialTransitionKind.OPCION,
                evidence_reference="modelo-303-2026-prorrata-opcion",
            ),
        )

        updated = service.declare_especial_transition(entry)
        loaded = repository.load()

    assert updated == loaded
    persisted = loaded.entry_for(2026)
    assert persisted is not None
    assert persisted.especial_transition is not None
    assert persisted.especial_transition.kind is ProrrataEspecialTransitionKind.OPCION
    assert persisted.especial_transition.evidence_reference == "modelo-303-2026-prorrata-opcion"


def test_record_aeat_autorizada_persists_authorised_override(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repository = ProrrataRegisterRepository(objects=profile.repository)
        service = ProrrataRegisterService(repository=repository)
        service.declare(
            ProrrataRegisterEntry(
                ejercicio=2026,
                regime=ProrrataRegisterRegime.GENERAL,
                especial_transition=None,
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


def test_record_inicio_actividad_persists_proposed_override(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repository = ProrrataRegisterRepository(objects=profile.repository)
        service = ProrrataRegisterService(repository=repository)
        service.declare(
            ProrrataRegisterEntry(
                ejercicio=2026,
                regime=ProrrataRegisterRegime.GENERAL,
                especial_transition=None,
                provisional_percentage=Decimal("80"),
                provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
                source_observation_ref="303:2025:4T",
            ),
        )

        updated = service.record_inicio_actividad(
            ejercicio=2026,
            provisional_percentage=Decimal("55"),
            proposal_reference="INICIO-036-2026-0003",
        )
        loaded = repository.load()

    assert updated == loaded
    assert len(loaded.entries) == 1
    entry = loaded.entry_for(2026)
    assert entry is not None
    assert entry.regime is ProrrataRegisterRegime.GENERAL
    assert entry.provisional_percentage == Decimal("55")
    assert entry.provisional_provenance is ProrrataProvisionalProvenance.INICIO_ACTIVIDAD
    assert entry.authorisation_reference == "INICIO-036-2026-0003"
    assert entry.source_observation_ref is None


def test_record_inicio_actividad_preserves_sector_and_regime(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repository = ProrrataRegisterRepository(objects=profile.repository)
        service = ProrrataRegisterService(repository=repository)

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


def test_resolve_provisional_uses_ladder_for_authorised_candidate(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repository = ProrrataRegisterRepository(objects=profile.repository)
        service = ProrrataRegisterService(repository=repository)
        service.declare(
            ProrrataRegisterEntry(
                ejercicio=2026,
                regime=ProrrataRegisterRegime.GENERAL,
                especial_transition=None,
                provisional_percentage=Decimal("80"),
                provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
                source_observation_ref="303:2025:4T",
            ),
        )
        authorised = ProrrataRegisterEntry(
            ejercicio=2026,
            regime=ProrrataRegisterRegime.GENERAL,
            especial_transition=None,
            provisional_percentage=Decimal("63"),
            provisional_provenance=ProrrataProvisionalProvenance.AEAT_AUTORIZADA,
            authorisation_reference="AEAT-AUTH-2026-0009",
        )

        resolution = service.resolve_provisional(2026, candidate_entries=(authorised,))

    assert resolution.resolved
    assert resolution.percentage == Decimal("63")
    assert resolution.provenance is ProrrataProvisionalProvenance.AEAT_AUTORIZADA


def test_resolve_provisional_uses_ladder_for_inicio_candidate(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repository = ProrrataRegisterRepository(objects=profile.repository)
        service = ProrrataRegisterService(repository=repository)
        service.declare(
            ProrrataRegisterEntry(
                ejercicio=2026,
                regime=ProrrataRegisterRegime.GENERAL,
                especial_transition=None,
                provisional_percentage=Decimal("80"),
                provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
                source_observation_ref="303:2025:4T",
            ),
        )
        inicio = ProrrataRegisterEntry(
            ejercicio=2026,
            regime=ProrrataRegisterRegime.GENERAL,
            especial_transition=None,
            provisional_percentage=Decimal("55"),
            provisional_provenance=ProrrataProvisionalProvenance.INICIO_ACTIVIDAD,
            authorisation_reference="INICIO-036-2026-0005",
        )

        resolution = service.resolve_provisional(2026, candidate_entries=(inicio,))

    assert resolution.resolved
    assert resolution.percentage == Decimal("55")
    assert resolution.provenance is ProrrataProvisionalProvenance.INICIO_ACTIVIDAD


def test_resolve_provisional_filters_candidates_to_requested_sector(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repository = ProrrataRegisterRepository(objects=profile.repository)
        service = ProrrataRegisterService(repository=repository)
        service.declare(
            ProrrataRegisterEntry(
                ejercicio=2026,
                regime=ProrrataRegisterRegime.GENERAL,
                especial_transition=None,
                sector_id="comercio",
                provisional_percentage=Decimal("80"),
                provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
                source_observation_ref="303:2025:4T",
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
        )

        resolution = service.resolve_provisional(
            2026,
            sector_id="comercio",
            candidate_entries=(other_sector,),
        )

    assert resolution.resolved
    assert resolution.percentage == Decimal("80")
    assert resolution.provenance is ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA
