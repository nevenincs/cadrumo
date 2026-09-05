"""Detector-teeth tests for runtime-specific sealed dependency wheelhouses."""

from __future__ import annotations

import hashlib
import json
import threading
import zipfile
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from ..._paths import REPO_ROOT
from ..runtime_wheelhouse import (
    PLATFORM_FLOORS,
    SUPPORTED_TARGETS,
    WHEELHOUSE_SCHEMA,
    LockedWheel,
    RuntimeWheelhousePlan,
    _acquire_all,
    _store_in_cache,
    extract_runtime_wheelhouse,
    grouped_wheel_requests,
    load_runtime_wheelhouse,
    plan_runtime_wheelhouses,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_LOCK_SHA256 = "a" * 64


def _runtime_entry(runtime: str, filename: str, payload: bytes) -> dict[str, object]:
    """Build one strict ready entry whose bytes are supplied by the archive."""
    return {
        "platforms": {target.name: {"native-dependency": filename} for target in SUPPORTED_TARGETS},
        "python": runtime,
        "status": "ready",
        "wheels": {
            filename: {
                "distribution": "native-dependency",
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size": len(payload),
                "version": "1.0.0",
            }
        },
    }


#: The wheel names and bytes this fixture seals, shared with the assertions
#: that read them back. They were transcribed a second time inside the test,
#: and one of those copies feeds an ABSENCE claim - a drifted name there
#: would assert the non-existence of a file that could never exist.
_CP313_WHEEL = "native_dependency-1.0.0-cp313-cp313-win_amd64.whl"
_CP314_WHEEL = "native_dependency-1.0.0-cp314-cp314-win_amd64.whl"
_CP313_PAYLOAD = b"sealed cp313 dependency"
_CP314_PAYLOAD = b"sealed cp314 dependency"


def _wheelhouse_fixture(tmp_path: Path) -> Path:
    """Write two runtime closures plus an attributable advisory canary row."""
    cp313_name = _CP313_WHEEL
    cp314_name = _CP314_WHEEL
    cp313_payload = _CP313_PAYLOAD
    cp314_payload = _CP314_PAYLOAD
    manifest = {
        "lock_sha256": _LOCK_SHA256,
        "platform_floors": PLATFORM_FLOORS,
        "runtimes": {
            "3.13": _runtime_entry("3.13", cp313_name, cp313_payload),
            "3.14": _runtime_entry("3.14", cp314_name, cp314_payload),
            "3.15": {
                "missing": [
                    {
                        "distribution": "native-dependency",
                        "platform": "windows-x86-64",
                        "reason": "no-compatible-wheel",
                        "requirement": "native-dependency==1.0.0",
                    }
                ],
                "python": "3.15",
                "status": "missing-wheel",
            },
        },
        "schema": WHEELHOUSE_SCHEMA,
    }
    archive_path = tmp_path / "runtime-wheelhouse.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("runtime-wheelhouse.json", json.dumps(manifest, sort_keys=True))
        archive.writestr(f"wheels/3.13/{cp313_name}", cp313_payload)
        archive.writestr(f"wheels/3.14/{cp314_name}", cp314_payload)
    return archive_path


def test_load_and_extract_select_the_observed_runtime_closure(tmp_path: Path) -> None:
    """A 3.14 extraction cannot accidentally expose the 3.13 wheel bytes."""
    archive = _wheelhouse_fixture(tmp_path)
    loaded = load_runtime_wheelhouse(
        archive,
        expected_lock_sha256=_LOCK_SHA256,
        expected_python="3.14",
    )
    assert loaded.manifest["runtimes"]["3.14"]["status"] == "ready"

    extracted = tmp_path / "extracted-3.14"
    extract_runtime_wheelhouse(archive, extracted, python_version="3.14")
    assert (extracted / _CP314_WHEEL).read_bytes() == _CP314_PAYLOAD
    # The absence claim now names the wheel the fixture actually sealed. As a
    # second transcription it would have held over a renamed file, proving
    # nothing about 3.13 bytes leaking into a 3.14 extraction.
    assert not (extracted / _CP313_WHEEL).exists()


def test_advisory_missing_runtime_is_not_presented_as_ready(tmp_path: Path) -> None:
    """An incomplete 3.15 row remains attributable and cannot be extracted."""
    archive = _wheelhouse_fixture(tmp_path)
    loaded = load_runtime_wheelhouse(archive, expected_lock_sha256=_LOCK_SHA256)
    missing = loaded.manifest["runtimes"]["3.15"]
    assert missing["status"] == "missing-wheel"
    assert missing["missing"][0]["distribution"] == "native-dependency"

    with pytest.raises(SystemExit, match=r"no ready entry for Python 3\.15"):
        load_runtime_wheelhouse(archive, expected_python="3.15")


def test_runtime_wheelhouse_rejects_unmanifested_runtime_member(tmp_path: Path) -> None:
    """A stray runtime wheel cannot cross the sealed archive boundary."""
    archive = _wheelhouse_fixture(tmp_path)
    with zipfile.ZipFile(archive, "a") as bundle:
        bundle.writestr("wheels/3.14/unmanifested.whl", b"stowaway")

    with pytest.raises(SystemExit, match="member inventory drifted"):
        load_runtime_wheelhouse(archive)


def test_current_lock_selects_distinct_stable_runtime_wheels() -> None:
    """The real lock has ready 3.13/3.14 closures and an explicit 3.15 gap."""
    plans = plan_runtime_wheelhouses(REPO_ROOT)
    assert plans["3.13"].missing == ()
    assert plans["3.14"].missing == ()
    assert "cp313-cp313" in plans["3.13"].platforms["linux-x86-64"]["cffi"]
    assert "cp314-cp314" in plans["3.14"].platforms["linux-x86-64"]["cffi"]
    assert {item["distribution"] for item in plans["3.15"].missing} == {"pydantic-core", "pyyaml"}


def _locked_wheel(payload: bytes, url: str) -> LockedWheel:
    return LockedWheel(
        distribution="universal-dependency",
        version="1.0.0",
        filename="universal_dependency-1.0.0-py3-none-any.whl",
        url=url,
        sha256=hashlib.sha256(payload).hexdigest(),
        size=len(payload),
    )


def _plan(runtime: str, wheel: LockedWheel) -> RuntimeWheelhousePlan:
    return RuntimeWheelhousePlan(
        python_version=runtime,
        platforms={target.name: {"universal-dependency": wheel.filename} for target in SUPPORTED_TARGETS},
        wheels=(wheel,),
    )


class _CountingIndex:
    """A real HTTP index that serves one wheel and counts the requests it answers.

    A real socket and a real ``urlopen`` rather than a substituted downloader:
    the property under test is how many times the acquisition reaches the index,
    and a stand-in for the download would be measuring the test's own bookkeeping
    instead of the behaviour.
    """

    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.requests = 0
        index = self

        class _Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                index.requests += 1
                self.send_response(200)
                self.send_header("Content-Length", str(len(index.payload)))
                self.end_headers()
                self.wfile.write(index.payload)

            def log_message(self, *_args: object) -> None:
                return

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def __enter__(self) -> _CountingIndex:
        self._thread.start()
        host, port = self._server.server_address[:2]
        self.url = f"http://{host!s}:{port}/universal_dependency-1.0.0-py3-none-any.whl"
        return self

    def __exit__(self, *_exc: object) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=10)


