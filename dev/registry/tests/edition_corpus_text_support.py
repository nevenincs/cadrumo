"""Read a bundled design source's normalised corpus text for the per-edition registry tests."""

from __future__ import annotations

import json

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.schema_catalogues import RegistryCatalogues


def corpus_text(catalogues: RegistryCatalogues, source_id: str) -> str:
    corpus_path = catalogues.sources[source_id].corpus_path
    assert corpus_path is not None
    sidecar = bundled_path("manual_corpus_text", *corpus_path.removeprefix("corpus/").split("/"))
    sidecar = sidecar.with_name(sidecar.name + ".corpus_text.json")
    text = json.loads(sidecar.read_text(encoding="utf-8"))["normalised_text"]
    assert isinstance(text, str)
    return text
