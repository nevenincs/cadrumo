"""Concurrent readers never observe a half-written registry identity stamp.

The real concurrency shape is one writer and many readers: the release build
stamps once, and every runtime process afterwards reads. So this races a single
rewriting writer against four reading processes and requires every observation
to be a whole stamp or nothing -- never a truncated digest parsed as an identity.

**Why not many concurrent WRITERS.** That was tried first and it is not the
production shape. It also fails on Windows for a reason worth recording: with two
processes replacing the same path, ``os.replace`` raises
``PermissionError [WinError 5]`` when the destination is open elsewhere, so the
writes error rather than interleave. The stamp writer deliberately does NOT
retry or swallow that -- a release build whose stamp failed must say so, because
the verdict is keyed on the identity and a silently unstamped tree would ship a
verdict pointing at a digest with no stamp behind it. The compiled-registry cache
carries a bounded retry on its READ side for the mirror-image of this hazard;
here the reader needs none, because a sharing violation surfaces as an
unreadable stamp and :func:`read_registry_identity_stamp` already answers that
with ``None`` and a walk.

The anti-tautology half -- that a truncated stamp really is refused rather than
parsed -- lives in the durability module. Without it this race would pass no
matter how the writer behaved.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from ..... import __version__
from .....core.atomic_write import atomic_write_best_effort_text
from .._identity import (
    REGISTRY_IDENTITY_SCHEMA_VERSION,
    RegistryIdentityStamp,
    read_registry_identity_stamp,
    registry_identity_stamp_location,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_domain]

_READER_PROCESSES = 4
_READER_WINDOW_SECONDS = 3.0
_WRITER_WINDOW_SECONDS = 4.0
_SUBPROCESS_TIMEOUT_SECONDS = 300
_MINIMUM_READS = 50
"""Both sides run on a CLOCK, not a count, and the writer's window is the longer.

A counted loop does not race here: spawning four interpreters and importing the
package costs about a second, by which time a parent doing a fixed number of
rewrites has already finished, so every read lands on the final payload and the
test proves nothing. Measured -- the counted version passed while observing a
single payload in three consecutive runs. Overlapping windows are what make the
reads actually straddle a rewrite.
"""

_SHORT_DIGEST = "a" * 8
_LONG_DIGEST = "b" * 4096
"""Two payloads of wildly different length.

Length is what makes a torn read DETECTABLE: same-sized payloads written over
each other could interleave into something that still parses, and the test would
pass while exercising nothing. A 4 KB payload replacing an 8-byte one cannot be
mistaken for it.
"""

_CHILD_ROOT_ENV_VAR = "CADRUMO_TEST_IDENTITY_STAMP_ROOT"

_READER_SOURCE = f"""
import json, os, sys, time
from pathlib import Path

from cadrumo.domain.calculations.registry._identity import read_registry_identity_stamp

root = Path(os.environ[{_CHILD_ROOT_ENV_VAR!r}])
observed = []
deadline = time.monotonic() + {_READER_WINDOW_SECONDS}
while time.monotonic() < deadline:
    seen = read_registry_identity_stamp(root)
    observed.append(None if seen is None else [seen.tree_digest, seen.entry_count])
    # A hair of breathing room. Without it four readers hold the file open
    # essentially continuously and the writer cannot land a replace at all,
    # which starves the race rather than intensifying it.
    time.sleep(0.001)

sys.stdout.write(json.dumps(observed))
"""


def _stamp_text(digest: str) -> str:
    """Render one complete, strictly-valid stamp carrying ``digest``."""
    return RegistryIdentityStamp(
        schema_version=REGISTRY_IDENTITY_SCHEMA_VERSION,
        package_version=__version__,
        tree_digest=digest,
        entry_count=len(digest),
    ).model_dump_json()


_WRITE_RETRY_ATTEMPTS = 400
_WRITE_RETRY_DELAY_SECONDS = 0.005


def _write_with_retry(location: Path, text: str) -> None:
    """Replace the stamp, outlasting a reader's transient sharing violation.

    Only the TEST needs this, and the budget is generous for a measured reason:
    on Windows ``os.replace`` raises ``PermissionError [WinError 5]`` while the
    destination is open elsewhere, and four readers looping on one small file
    keep it open almost continuously. A 100 ms budget failed one run in three.
    Two seconds is not papering over a production defect -- production stamps
    once, from the build, with no concurrent reader -- it is what lets the race
    be driven hard enough to mean something without being flaky.
    """
    for attempt in range(_WRITE_RETRY_ATTEMPTS):
        try:
            atomic_write_best_effort_text(location, text, encoding="utf-8")
        except OSError:
            if attempt == _WRITE_RETRY_ATTEMPTS - 1:
                raise
            time.sleep(_WRITE_RETRY_DELAY_SECONDS)
        else:
            return


def test_concurrent_readers_never_observe_a_half_written_stamp(tmp_path: Path) -> None:
    """Every read taken while the stamp is being rewritten is whole, or nothing."""
    root = tmp_path / "registry" / "aeat"
    root.mkdir(parents=True)
    (root / "manifest.toml").write_text("modelos = []\n", encoding="utf-8")
    location = registry_identity_stamp_location(root)
    _write_with_retry(location, _stamp_text(_SHORT_DIGEST))

    env = {**os.environ, _CHILD_ROOT_ENV_VAR: str(root)}
    readers = [
        subprocess.Popen(  # noqa: S603 - fixed interpreter, in-test source, no shell
            [sys.executable, "-c", _READER_SOURCE],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        for _ in range(_READER_PROCESSES)
    ]

    payloads = (_SHORT_DIGEST, _LONG_DIGEST)
    step = 0
    deadline = time.monotonic() + _WRITER_WINDOW_SECONDS
    while time.monotonic() < deadline:
        _write_with_retry(location, _stamp_text(payloads[step % 2]))
        step += 1

    results: list[list[list[object] | None]] = []
    for reader in readers:
        stdout, stderr = reader.communicate(timeout=_SUBPROCESS_TIMEOUT_SECONDS)
        assert reader.returncode == 0, f"a reading child failed: {stderr}"
        results.append(json.loads(stdout))

    reads = [entry for child_reads in results for entry in child_reads]
    assert step > _MINIMUM_READS, f"the writer only managed {step} rewrites; the race window was too short"
    assert len(reads) > _MINIMUM_READS, f"the readers only managed {len(reads)} reads; the race window was too short"

    permitted = {(_SHORT_DIGEST, len(_SHORT_DIGEST)), (_LONG_DIGEST, len(_LONG_DIGEST))}
    observed = {(entry[0], entry[1]) for entry in reads if entry is not None}
    assert observed, "every read returned None; the readers never saw a stamp and so prove nothing"
    assert observed <= permitted, (
        "a reader observed a stamp no writer wrote whole -- a torn write was parsed as an identity"
    )
    assert observed == permitted, (
        "readers only ever saw one payload, so no read landed across a rewrite and the race is vacuous"
    )

    final = read_registry_identity_stamp(root)
    assert final is not None
    assert (final.tree_digest, final.entry_count) in permitted
