"""Unit tests for the cross-period prorrata register domain model and ladder.

Covers the strict :class:`ProrrataRegisterEntry` field-coupling invariants, the
:class:`ProrrataRegister` duplicate-key rejection and lookups, and the pure LIVA
art. 105 precedence-ladder resolver (:func:`resolve_provisional_percentage`),
including its refusal to fabricate a default percentage.

See Also:
    :mod:`~domain.prorrata_register`
        Domain aggregate and resolver under test for the register carry home.
    :class:`~domain.prorrata_register.ProrrataRegisterEntry`
        Strict per-ejercicio row whose provisional, referenced, and settlement
        field groups are coupled by validators.
    :func:`~domain.prorrata_register.resolve_provisional_percentage`
        Pure art. 105 ladder that resolves authorised/inicio provenance before
        the carried prior definitive.
    :class:`~core.ProrrataProvisionalProvenance`
        Closed provenance axis asserted by the resolver and field-coupling
        tests.
"""

from __future__ import annotations

from decimal import Decimal

import pydantic
import pytest

from ....core import (
    ProrrataProvisionalProvenance,
    ProrrataRegisterRegime,
    SectorDiferenciadoLetra,
)
from .. import (
    ProrrataRegister,
    ProrrataRegisterEntry,
    SectorDefinition,
    resolve_provisional_percentage,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _carried_entry(ejercicio: int = 2024, pct: str = "80") -> ProrrataRegisterEntry:
    return ProrrataRegisterEntry(
        ejercicio=ejercicio,
        regime=ProrrataRegisterRegime.GENERAL,
        provisional_percentage=Decimal(pct),
        provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
        source_observation_ref="303:2023:4T",
    )


def _authorised_entry(ejercicio: int = 2024, pct: str = "60") -> ProrrataRegisterEntry:
    return ProrrataRegisterEntry(
        ejercicio=ejercicio,
        regime=ProrrataRegisterRegime.GENERAL,
        provisional_percentage=Decimal(pct),
        provisional_provenance=ProrrataProvisionalProvenance.AEAT_AUTORIZADA,
        authorisation_reference="AEAT-AUTH-2024-0007",
    )


def _inicio_entry(ejercicio: int = 2024, pct: str = "50") -> ProrrataRegisterEntry:
    return ProrrataRegisterEntry(
        ejercicio=ejercicio,
        regime=ProrrataRegisterRegime.GENERAL,
        provisional_percentage=Decimal(pct),
        provisional_provenance=ProrrataProvisionalProvenance.INICIO_ACTIVIDAD,
        authorisation_reference="INICIO-036-2024",
    )


# --------------------------------------------------------------------------- #
# Precedence ladder                                                           #
# --------------------------------------------------------------------------- #


def test_ladder_authorised_outranks_carried() -> None:
    """An AEAT-authorised provisional (105.Dos) outranks the carried prior definitive (105.Uno)."""
    resolution = resolve_provisional_percentage((_carried_entry(pct="80"), _authorised_entry(pct="60")))
    assert resolution.resolved is True
    assert resolution.percentage == Decimal("60")
    assert resolution.provenance is ProrrataProvisionalProvenance.AEAT_AUTORIZADA


def test_ladder_inicio_outranks_carried() -> None:
    """An inicio-de-actividades proposal (105.Tres) outranks the carried prior definitive."""
    resolution = resolve_provisional_percentage((_carried_entry(pct="80"), _inicio_entry(pct="50")))
    assert resolution.percentage == Decimal("50")
    assert resolution.provenance is ProrrataProvisionalProvenance.INICIO_ACTIVIDAD


def test_ladder_authorised_outranks_inicio() -> None:
    """The deterministic tie-break: an explicit AEAT authorisation outranks a self-proposed inicio percentage."""
    resolution = resolve_provisional_percentage((_inicio_entry(pct="50"), _authorised_entry(pct="60")))
    assert resolution.percentage == Decimal("60")
    assert resolution.provenance is ProrrataProvisionalProvenance.AEAT_AUTORIZADA


def test_ladder_single_carried_resolves() -> None:
    """A lone carried entry resolves to its own percentage."""
    resolution = resolve_provisional_percentage((_carried_entry(pct="72"),))
    assert resolution.percentage == Decimal("72")
    assert resolution.provenance is ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA


def test_ladder_no_candidates_is_unresolved_never_default() -> None:
    """No candidates resolves to the visible unresolved state, never a fabricated 100%."""
    resolution = resolve_provisional_percentage(())
    assert resolution.resolved is False
    assert resolution.percentage is None
    assert resolution.provenance is None


def test_ladder_ignores_entry_without_percentage() -> None:
    """An entry that records a regime but no provisional percentage does not contribute a value."""
    regime_only = ProrrataRegisterEntry(ejercicio=2024, regime=ProrrataRegisterRegime.GENERAL)
    resolution = resolve_provisional_percentage((regime_only,))
    assert resolution.resolved is False
    assert resolution.percentage is None


# --------------------------------------------------------------------------- #
# Entry field-coupling invariants                                             #
# --------------------------------------------------------------------------- #


def test_entry_percentage_requires_provenance() -> None:
    """A provisional percentage without a provenance is rejected."""
    with pytest.raises(pydantic.ValidationError, match="present or absent together"):
        ProrrataRegisterEntry(
            ejercicio=2024,
            regime=ProrrataRegisterRegime.GENERAL,
            provisional_percentage=Decimal("80"),
        )


def test_entry_provenance_requires_percentage() -> None:
    """A provenance without a provisional percentage is rejected."""
    with pytest.raises(pydantic.ValidationError, match="present or absent together"):
        ProrrataRegisterEntry(
            ejercicio=2024,
            regime=ProrrataRegisterRegime.GENERAL,
            provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
        )


def test_entry_authorised_requires_reference() -> None:
    """An aeat_autorizada provenance without an authorisation reference is rejected."""
    with pytest.raises(pydantic.ValidationError, match="requires an authorisation_reference"):
        ProrrataRegisterEntry(
            ejercicio=2024,
            regime=ProrrataRegisterRegime.GENERAL,
            provisional_percentage=Decimal("60"),
            provisional_provenance=ProrrataProvisionalProvenance.AEAT_AUTORIZADA,
        )


def test_entry_carried_forbids_authorisation_reference() -> None:
    """A carried provenance may not carry an authorisation reference."""
    with pytest.raises(pydantic.ValidationError, match="permitted only for an AEAT-authorised"):
        ProrrataRegisterEntry(
            ejercicio=2024,
            regime=ProrrataRegisterRegime.GENERAL,
            provisional_percentage=Decimal("80"),
            provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
            authorisation_reference="should-not-be-here",
        )


def test_entry_partial_settlement_rejected() -> None:
    """A definitive percentage without both volume inputs is rejected."""
    with pytest.raises(pydantic.ValidationError, match="present or absent together"):
        ProrrataRegisterEntry(
            ejercicio=2024,
            regime=ProrrataRegisterRegime.GENERAL,
            definitive_percentage=Decimal("65"),
            definitive_volume_con_derecho=Decimal("130000.00"),
        )


def test_entry_source_observation_only_for_carried() -> None:
    """A source observation reference is permitted only for a carried entry."""
    with pytest.raises(pydantic.ValidationError, match="carried_prior_definitiva"):
        ProrrataRegisterEntry(
            ejercicio=2024,
            regime=ProrrataRegisterRegime.GENERAL,
            provisional_percentage=Decimal("60"),
            provisional_provenance=ProrrataProvisionalProvenance.AEAT_AUTORIZADA,
            authorisation_reference="AEAT-AUTH-2024-0007",
            source_observation_ref="303:2023:4T",
        )


def test_interrupted_entry_roundtrips_and_defaults_carry_no_percentages() -> None:
    """An art-105.Cinco interrupted (sin operaciones) entry survives JSON roundtrip with no percentages."""
    entry = ProrrataRegisterEntry(
        ejercicio=2023,
        regime=ProrrataRegisterRegime.NINGUNA,
        interrupted=True,
    )
    restored = ProrrataRegisterEntry.model_validate_json(entry.model_dump_json())
    assert restored == entry
    assert restored.interrupted is True
    assert restored.provisional_percentage is None
    assert restored.definitive_percentage is None


def test_interrupted_entry_forbids_percentages_and_volumes() -> None:
    """An interrupted ejercicio had no operations, so it carries no definitive percentage/volumes."""
    with pytest.raises(pydantic.ValidationError, match="interrupted"):
        ProrrataRegisterEntry(
            ejercicio=2023,
            regime=ProrrataRegisterRegime.GENERAL,
            interrupted=True,
            definitive_percentage=Decimal("50"),
            definitive_volume_con_derecho=Decimal("10000.00"),
            definitive_volume_sin_derecho=Decimal("10000.00"),
        )


def test_interrumpida_tres_ultimos_provenance_resolves_in_ladder() -> None:
    """A resumed ejercicio seeded by the art-105.Cinco three-year rule resolves its provisional percentage."""
    resumed = ProrrataRegisterEntry(
        ejercicio=2024,
        regime=ProrrataRegisterRegime.GENERAL,
        provisional_percentage=Decimal("70"),
        provisional_provenance=ProrrataProvisionalProvenance.INTERRUMPIDA_TRES_ULTIMOS,
    )
    resolution = resolve_provisional_percentage((resumed,))
    assert resolution.percentage == Decimal("70")
    assert resolution.provenance is ProrrataProvisionalProvenance.INTERRUMPIDA_TRES_ULTIMOS


def _settled(ejercicio: int, con: str, sin: str) -> ProrrataRegisterEntry:
    return ProrrataRegisterEntry(
        ejercicio=ejercicio,
        regime=ProrrataRegisterRegime.GENERAL,
        definitive_percentage=Decimal("50"),
        definitive_volume_con_derecho=Decimal(con),
        definitive_volume_sin_derecho=Decimal(sin),
    )


def _interrupted(ejercicio: int) -> ProrrataRegisterEntry:
    return ProrrataRegisterEntry(ejercicio=ejercicio, regime=ProrrataRegisterRegime.NINGUNA, interrupted=True)


def test_walk_collects_last_three_active_years_skipping_the_interruption_gap() -> None:
    """The art-105.Cinco walk takes the last three ACTIVE años, skipping interrupted years."""
    register = ProrrataRegister(
        entries=(
            _settled(2019, "1000", "0"),
            _settled(2020, "10000", "0"),
            _settled(2021, "6000", "4000"),
            _settled(2022, "8000", "2000"),
            _interrupted(2023),
        ),
    )
    aggregate = register.collect_last_three_active_years(before_ejercicio=2024)
    assert aggregate.contributing_ejercicios == (2022, 2021, 2020)
    assert aggregate.sufficient is True
    assert aggregate.summed_volume_con_derecho == Decimal("24000")
    assert aggregate.summed_volume_sin_derecho == Decimal("6000")


def test_walk_reports_insufficient_history_with_fewer_than_three_active_years() -> None:
    """Fewer than three active años yields an insufficient aggregate, never a fabricated fill."""
    register = ProrrataRegister(entries=(_settled(2022, "8000", "2000"), _interrupted(2023)))
    aggregate = register.collect_last_three_active_years(before_ejercicio=2024)
    assert aggregate.contributing_ejercicios == (2022,)
    assert aggregate.sufficient is False


def test_walk_skips_unsettled_years() -> None:
    """A year with no definitive volumes (not yet settled) is not an active year for the walk."""
    register = ProrrataRegister(
        entries=(
            _settled(2020, "10000", "0"),
            _settled(2021, "6000", "4000"),
            ProrrataRegisterEntry(ejercicio=2022, regime=ProrrataRegisterRegime.GENERAL),
        ),
    )
    aggregate = register.collect_last_three_active_years(before_ejercicio=2023)
    assert aggregate.contributing_ejercicios == (2021, 2020)
    assert aggregate.sufficient is False


def test_entry_unsupported_schema_version_rejected() -> None:
    """An unsupported schema_version is rejected."""
    with pytest.raises(pydantic.ValidationError, match="unsupported ProrrataRegisterEntry"):
        ProrrataRegisterEntry(ejercicio=2024, regime=ProrrataRegisterRegime.GENERAL, schema_version="9")


def test_entry_fully_settled_carried_is_valid() -> None:
    """A fully-populated carried entry (provisional + settled) validates."""
    entry = ProrrataRegisterEntry(
        ejercicio=2024,
        regime=ProrrataRegisterRegime.GENERAL,
        provisional_percentage=Decimal("80"),
        provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
        source_observation_ref="303:2023:4T",
        definitive_percentage=Decimal("77"),
        definitive_volume_con_derecho=Decimal("154000.00"),
        definitive_volume_sin_derecho=Decimal("46000.00"),
    )
    assert entry.definitive_percentage == Decimal("77")


# --------------------------------------------------------------------------- #
# Register aggregate                                                          #
# --------------------------------------------------------------------------- #


def test_register_rejects_duplicate_key() -> None:
    """Two entries for the same (ejercicio, sector) are rejected."""
    with pytest.raises(pydantic.ValidationError, match="duplicate"):
        ProrrataRegister(entries=(_carried_entry(2024), _authorised_entry(2024)))


def test_register_distinct_sectors_coexist() -> None:
    """Two entries for the same ejercicio but different sectors coexist."""
    a = ProrrataRegisterEntry(ejercicio=2024, regime=ProrrataRegisterRegime.GENERAL, sector_id="comercio")
    b = ProrrataRegisterEntry(ejercicio=2024, regime=ProrrataRegisterRegime.ESPECIAL, sector_id="alquiler")
    register = ProrrataRegister(entries=(a, b))
    assert len(register.entries_for_ejercicio(2024)) == 2


def test_register_entry_for_returns_matching_key() -> None:
    """entry_for resolves the (ejercicio, sector) key, and None when absent."""
    register = ProrrataRegister(entries=(_carried_entry(2024),))
    assert register.entry_for(2024) is not None
    assert register.entry_for(2023) is None
    assert register.entry_for(2024, sector_id="comercio") is None


def test_register_resolve_provisional_delegates_to_ladder() -> None:
    """resolve_provisional returns the entry's percentage, and unresolved when absent."""
    register = ProrrataRegister(entries=(_carried_entry(2024, pct="80"),))
    resolved = register.resolve_provisional(2024)
    assert resolved.percentage == Decimal("80")
    assert register.resolve_provisional(2023).resolved is False


def _sector(sector_id: str, letra: SectorDiferenciadoLetra, *codes: str) -> SectorDefinition:
    return SectorDefinition(sector_id=sector_id, letra=letra, member_activity_codes=codes)


def test_register_without_sector_definitions_is_whole_entity() -> None:
    """Fail-closed: an empty sector partition is a whole-entity register."""
    register = ProrrataRegister(entries=(_carried_entry(2024),))
    assert register.is_sectorized is False
    assert register.sector_ids() == ()
    assert register.sector_definition_for("comercio") is None


def test_register_sector_definitions_declare_partition() -> None:
    """A declared sector partition is queryable by sector_id and carries its art. 9.1.c letra."""
    comercio = _sector("comercio", SectorDiferenciadoLetra.A, "4711", "4719")
    arrendamiento = _sector("arrendamiento", SectorDiferenciadoLetra.A, "6820")
    register = ProrrataRegister(
        entries=(_carried_entry(2024),),
        sector_definitions=(comercio, arrendamiento),
    )
    assert register.is_sectorized is True
    assert register.sector_ids() == ("comercio", "arrendamiento")
    assert register.sector_definition_for("arrendamiento") is arrendamiento
    assert register.sector_definition_for("arrendamiento").letra is SectorDiferenciadoLetra.A
    assert register.sector_definition_for("unknown") is None


def test_register_rejects_duplicate_sector_definition() -> None:
    """Two sector definitions for the same sector_id are rejected."""
    with pytest.raises(pydantic.ValidationError, match="duplicate sector_id"):
        ProrrataRegister(
            sector_definitions=(
                _sector("comercio", SectorDiferenciadoLetra.A, "4711"),
                _sector("comercio", SectorDiferenciadoLetra.B, "0111"),
            ),
        )


def test_sector_definition_requires_member_codes() -> None:
    """A sector definition must group at least one activity code (min_length=1)."""
    with pytest.raises(pydantic.ValidationError):
        SectorDefinition(sector_id="comercio", letra=SectorDiferenciadoLetra.A, member_activity_codes=())


def test_sector_definition_rejects_blank_member_code() -> None:
    """A blank member activity code is refused — every grouped code is a real token."""
    with pytest.raises(pydantic.ValidationError, match="blank code"):
        SectorDefinition(
            sector_id="comercio",
            letra=SectorDiferenciadoLetra.A,
            member_activity_codes=("4711", "   "),
        )


def test_sector_definition_letra_hydrates_from_stored_token() -> None:
    """The art. 9.1.c letra hydrates from its stored StrEnum token across a JSON cycle."""
    original = _sector("arrendamiento-financiero", SectorDiferenciadoLetra.C, "6491")
    restored = SectorDefinition.model_validate_json(original.model_dump_json())
    assert restored == original
    assert restored.letra is SectorDiferenciadoLetra.C
