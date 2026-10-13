"""A peer is its OS owner and process; the program path beside them is evidence for a person, not identity."""

import pytest

from ..contracts import RuntimePeer

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_two_reads_of_one_process_are_one_peer_whatever_path_each_read() -> None:
    first = RuntimePeer(os_owner_id="S-1-5-21-1", process_id=41, image_path=r"C:\Tools\current\agent.exe")
    # A link in the path replaced between two reads names the same process differently.
    second = RuntimePeer(os_owner_id="S-1-5-21-1", process_id=41, image_path=r"C:\Tools\2.1\agent.exe")
    unread = RuntimePeer(os_owner_id="S-1-5-21-1", process_id=41)
    assert first == second == unread
    assert len({first, second, unread}) == 1


@pytest.mark.parametrize(
    "other",
    [
        RuntimePeer(os_owner_id="S-1-5-21-1", process_id=42, image_path=r"C:\Tools\current\agent.exe"),
        RuntimePeer(os_owner_id="S-1-5-21-2", process_id=41, image_path=r"C:\Tools\current\agent.exe"),
    ],
    ids=["another_process", "another_owner"],
)
def test_the_same_program_in_another_process_or_owner_is_another_peer(other: RuntimePeer) -> None:
    peer = RuntimePeer(os_owner_id="S-1-5-21-1", process_id=41, image_path=r"C:\Tools\current\agent.exe")
    assert peer != other
    assert peer != object()
