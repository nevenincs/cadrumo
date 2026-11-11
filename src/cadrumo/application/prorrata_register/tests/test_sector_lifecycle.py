"""Per-sector provisional/definitive lifecycle (LIVA arts. 9.1.c / 101 / 105).

Proves the differentiated-sector lifecycle runs the landed cross-period
mechanism per sector: each sector settles its own year-end definitive from its
OWN annual volumes, and each sector's next-year provisional carries that sector's
prior definitive (never the other sector's, never the whole-entity Modelo 303
percentage). The anti-tautology angle is structural: two sectors with different
volumes settle to different definitives and each carries its own forward, so a
shared-source / cross-sector-leak regression surfaces as an inequality.

See Also:
    :func:`~application.prorrata_register.seed_sector_carried_definitive_from_register`
        The register-sourced per-sector carried seed under test.
    :func:`~application.prorrata_register.settle_sector_definitive`
        The per-sector settlement write-back under test.
    :class:`~domain.prorrata_register.ProrrataRegister`
        Sector-keyed register the lifecycle reads and writes.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from cadrumo.core.prorrata_register import ProrrataProvisionalProvenance, ProrrataRegisterRegime

from ....core.modelo import Modelo
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope, revision_covering
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.prorrata_register.register import ProrrataRegister, ProrrataRegisterEntry
from ..sector_lifecycle import seed_sector_carried_definitive_from_register, settle_sector_definitive

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_YEAR = filing_year_envelope().horizon
_PRIOR_YEAR = _YEAR - 1


def _m303_snapshot_ref(ejercicio: int) -> RegistrySnapshotRef:
    return published_snapshot(Modelo("303").value, filing_year=ejercicio, period="4T").snapshot_ref


def _provisional_entry(*, ejercicio: int, sector_id: str, percentage: Decimal) -> ProrrataRegisterEntry:
    return ProrrataRegisterEntry(
        ejercicio=ejercicio,
        regime=ProrrataRegisterRegime.from_registry("general"),
        especial_transition=None,
        sector_id=sector_id,
        provisional_percentage=percentage,
        provisional_provenance=ProrrataProvisionalProvenance.from_registry("carried_prior_definitiva"),
        source_observation_ref=f"prorrata-register:{ejercicio - 1}:{sector_id}",
        source_registry_snapshot_refs=(_m303_snapshot_ref(ejercicio - 1),),
    )


#: The year-end Modelo 303 coordinate whose rules produced a settled definitive.
_YEAR_END_REF = RegistrySnapshotRef(
    modelo="303", revision_id=revision_covering("303", _PRIOR_YEAR).id, modelo_year=_PRIOR_YEAR, period="4T"
)


def test_settle_sector_definitive_derives_percentage_from_its_own_volumes() -> None:
    """A sector's definitive is the con/total ratio of ITS OWN annual volumes (art. 105.Cuatro)."""
    entry = _provisional_entry(ejercicio=_PRIOR_YEAR, sector_id="comercio", percentage=Decimal("85"))
    settled = settle_sector_definitive(
        entry,
        con_derecho_volume=Decimal("90000.00"),
        sin_derecho_volume=Decimal("10000.00"),
        producing_snapshot_ref=_YEAR_END_REF,
    )
    # 90000 / 100000 = 90% (art. 102.Uno + 102.Dos round-up); volumes preserved.
    assert settled.definitive_percentage == Decimal("90")
    assert settled.definitive_volume_con_derecho == Decimal("90000.00")
    assert settled.definitive_volume_sin_derecho == Decimal("10000.00")
    # The provisional applied in-year is preserved for the regularización compare.
    assert settled.provisional_percentage == Decimal("85")
    # The next year's carried seed must be able to cite what produced it.
    assert _YEAR_END_REF in settled.source_registry_snapshot_refs


def test_sector_provisional_carries_its_own_prior_definitive() -> None:
    """Next year's per-sector provisional is that sector's prior-year definitive (art. 105.Uno)."""
    settled = settle_sector_definitive(
        _provisional_entry(ejercicio=_PRIOR_YEAR, sector_id="comercio", percentage=Decimal("85")),
        con_derecho_volume=Decimal("90000.00"),
        sin_derecho_volume=Decimal("10000.00"),
        producing_snapshot_ref=_YEAR_END_REF,
    )
    register = ProrrataRegister(entries=(settled,))
    seed = seed_sector_carried_definitive_from_register(register, ejercicio=_YEAR, sector_id="comercio")
    assert seed is not None
    assert seed.ejercicio == _YEAR
    assert seed.sector_id == "comercio"
    assert seed.provisional_provenance == ProrrataProvisionalProvenance.from_registry("carried_prior_definitiva")
    # The seed year's provisional equals the prior year's sector definitive (90%), not the 85% provisional.
    assert seed.provisional_percentage == Decimal("90")


