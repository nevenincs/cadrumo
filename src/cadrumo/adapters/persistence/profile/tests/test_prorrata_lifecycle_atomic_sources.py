"""Real encrypted-store races for canonical prorrata lifecycle writes."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import override

import pytest

from .....application.prorrata_register.ports import ProrrataPriorSettlementSourceSnapshot
from .....application.prorrata_register.service import (
    ProrrataRegisterService,
    ProrrataWholeSeedUnavailableError,
)
from .....application.prorrata_register.tests.provisional_override import record_aeat_autorizada
from .....core.casilla_id import validated_casilla_id
from .....core.prorrata_register import ProrrataProvisionalProvenance, ProrrataRegisterRegime
from .....domain.calculations.registry.tests.registry_observations import registry_grounded_modelo_observation
from .....domain.prorrata_register.register import ProrrataRegister, ProrrataRegisterEntry
from ...tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from ..calculation_observations import CalculationObservationRepository
from ..prorrata_register import ProrrataRegisterRepository
from .modelo_303_filed_disposition import modelo_303_filed_disposition
from .published_authority_support import published_authority_operation

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_runtime_profile = bucket_scoped_runtime_profile_fixture("11961196-1196-4196-8196-119611961196")
_PERCENTAGE = validated_casilla_id("iva.prorrata-porcentaje")
_AUTHORITY = published_authority_operation()


def _service(repository: ProrrataRegisterRepository | None = None) -> ProrrataRegisterService:
    return ProrrataRegisterService(repository=repository or ProrrataRegisterRepository(), operation=_AUTHORITY)


def _observation(
    period: str,
    percentage: str,
    *,
    hour: int,
    member_nif: str | None = None,
) -> None:
    repository = CalculationObservationRepository()
    values, headers = modelo_303_filed_disposition(
        {_PERCENTAGE: Decimal(percentage)}, source_locator=f"prorrata-race:{period}"
    )
    observation = registry_grounded_modelo_observation(
        modelo="303", filing_year=2025, period=period, casilla_values=values
    )
    revision = _AUTHORITY.snapshot("303", filing_year=2025, period=period).revision.id
    repository.save(
        repository.prepare_observation_envelope(
            observation,
            source_kind="aeat_sede_justificante",
            stamped_revision_id=str(revision),
            captured_at=datetime(2026, 1, 10, hour, tzinfo=UTC),
            source_headers=headers,
            member_nif=member_nif,
        )
    )


class _RacingWholeSeedRepository(ProrrataRegisterRepository):
    """Land one real interloper write after the service reads and before CAS."""

    def __init__(self, interloper: Callable[[], object]) -> None:
        super().__init__()
        self._interloper = interloper
        self._raced = False

    @override
    def commit_whole_carried_seed(
        self,
        register: ProrrataRegister,
        *,
        ejercicio: int,
        expected_revision_id: str,
        source_snapshot: ProrrataPriorSettlementSourceSnapshot,
    ) -> None:
        if not self._raced:
            self._raced = True
            self._interloper()
        super().commit_whole_carried_seed(
            register,
            ejercicio=ejercicio,
            expected_revision_id=expected_revision_id,
            source_snapshot=source_snapshot,
        )


def test_new_monthly_source_invalidates_absent_row_and_recomputes_seed() -> None:
    """An absent 12 row cannot appear after 4T selection without forcing retry."""
    _observation("4T", "80", hour=10)
    repository = _RacingWholeSeedRepository(lambda: _observation("12", "90", hour=11))

    result = _service(repository).seed_whole_carried(2026, observation_repository=CalculationObservationRepository())

    assert result.seed.source_period == "12"
    assert result.seed.entry.provisional_percentage == Decimal("90")
    assert ProrrataRegisterRepository().load().entry_for(2026) == result.seed.entry


def test_concurrent_regulated_override_survives_target_revision_retry() -> None:
    """A new standing target is re-read and may refuse the stale proposed carry."""
    _observation("4T", "80", hour=10)
    repository = _RacingWholeSeedRepository(
        lambda: record_aeat_autorizada(
            _service(),
            ejercicio=2026,
            provisional_percentage=Decimal("55"),
            authorisation_reference="AEAT-PRORRATA-RACE-2026",
        )
    )

    with pytest.raises(ProrrataWholeSeedUnavailableError) as captured:
        _service(repository).seed_whole_carried(2026, observation_repository=CalculationObservationRepository())

    assert captured.value.reason == "regulated_override_standing"
    standing = ProrrataRegisterRepository().load().entry_for(2026)
    assert standing is not None
    assert standing.provisional_percentage == Decimal("55")
    assert standing.provisional_provenance == ProrrataProvisionalProvenance.from_registry("aeat_autorizada")


def test_member_only_settlement_cannot_seed_whole_entity() -> None:
    """A group's member observation is not the whole-entity 303 source."""
    _observation("4T", "80", hour=10, member_nif="12345678Z")

    with pytest.raises(ProrrataWholeSeedUnavailableError) as captured:
        _service().seed_whole_carried(2026, observation_repository=CalculationObservationRepository())

    assert captured.value.reason == "source_absent"
    assert ProrrataRegisterRepository().load().entry_for(2026) is None


