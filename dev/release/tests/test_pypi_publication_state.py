"""Proof that a re-run publication converges, and refuses foreign index bytes."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

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
