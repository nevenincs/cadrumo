"""Proof that a re-run publication converges, and refuses foreign index bytes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from .. import package_index_probe
from ..pypi_publication_state import (
    PublicationConflictError,
    PublicationState,
    index_files,
    local_files,
    publication_state,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_FILES = (
    "cadrumo-1.2.0-py3-none-any.whl",
    "cadrumo-1.2.0.tar.gz",
    "cadrumo_data_manuals-1.2.0-py3-none-any.whl",
    "cadrumo_data_manuals-1.2.0.tar.gz",
)


def _sealed(directory: Path) -> dict[str, dict[str, str]]:
    """Write a sealed set and return the index view that serves exactly it."""
    served: dict[str, dict[str, str]] = {}
    for name in _FILES:
        payload = f"bytes of {name}".encode()
        (directory / name).write_bytes(payload)
        project = "cadrumo" if name.startswith("cadrumo-") else "cadrumo-data-manuals"
        served.setdefault(project, {})[name] = hashlib.sha256(payload).hexdigest()
    return served


def test_an_index_serving_every_sealed_file_is_already_published(tmp_path: Path) -> None:
    served = _sealed(tmp_path)
    assert publication_state(local_files(tmp_path), served) is PublicationState.PUBLISHED


def test_an_index_serving_nothing_is_absent(tmp_path: Path) -> None:
    _sealed(tmp_path)
    assert publication_state(local_files(tmp_path), {}) is PublicationState.ABSENT


def test_a_partial_upload_with_matching_digests_proceeds(tmp_path: Path) -> None:
    served = _sealed(tmp_path)
    del served["cadrumo-data-manuals"]
    assert publication_state(local_files(tmp_path), served) is PublicationState.PARTIAL


def test_a_differing_digest_refuses(tmp_path: Path) -> None:
    served = _sealed(tmp_path)
    served["cadrumo"]["cadrumo-1.2.0.tar.gz"] = "f" * 64
    with pytest.raises(PublicationConflictError, match=r"cadrumo-1\.2\.0\.tar\.gz: index sha256"):
        publication_state(local_files(tmp_path), served)


def test_a_file_the_sealed_set_lacks_refuses(tmp_path: Path) -> None:
    served = _sealed(tmp_path)
    served["cadrumo"]["cadrumo-1.2.0-py3-none-win_amd64.whl"] = "a" * 64
    with pytest.raises(PublicationConflictError, match="absent from the sealed set"):
        publication_state(local_files(tmp_path), served)


def test_an_empty_distribution_directory_refuses(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no distributions"):
        local_files(tmp_path)


@pytest.mark.parametrize("index_url", ["http://pypi.org/pypi", "file:///tmp/pypi", "https:///pypi"])
def test_a_non_https_index_endpoint_is_refused_before_any_request(index_url: str) -> None:
    with pytest.raises(PublicationConflictError, match="not an HTTPS endpoint"):
        index_files("cadrumo", "1.2.0", index_url=index_url)


def test_index_files_uses_https_full_metadata_and_encoded_path_segments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = json.dumps({"urls": [{"filename": "cadrumo.whl", "digests": {"sha256": "a" * 64}}]}).encode("utf-8")
    connection_args: list[tuple[str, int | None, int]] = []
    requests: list[tuple[str, str, dict[str, str]]] = []
    read_calls: list[tuple[int, ...]] = []
    closed: list[bool] = []
    statuses = [200]

    class _Response:
        @property
        def status(self) -> int:
            return statuses[0]

        def read(self, *args: int) -> bytes:
            read_calls.append(args)
            return body[: args[0]] if args else body

    class _Connection:
        def __init__(self, hostname: str, port: int | None, *, timeout: int) -> None:
            connection_args.append((hostname, port, timeout))

        def request(self, method: str, target: str, *, headers: dict[str, str]) -> None:
            requests.append((method, target, headers))

        def getresponse(self) -> _Response:
            return _Response()

        def close(self) -> None:
            closed.append(True)

    monkeypatch.setattr(package_index_probe.http.client, "HTTPSConnection", _Connection)

    served = index_files(
        "project/name",
        "1.2+build",
        index_url="https://index.example:8443/custom/pypi/?token=omit#fragment",
    )

    assert served == {"cadrumo.whl": "a" * 64}
    assert connection_args == [("index.example", 8443, 30)]
    assert requests == [("GET", "/custom/pypi/project%2Fname/1.2%2Bbuild/json", {"Accept": "application/json"})]
    assert read_calls == [()]
    assert closed == [True]

    statuses[0] = 404
    assert (
        index_files(
            "project/name",
            "1.2+build",
            index_url="https://index.example:8443/custom/pypi/?token=omit#fragment",
        )
        == {}
    )

    statuses[0] = 503
    with pytest.raises(PublicationConflictError, match="HTTP 503"):
        index_files(
            "project/name",
            "1.2+build",
            index_url="https://index.example:8443/custom/pypi/?token=omit#fragment",
        )

    assert len(requests) == 3
    assert read_calls == [(), (), ()]
    assert closed == [True, True, True]


def test_index_files_refuses_when_connection_close_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    body = json.dumps({"urls": []}).encode("utf-8")
    closed: list[bool] = []

    class _Response:
        status = 200

        def read(self) -> bytes:
            return body

    class _Connection:
        def __init__(self, hostname: str, port: int | None, *, timeout: int) -> None:
            del hostname, port, timeout

        def request(self, method: str, target: str, *, headers: dict[str, str]) -> None:
            del method, target, headers

        def getresponse(self) -> _Response:
            return _Response()

        def close(self) -> None:
            closed.append(True)
            raise OSError("close failed")

    monkeypatch.setattr(package_index_probe.http.client, "HTTPSConnection", _Connection)

    with pytest.raises(PublicationConflictError, match="index check failed for cadrumo: close failed"):
        index_files("cadrumo", "1.2.0", index_url="https://index.example/pypi")

    assert closed == [True]
