"""Acquire verified runtime wheels and maintain the bounded digest cache."""

from __future__ import annotations

import contextlib
import hashlib
import os
import shutil
import uuid
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.client import HTTPConnection, HTTPSConnection
from pathlib import Path
from typing import Final
from urllib.parse import urlsplit

from cadrumo.core.directory_scan import scan_directory
from dev.cache_root import dev_cache_dir

from .hashing import sha256_path
from .runtime_wheelhouse_contract import (
    LockedWheel,
    RuntimeWheelhousePlan,
)

_DOWNLOAD_TIMEOUT_SECONDS: Final[float] = 180.0
_DOWNLOAD_WORKERS: Final[int] = 8
_CACHE_DIR_ENV: Final[str] = "CADRUMO_RUNTIME_WHEEL_CACHE_DIR"
_CACHE_BYTES_ENV: Final[str] = "CADRUMO_RUNTIME_WHEEL_CACHE_BYTES"
_DEFAULT_CACHE_BYTES: Final[int] = 8 * 1024**3


def _wheel_http_request(url: str) -> tuple[HTTPConnection, str]:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise SystemExit(f"runtime lock wheel URL is not an HTTP(S) resource: {url!r}")
    try:
        port = parsed.port
    except ValueError as error:
        raise SystemExit(f"runtime lock wheel URL has an invalid port: {url!r}") from error
    connection_type = HTTPSConnection if parsed.scheme == "https" else HTTPConnection
    request_path = parsed.path or "/"
    if parsed.query:
        request_path = f"{request_path}?{parsed.query}"
    connection = connection_type(parsed.hostname, port, timeout=_DOWNLOAD_TIMEOUT_SECONDS)
    return connection, request_path


def _download(wheel: LockedWheel, destination: Path) -> None:
    digest = hashlib.sha256()
    size = 0
    connection, request_path = _wheel_http_request(wheel.url)
    try:
        connection.request("GET", request_path, headers={"User-Agent": "cadrumo-runtime-wheelhouse"})
        response = connection.getresponse()
        if response.status < 200 or response.status >= 300:
            raise SystemExit(
                f"runtime wheel download failed for {wheel.filename!r}: HTTP {response.status} {response.reason}"
            )
        with response, destination.open("xb") as handle:
            while chunk := response.read(1024 * 1024):
                handle.write(chunk)
                digest.update(chunk)
                size += len(chunk)
    finally:
        connection.close()
    if size != wheel.size or digest.hexdigest() != wheel.sha256:
        destination.unlink(missing_ok=True)
        raise SystemExit(
            f"downloaded runtime wheel drifted for {wheel.filename!r}: "
            f"expected size/digest {wheel.size}/{wheel.sha256}, got {size}/{digest.hexdigest()}"
        )


def wheel_cache_dir() -> Path | None:
    """Return the runner-local wheel cache directory, or ``None`` when disabled.

    Follows the proof cache's convention: an explicit
    ``CADRUMO_RUNTIME_WHEEL_CACHE_DIR`` wins, otherwise the checkout's own
    ``.cache/runtime-wheel-cache`` holds it.
    Setting the variable to an empty value disables caching outright, which is
    what a run that must prove it fetched from the index sets.

    The cache is safe by construction rather than by policy: every entry is
    named for the SHA-256 the lock records, and is re-hashed against that name
    before it is served. There is no invalidation question to get wrong -- a
    lock change asks for a different digest, so it addresses a different entry.
    """
    override = os.environ.get(_CACHE_DIR_ENV)
    if override is not None:
        return Path(override) if override.strip() else None
    return dev_cache_dir("runtime-wheel-cache")


def _cache_entry(cache: Path, wheel: LockedWheel) -> Path:
    return cache / wheel.sha256


def _serve_from_cache(cache: Path | None, wheel: LockedWheel, destination: Path) -> bool:
    """Copy ``wheel`` out of ``cache`` when the cached bytes still prove out."""
    if cache is None:
        return False
    entry = _cache_entry(cache, wheel)
    try:
        if entry.stat().st_size != wheel.size or sha256_path(entry) != wheel.sha256:
            return False
        shutil.copyfile(entry, destination)
    except OSError:
        return False
    return True


def _store_in_cache(cache: Path | None, wheel: LockedWheel, source: Path) -> None:
    """Publish verified bytes into the cache, tolerating any storage refusal.

    Written to a neighbour unique to this WRITE and moved into place, so a
    reader never observes a partially written entry, and a loser of a race
    between two writers overwrites an identical file rather than corrupting
    one. Unique per write rather than per process, because the writers that
    meet here most often are threads of one process: the runtimes select the
    same universal wheels, so a process identifier alone gave several workers
    one staging path, and on Windows the ensuing replace fails with a sharing
    violation that this function then swallows.
    """
    if cache is None:
        return
    entry = _cache_entry(cache, wheel)
    staging = entry.with_name(f".{entry.name}.{os.getpid()}.{uuid.uuid4().hex}.partial")
    try:
        cache.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, staging)
        staging.replace(entry)
    except OSError:
        with contextlib.suppress(OSError):
            staging.unlink(missing_ok=True)


