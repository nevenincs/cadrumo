"""Typed record-design manifest records and deterministic census projections."""

from __future__ import annotations

from typing import NotRequired, TypedDict


class _Artifact(TypedDict):
    modelo: str
    title: str
    #: ``None`` where no official index page was established for the artefact.
    #: Two bundled rows instead carry the file's own URL here, which is neither
    #: an index page nor an honest ``None``; correcting them needs the live
    #: index and is not settled offline.
    source_page: str | None
    url: str
    stored_path: str
    original_filename: str
    content_type: str
    bytes: int
    sha256: str
    retrieved_at: str
    url_aliases: NotRequired[list[str]]


class _Manifest(TypedDict):
    source: str
    modelo: str
    retrieved_at: str
    source_pages: list[str]
    artefact_count: int
    artefacts: list[_Artifact]


class _ModeloRow(TypedDict):
    modelo: str
    artefact_count: int


class _RootAggregate(TypedDict):
    supported_corpus_modelos: list[str]
    model_count: int
    artefact_count: int
    modelos: list[_ModeloRow]


class _HistoricalExclusions(TypedDict):
    schema_version: int
    disposition: str
    source_pages: list[str]
    urls: list[str]


def _artifact_urls(artifact: _Artifact) -> set[str]:
    return {str(artifact["url"]), *(str(url) for url in artifact.get("url_aliases", []))}


def _root_aggregate(manifests: dict[str, _Manifest]) -> _RootAggregate:
    """Derive the root manifest's census fields from the per-modelo manifests.

    These four fields are a pure function of what the per-modelo manifests
    hold, so they have exactly one definition here. :func:`_write_manifests`
    applies it after a pull, :func:`_regenerate_root_aggregate` applies it
    without one, and :func:`check` compares against it; a second summation
    would let the writer and the gate drift apart while both looked right.
    """
    modelos = sorted(manifests)
    return {
        "supported_corpus_modelos": modelos,
        "model_count": len(modelos),
        "artefact_count": sum(len(manifests[modelo]["artefacts"]) for modelo in modelos),
        "modelos": [{"modelo": modelo, "artefact_count": len(manifests[modelo]["artefacts"])} for modelo in modelos],
    }


def _represented_urls(manifests: dict[str, _Manifest]) -> set[str]:
    """Project every declared source URL and alias from the complete manifest inventory."""
    return {
        url for manifest in manifests.values() for artifact in manifest["artefacts"] for url in _artifact_urls(artifact)
    }
