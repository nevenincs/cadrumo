"""Modelo 100 source-tier data hygiene checks."""

from __future__ import annotations

import tomllib
from collections.abc import Iterator
from pathlib import Path

import pytest

from .....core.directory_scan import scan_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ROOT = Path(__file__).resolve().parents[6]
_LEGAL_IRPF = _ROOT / "src/cadrumo/_data/registry/aeat/legal/irpf.toml"
_MODELO_100_ROOT = _ROOT / "src/cadrumo/_data/registry/aeat/modelos/100"
_BOE_FORM_SOURCES = frozenset(f"boe-modelo-100-{year}-form" for year in range(2020, 2026))


def _source_citation_refs(value: object) -> Iterator[str]:
    if isinstance(value, dict):
        citations = value.get("source_citations")
        if isinstance(citations, list):
            for citation in citations:
                if isinstance(citation, dict):
                    source_ref = citation.get("source_ref")
                    if isinstance(source_ref, str):
                        yield source_ref
        for child in value.values():
            yield from _source_citation_refs(child)
    elif isinstance(value, list):
        for child in value:
            yield from _source_citation_refs(child)


def test_modelo_100_boe_form_sources_are_layout_only() -> None:
    sources = tomllib.loads(_LEGAL_IRPF.read_text(encoding="utf-8"))["sources"]

    for source_ref in _BOE_FORM_SOURCES:
        source = sources[source_ref]
        assert source["authority"] == "boe"
        assert source["kind"] == "form_spec"
        assert source["evidence_tier"] == "layout_authority"


def test_modelo_100_source_citations_do_not_use_layout_sources() -> None:
    offenders = []
    for path in scan_directory(_MODELO_100_ROOT, pattern="*.toml", recursive=True):
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        for source_ref in _source_citation_refs(data):
            if source_ref in _BOE_FORM_SOURCES:
                offenders.append(f"{path.relative_to(_ROOT).as_posix()} -> {source_ref}")

    assert offenders == []
