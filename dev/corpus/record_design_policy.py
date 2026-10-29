"""Record-design corpus classification and known provenance debt."""

from pathlib import PurePosixPath
from typing import Final

from .artifact_catalogue import DerivedArtifact

#: Filenames a model directory legitimately holds without a manifest entry:
#: the manifest itself, and the derivatives other tooling writes beside a
#: payload. Everything else in there is corpus content, and corpus content
#: without a manifest entry has no source URL, licence, digest or retrieval
#: date attached to it.
_MANIFEST_NAME: Final[str] = "manifest.json"


#: Project-authored classification declarations that sit beside a payload
#: rather than being one. They carry their own reasoning and are not AEAT
#: content, so no artefact entry describes them.
_DECLARATION_NAMES: Final[frozenset[str]] = frozenset(
    {_MANIFEST_NAME, "declared-non-record-sheets.json"},
)


_CORRECTION_SUFFIX: Final[str] = ".record-design-correction.json"


_DERIVED_SUFFIXES: Final[tuple[str, ...]] = (
    ".extracted.md",
    ".extracted.json",
    _CORRECTION_SUFFIX,
)


#: Payload files that are present in the corpus and named by no manifest.
#:
#: This is a census of known debt, not a suppression: :func:`check` requires
#: the observed set to EQUAL this one, so a new unattested file fails and so
#: does attesting one of these without removing it from here.
#:
#: The single entry is a partial revert. A bulk pass removed 25 ``.xlsx``
#: copies that each had an ``.xls`` sibling, and dropped their manifest
#: entries with them. One was then restored, because ``xlrd`` cannot read
#: formula text and the modelo 200 totals assertion is grounded in the
#: ``=SUM(C6:C118)`` the ``.xlsx`` carries. The bytes came back; the manifest
#: entry did not. The corpus census therefore reads 248 while 249
#: provenance-bearing files sit on disk, and the one that is missing is
#: load-bearing evidence for an AEAT authority check.
UNATTESTED_CORPUS_FILES: Final[tuple[str, ...]] = ("modelo_200/files/01-200-ejercicio-2025-10-9-mb-xls.xlsx",)


#: Sheet-text extractions of sibling payloads which remain in their historical
#: manifests.  They are explicitly catalogued as derivatives, rather than
#: acquisition artefacts: each listed URL serves the sibling ``.xls`` and can
#: never reproduce the rendered text bytes.
#:
#: These are named records rather than a suffix exemption, so an unrecorded
#: text file remains unclassified.  The source digests make the existing
#: relationship fail closed when a workbook changes without re-extraction.
_EXTRACTION_SIDECAR_DERIVATIONS: Final[tuple[DerivedArtifact, ...]] = (
    DerivedArtifact(
        path=PurePosixPath("modelo_123/files/01-123-orden-eha-3435-2007-ejercicio-2024-y-siguientes-190-kb-xls.txt"),
        input_path=PurePosixPath(
            "modelo_123/files/01-123-orden-eha-3435-2007-ejercicio-2024-y-siguientes-190-kb-xls.xls"
        ),
        input_sha256="85ffe058c1728a50d11d3c6fcfe03f77e172e0458b53920a620aa434d66d07b4",
        producer="record-design-sheet-text-extractor",
    ),
    DerivedArtifact(
        path=PurePosixPath("modelo_123/files/02-123-eha-3435-2007-ejercicios-2019-2023-169-kb-xls.txt"),
        input_path=PurePosixPath("modelo_123/files/02-123-eha-3435-2007-ejercicios-2019-2023-169-kb-xls.xls"),
        input_sha256="21ec4feed2950c57c689a772166952b3c2245e7101bce7836c2baedc1f4f8dbd",
        producer="record-design-sheet-text-extractor",
    ),
)
