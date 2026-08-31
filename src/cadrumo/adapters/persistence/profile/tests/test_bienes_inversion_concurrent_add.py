"""Two concurrent capital-good adds both survive.

The bienes de inversión register is a SINGLETON row, so ``add`` is really
read-whole-register, rebuild, write-whole-register. Performed unguarded, two
callers adding DIFFERENT records both read the same register and the later
write silently discarded the earlier record.

That is a lost update, not a duplicate: the two records never met in one
document, so no uniqueness check could have noticed. The only way to observe it
is to interleave the two halves of the read-modify-write, which is what this
module does -- deterministically, by holding one repository's read open across
the other's complete write, rather than by racing threads.

Real behaviour throughout: a real isolated bucket runtime, the real encrypted
SQL backend, and two genuine repository instances. Nothing is mocked.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from .....domain.bienes_inversion.register import BienesInversionIvaRegister, BienInversionIvaRecord, BienInversionKind
from ...tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from ..bienes_inversion import BienesInversionIvaRegisterRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "51555155-5155-4155-8155-515551555155"

_runtime_profile = bucket_scoped_runtime_profile_fixture(_BUCKET_ID)


def _record(identifier: str, *, year: int) -> BienInversionIvaRecord:
    return BienInversionIvaRecord(
        identifier=identifier,
        description=f"capital good {identifier}",
        acquisition_year=year,
        cuota_soportada=Decimal("4200.00"),
        prorrata_inicial_pct=Decimal("80"),
        kind=BienInversionKind.MUEBLE,
        acquisition_ledger_id=f"ledger-{identifier}",
    )


def test_two_repository_instances_both_land_their_records() -> None:
    """Sequential adds through independent instances accumulate.

    The baseline the interleaved case below is measured against: nothing about
    using two repository instances loses a record on its own.
    """
    BienesInversionIvaRegisterRepository().add(_record("bien-2022", year=2022))
    BienesInversionIvaRegisterRepository().add(_record("bien-2023", year=2023))

    identifiers = [item.identifier for item in BienesInversionIvaRegisterRepository().load().records]
    assert sorted(identifiers) == ["bien-2022", "bien-2023"]


def test_a_concurrent_add_does_not_discard_the_other_record() -> None:
    """DISCRIMINATING: the interleaving that used to lose a record.

    ``mutation`` is invoked with the register the guarded unit of work just
    read. Writing a SECOND record from inside it -- through an independent
    repository instance -- lands that record after this attempt's read and
    before its write, which is exactly the window two concurrent callers race
    in. Before the guard, this attempt's write overwrote the interloper and
    only one record remained.

    The guard makes the stale write refuse, the mutation re-run against the
    now-current register, and both records survive.
    """
    repo = BienesInversionIvaRegisterRepository()
    interloper_written = False

    def _add_first_while_a_second_lands(current: BienesInversionIvaRegister) -> BienesInversionIvaRegister:
        nonlocal interloper_written
        if not interloper_written:
            interloper_written = True
            BienesInversionIvaRegisterRepository().add(_record("bien-2023", year=2023))
        return BienesInversionIvaRegister(records=(*current.records, _record("bien-2022", year=2022)))

    # Reaches through the repository's storage kernel deliberately: the point is
    # to interleave INSIDE one guarded add, which the public method does not
    # expose a seam for.
    repo._storage.mutate(_add_first_while_a_second_lands)

    identifiers = [item.identifier for item in BienesInversionIvaRegisterRepository().load().records]
    assert sorted(identifiers) == ["bien-2022", "bien-2023"]


def test_a_duplicate_identifier_is_still_refused_and_not_retried() -> None:
    """A refusal is not a conflict, so the guard must not retry it.

    Pins that wrapping ``add`` in a retrying unit of work did not turn its
    duplicate refusal into a loop or, worse, into an eventual success.
    """
    repo = BienesInversionIvaRegisterRepository()
    repo.add(_record("bien-2022", year=2022))

    from .....domain.bienes_inversion.register import BienInversionRecordError

    with pytest.raises(BienInversionRecordError):
        BienesInversionIvaRegisterRepository().add(_record("bien-2022", year=2022))

    assert len(BienesInversionIvaRegisterRepository().load().records) == 1
