"""Preprocess the pinned Modelo 100 XML dictionaries for RAG."""

from __future__ import annotations

from pathlib import Path
from typing import Final

from .schema import ExtractionStatus, PreprocessOutput, PreprocessUnit, SourceDocumentKind
from .sidecar import sha256_of

MODELO_100_PROPERTIES_EXTRACTOR_ID: Final[str] = "modelo-100-properties-cp1252"
MODELO_100_PROPERTIES_EXTRACTOR_VERSION: Final[str] = "1.0"
_CP1252: Final[str] = "cp1252"
_ATTRIBUTION: Final[str] = "Agencia Estatal de Administración Tributaria (AEAT), Modelo 100 XML dictionary."
_C1_CONTROL_RANGE = range(0x80, 0xA0)


def build_outputs(source: Path, *, repo_root: Path) -> list[PreprocessOutput]:
    """Decode one official Modelo 100 ``.properties`` dictionary as strict CP1252."""
    text = source.read_bytes().decode(_CP1252)
    c1_controls = sorted({ord(char) for char in text if ord(char) in _C1_CONTROL_RANGE})
    if c1_controls:
        rendered = ", ".join(f"U+{codepoint:04X}" for codepoint in c1_controls)
        raise UnicodeError(f"CP1252 dictionary decoded to forbidden C1 controls: {rendered}")

    relpath = source.resolve().relative_to(repo_root.resolve()).as_posix()
    unit_text = text.strip()
    units = (
        (PreprocessUnit(text=unit_text, title=source.name, section="Modelo 100 XML dictionary"),) if unit_text else ()
    )
    return [
        PreprocessOutput(
            source_kind=SourceDocumentKind.MODELO_100_PROPERTIES,
            status=ExtractionStatus.OK if units else ExtractionStatus.EMPTY,
            source_relpath=relpath,
            source_sha256=sha256_of(source),
            preprocessor_id=MODELO_100_PROPERTIES_EXTRACTOR_ID,
            preprocessor_version=MODELO_100_PROPERTIES_EXTRACTOR_VERSION,
            attribution=_ATTRIBUTION,
            units=units,
        )
    ]
