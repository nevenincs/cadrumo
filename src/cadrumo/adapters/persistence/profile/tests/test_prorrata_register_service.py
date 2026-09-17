"""Persistence integration tests for the cross-period prorrata register service.

See Also:
    :class:`~application.prorrata_register.ProrrataRegisterService`
        Application facade exercised against the encrypted repository.
    :class:`~adapters.persistence.profile.prorrata_register.ProrrataRegisterRepository`
        Real encrypted register repository used by the service tests.
    :class:`~domain.prorrata_register.ProrrataRegisterEntry`
        Strict register row type persisted for carried, authorised, and inicio
        provenance paths.
    :func:`~domain.prorrata_register.resolve_provisional_percentage`
        Single domain precedence ladder delegated to by the service resolver.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.prorrata_register.service import ProrrataRegisterService
from cadrumo.core.modelo import Modelo
from cadrumo.core.prorrata_register import (
    ProrrataEspecialTransitionKind,
    ProrrataProvisionalProvenance,
    ProrrataRegisterRegime,
)
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.calculations.registry.schema_references import RegistrySnapshotRef
from cadrumo.domain.prorrata_register.register import ProrrataEspecialTransitionEvidence, ProrrataRegisterEntry

from .published_authority_support import published_authority_operation

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter, pytest.mark.usefixtures("operation")]


@pytest.fixture
def authority_operation() -> Iterator[PinnedAuthorityOperation]:
    """Lease one published authority generation across each service operation."""
    with bundled_indexed_authority().operation() as operation:
        yield operation


def _prior_registry_snapshot_ref() -> RegistrySnapshotRef:
    return published_authority_operation().snapshot(Modelo("303").value, filing_year=2025, period="4T").snapshot_ref


def test_declare_especial_transition_persists_typed_option(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repository = ProrrataRegisterRepository(objects=profile.repository)
        service = ProrrataRegisterService(repository=repository, operation=authority_operation)
        entry = ProrrataRegisterEntry(
            ejercicio=2026,
            regime=ProrrataRegisterRegime.from_registry("especial"),
            provisional_percentage=Decimal("60"),
            provisional_provenance=ProrrataProvisionalProvenance.from_registry("carried_prior_definitiva"),
            especial_transition=ProrrataEspecialTransitionEvidence(
                kind=ProrrataEspecialTransitionKind.from_registry("opcion"),
                evidence_reference="modelo-303-2026-prorrata-opcion",
            ),
            source_registry_snapshot_refs=(_prior_registry_snapshot_ref(),),
        )

        updated = service.declare_especial_transition(entry)
        loaded = repository.load()

    assert updated == loaded
    persisted = loaded.entry_for(2026)
    assert persisted is not None
    assert persisted.especial_transition is not None
    assert persisted.especial_transition.kind == ProrrataEspecialTransitionKind.from_registry("opcion")
    assert persisted.especial_transition.evidence_reference == "modelo-303-2026-prorrata-opcion"


def test_record_aeat_autorizada_persists_authorised_override(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repository = ProrrataRegisterRepository(objects=profile.repository)
        service = ProrrataRegisterService(repository=repository, operation=authority_operation)
        service.declare(
            ProrrataRegisterEntry(
                ejercicio=2026,
                regime=ProrrataRegisterRegime.from_registry("general"),
                especial_transition=None,
                provisional_percentage=Decimal("80"),
                provisional_provenance=ProrrataProvisionalProvenance.from_registry("carried_prior_definitiva"),
                source_observation_ref="303:2025:4T",
                source_registry_snapshot_refs=(_prior_registry_snapshot_ref(),),
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
    assert entry.regime == ProrrataRegisterRegime.from_registry("general")
    assert entry.provisional_percentage == Decimal("63.5")
    assert entry.provisional_provenance == ProrrataProvisionalProvenance.from_registry("aeat_autorizada")
    assert entry.authorisation_reference == "AEAT-AUTH-2026-0007"
    assert entry.source_observation_ref is None
