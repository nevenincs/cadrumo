"""The singleton-ledger write verbs route through the revision-guarded seam.

WHAT THIS GATE IS FOR, AND WHAT IT MUST NOT BE MISTAKEN FOR.

It asserts that `AssetsLedgerRepository.add`, `InventoryLedgerRepository.create`
and `InventoryLedgerRepository.record_movement` still ROUTE through
`ProfileBareModelSecurePersistence.mutate`. It does NOT assert that the guard
WORKS -- the concurrency regressions in `test_assets_concurrent_add.py` and
`test_inventory_concurrent_write.py` do that, and a reader who treats this file
as proof of correctness will stop looking at the ones that actually measure
behaviour.

It exists because those behavioural regressions cannot see the routing. They
reach the interleaving window through `repo._storage.mutate(...)` directly,
because the public verbs expose no seam to interleave at, so an edit reverting a
verb to inline load / check / save leaves every one of them green. That gap was
found by reverting `assets.py` and `inventory.py` to their pre-fix parents and
watching all eight regressions pass against unguarded code. Two mutations answer
two questions: removing the guard FROM the seam is what those tests notice;
removing the ROUTING from the verb is what this file notices.

Closing it by interleaving two real threads on the public verb is not currently
possible: the active bucket session is context-scoped and does not cross
threads, so both workers die before writing. Until a thread-surviving session
exists, structural assertion is the available instrument -- the same trade the
secure-object decode-order gate documents, and this file mirrors its shape.

TWO LIMITS, both deliberate:

* It asserts SPELLING, not behaviour. A verb that calls `mutate` and then does
  something wrong still passes here.
* Reading a peer's source mid-run can red it for reasons that are not the
  code's: a commit landing above the subject between import and assertion has
  reddened a source-reading gate in this repo before, and it was blamed on the
  code rather than the race. Re-read at HEAD before attributing a failure here.

The negative half matters as much as the positive one. "Calls `mutate`" and
"calls `mutate` AND carries no second write path" are different assertions, and
only the second survives a PARTIAL re-inlining that leaves the call in place
beside a reintroduced direct save.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable

import pytest

from ..assets import AssetsLedgerRepository
from ..inventory import InventoryLedgerRepository
from ..invoices import InvoiceCatalogueRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

#: The one guarded read-modify-write every singleton write verb must go through.
_GUARDED_SEAM = "_storage.mutate"

#: Write paths that bypass the revision guard. A verb re-inlining its own
#: load-modify-save reintroduces the lost update these verbs were fixed for, and
#: does it while the concurrency regressions stay green.
_BYPASSING_WRITE_PATHS = (
    "_storage.save(",
    "_save_unlocked(",
    "save_many(",
    "to_secure_object_write(",
)

#: The guarded seam an APPLICATION service reaches, one layer above the
#: repository's own. The invoice catalogue's creation service owns its
#: read-modify-write rather than delegating to a repository verb, so its seam is
#: the repository's ``mutate`` rather than the storage object's.
_GUARDED_SERVICE_SEAM = ".mutate("

#: Every public verb that mutates a profile singleton document in place.
_GUARDED_VERBS: tuple[tuple[str, Callable[..., object]], ...] = (
    ("AssetsLedgerRepository.add", AssetsLedgerRepository.add),
    ("InventoryLedgerRepository.create", InventoryLedgerRepository.create),
    ("InventoryLedgerRepository.record_movement", InventoryLedgerRepository.record_movement),
    ("InvoiceCatalogueRepository.mutate", InvoiceCatalogueRepository.mutate),
)
_VERB_IDS = tuple(name for name, _fn in _GUARDED_VERBS)


@pytest.mark.parametrize(("name", "verb"), _GUARDED_VERBS, ids=_VERB_IDS)
def test_write_verb_routes_through_the_guarded_seam(name: str, verb: Callable[..., object]) -> None:
    """The verb delegates its write to the revision-guarded unit of work."""
    source = inspect.getsource(verb)

    assert _GUARDED_SEAM in source, (
        f"{name} does not route through {_GUARDED_SEAM}; a verb that rebuilds and saves "
        f"the singleton itself loses concurrent updates, and the concurrency regressions "
        f"cannot see it because they reach the seam directly"
    )


@pytest.mark.parametrize(("name", "verb"), _GUARDED_VERBS, ids=_VERB_IDS)
def test_write_verb_carries_no_unguarded_write_path(name: str, verb: Callable[..., object]) -> None:
    """The verb keeps no second, unguarded route to storage.

    DISCRIMINATING against a PARTIAL re-inlining, which the routing assertion
    above cannot see: a verb that still calls ``mutate`` but has regained a
    direct save beside it satisfies "routes through the seam" while writing
    around it.
    """
    source = inspect.getsource(verb)

    reintroduced = [path for path in _BYPASSING_WRITE_PATHS if path in source]

    assert not reintroduced, (
        f"{name} reaches storage directly via {reintroduced}; every write to a profile "
        f"singleton must go through {_GUARDED_SEAM} so it carries the revision it was read at"
    )


def test_the_invoice_creation_service_routes_through_the_repository_guard() -> None:
    """The catalogue creation service must not rebuild and save the catalogue itself.

    This service is the one singleton mutator that lives in the APPLICATION
    layer rather than behind a repository verb, so the repository-seam gates
    above cannot see it. It was the last unguarded singleton write: the
    catalogue composes the enveloped persistence, which carried no guarded seam
    until one was ported to it, and two operators creating different invoices
    lost one silently.

    Asserted on spelling, with the same limits the module docstring states.
    ``test_invoices_concurrent_create`` is what measures the behaviour.
    """
    from .....application.invoices._creation import create_catalogue_invoice

    source = inspect.getsource(create_catalogue_invoice)

    assert _GUARDED_SERVICE_SEAM in source, (
        "create_catalogue_invoice does not route through the repository's guarded mutate; "
        "a service that loads, rebuilds and saves the catalogue itself drops a concurrently "
        "created invoice, which under-declares"
    )
    reintroduced = [path for path in ("repo.save(", "repository.save(") if path in source]
    assert not reintroduced, (
        f"create_catalogue_invoice reaches storage directly via {reintroduced}; the guarded "
        f"mutate is the only write path for a singleton catalogue"
    )


def test_the_seam_these_verbs_depend_on_still_exists() -> None:
    """POSITIVE CONTROL for the two gates above.

    Both assert on the presence or absence of substrings. If ``mutate`` were
    renamed or removed, the routing assertion would fail for the right reason
    but the bypass assertion would pass vacuously, and a reader could conclude
    the surface was fine. Pin that the seam is real and is the guarded one.
    """
    from .._secure_model_document import ProfileBareModelSecurePersistence

    mutate = ProfileBareModelSecurePersistence.mutate
    source = inspect.getsource(mutate)

    assert callable(mutate)
    assert "expected_revision_id" in source, (
        "ProfileBareModelSecurePersistence.mutate no longer pins the revision it read; "
        "the verbs routing through it are no longer guarded against lost updates"
    )
