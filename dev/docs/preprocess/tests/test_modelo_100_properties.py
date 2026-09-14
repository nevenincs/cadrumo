"""Real-corpus tests for the dedicated Modelo 100 properties extractor."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

from ..modelo_100_properties import (
    MODELO_100_PROPERTIES_EXTRACTOR_ID,
    MODELO_100_PROPERTIES_EXTRACTOR_VERSION,
    build_outputs,
)
from ..schema import ExtractionStatus, SourceDocumentKind

pytestmark = [pytest.mark.unit, pytest.mark.docs, pytest.mark.hex_core]

_FILES = (
    REPO_ROOT / "src" / "cadrumo" / "_data" / "corpus" / "aeat_official" / "disenos_registro" / "modelo_100" / "files"
)


def _sources() -> list[Path]:
    return sorted(_FILES.glob("*.properties"))


def test_all_pinned_properties_decode_strictly_without_loss_or_c1_controls() -> None:
    """Every enrolled source emits UTF-8-safe text tied to its untouched raw bytes."""
    sources = _sources()
    assert sources
    for source in sources:
        raw = source.read_bytes()
        with pytest.raises(UnicodeDecodeError):
            raw.decode("utf-8")

        output = build_outputs(source, repo_root=REPO_ROOT)[0]
        assert output.source_kind is SourceDocumentKind.MODELO_100_PROPERTIES
        assert output.status is ExtractionStatus.OK
        assert output.preprocessor_id == MODELO_100_PROPERTIES_EXTRACTOR_ID
        assert output.preprocessor_version == MODELO_100_PROPERTIES_EXTRACTOR_VERSION
        assert output.source_sha256 == hashlib.sha256(raw).hexdigest()
        text = "\n".join(unit.text for unit in output.units)
        assert text.encode("utf-8").decode("utf-8") == text
        assert "\ufffd" not in text
        assert not any(0x80 <= ord(char) <= 0x9F for char in text)


def test_file04_maps_cp1252_punctuation_to_an_en_dash() -> None:
    """Byte 0x96 is punctuation, not the Latin-1 U+0096 control."""
    source = next(_FILES.glob("04-*.properties"))
    assert b"\x96" in source.read_bytes()
    text = build_outputs(source, repo_root=REPO_ROOT)[0].units[0].text
    assert "\u2013[0454]" in text
    assert "\u0096" not in text