def test_two_sectors_carry_distinct_prior_definitives() -> None:
    """Each sector seeds from ITS OWN prior definitive — no cross-sector leak.

    Anti-tautology: comercio and arrendamiento settle to different definitives
    from different volumes; each seed-year provisional must equal its own prior-year
    definitive. A shared-source regression would make the two provisionals equal.
    """
    comercio_prior = settle_sector_definitive(
        _provisional_entry(ejercicio=_PRIOR_YEAR, sector_id="comercio", percentage=Decimal("85")),
        con_derecho_volume=Decimal("90000.00"),
        sin_derecho_volume=Decimal("10000.00"),
        producing_snapshot_ref=_YEAR_END_REF,
    )
    arrendamiento_prior = settle_sector_definitive(
        _provisional_entry(ejercicio=_PRIOR_YEAR, sector_id="arrendamiento", percentage=Decimal("25")),
        con_derecho_volume=Decimal("30000.00"),
        sin_derecho_volume=Decimal("70000.00"),
        producing_snapshot_ref=_YEAR_END_REF,
    )
    register = ProrrataRegister(entries=(comercio_prior, arrendamiento_prior))

    comercio_seed = seed_sector_carried_definitive_from_register(register, ejercicio=_YEAR, sector_id="comercio")
    arrendamiento_seed = seed_sector_carried_definitive_from_register(
        register, ejercicio=_YEAR, sector_id="arrendamiento"
    )

    assert comercio_seed is not None
    assert arrendamiento_seed is not None
    # comercio 90000/100000 = 90%; arrendamiento 30000/100000 = 30%; a >50-point spread.
    assert comercio_seed.provisional_percentage == Decimal("90")
    assert arrendamiento_seed.provisional_percentage == Decimal("30")
    assert comercio_seed.provisional_percentage != arrendamiento_seed.provisional_percentage
    comercio_percentage = comercio_seed.provisional_percentage
    arrendamiento_percentage = arrendamiento_seed.provisional_percentage
    assert comercio_percentage is not None
    assert arrendamiento_percentage is not None
    assert (comercio_percentage - arrendamiento_percentage) > Decimal("50")


def test_sector_without_prior_definitive_returns_none_never_defaults() -> None:
    """A sector with no settled prior-year definitive seeds ``None`` (no silent default).

    A first ejercicio, or a gap year, must surface the missing-provisional
    advisory rather than assuming a percentage.
    """
    register = ProrrataRegister(
        entries=(
            # A prior-year sector entry that is provisional-only (never settled).
            _provisional_entry(ejercicio=_PRIOR_YEAR, sector_id="comercio", percentage=Decimal("80")),
        ),
    )
    assert seed_sector_carried_definitive_from_register(register, ejercicio=_YEAR, sector_id="comercio") is None
    # A sector entirely absent from the prior year is likewise unseeded.
    assert seed_sector_carried_definitive_from_register(register, ejercicio=_YEAR, sector_id="nuevo") is None


def test_sector_seed_does_not_read_whole_entity_definitive() -> None:
    """The per-sector seed reads the sector's key, never the whole-entity entry.

    A whole-entity (``sector_id=None``) settled definitive must not leak into a
    sector's carried provisional — the sector's own key is empty, so the seed is
    ``None``.
    """
    whole_entity_prior = settle_sector_definitive(
        ProrrataRegisterEntry(
            ejercicio=_PRIOR_YEAR,
            regime=ProrrataRegisterRegime.from_registry("general"),
            especial_transition=None,
            provisional_percentage=Decimal("70"),
            provisional_provenance=ProrrataProvisionalProvenance.from_registry("carried_prior_definitiva"),
            source_observation_ref=f"303:{_PRIOR_YEAR - 1}:4T",
            source_registry_snapshot_refs=(_m303_snapshot_ref(_PRIOR_YEAR - 1),),
        ),
        con_derecho_volume=Decimal("50000.00"),
        sin_derecho_volume=Decimal("50000.00"),
        producing_snapshot_ref=_YEAR_END_REF,
    )
    register = ProrrataRegister(entries=(whole_entity_prior,))
    assert seed_sector_carried_definitive_from_register(register, ejercicio=_YEAR, sector_id="comercio") is None
