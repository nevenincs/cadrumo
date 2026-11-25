"""Typed record-design manifest records and deterministic census projections."""

from __future__ import annotations

from pathlib import Path
from typing import Final, NotRequired, TypedDict

from pydantic import TypeAdapter

#: The bundled record-design corpus: one directory per modelo, each holding its manifest and payloads.
DESIGN_CORPUS: Final = Path(__file__).resolve().parents[2] / "src/cadrumo/_data/corpus/aeat_official/disenos_registro"


class Artifact(TypedDict):
    """A typed record of one bundled official design artefact in a modelo manifest."""

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


class Manifest(TypedDict):
    """A typed per-modelo design manifest listing its source pages and artefacts."""

    source: str
    modelo: str
    retrieved_at: str
    source_pages: list[str]
    artefact_count: int
    artefacts: list[Artifact]
    #: Present where the index offered no design to record for the modelo.
    not_found_note: NotRequired[str]


#: Validates a manifest read from disk against its declared shape.
_MANIFEST_ADAPTER: Final = TypeAdapter(Manifest)


class ModeloRow(TypedDict):
    """A per-modelo artefact count row of the root design manifest."""

    modelo: str
    artefact_count: int


class RootAggregate(TypedDict):
    """The census fields of the root design manifest derived from the per-modelo manifests."""

    supported_corpus_modelos: list[str]
    model_count: int
    artefact_count: int
    modelos: list[ModeloRow]


class HistoricalExclusions(TypedDict):
    """A typed record of historical design URLs deliberately excluded from the corpus."""

    schema_version: int
    disposition: str
    source_pages: list[str]
    urls: list[str]


def recorded_artifact(modelo: str, *, relative_url: str | None = None, sha256: str | None = None) -> Artifact:
    """Return the bundled manifest's record of one artefact, selected by its URL tail or its payload digest.

    AEAT names its design files, and the titles of their index links, after the exercises they
    apply to. Those names are external identifiers the manifests already record, so a caller that
    needs one reads it here instead of writing it a second time.
    """
    if (relative_url is None) == (sha256 is None):
        raise ValueError("select a recorded artefact by exactly one of its URL tail or its digest")
    manifest = _MANIFEST_ADAPTER.validate_json(
        (DESIGN_CORPUS / f"modelo_{modelo}" / "manifest.json").read_text(encoding="utf-8")
    )
    matches = [
        artifact
        for artifact in manifest["artefacts"]
        if (
            str(artifact["url"]).endswith(f"/{relative_url}")
            if relative_url is not None
            else artifact["sha256"] == sha256
        )
    ]
    if len(matches) != 1:
        raise LookupError(f"modelo {modelo} manifest records {len(matches)} artefacts for {relative_url or sha256}")
    return matches[0]


def artifact_urls(artifact: Artifact) -> set[str]:
    """Return the primary URL of an artefact together with its URL aliases."""
    return {str(artifact["url"]), *(str(url) for url in artifact.get("url_aliases", []))}


def root_aggregate(manifests: dict[str, Manifest]) -> RootAggregate:
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


def record_design_manifests_represented_urls(manifests: dict[str, Manifest]) -> set[str]:
    """Project every declared source URL and alias from the complete manifest inventory."""
    return {
        url for manifest in manifests.values() for artifact in manifest["artefacts"] for url in artifact_urls(artifact)
    }
