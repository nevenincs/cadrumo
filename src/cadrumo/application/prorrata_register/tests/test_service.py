"""Application-policy tests for the cross-period prorrata register service.

These tests exercise the service facade through its application-owned repository
protocol.  The fake keeps register state in memory so the assertions cover
override construction, sector selection, and the domain precedence ladder
without reaching encrypted persistence.  Repository round-trip behavior lives
with the profile-persistence adapter tests.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal

import pytest

from cadrumo.core.modelo import Modelo
from cadrumo.core.prorrata_register import ProrrataProvisionalProvenance, ProrrataRegisterRegime
from cadrumo.core.secure_object_write import SecureObjectWrite
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.calculations.registry.schema_references import RegistrySnapshotRef
from cadrumo.domain.prorrata_register.register import (
    ProrrataActivityRow,
    ProrrataRegister,
    ProrrataRegisterEntry,
    SectorDefinition,
)

from ....domain.calculations.registry.tests.published_authority import published_snapshot
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

    def load_revisioned(self) -> tuple[ProrrataRegister, str]:
        return self._register, "test-revision"

    def to_secure_object_write(
        self,
        register: ProrrataRegister,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        del register
        del expected_revision_id
        raise AssertionError("secure-object writes are not part of this application-policy test")

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

    def upsert_sector_definition(self, definition: SectorDefinition) -> ProrrataRegister:
        retained = tuple(
            existing for existing in self._register.sector_definitions if existing.sector_id != definition.sector_id
        )
        self._register = ProrrataRegister(
            entries=self._register.entries,
            sector_definitions=(*retained, definition),
            activity_rows=self._register.activity_rows,
        )
        return self._register

    def upsert_activity_row(self, row: ProrrataActivityRow) -> ProrrataRegister:
        retained = tuple(
            existing
            for existing in self._register.activity_rows
            if (existing.ejercicio, existing.activity_id) != (row.ejercicio, row.activity_id)
        )
        self._register = ProrrataRegister(
            entries=self._register.entries,
            sector_definitions=self._register.sector_definitions,
            activity_rows=(*retained, row),
        )
        return self._register


@pytest.fixture
def authority_operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as operation:
        yield operation


def _service(operation: PinnedAuthorityOperation) -> ProrrataRegisterService:
    return ProrrataRegisterService(repository=_InMemoryProrrataRegisterRepository(), operation=operation)


def _prior_registry_snapshot_ref() -> RegistrySnapshotRef:
    return published_snapshot(Modelo("303").value, filing_year=2025, period="4T").snapshot_ref


def test_record_aeat_autorizada_preserves_sector_and_regime(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    service = _service(authority_operation)

    updated = service.record_aeat_autorizada(
        ejercicio=2026,
        provisional_percentage=Decimal("58"),
        authorisation_reference="AEAT-AUTH-2026-SECTOR-02",
        sector_id="arrendamiento",
        regime=ProrrataRegisterRegime.from_registry("especial"),
    )

    entry = updated.entry_for(2026, sector_id="arrendamiento")
    assert entry is not None
    assert entry.regime is ProrrataRegisterRegime.from_registry("especial")
    assert entry.provisional_percentage == Decimal("58")
    assert entry.provisional_provenance is ProrrataProvisionalProvenance.from_registry("aeat_autorizada")
    assert entry.authorisation_reference == "AEAT-AUTH-2026-SECTOR-02"


def test_record_inicio_actividad_preserves_sector_and_regime(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    service = _service(authority_operation)

    updated = service.record_inicio_actividad(
        ejercicio=2026,
        provisional_percentage=Decimal("52"),
        proposal_reference="INICIO-036-2026-SECTOR-04",
        sector_id="formacion",
        regime=ProrrataRegisterRegime.from_registry("especial"),
    )

    entry = updated.entry_for(2026, sector_id="formacion")
    assert entry is not None
    assert entry.regime is ProrrataRegisterRegime.from_registry("especial")
    assert entry.provisional_percentage == Decimal("52")
    assert entry.provisional_provenance is ProrrataProvisionalProvenance.from_registry("inicio_actividad")
    assert entry.authorisation_reference == "INICIO-036-2026-SECTOR-04"


def test_resolve_provisional_uses_ladder_for_authorised_candidate(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    service = _service(authority_operation)
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
    authorised = ProrrataRegisterEntry(
        ejercicio=2026,
        regime=ProrrataRegisterRegime.from_registry("general"),
        especial_transition=None,
        provisional_percentage=Decimal("63"),
        provisional_provenance=ProrrataProvisionalProvenance.from_registry("aeat_autorizada"),
        authorisation_reference="AEAT-AUTH-2026-0009",
        source_registry_snapshot_refs=(),
    )

    resolution = service.resolve_provisional(2026, candidate_entries=(authorised,))

    assert resolution.resolved
    assert resolution.percentage == Decimal("63")
    assert resolution.provenance is ProrrataProvisionalProvenance.from_registry("aeat_autorizada")


def test_resolve_provisional_uses_ladder_for_inicio_candidate(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    service = _service(authority_operation)
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
    inicio = ProrrataRegisterEntry(
        ejercicio=2026,
        regime=ProrrataRegisterRegime.from_registry("general"),
        especial_transition=None,
        provisional_percentage=Decimal("55"),
        provisional_provenance=ProrrataProvisionalProvenance.from_registry("inicio_actividad"),
        authorisation_reference="INICIO-036-2026-0005",
        source_registry_snapshot_refs=(),
    )

    resolution = service.resolve_provisional(2026, candidate_entries=(inicio,))

    assert resolution.resolved
    assert resolution.percentage == Decimal("55")
    assert resolution.provenance is ProrrataProvisionalProvenance.from_registry("inicio_actividad")


def test_resolve_provisional_filters_candidates_to_requested_sector(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    service = _service(authority_operation)
    service.declare(
        ProrrataRegisterEntry(
            ejercicio=2026,
            regime=ProrrataRegisterRegime.from_registry("general"),
            especial_transition=None,
            sector_id="comercio",
            provisional_percentage=Decimal("80"),
            provisional_provenance=ProrrataProvisionalProvenance.from_registry("carried_prior_definitiva"),
            source_observation_ref="303:2025:4T",
            source_registry_snapshot_refs=(_prior_registry_snapshot_ref(),),
        ),
    )
    other_sector = ProrrataRegisterEntry(
        ejercicio=2026,
        regime=ProrrataRegisterRegime.from_registry("general"),
        especial_transition=None,
        sector_id="arrendamiento",
        provisional_percentage=Decimal("63"),
        provisional_provenance=ProrrataProvisionalProvenance.from_registry("aeat_autorizada"),
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
    assert resolution.provenance is ProrrataProvisionalProvenance.from_registry("carried_prior_definitiva")
