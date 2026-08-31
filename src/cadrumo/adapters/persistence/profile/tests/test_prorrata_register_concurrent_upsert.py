"""Two concurrent prorrata declarations both survive.

The prorrata register is a SINGLETON row, so both ``upsert_entry`` and
``upsert_sector_definition`` are really read-whole-register, rebuild,
write-whole-register. Run unguarded, two callers declaring DIFFERENT keys both
read the same register and the later save silently dropped the earlier caller's
declaration.

That is a lost update, not a key collision: the key-replacement logic never saw
both, because they never met in one document. The two methods write the SAME
row, so the guard has to cover both -- a sector declaration can discard a
concurrently-declared entry just as easily as another definition.

Observed deterministically, by landing the interloping write inside the guarded
unit of work's read-to-write window, rather than by racing threads.

Real behaviour throughout: a real isolated bucket runtime, the real encrypted
SQL backend, and genuine repository instances. Nothing is mocked.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from .....core.prorrata_register import ProrrataProvisionalProvenance, ProrrataRegisterRegime
from .....domain.prorrata_register import ProrrataRegister, ProrrataRegisterEntry
from ...tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from ..prorrata_register import ProrrataRegisterRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "51355135-5135-4135-8135-513551355135"

_runtime_profile = bucket_scoped_runtime_profile_fixture(_BUCKET_ID)


def _entry(ejercicio: int, *, percentage: str) -> ProrrataRegisterEntry:
    return ProrrataRegisterEntry(
        ejercicio=ejercicio,
        regime=ProrrataRegisterRegime.GENERAL,
        especial_transition=None,
        provisional_percentage=Decimal(percentage),
        provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
        source_observation_ref=f"303:{ejercicio - 1}:4T",
    )


def test_sequential_upserts_for_distinct_ejercicios_accumulate() -> None:
    """Baseline: nothing about two repository instances loses an entry."""
    ProrrataRegisterRepository().upsert_entry(_entry(2024, percentage="80"))
    ProrrataRegisterRepository().upsert_entry(_entry(2025, percentage="70"))

    ejercicios = [entry.ejercicio for entry in ProrrataRegisterRepository().load().entries]
    assert sorted(ejercicios) == [2024, 2025]


def test_a_concurrent_upsert_does_not_discard_the_other_entry() -> None:
    """DISCRIMINATING: the interleaving that used to lose a declaration.

    The interloping upsert lands after this guarded attempt's read and before
    its write, which is exactly the window two concurrent callers race in.
    Before the guard, this attempt's write overwrote the interloper and only
    one ejercicio remained.
    """
    repo = ProrrataRegisterRepository()
    interloper_written = False

    def _apply_2024_while_2025_lands(current: ProrrataRegister) -> ProrrataRegister:
        nonlocal interloper_written
        if not interloper_written:
            interloper_written = True
            ProrrataRegisterRepository().upsert_entry(_entry(2025, percentage="70"))
        return ProrrataRegister(
            entries=(*current.entries, _entry(2024, percentage="80")),
            sector_definitions=current.sector_definitions,
        )

    # Reaches through the repository's storage kernel deliberately: the point is
    # to interleave INSIDE one guarded upsert, which the public method does not
    # expose a seam for.
    repo._storage.mutate(_apply_2024_while_2025_lands)

    ejercicios = [entry.ejercicio for entry in ProrrataRegisterRepository().load().entries]
    assert sorted(ejercicios) == [2024, 2025]


def test_replacing_an_existing_key_still_replaces_rather_than_duplicates() -> None:
    """POSITIVE CONTROL: the upsert semantics survive the guard.

    The register carries one entry per ``(ejercicio, sector_id)`` across the
    ejercicio's lifecycle, so a second declaration for the same key must
    REPLACE. Without this, the concurrency fix could have been "keep both",
    which would silently duplicate a provisional and a definitive settlement.
    """
    ProrrataRegisterRepository().upsert_entry(_entry(2024, percentage="80"))
    ProrrataRegisterRepository().upsert_entry(_entry(2024, percentage="65"))

    entries = ProrrataRegisterRepository().load().entries
    assert len(entries) == 1
    assert entries[0].provisional_percentage == Decimal("65")