def test_one_universal_wheel_selected_by_three_runtimes_is_fetched_once(tmp_path: Path) -> None:
    """The saving the acquisition claims is delivered, against a real index.

    Every runtime selects the same ``py3-none-any`` wheel, and all of them are
    submitted into one pool in one process. Deduplicating on the lock-recorded
    digest before submission is what makes the collapse real: without it three
    workers miss the cold cache together, each downloads, and their stores then
    race for one cache entry.
    """
    payload = b"universal wheel bytes"
    cache = tmp_path / "cache"
    wheel_dir = tmp_path / "wheels"
    runtimes = ("3.13", "3.14", "3.15")
    for runtime in runtimes:
        (wheel_dir / runtime).mkdir(parents=True)

    with _CountingIndex(payload) as index:
        wheel = _locked_wheel(payload, index.url)
        _acquire_all([_plan(runtime, wheel) for runtime in runtimes], wheel_dir, cache)

        assert index.requests == 1

    for runtime in runtimes:
        assert (wheel_dir / runtime / wheel.filename).read_bytes() == payload
    assert sorted(path.name for path in cache.iterdir()) == [wheel.sha256]


def test_a_concurrent_cache_store_leaves_no_partial_entry(tmp_path: Path) -> None:
    """Two writers publishing one digest at once both land, and neither is observed partial.

    The staging neighbour is unique per WRITE rather than per process, because
    the writers that meet here are threads of one process. Sharing a staging
    path made the second replace fail with a Windows sharing violation, which
    this function swallows -- so the failure was silent and the entry was
    whichever writer happened to win.
    """
    payload = b"universal wheel bytes"
    cache = tmp_path / "cache"
    source = tmp_path / "source.whl"
    source.write_bytes(payload)
    wheel = _locked_wheel(payload, "http://index.invalid/unused")

    barrier = threading.Barrier(4)

    def store() -> None:
        barrier.wait(timeout=10)
        _store_in_cache(cache, wheel, source)

    with ThreadPoolExecutor(max_workers=4) as pool:
        for future in [pool.submit(store) for _ in range(4)]:
            future.result()

    assert sorted(path.name for path in cache.iterdir()) == [wheel.sha256]
    assert (cache / wheel.sha256).read_bytes() == payload


def test_requests_are_grouped_by_digest_not_by_filename() -> None:
    """Two runtimes selecting the same bytes make one request carrying both destinations.

    Grouped on the lock-recorded digest, which is what makes two selections the
    same bytes; a filename key would collapse two genuinely different wheels
    that happen to share a name.
    """
    same = b"universal wheel bytes"
    other = b"a different wheel entirely"
    universal = _locked_wheel(same, "http://index.invalid/universal")
    native = LockedWheel(
        distribution="native-dependency",
        version="1.0.0",
        filename="universal_dependency-1.0.0-py3-none-any.whl",
        url="http://index.invalid/native",
        sha256=hashlib.sha256(other).hexdigest(),
        size=len(other),
    )

    grouped = grouped_wheel_requests(
        [
            _plan("3.13", universal),
            _plan("3.14", universal),
            RuntimeWheelhousePlan(python_version="3.15", platforms={}, wheels=(native,)),
        ]
    )

    assert [(wheel.sha256, [str(path) for path in destinations]) for wheel, destinations in grouped] == [
        (
            universal.sha256,
            [str(Path("3.13") / universal.filename), str(Path("3.14") / universal.filename)],
        ),
        (native.sha256, [str(Path("3.15") / native.filename)]),
    ]
