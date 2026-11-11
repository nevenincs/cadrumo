"""The run artifact cache publishes each key once and serves only verified entries."""

from __future__ import annotations

import os
import shutil
import sys
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from .audited_process import run_audited_process
from .run_artifact import run_artifact, run_scoped_digest

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


# The digest analogue of _RACER: the first process computes inside the lock and
# blocks until the second signals from inside run_scoped_digest, past its
# unlocked read. The second must then read the first one's record, never
# compute its own -- the snapshot a mid-run edit would otherwise split.
_DIGEST_RACER = """
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


def compute():
    with (signals / "compute-calls").open("a") as stream:
        stream.write(role + "\\n")
    if role == "first":
        (signals / "computing").touch()
        guard = time.monotonic() + 120
        while not (signals / "contender-waiting").exists():
            if time.monotonic() > guard:
                raise SystemExit("hang guard: the contender never signalled")
            time.sleep(0.01)
    return "digestof" + role


print(cache.run_scoped_digest("inputs", compute, cache_root=cache_root))
"""


def test_racing_processes_key_one_run_on_the_first_process_s_digest(tmp_path: Path) -> None:
    cache_root, signals = tmp_path / "cache", tmp_path / "signals"
    signals.mkdir()

    def run(role: str):
        return run_audited_process(
            [sys.executable, "-c", _DIGEST_RACER, str(cache_root), str(signals), role],
            capture_output=True,
            text=True,
            timeout=180,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(run, "first")
        guard = time.monotonic() + 120
        while not (signals / "computing").exists():
            assert not first.done(), first.result().stderr
            assert time.monotonic() < guard, "hang guard: the first process never signalled"
            time.sleep(0.01)
        contender = pool.submit(run, "contender")
        outcomes = [first.result(), contender.result()]

    assert [outcome.returncode for outcome in outcomes] == [0, 0], [outcome.stderr for outcome in outcomes]
    assert (signals / "compute-calls").read_text().splitlines() == ["first"]
    assert [str(outcome.stdout).strip() for outcome in outcomes] == ["digestoffirst", "digestoffirst"]


def test_a_recorded_digest_is_read_without_computing_and_kinds_are_separate(tmp_path: Path) -> None:
    calls: list[str] = []

    def compute(value: str):
        def digest() -> str:
            calls.append(value)
            return value

        return digest

    assert run_scoped_digest("site", compute("aaaa"), cache_root=tmp_path) == "aaaa"
    assert run_scoped_digest("site", compute("bbbb"), cache_root=tmp_path) == "aaaa"
    assert run_scoped_digest("stubs", compute("cccc"), cache_root=tmp_path) == "cccc"
    assert calls == ["aaaa", "cccc"]


def test_a_digest_that_is_not_alphanumeric_is_refused_and_never_recorded(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="alphanumeric"):
        run_scoped_digest("site", lambda: "not/a/digest", cache_root=tmp_path)

    assert run_scoped_digest("site", lambda: "abcd", cache_root=tmp_path) == "abcd"


def test_an_entry_another_worker_retires_during_retirement_is_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[Path] = []
    for digest in ("aaaa", "bbbb"):
        run_artifact("kind", digest, publish=_counting_publisher(calls), verify=_verify, cache_root=tmp_path)
    victim = tmp_path / "kind" / "aaaa"
    assert victim.is_dir()
    real_iterdir = Path.iterdir

    def listing_raced_by_another_retirement(path: Path) -> Iterator[Path]:
        # Another worker removes the entry once this worker has listed it, before it reads the entry's age.
        for entry in real_iterdir(path):
            yield entry
            if entry == victim and os.path.isdir(victim):
                shutil.rmtree(victim)

    monkeypatch.setattr(Path, "iterdir", listing_raced_by_another_retirement)
    newest = run_artifact(
        "kind", "cccc", publish=_counting_publisher(calls), verify=_verify, cache_root=tmp_path, retain=3
    )

    assert newest.published_by_this_call
    assert not victim.exists()
    assert (tmp_path / "kind" / "bbbb").is_dir()
