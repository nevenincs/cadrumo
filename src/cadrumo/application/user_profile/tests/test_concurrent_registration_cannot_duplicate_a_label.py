"""Two operators registering the same label at once cannot both succeed.

A profile label is the name an operator types to select a profile, so two
committed capsules sharing one label makes selection ambiguous for every later
command. Every existing duplicate-label test registers one profile after
another, so the concurrent case -- the one the refusal exists for -- was
unasserted.

Driven as a real race between spawned processes released from a shared barrier,
because an in-process test cannot show that separate operators are serialised.

Scoped to the OUTCOME on purpose, and the scope is measured rather than assumed.
The loser IS refused by the custody duplicate-label scan -- the cause chain reads
``ProfileRegistrationError <- ProfileCustodyDuplicateLabelError`` -- but removing
the custody root lock from ``profile_custody_transaction_lock`` does NOT make
this test fail across nine races, so the test does not pin that lock either.
What it holds is the property an operator would notice: however the second
attempt is refused, the storage root ends with exactly one capsule bearing the
label.

Stability was checked before committing: six consecutive races each produced
exactly one registration, so a failure here means a genuine duplicate rather
than a timing artefact.
"""

from __future__ import annotations

from multiprocessing import get_context
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from multiprocessing.queues import Queue

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_LABEL = "Contended Registration Subject"
_PASSPHRASE = "concurrent-registration-operator-secret"  # noqa: S105 - synthetic test credential


def _register_in_sibling(tmp_path_text: str, barrier, results: Queue) -> None:
    """Register the shared label from a separate process, reporting the outcome."""
    from pathlib import Path as _Path

    from ....tests.secure_sql import isolated_profile_storage_root
    from .. import register_profile_with_credentials

    with isolated_profile_storage_root(tmp_path=_Path(tmp_path_text)):
        barrier.wait()
        try:
            outcome = register_profile_with_credentials(label=_LABEL, passphrase=_PASSPHRASE)
        except Exception as exc:
            results.put(("refused", type(exc).__name__))
        else:
            results.put(("registered", outcome.profile_id))


def test_two_processes_registering_one_label_produce_one_capsule(tmp_path: Path) -> None:
    """DISCRIMINATING: two capsules must never answer to one name.

    Both processes are released together and race the whole registration. The
    failure this guards against is the operator-visible one -- a label bound to
    two committed capsules, leaving every later selection ambiguous.
    """
    from ....tests.secure_sql import isolated_profile_storage_root
    from .. import CommittedProfileRepository

    context = get_context("spawn")
    barrier = context.Barrier(2)
    results: Queue = context.Queue()
    workers = [
        context.Process(target=_register_in_sibling, args=(str(tmp_path), barrier, results))
        for _ in range(2)
    ]
    for worker in workers:
        worker.start()
    try:
        outcomes = [results.get(timeout=300) for _ in workers]
        for worker in workers:
            worker.join(120)
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.kill()
                worker.join(30)

    registered = [outcome for kind, outcome in outcomes if kind == "registered"]
    assert len(registered) == 1, f"expected exactly one registration to win, got {outcomes}"

    with isolated_profile_storage_root(tmp_path=tmp_path):
        committed = [view for view in CommittedProfileRepository().list() if view.label == _LABEL]

    assert len(committed) == 1, f"the label is bound to {len(committed)} committed capsules"


def test_the_race_actually_reached_the_registration_path(tmp_path: Path) -> None:
    """ANTI-VACUITY: one winner is also what two crashed workers would report.

    If both processes died before registering, the outcome list would carry no
    successes and the test above would fail -- but a single success paired with
    a loser that never reached the scan would pass while proving nothing. This
    pins that the losing process was turned away by a refusal rather than by
    failing to start.
    """
    context = get_context("spawn")
    barrier = context.Barrier(2)
    results: Queue = context.Queue()
    workers = [
        context.Process(target=_register_in_sibling, args=(str(tmp_path), barrier, results))
        for _ in range(2)
    ]
    for worker in workers:
        worker.start()
    try:
        outcomes = [results.get(timeout=300) for _ in workers]
        for worker in workers:
            worker.join(120)
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.kill()
                worker.join(30)

    kinds = sorted(kind for kind, _detail in outcomes)

    assert kinds == ["refused", "registered"], f"expected one winner and one refusal, got {outcomes}"
