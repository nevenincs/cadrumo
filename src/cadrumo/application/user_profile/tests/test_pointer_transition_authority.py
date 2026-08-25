"""Current active-profile pointer transition authority contracts."""

from __future__ import annotations

from multiprocessing import get_context
from pathlib import Path
from typing import Any

import pytest

from ....core.bucket_pointer import BucketPointer, pointer_path, read_pointer
from ..profile_pointer import (
    ActiveProfilePointerTransactionError,
    active_profile_pointer_transaction,
    observe_active_profile_pointer,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_A = "11111111-1111-4111-8111-111111111111"
_B = "22222222-2222-4222-8222-222222222222"


def _select_b_then_a_in_child(root_text: str, result_queue: Any) -> None:
    """Publish two real transitions from one fresh interpreter."""
    from ....tests.profile_persistence import composed_profile_persistence_ports
    from ..profile_pointer import active_profile_pointer_transaction as transaction_context

    with composed_profile_persistence_ports(), transaction_context(Path(root_text)) as transaction:
        selected_b = transaction.select(_B)
        selected_a = transaction.select(_A)
    result_queue.put((selected_b, selected_a))


def test_absence_idempotence_and_restore_keep_one_durable_lineage(tmp_path: Path) -> None:
    """A clear tombstone and restore never erase or reuse a coordinate."""
    assert observe_active_profile_pointer(tmp_path) == BucketPointer.absent(transition_revision=0)

    with active_profile_pointer_transaction(tmp_path) as transaction:
        assert transaction.clear() == BucketPointer.absent(transition_revision=0)
        selected_a = transaction.select(_A)
        assert transaction.select(_A) == selected_a
        selected_b = transaction.select(_B)
        restored_a = transaction.compare_and_restore(expected=selected_b, captured=selected_a)
        tombstone = transaction.clear()
        assert transaction.clear() == tombstone

    assert selected_a.transition_revision == 1
    assert selected_b.transition_revision == 2
    assert restored_a.bucket_id == _A
    assert restored_a.transition_revision == 3
    assert tombstone == BucketPointer.absent(transition_revision=4)
    assert pointer_path(tmp_path).is_file(), "clear must retain an explicit durable tombstone"
    assert read_pointer(tmp_path) == tombstone


def test_real_child_a_to_b_to_a_advances_every_transition_and_refuses_stale_aba(tmp_path: Path) -> None:
    """A real spawned process cannot turn A→B→A into the original A witness."""
    with active_profile_pointer_transaction(tmp_path) as transaction:
        initial_a = transaction.select(_A)

    context = get_context("spawn")
    result_queue = context.Queue()
    child = context.Process(target=_select_b_then_a_in_child, args=(str(tmp_path), result_queue))
    child.start()
    child.join(30)

    assert child.exitcode == 0
    selected_b, selected_a_again = result_queue.get(timeout=10)
    assert selected_b.bucket_id == _B
    assert selected_b.transition_revision == initial_a.transition_revision + 1
    assert selected_a_again.bucket_id == _A
    assert selected_a_again.transition_revision == initial_a.transition_revision + 2
    assert selected_a_again != initial_a
    assert observe_active_profile_pointer(tmp_path) == selected_a_again

    with (
        active_profile_pointer_transaction(tmp_path) as transaction,
        pytest.raises(ActiveProfilePointerTransactionError),
    ):
        transaction.compare_and_select(expected=initial_a, bucket_id=_B)


def test_defining_modules_are_the_only_public_pointer_transition_surface() -> None:
    """Only defining modules own pointer contracts; package namespaces are inert."""
    import cadrumo.application.user_profile as user_profile
    import cadrumo.core as core
    from cadrumo.application.user_profile import profile_pointer
    from cadrumo.core import bucket_pointer

    assert profile_pointer.active_profile_pointer_transaction.__module__.endswith("profile_pointer")
    assert profile_pointer.observe_active_profile_pointer.__module__.endswith("profile_pointer")
    assert profile_pointer.ActiveProfilePointerTransaction.__module__.endswith("profile_pointer")
    assert bucket_pointer.BucketPointer.__module__.endswith("bucket_pointer")
    for forbidden_name in (
        "active_profile_pointer_transaction",
        "observe_active_profile_pointer",
        "ActiveProfilePointerTransaction",
        "BucketPointer",
        "read_pointer",
        "write_pointer",
    ):
        assert not hasattr(user_profile, forbidden_name)
        assert not hasattr(core, forbidden_name)
    for retired_name in (
        "ProfileCustodyPointerSnapshot",
        "compare_and_swap_profile_pointer",
        "capture_pointer",
        "restore_pointer",
        "clear_pointer",
    ):
        assert retired_name not in user_profile.__all__
        assert not hasattr(user_profile, retired_name)
    for retired_name in ("capture_pointer", "restore_pointer", "clear_pointer"):
        assert retired_name not in core.__all__
        assert not hasattr(core, retired_name)


def test_only_the_transaction_owner_calls_the_low_level_pointer_writer() -> None:
    """Production source has one anchored writer owner, not an empty scan."""
    source_root = Path(__file__).parents[3]
    transaction_source = source_root / "application" / "user_profile" / "profile_pointer.py"
    writer_callers = {
        source
        for source in source_root.rglob("*.py")
        if "tests" not in source.parts
        and any(
            line.lstrip().startswith("write_pointer(")
            for line in source.read_text(encoding="utf-8").splitlines()
        )
    }

    assert transaction_source in writer_callers
    assert writer_callers == {transaction_source}
