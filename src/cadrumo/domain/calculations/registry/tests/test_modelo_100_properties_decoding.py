"""Runtime decoding proof for the official Modelo 100 dictionary."""

from __future__ import annotations

import pytest

from .....core.resources.bundled_data import bundled_path
from ..errors import RegistryValidationError
from ..export_parse import _read_dictionary_text, xml_dictionary_entries
from ..schema import ModeloDefinition, RegistryCatalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_cp1252_dictionary_preserves_runtime_ids_and_decodes_0x96_as_punctuation(
    registry_tree: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> None:
    """The canonical parser retains the 2020 row set without Latin-1 C1 degradation."""
    modelos, catalogues = registry_tree
    modelo = next(item for item in modelos if item.id == "100")
    revision = modelo.revisions["2020"]
    layout = next(item for item in revision.export_layouts if item.dictionary_source_ref is not None)
    source_ref = layout.dictionary_source_ref
    assert source_ref is not None
    source = catalogues.sources[source_ref]
    source_path = bundled_path() / source.corpus_path
    raw = source_path.read_bytes()
    decoded = _read_dictionary_text(raw)
    assert "\u2013[0454]" in decoded
    assert "\u0096" not in decoded

    entries = xml_dictionary_entries(
        layout,
        sources=catalogues.sources,
        source_payloads={str(source.id): raw},
    )

    assert len(entries) == 1796
    assert (entries[0].field_id, entries[-1].field_id) == ("DPNIF_D", "RESDECCOMP")


def test_dictionary_decoder_refuses_bytes_undefined_in_cp1252() -> None:
    """Malformed fallback bytes surface through the registry validation contract."""
    with pytest.raises(RegistryValidationError, match="neither UTF-8 nor CP1252"):
        _read_dictionary_text(b"\x81")
