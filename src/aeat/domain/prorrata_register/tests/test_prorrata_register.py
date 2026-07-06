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

from ....core import ProrrataProvisionalProvenance, ProrrataRegisterRegime
from .. import (
    ProrrataRegister,
    ProrrataRegisterEntry,
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
