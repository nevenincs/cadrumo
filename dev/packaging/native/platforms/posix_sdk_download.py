"""Admit and bound downloads of pinned POSIX SDK archives."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import BinaryIO

import httpx

_SDK_DOWNLOAD_HOSTS = frozenset({"github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com"})

_SDK_DOWNLOAD_LIMIT = 1024 * 1024 * 1024


def _validate_sdk_redirect(current: httpx.URL) -> None:
    if (
        current.scheme != "https"
        or current.host not in _SDK_DOWNLOAD_HOSTS
        or current.port not in {None, 443}
        or current.userinfo
    ):
        raise ValueError("CPython SDK redirect leaves the admitted HTTPS origins")


def _write_sdk_download(chunks: Iterable[bytes], output: BinaryIO) -> None:
    size = 0
    for chunk in chunks:
        size += len(chunk)
        if size > _SDK_DOWNLOAD_LIMIT:
            raise ValueError("CPython SDK exceeds the download size limit")
        output.write(chunk)


def download_sdk(url: str, archive: Path) -> None:
    """Follow at most three HTTPS redirects within GitHub's release asset origins."""
    current = httpx.URL(url)
    if current.host != "github.com" or not current.path.startswith(
        "/astral-sh/python-build-standalone/releases/download/"
    ):
        raise ValueError("CPython SDK must originate from the pinned GitHub release")
    partial = archive.with_name(archive.name + ".partial")
    created = False
    try:
        for redirects in range(4):
            _validate_sdk_redirect(current)
            with httpx.stream("GET", current, timeout=120, follow_redirects=False) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location or redirects == 3:
                        raise ValueError("CPython SDK redirect is missing or exceeds the redirect limit")
                    current = current.join(location)
                    continue
                response.raise_for_status()
                with partial.open("xb") as output:
                    created = True
                    _write_sdk_download(response.iter_bytes(), output)
                partial.rename(archive)
                created = False
                return
    finally:
        if created:
            partial.unlink(missing_ok=True)
