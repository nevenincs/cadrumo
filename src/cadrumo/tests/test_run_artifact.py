"""The run artifact cache publishes each key once and serves only verified entries."""

from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from .audited_process import run_audited_process
from .run_artifact import run_artifact

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PAYLOAD = b"artifact bytes"

# Process A publishes and, inside its publisher, signals "publishing" and then
# blocks until B signals "contender-waiting". B is started only after A's
# signal, so the entry cannot exist yet; B raises its signal from inside
# run_artifact, past the unlocked pre-check, as it asks for the lock. Under the
# lock B therefore waits for A and reuses its entry; without it, B publishes
# too. Deadlines are hang guards only.
_RACER = """
import sys
import time
from pathlib import Path

from cadrumo.tests import run_artifact as cache

cache_root, signals, role = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
lock = cache.exclusive_file_lock


def signalled_lock(*args, **kwargs):
    if role == "contender":
        (signals / "contender-waiting").touch()
    return lock(*args, **kwargs)


cache.exclusive_file_lock = signalled_lock


def publish(staging):
    with (signals / "publisher-calls").open("a") as stream:
        stream.write(role + "\\n")
    if role == "publisher":
        (signals / "publishing").touch()
        guard = time.monotonic() + 120
        while not (signals / "contender-waiting").exists():
            if time.monotonic() > guard:
                raise SystemExit("hang guard: the contender never signalled")
            time.sleep(0.01)
    (staging / "payload").write_bytes(b"artifact bytes")


artifact = cache.run_artifact(
    "race",
    "samekey",
    publish=publish,
    verify=lambda root: (root / "payload").is_file() and (root / "payload").read_bytes() == b"artifact bytes",
    cache_root=cache_root,
)
print(artifact.published_by_this_call)
"""


def _verify(root: Path) -> bool:
    payload = root / "payload"
    return payload.is_file() and payload.read_bytes() == _PAYLOAD


def _counting_publisher(calls: list[Path]):
    def publish(staging: Path) -> None:
        calls.append(staging)
        (staging / "payload").write_bytes(_PAYLOAD)

    return publish


def test_two_racing_processes_publish_the_same_key_exactly_once(tmp_path: Path) -> None:
    cache_root, signals = tmp_path / "cache", tmp_path / "signals"
    signals.mkdir()

    def run(role: str):
        return run_audited_process(
            [sys.executable, "-c", _RACER, str(cache_root), str(signals), role],
            capture_output=True,
            text=True,
            timeout=180,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        publisher = pool.submit(run, "publisher")
        guard = time.monotonic() + 120
        while not (signals / "publishing").exists():
            assert not publisher.done(), publisher.result().stderr
            assert time.monotonic() < guard, "hang guard: the publisher never signalled"
            time.sleep(0.01)
        contender = pool.submit(run, "contender")
        outcomes = [publisher.result(), contender.result()]

    assert (signals / "publisher-calls").read_text().splitlines() == ["publisher"]
    assert [outcome.returncode for outcome in outcomes] == [0, 0], [outcome.stderr for outcome in outcomes]
    assert [str(outcome.stdout).strip() for outcome in outcomes] == ["True", "False"]
    assert (cache_root / "race" / "samekey" / "payload").read_bytes() == _PAYLOAD


def test_an_entry_that_fails_verification_is_removed_and_published_again(tmp_path: Path) -> None:
    calls: list[Path] = []
    first = run_artifact("kind", "key", publish=_counting_publisher(calls), verify=_verify, cache_root=tmp_path)
    (first.root / "payload").write_bytes(b"corrupted")
    (first.root / "stray").write_bytes(b"left by the corrupted entry")

    again = run_artifact("kind", "key", publish=_counting_publisher(calls), verify=_verify, cache_root=tmp_path)

    assert again.published_by_this_call
    assert len(calls) == 2
    assert again.root == first.root
    assert (again.root / "payload").read_bytes() == _PAYLOAD
    assert not (again.root / "stray").exists()


def test_a_publisher_that_raises_leaves_nothing_and_the_next_caller_publishes_cleanly(tmp_path: Path) -> None:
    def failing(staging: Path) -> None:
        (staging / "payload").write_bytes(b"half written")
        raise RuntimeError("publisher failed")

    with pytest.raises(RuntimeError, match="publisher failed"):
        run_artifact("kind", "key", publish=failing, verify=_verify, cache_root=tmp_path)
    assert [path.name for path in (tmp_path / "kind").iterdir() if path.is_dir()] == []

    calls: list[Path] = []
    published = run_artifact("kind", "key", publish=_counting_publisher(calls), verify=_verify, cache_root=tmp_path)
    assert published.published_by_this_call
    assert len(calls) == 1
    assert sorted(path.name for path in published.root.iterdir()) == ["payload"]


def test_different_digests_get_different_entries_and_a_repeat_is_reused(tmp_path: Path) -> None:
    calls: list[Path] = []
    first = run_artifact("kind", "aaaa", publish=_counting_publisher(calls), verify=_verify, cache_root=tmp_path)
    second = run_artifact("kind", "bbbb", publish=_counting_publisher(calls), verify=_verify, cache_root=tmp_path)
    repeat = run_artifact("kind", "aaaa", publish=_counting_publisher(calls), verify=_verify, cache_root=tmp_path)

    assert first.root != second.root
    assert len(calls) == 2
    assert not repeat.published_by_this_call
    assert repeat.root == first.root


def test_writable_copy_mutations_do_not_reach_the_entry(tmp_path: Path) -> None:
    artifact = run_artifact("kind", "key", publish=_counting_publisher([]), verify=_verify, cache_root=tmp_path / "c")

    copy = artifact.writable_copy(tmp_path / "copy")
    (copy / "payload").write_bytes(b"mutated")
    (copy / "added").write_bytes(b"new file")

    assert (artifact.root / "payload").read_bytes() == _PAYLOAD
    assert not (artifact.root / "added").exists()
    assert _verify(artifact.root)