def _acquire(wheel: LockedWheel, destination: Path, cache: Path | None) -> bool:
    """Place ``wheel``'s exact lock-recorded bytes at ``destination``.

    Returns:
        Whether the bytes came from the cache rather than the index.
    """
    if _serve_from_cache(cache, wheel, destination):
        return True
    _download(wheel, destination)
    _store_in_cache(cache, wheel, destination)
    return False


def grouped_wheel_requests(
    plans: Sequence[RuntimeWheelhousePlan],
) -> tuple[tuple[LockedWheel, tuple[Path, ...]], ...]:
    """Collapse every runtime's selection into one request per distinct wheel.

    Keyed on the lock-recorded SHA-256, which is what makes two runtimes'
    selections the same bytes rather than merely the same filename. The
    destinations are kept in encounter order so the runtime that first asked
    for a wheel is the one it is fetched into.

    Returns:
        One ``(wheel, destinations)`` pair per distinct digest, each carrying
        every runtime directory that wheel belongs in.
    """
    grouped: dict[str, tuple[LockedWheel, list[Path]]] = {}
    for plan in plans:
        for wheel in plan.wheels:
            _selected, destinations = grouped.setdefault(wheel.sha256, (wheel, []))
            destinations.append(Path(plan.python_version) / wheel.filename)
    return tuple((wheel, tuple(destinations)) for wheel, destinations in grouped.values())


def _acquire_group(wheel: LockedWheel, destinations: Sequence[Path], cache: Path | None) -> None:
    """Obtain one wheel's bytes once and place them in every runtime that selected it."""
    primary, *copies = destinations
    _acquire(wheel, primary, cache)
    for copy in copies:
        shutil.copyfile(primary, copy)


def _acquire_all(
    plans: Sequence[RuntimeWheelhousePlan],
    wheel_dir: Path,
    cache: Path | None,
) -> None:
    """Fetch every selected wheel for every runtime, in parallel and once each.

    Two distinct repetitions are removed here. Within one build the runtimes
    overwhelmingly select the SAME universal wheels, so a serial pass over
    ``plans`` fetched identical bytes up to three times.
    :func:`grouped_wheel_requests` collapses that to one fetch plus local
    copies BEFORE anything is submitted. Deduplicating at submission rather
    than leaving it to the cache is what makes the collapse real: three workers
    holding one digest all miss the empty cache together, so each of them
    downloads, and their stores then race for one entry.

    Across builds an unchanged lock asks for exactly the digests the previous
    build already stored, which is the repetition the cache removes.

    Concurrency is deliberately modest. The index is a shared service and the
    work is entirely network-bound, so a small pool removes the round-trip
    stalls without turning a release build into a load generator.
    """
    failures: list[BaseException] = []
    with ThreadPoolExecutor(max_workers=_DOWNLOAD_WORKERS) as pool:
        futures = [
            pool.submit(_acquire_group, wheel, tuple(wheel_dir / relative for relative in destinations), cache)
            for wheel, destinations in grouped_wheel_requests(plans)
        ]
        for future in as_completed(futures):
            try:
                future.result()
            except BaseException as exc:
                # Collected rather than raised here so every worker settles
                # first: a raise inside the pool's context leaves the remaining
                # futures to be cancelled mid-write. The first failure is
                # re-raised below with its own traceback intact.
                failures.append(exc)
    if failures:
        raise failures[0]


def prune_wheel_cache(cache: Path | None, *, limit_bytes: int | None = None) -> int:
    """Evict oldest-first until the cache fits its byte ceiling; return bytes removed.

    Every persistent cache in this repository is bounded. Bounded by BYTES
    rather than by entry count because the entries are wheels spanning four
    orders of magnitude in size, so a count cap says nothing about the disk a
    cache occupies. Eviction is by modification time, which a cache hit does not
    refresh -- an entry's age is therefore its age since it was fetched, and the
    ceiling bounds the store rather than modelling reuse.
    """
    if cache is None:
        return 0
    ceiling = _cache_limit_bytes() if limit_bytes is None else limit_bytes
    try:
        entries = [(path, path.stat()) for path in scan_directory(cache) if path.is_file()]
    except OSError:
        return 0
    total = sum(stat.st_size for _path, stat in entries)
    if total <= ceiling:
        return 0
    removed = 0
    for path, stat in sorted(entries, key=lambda item: item[1].st_mtime):
        if total - removed <= ceiling:
            break
        with contextlib.suppress(OSError):
            path.unlink()
            removed += stat.st_size
    return removed


def _cache_limit_bytes() -> int:
    raw = os.environ.get(_CACHE_BYTES_ENV, "").strip()
    if not raw:
        return _DEFAULT_CACHE_BYTES
    try:
        value = int(raw)
    except ValueError as exc:
        raise SystemExit(f"{_CACHE_BYTES_ENV} must be an integer byte count: {raw!r}") from exc
    if value < 0:
        raise SystemExit(f"{_CACHE_BYTES_ENV} must not be negative: {value}")
    return value
