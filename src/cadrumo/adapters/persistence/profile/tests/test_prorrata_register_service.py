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
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.schema_references import RegistrySnapshotRef
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.domain.prorrata_register.register import ProrrataEspecialTransitionEvidence, ProrrataRegisterEntry

from .....application.prorrata_register.tests.provisional_override import record_aeat_autorizada
from .published_authority_support import published_authority_operation

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter, pytest.mark.usefixtures("operation")]

_EJERCICIO = filing_year_envelope().horizon


def _prior_registry_snapshot_ref() -> RegistrySnapshotRef:
    return (
        published_authority_operation()
        .snapshot(Modelo("303").value, filing_year=_EJERCICIO - 1, period="4T")
        .snapshot_ref
    )


def test_declare_especial_transition_persists_typed_option(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repository = ProrrataRegisterRepository(objects=profile.repository)
        service = ProrrataRegisterService(repository=repository, operation=authority_operation)
        entry = ProrrataRegisterEntry(
            ejercicio=_EJERCICIO,
            regime=ProrrataRegisterRegime.from_registry("especial"),
            provisional_percentage=Decimal("60"),
            provisional_provenance=ProrrataProvisionalProvenance.from_registry("carried_prior_definitiva"),
            especial_transition=ProrrataEspecialTransitionEvidence(
                kind=ProrrataEspecialTransitionKind.from_registry("opcion"),
                evidence_reference=f"modelo-303-{_EJERCICIO}-prorrata-opcion",
            ),
            source_registry_snapshot_refs=(_prior_registry_snapshot_ref(),),
        )

        updated = service.declare_especial_transition(entry)
        loaded = repository.load()

    assert updated == loaded
    persisted = loaded.entry_for(_EJERCICIO)
    assert persisted is not None
    assert persisted.especial_transition is not None
    assert persisted.especial_transition.kind == ProrrataEspecialTransitionKind.from_registry("opcion")
    assert persisted.especial_transition.evidence_reference == f"modelo-303-{_EJERCICIO}-prorrata-opcion"


def test_record_aeat_autorizada_persists_authorised_override(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repository = ProrrataRegisterRepository(objects=profile.repository)
        service = ProrrataRegisterService(repository=repository, operation=authority_operation)
        service.declare(
            ProrrataRegisterEntry(
                ejercicio=_EJERCICIO,
                regime=ProrrataRegisterRegime.from_registry("general"),
                especial_transition=None,
                provisional_percentage=Decimal("80"),
                provisional_provenance=ProrrataProvisionalProvenance.from_registry("carried_prior_definitiva"),
                source_observation_ref=f"303:{_EJERCICIO - 1}:4T",
                source_registry_snapshot_refs=(_prior_registry_snapshot_ref(),),
            ),
        )

        updated = record_aeat_autorizada(
            service,
            ejercicio=_EJERCICIO,
            provisional_percentage=Decimal("63.5"),
            authorisation_reference=f"AEAT-AUTH-{_EJERCICIO}-0007",
        )
        loaded = repository.load()

    assert updated == loaded
    assert len(loaded.entries) == 1
    entry = loaded.entry_for(_EJERCICIO)
    assert entry is not None
    assert entry.regime == ProrrataRegisterRegime.from_registry("general")
    assert entry.provisional_percentage == Decimal("63.5")
    assert entry.provisional_provenance == ProrrataProvisionalProvenance.from_registry("aeat_autorizada")
    assert entry.authorisation_reference == f"AEAT-AUTH-{_EJERCICIO}-0007"
    assert entry.source_observation_ref is None
