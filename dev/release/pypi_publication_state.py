"""Decide whether a sealed distribution set is already on the package index.

A publication that is re-run must converge rather than fail: when the index
already serves every file of the set with the same bytes, the upload is done
and the run skips it. When the index serves any file of this version with
different bytes, or a file the set does not contain, the version belongs to
other bytes and the run refuses. Anything in between is a partial upload that
the next upload completes.

The decision core is pure; only :func:`index_files` touches the network.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import sys
import urllib.parse
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from packaging.utils import canonicalize_name, parse_sdist_filename, parse_wheel_filename

from dev._paths import UTF_8

_UTF_8: Final[str] = UTF_8
_PYPI_JSON_INDEX: Final[str] = "https://pypi.org/pypi"
_TIMEOUT_S: Final[int] = 30
_CHUNK: Final[int] = 1 << 20


class PublicationState(StrEnum):
    """Where the sealed set stands on the index."""

    ABSENT = "absent"
    PARTIAL = "partial"
    PUBLISHED = "published"


class PublicationConflictError(RuntimeError):
    """The index serves this version with bytes the sealed set does not hold."""


@dataclass(frozen=True, slots=True)
class LocalFile:
    """One sealed distribution file."""

    project: str
    filename: str
    sha256: str


def distribution_project(filename: str) -> str:
    """Return the canonical project name a distribution filename belongs to."""
    if filename.endswith(".whl"):
        return str(parse_wheel_filename(filename)[0])
    if filename.endswith(".tar.gz"):
        return str(parse_sdist_filename(filename)[0])
    raise ValueError(f"{filename!r} is not a wheel or source distribution")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def local_files(directory: Path) -> tuple[LocalFile, ...]:
    """Return every sealed distribution file in ``directory``."""
    paths = sorted([*directory.glob("*.whl"), *directory.glob("*.tar.gz")])
    if not paths:
        raise ValueError(f"no distributions found in {directory}")
    return tuple(LocalFile(distribution_project(path.name), path.name, _sha256(path)) for path in paths)


def publication_state(
    local: tuple[LocalFile, ...],
    served: Mapping[str, Mapping[str, str]],
) -> PublicationState:
    """Classify the sealed set against what the index serves for its version.

    Args:
        local: The sealed distribution files.
        served: Per canonical project, the index's ``filename -> sha256`` for
            this version; a project absent from the index maps to nothing.

    Returns:
        The publication state.

    Raises:
        PublicationConflictError: the index serves different or foreign bytes.
    """
    conflicts: list[str] = []
    expected: dict[str, dict[str, str]] = {}
    for item in local:
        expected.setdefault(canonicalize_name(item.project), {})[item.filename] = item.sha256
    present = 0
    for project, files in expected.items():
        index = served.get(project, {})
        for filename, sha256 in files.items():
            observed = index.get(filename)
            if observed is None:
                continue
            if observed.lower() != sha256.lower():
                conflicts.append(f"{filename}: index sha256 {observed}, sealed sha256 {sha256}")
            else:
                present += 1
        conflicts.extend(
            f"{filename}: served by the index but absent from the sealed set"
            for filename in sorted(set(index) - set(files))
        )
    if conflicts:
        raise PublicationConflictError(
            "the index already serves this version with other bytes:\n  - " + "\n  - ".join(conflicts)
        )
    if present == 0:
        return PublicationState.ABSENT
    if present == len(local):
        return PublicationState.PUBLISHED
    return PublicationState.PARTIAL


def index_files(project: str, version: str, *, index_url: str = _PYPI_JSON_INDEX) -> dict[str, str]:
    """Return the index's ``filename -> sha256`` for one project version.

    A 404 is the only answer read as "nothing served"; every other failure
    raises, because an unreachable index proves nothing about the version.
    Only an HTTPS endpoint is asked: any other scheme could answer from
    somewhere other than an index.
    """
    endpoint = urllib.parse.urlsplit(index_url)
    if endpoint.scheme != "https" or not endpoint.hostname:
        raise PublicationConflictError(f"index endpoint {index_url!r} is not an HTTPS endpoint")
    path = f"{endpoint.path.rstrip('/')}/{urllib.parse.quote(project)}/{urllib.parse.quote(version)}/json"
    connection = http.client.HTTPSConnection(endpoint.hostname, endpoint.port, timeout=_TIMEOUT_S)
    try:
        connection.request("GET", path, headers={"Accept": "application/json"})
        response = connection.getresponse()
        body = response.read()
    except (OSError, http.client.HTTPException) as exc:
        raise PublicationConflictError(f"index check failed for {project}: {exc}") from exc
    finally:
        connection.close()
    if response.status == 404:
        return {}
    if not 200 <= response.status < 300:
        raise PublicationConflictError(f"index check failed for {project}: HTTP {response.status}")
    try:
        payload = json.loads(body.decode(_UTF_8))
        return {str(entry["filename"]): str(entry["digests"]["sha256"]) for entry in payload.get("urls", ())}
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise PublicationConflictError(f"index answered unreadable metadata for {project}: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    """Print the publication state of a sealed set, refusing a conflicting index."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--dist-dir", required=True, type=Path)
    parser.add_argument("--github-output", type=Path, default=None, help="Append state=<value> to this file.")
    args = parser.parse_args(argv)
    try:
        local = local_files(args.dist_dir)
        projects = sorted({str(canonicalize_name(item.project)) for item in local})
        served = {project: index_files(project, args.version) for project in projects}
        state = publication_state(local, served)
    except (PublicationConflictError, ValueError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1
    print(f"package index state for {args.version}: {state.value}")
    if args.github_output is not None:
        with args.github_output.open("a", encoding=_UTF_8) as sink:
            sink.write(f"state={state.value}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
