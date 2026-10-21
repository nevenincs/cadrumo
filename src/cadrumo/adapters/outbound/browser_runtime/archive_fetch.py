"""Downloading one pinned browser archive, refusing every byte that is not exactly the pinned one.

The vendor installer follows any redirect, to any host and over plain HTTP, and
checks nothing but a length. :func:`fetch_pinned_archive` therefore performs the
download itself: every hop of the redirect chain must be HTTPS to one of the
approved hosts on the default port, the chain is bounded, and the body must be
the pinned size with the pinned SHA-256. Only a file that passed is left at the
destination; any failure removes what was written.
"""

from __future__ import annotations

import hashlib
import ssl
import time
from collections.abc import Callable, Collection
from pathlib import Path
from typing import Final

import httpx

from cadrumo_client.contracts.failure_categories import DependencyFailureCategory

from ....application.browser_archive_pins import BrowserArchivePin
from ....application.dependency_network import DependencyProxy
from ....application.dependency_transfer import (
    DependencyTransferError,
    classify_transfer_exception,
    classify_transfer_status,
)

__all__ = ["ARCHIVE_FETCH_MAX_REDIRECTS", "fetch_pinned_archive"]

#: Hops one download may take before it is refused; the vendor's chains take one.
ARCHIVE_FETCH_MAX_REDIRECTS: Final = 5

_CHUNK_BYTES: Final = 1024 * 1024
_CONNECT_TIMEOUT_S: Final = 15.0
_READ_TIMEOUT_S: Final = 60.0

#: Failures another mirror cannot cure: the bytes, the approval, the disk or the person said no.
_FINAL_FOR_EVERY_SOURCE: Final = frozenset(
    {
        DependencyFailureCategory.DAMAGED_DOWNLOAD,
        DependencyFailureCategory.BLOCKED_BY_NETWORK,
        DependencyFailureCategory.CANCELLED,
        DependencyFailureCategory.DISK_FULL,
        DependencyFailureCategory.NO_PERMISSION,
    }
)


def fetch_pinned_archive(
    pin: BrowserArchivePin,
    destination: Path,
    *,
    allowed_hosts: Collection[str],
    proxy: DependencyProxy | None,
    progress: Callable[[int], None],
    cancelled: Callable[[], bool],
    deadline: float,
    transport: httpx.BaseTransport | None = None,
) -> None:
    """Download ``pin`` to ``destination``, trying its sources in order, and keep it only if it matches.

    ``progress`` receives this archive's bytes received so far. A source that
    fails for a network reason gives way to the next; a mismatch, an
    unapproved hop, a full disk or a cancel ends the download at once.

    Raises:
        DependencyTransferError: The classified failure of the last source tried.
    """
    hosts = frozenset(host.lower() for host in allowed_hosts)
    failure: DependencyTransferError | None = None
    for url in pin.urls:
        try:
            _fetch_from(url, pin, destination, hosts, proxy, progress, cancelled, deadline, transport)
        except DependencyTransferError as error:
            destination.unlink(missing_ok=True)
            if error.category in _FINAL_FOR_EVERY_SOURCE:
                raise
            failure = error
        except BaseException:
            destination.unlink(missing_ok=True)
            raise
        else:
            return
    if failure is None:
        raise DependencyTransferError(DependencyFailureCategory.UNEXPECTED, transient=False)
    raise failure


def _fetch_from(
    url: str,
    pin: BrowserArchivePin,
    destination: Path,
    hosts: frozenset[str],
    proxy: DependencyProxy | None,
    progress: Callable[[int], None],
    cancelled: Callable[[], bool],
    deadline: float,
    transport: httpx.BaseTransport | None,
) -> None:
    current = httpx.URL(url)
    for _hop in range(ARCHIVE_FETCH_MAX_REDIRECTS + 1):
        _admit(current, hosts)
        try:
            with (
                _client(current.host, proxy, transport) as client,
                client.stream("GET", current, headers={"Accept-Encoding": "identity"}) as response,
            ):
                if response.is_redirect:
                    current = response.url.join(response.headers["location"])
                    continue
                refused = classify_transfer_status(response.status_code)
                if refused is not None:
                    raise refused
                if response.status_code != httpx.codes.OK:
                    raise DependencyTransferError(
                        DependencyFailureCategory.UNEXPECTED,
                        transient=False,
                        facts={"http_status": response.status_code},
                    )
                _receive(response, pin, destination, progress, cancelled, deadline)
                return
        except DependencyTransferError:
            raise
        except (httpx.HTTPError, OSError) as error:
            raise classify_transfer_exception(error) from error
    raise _unapproved_source()


def _admit(url: httpx.URL, hosts: frozenset[str]) -> None:
    """Refuse a hop that is not HTTPS to an approved host on the default port, without credentials."""
    port_is_default = url.port is None or url.port == 443
    if url.scheme != "https" or url.host.lower() not in hosts or not port_is_default or url.userinfo:
        raise _unapproved_source()


def _unapproved_source() -> DependencyTransferError:
    return DependencyTransferError(
        DependencyFailureCategory.BLOCKED_BY_NETWORK, transient=False, facts={"unapproved_source": True}
    )


def _client(host: str, proxy: DependencyProxy | None, transport: httpx.BaseTransport | None) -> httpx.Client:
    via = proxy.url(with_credentials=True) if proxy is not None and not proxy.bypasses(host) else None
    return httpx.Client(
        verify=ssl.create_default_context(),
        trust_env=False,
        follow_redirects=False,
        proxy=None if transport is not None else via,
        transport=transport,
        timeout=httpx.Timeout(_READ_TIMEOUT_S, connect=_CONNECT_TIMEOUT_S),
    )


def _receive(
    response: httpx.Response,
    pin: BrowserArchivePin,
    destination: Path,
    progress: Callable[[int], None],
    cancelled: Callable[[], bool],
    deadline: float,
) -> None:
    """Stream the body into ``destination``, refusing it the moment it cannot be the pinned archive."""
    declared = response.headers.get("content-length")
    if declared is not None and declared != str(pin.download_bytes):
        raise _damaged()
    digest = hashlib.sha256()
    received = 0
    with destination.open("xb") as file:
        for chunk in response.iter_raw(_CHUNK_BYTES):
            if cancelled():
                raise DependencyTransferError(DependencyFailureCategory.CANCELLED, transient=False)
            if time.monotonic() >= deadline:
                raise DependencyTransferError(
                    DependencyFailureCategory.HOST_UNREACHABLE, transient=True, facts={"timed_out": True}
                )
            received += len(chunk)
            if received > pin.download_bytes:
                raise _damaged()
            digest.update(chunk)
            file.write(chunk)
            progress(received)
    if received != pin.download_bytes or digest.hexdigest() != pin.sha256:
        raise _damaged()


def _damaged() -> DependencyTransferError:
    return DependencyTransferError(DependencyFailureCategory.DAMAGED_DOWNLOAD, transient=False)
