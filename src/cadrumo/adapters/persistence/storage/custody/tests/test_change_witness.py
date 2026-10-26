"""A custody observation is answered from memory only while the OS reports nothing changed.

Authority checks read custody at every boundary to see changes another process
published. These cases pin what lets the witness answer from memory instead:
a change made by another process is seen at the next check, a change during a
read is not lost, and anything the witness cannot watch is read every time.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from ..change_witness import CustodyChangeWitness, WatchedDirectory

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


@dataclass
class _Notifications:
    """A notification source whose handles the test signals, for the witness's own logic."""

    openable: bool = True
    unopenable: frozenset[Path] = frozenset()
    rearmable: bool = True
    broken: bool = False
    signals: dict[int, bool] = field(default_factory=dict)
    rearmed: list[int] = field(default_factory=list)
    closed: list[int] = field(default_factory=list)
    opened: int = 0

    def open(self, directory: WatchedDirectory) -> int | None:
        if not self.openable or directory.path in self.unopenable:
            return None
        self.opened += 1
        self.signals[self.opened] = False
        return self.opened

    def signaled(self, handle: int) -> bool | None:
        return None if self.broken else self.signals[handle]

    def rearm(self, handle: int) -> bool:
        self.rearmed.append(handle)
        self.signals[handle] = False
        return self.rearmable

    def close(self, handle: int) -> None:
        self.closed.append(handle)

    def change(self) -> None:
        for handle in self.signals:
            self.signals[handle] = True


class _Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


class _Reads:
    def __init__(self) -> None:
        self.count = 0

    def __call__(self) -> int:
        self.count += 1
        return self.count


def _witness(notifications: _Notifications, clock: _Clock | None = None) -> CustodyChangeWitness[int]:
    return CustodyChangeWitness(
        (WatchedDirectory(Path("custody"), subtree=True), WatchedDirectory(Path("bucket"), subtree=False)),
        maximum_age=0.5,
        monotonic=clock or _Clock(),
        notifications=notifications,
    )


def test_an_unchanged_observation_is_answered_without_reading() -> None:
    notifications, reads = _Notifications(), _Reads()
    witness = _witness(notifications)
    assert [witness.observe(reads) for _ in range(5)] == [1, 1, 1, 1, 1]
    assert reads.count == 1


def test_a_reported_change_is_re_armed_before_the_read_it_triggers() -> None:
    notifications = _Notifications()
    witness = _witness(notifications)
    witness.observe(_Reads())

    def read_after_rearm() -> int:
        assert notifications.rearmed == [1, 2], "the read began before every notification was re-armed"
        return 7

    notifications.change()
    assert witness.observe(read_after_rearm) == 7


def test_a_change_during_a_read_is_seen_by_the_next_check() -> None:
    notifications, reads = _Notifications(), _Reads()
    witness = _witness(notifications)

    def read_while_changing() -> int:
        notifications.change()
        return reads()

    assert witness.observe(read_while_changing) == 1
    assert witness.observe(reads) == 2


def test_an_observation_older_than_its_maximum_age_is_read_again() -> None:
    notifications, reads, clock = _Notifications(), _Reads(), _Clock()
    witness = _witness(notifications, clock)
    witness.observe(reads)
    clock.now += 0.49
    assert witness.observe(reads) == 1
    clock.now += 0.01
    assert witness.observe(reads) == 2


def test_an_aged_observation_is_kept_while_its_unnotified_probe_answers_the_same() -> None:
    notifications, reads, clock = _Notifications(), _Reads(), _Clock()
    native = ["anchor-1"]
    probes: list[str] = []

    def probe() -> str:
        probes.append(native[0])
        return native[0]

    witness = CustodyChangeWitness(
        (WatchedDirectory(Path("custody"), subtree=True),),
        maximum_age=0.5,
        unnotified=probe,
        monotonic=clock,
        notifications=notifications,
    )
    assert [witness.observe(reads) for _ in range(3)] == [1, 1, 1]
    assert probes == ["anchor-1"], "a young observation needs no probe"
    clock.now += 0.5
    assert witness.observe(reads) == 1
    assert len(probes) == 2
    clock.now += 0.49
    assert witness.observe(reads) == 1
    assert len(probes) == 2, "a kept observation ages again from its last probe"
    native[0] = "anchor-2"
    clock.now += 0.01
    assert witness.observe(reads) == 2
    notifications.change()
    assert witness.observe(reads) == 3, "a directory change reads whatever the probe answers"


def test_a_read_that_raises_is_not_held() -> None:
    notifications = _Notifications()
    witness = _witness(notifications)

    def refuse() -> int:
        raise OSError("custody unavailable")

    with pytest.raises(OSError, match="custody unavailable"):
        witness.observe(refuse)
    assert witness.observe(_Reads()) == 1


def test_an_invalidation_during_a_read_discards_what_that_read_returned() -> None:
    notifications, reads = _Notifications(), _Reads()
    witness = _witness(notifications)

    def read_while_publishing() -> int:
        witness.invalidate()
        return reads()

    assert witness.observe(read_while_publishing) == 1
    assert witness.observe(reads) == 2