def _sector_entry(year: int, *, provisional: str, definitive: str | None = None) -> ProrrataRegisterEntry:
    ref = _AUTHORITY.snapshot("303", filing_year=year - 1, period="4T").snapshot_ref
    definitive_value = Decimal(definitive) if definitive is not None else None
    return ProrrataRegisterEntry(
        ejercicio=year,
        regime=ProrrataRegisterRegime.from_registry("general"),
        especial_transition=None,
        sector_id="comercio",
        provisional_percentage=Decimal(provisional),
        provisional_provenance=ProrrataProvisionalProvenance.from_registry("carried_prior_definitiva"),
        source_observation_ref=f"prorrata-register:{year - 1}:comercio",
        source_registry_snapshot_refs=(ref,),
        definitive_percentage=definitive_value,
        definitive_volume_con_derecho=definitive_value * Decimal("1000") if definitive_value is not None else None,
        definitive_volume_sin_derecho=(Decimal("100") - definitive_value) * Decimal("1000")
        if definitive_value is not None
        else None,
    )


def test_sector_carry_retry_uses_new_prior_definitive(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sector carry derives inside CAS retry rather than retaining the first read."""
    ProrrataRegisterRepository().upsert_entry(_sector_entry(2025, provisional="75", definitive="80"))
    repository = ProrrataRegisterRepository()
    original_mutate = repository._storage.mutate
    raced = False

    def _mutate_with_interloper(mutation: Callable[[ProrrataRegister], ProrrataRegister]) -> ProrrataRegister:
        def _apply(current: ProrrataRegister) -> ProrrataRegister:
            nonlocal raced
            if not raced:
                raced = True
                ProrrataRegisterRepository().upsert_entry(_sector_entry(2025, provisional="75", definitive="90"))
            return mutation(current)

        return original_mutate(_apply)

    monkeypatch.setattr(repository._storage, "mutate", _mutate_with_interloper)
    committed, entry = _service(repository).seed_sector_carried(2026, "comercio")

    assert entry.provisional_percentage == Decimal("90")
    assert committed.entry_for(2026, sector_id="comercio") == entry


def test_sector_settlement_retry_preserves_new_provisional(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settlement re-reads current sector state after CAS conflict, preserving its new provisional."""
    ProrrataRegisterRepository().upsert_entry(_sector_entry(2026, provisional="70"))
    repository = ProrrataRegisterRepository()
    original_mutate = repository._storage.mutate
    raced = False

    def _mutate_with_interloper(mutation: Callable[[ProrrataRegister], ProrrataRegister]) -> ProrrataRegister:
        def _apply(current: ProrrataRegister) -> ProrrataRegister:
            nonlocal raced
            if not raced:
                raced = True
                ProrrataRegisterRepository().upsert_entry(_sector_entry(2026, provisional="60"))
            return mutation(current)

        return original_mutate(_apply)

    monkeypatch.setattr(repository._storage, "mutate", _mutate_with_interloper)
    producing_ref = _AUTHORITY.snapshot("303", filing_year=2026, period="4T").snapshot_ref
    committed, entry = _service(repository).settle_sector(
        2026,
        "comercio",
        con_derecho_volume=Decimal("90000"),
        sin_derecho_volume=Decimal("10000"),
        producing_snapshot_ref=producing_ref,
    )

    assert entry.provisional_percentage == Decimal("60")
    assert entry.definitive_percentage == Decimal("90")
    assert committed.entry_for(2026, sector_id="comercio") == entry
