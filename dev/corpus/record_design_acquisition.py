"""Acquire verified payload bytes within an explicit corpus storage boundary."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

import httpx

from cadrumo.core.directory_scan import iter_directory
from dev.corpus.record_design_inventory import (
    _RETRIEVED_AT,
    _RequiredArtifact,
)
from dev.packaging.hashing import sha256_path

from .record_design_manifests import _Artifact, _artifact_urls, _Manifest


def _store_acquired_payload(
    files_dir: Path, extension: str, data: bytes, digest: str, artifacts: list[_Artifact], required: _RequiredArtifact
) -> Path:
    """Store acquired payload."""
    local_match = next(
        (
            candidate
            for candidate in iter_directory(files_dir, pattern=f"*{extension}")
            if candidate.stat().st_size == len(data) and sha256_path(candidate) == digest
        ),
        None,
    )
    if local_match is None:
        indexes = [
            int(match.group(1))
            for artifact in artifacts
            if (match := re.match(r"files/(\d+)-", str(artifact["stored_path"])))
        ]
        local_match = files_dir / (f"{max(indexes, default=0) + 1:02d}-{_slug(required.title)}{extension}")
        local_match.write_bytes(data)
    return local_match


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _slug(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:110].rstrip("-")


def _valid_signature(extension: str, data: bytes) -> bool:
    if extension == ".pdf":
        return data.startswith(b"%PDF-")
    if extension == ".xls":
        return data.startswith(bytes.fromhex("D0CF11E0A1B11AE1"))
    if extension in {".xlsx", ".xlsm"}:
        return data.startswith(b"PK\x03\x04")
    return bool(data)


def _pull_required_artifact(
    index: int,
    required: _RequiredArtifact,
    manifests: dict[str, _Manifest],
    client: httpx.Client,
    corpus_root: Path,
    required_count: int,
) -> None:
    """Pull required artifact."""
    manifest = manifests.get(required.modelo)
    if _update_existing_artifact(manifest, required):
        return

    response = client.get(required.url)
    response.raise_for_status()
    data = response.content
    extension = Path(urlparse(str(response.url)).path).suffix.lower()
    if not _valid_signature(extension, data):
        raise RuntimeError(f"Unexpected signature for {required.url}")
    digest = _sha256_bytes(data)
    print(f"FETCH {index:02d}/{required_count} M{required.modelo} {len(data):>9} {digest[:12]}")

    model_dir = corpus_root / f"modelo_{required.modelo}"
    files_dir = model_dir / "files"
    files_dir.mkdir(parents=True, exist_ok=True)
    if manifest is None:
        manifest = _Manifest(
            source="Agencia Tributaria Sede Electronica - Disenos de registro",
            modelo=required.modelo,
            retrieved_at=_RETRIEVED_AT,
            source_pages=[],
            artefact_count=0,
            artefacts=[],
        )
        manifests[required.modelo] = manifest
    if required.source_page is not None:
        source_pages = manifest["source_pages"]
        if required.source_page not in source_pages:
            source_pages.append(required.source_page)
    artifacts = manifest["artefacts"]
    same = next(
        (artifact for artifact in artifacts if artifact["sha256"] == digest and artifact["bytes"] == len(data)),
        None,
    )
    if same is not None:
        aliases = same.setdefault("url_aliases", [])
        aliases.append(required.url)
        return

    local_match = _store_acquired_payload(files_dir, extension, data, digest, artifacts, required)
    artifacts.append(
        {
            "modelo": required.modelo,
            "title": required.title,
            "source_page": required.source_page,
            "url": required.url,
            "stored_path": local_match.relative_to(model_dir).as_posix(),
            "original_filename": Path(urlparse(required.url).path).name,
            "content_type": response.headers.get("content-type", "application/octet-stream").split(";", 1)[0],
            "bytes": len(data),
            "sha256": digest,
            "retrieved_at": _RETRIEVED_AT,
        }
    )
    manifest["retrieved_at"] = _RETRIEVED_AT


def _update_existing_artifact(manifest: _Manifest | None, required: _RequiredArtifact) -> bool:
    """Return whether an already acquired URL needs no payload fetch."""
    if manifest:
        existing = next(
            (artifact for artifact in manifest["artefacts"] if required.url in _artifact_urls(artifact)),
            None,
        )
        if existing is not None:
            # A declaration with no established index page has nothing
            # to say about `source_page`, so it leaves the recorded
            # value alone rather than overwriting it with None.
            if required.source_page is not None:
                source_pages = manifest["source_pages"]
                if required.source_page not in source_pages:
                    source_pages.append(required.source_page)
                existing["source_page"] = required.source_page
            return True
    return False