def test_an_owner_publication_is_read_at_the_next_check() -> None:
    notifications, reads = _Notifications(), _Reads()
    witness = _witness(notifications)
    witness.observe(reads)
    witness.invalidate()
    assert witness.observe(reads) == 2


def test_a_directory_that_cannot_be_watched_is_read_every_time() -> None:
    notifications, reads = _Notifications(openable=False), _Reads()
    witness = _witness(notifications)
    assert [witness.observe(reads) for _ in range(3)] == [1, 2, 3]


def test_a_directory_created_by_a_read_is_watched_from_the_next_check() -> None:
    notifications, reads = _Notifications(openable=False), _Reads()
    witness = _witness(notifications)

    def read_creating_the_directory() -> int:
        notifications.openable = True
        return reads()

    assert witness.observe(read_creating_the_directory) == 1
    assert witness.observe(reads) == 2
    assert notifications.opened == 2
    assert witness.observe(reads) == 2


def test_a_partly_opened_watch_closes_what_it_opened() -> None:
    notifications = _Notifications(unopenable=frozenset({Path("bucket")}))
    witness = _witness(notifications)
    reads = _Reads()
    assert [witness.observe(reads) for _ in range(2)] == [1, 2]
    assert notifications.closed == [1, 2]


@pytest.mark.parametrize("failure", ["broken", "rearm"])
def test_a_failed_notification_stops_answering_from_memory(failure: str) -> None:
    notifications, reads = _Notifications(), _Reads()
    witness = _witness(notifications)
    witness.observe(reads)
    if failure == "broken":
        notifications.broken = True
    else:
        notifications.rearmable = False
        notifications.change()
    assert witness.observe(reads) == 2
    assert sorted(notifications.closed) == [1, 2]


def test_a_closed_witness_reads_every_time() -> None:
    notifications, reads = _Notifications(), _Reads()
    witness = _witness(notifications)
    witness.observe(reads)
    witness.close()
    assert [witness.observe(reads) for _ in range(2)] == [2, 3]
    assert sorted(notifications.closed) == [1, 2]


_native = pytest.mark.skipif(sys.platform != "win32", reason="directory change notifications are a Windows source")


def _in_another_process(code: str, *arguments: Path) -> None:
    subprocess.run([sys.executable, "-I", "-c", code, *map(str, arguments)], check=True, timeout=60)  # noqa: S603


@_native
def test_another_process_writing_a_watched_record_is_seen_at_the_next_check(tmp_path: Path) -> None:
    custody = tmp_path / "custody"
    custody.mkdir()
    (custody / "profile-lock.json").write_text("0", encoding="utf-8")
    witness: CustodyChangeWitness[int] = CustodyChangeWitness(
        (WatchedDirectory(custody, subtree=True),), maximum_age=60
    )
    record = custody / "profile-lock.json"

    def read() -> int:
        return int(record.read_text(encoding="utf-8"))

    assert witness.observe(read) == 0
    _in_another_process("import sys, pathlib; pathlib.Path(sys.argv[1]).write_text('1', encoding='utf-8')", record)
    assert witness.observe(read) == 1
    witness.close()


@_native
def test_another_process_replacing_a_record_by_rename_is_seen_at_the_next_check(tmp_path: Path) -> None:
    bucket = tmp_path / "bucket"
    bucket.mkdir()
    marker = bucket / "profile.commit.v1.json"
    marker.write_text("0", encoding="utf-8")
    witness: CustodyChangeWitness[int] = CustodyChangeWitness(
        (WatchedDirectory(bucket, subtree=False),), maximum_age=60
    )

    def read() -> int:
        return int(marker.read_text(encoding="utf-8"))

    assert witness.observe(read) == 0
    _in_another_process(
        "import os, sys, pathlib\n"
        "target = pathlib.Path(sys.argv[1]); staged = target.with_suffix('.tmp')\n"
        "staged.write_text('2', encoding='utf-8'); os.replace(staged, target)",
        marker,
    )
    assert witness.observe(read) == 2
    witness.close()


@_native
def test_a_change_deep_in_a_watched_subtree_is_seen(tmp_path: Path) -> None:
    automation = tmp_path / "automation"
    nested = automation / "grants" / "a"
    nested.mkdir(parents=True)
    reads = _Reads()
    witness: CustodyChangeWitness[int] = CustodyChangeWitness(
        (WatchedDirectory(automation, subtree=True),), maximum_age=60
    )
    assert witness.observe(reads) == 1
    assert witness.observe(reads) == 1
    _in_another_process("import sys, pathlib; (pathlib.Path(sys.argv[1]) / 'grant.json').write_text('x')", nested)
    assert witness.observe(reads) == 2
    witness.close()


@_native
def test_a_missing_directory_is_read_at_every_check(tmp_path: Path) -> None:
    reads = _Reads()
    witness: CustodyChangeWitness[int] = CustodyChangeWitness(
        (WatchedDirectory(tmp_path / "absent", subtree=True),), maximum_age=60
    )
    assert [witness.observe(reads) for _ in range(3)] == [1, 2, 3]
    witness.close()
