"""Synchronise the supported AEAT record-design corpus from official indexes."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from typing import Final, NotRequired, TypedDict, cast, override
from urllib.parse import urljoin, urlparse

import httpx

_UTF_8: Final[str] = "utf-8"
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if not __package__:
    __package__ = "dev.corpus"

from cadrumo.core.directory_scan import iter_directory, scan_directory  # noqa: E402
from cadrumo.domain.calculations.registry.artifact_catalogue import (  # noqa: E402
    ArtifactCatalogue,
    ArtifactDiagnostic,
    ArtifactDiagnosticKind,
    ArtifactRole,
    DerivedArtifact,
    compile_artifact_catalogue,
    record_design_manifest_identities,
)
from dev.packaging.hashing import sha256_path  # noqa: E402

_CORPUS = _ROOT / "src/cadrumo/_data/corpus/aeat_official/disenos_registro"
_HISTORICAL_EXCLUSIONS_PATH = _CORPUS / "historical_exclusions.json"
_RETRIEVED_AT = "2026-08-26"
_STATIC = "https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro"
_INDEX = "https://sede.agenciatributaria.gob.es/Sede/ayuda/disenos-registro"
_PAGES = {
    "01": f"{_INDEX}/modelos-01-99.html",
    "100": f"{_INDEX}/modelos-100-199.html",
    "200": f"{_INDEX}/modelos-200-299.html",
    "300": f"{_INDEX}/modelos-300-399.html",
    "resto": f"{_INDEX}/resto-modelos.html",
    "h100": f"{_INDEX}/ejercicios-anteriores-modelos-100-199.html",
    "h01": f"{_INDEX}/modelos-01-99_.html",
    "h200": f"{_INDEX}/ejercicios-anteriores-modelos-200-299.html",
    "h300": f"{_INDEX}/ejercicios-anteriores-modelos-300-399.html",
    "hresto": f"{_INDEX}/ejercicios-anteriores-resto-modelos.html",
}
_CURRENT_PAGE_KEYS = ("01", "100", "200", "300", "resto")
_HISTORICAL_PAGE_KEYS = ("h01", "h100", "h200", "h300", "hresto")
_RECORD_DESIGN_SUFFIXES = frozenset({".pdf", ".xls", ".xlsx", ".xlsm", ".xsd"})

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
_DERIVED_SUFFIXES: Final[tuple[str, ...]] = (
    ".extracted.md",
    ".extracted.json",
    ".record-design-correction.json",
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
_UNATTESTED_CORPUS_FILES: Final[tuple[str, ...]] = ("modelo_200/files/01-200-ejercicio-2025-10-9-mb-xls.xlsx",)

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


@dataclass(frozen=True)
class _RequiredArtifact:
    modelo: str
    title: str
    relative_url: str
    #: Key into :data:`_PAGES`, or ``None`` where the official index page the
    #: document was found on was never recorded. Two bundled artefacts are in
    #: that state: their manifest ``source_page`` is the file's own URL rather
    #: than an index page, so there is nothing to derive a key from. ``None``
    #: says so. Substituting the page a modelo's number suggests would assert
    #: an indexing fact no capture established, and the live check would then
    #: compare against a page AEAT may never have listed the document on.
    page_key: str | None

    @property
    def url(self) -> str:
        return f"{_STATIC}/{self.relative_url}"

    @property
    def source_page(self) -> str | None:
        return None if self.page_key is None else _PAGES[self.page_key]


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
    support_years: list[int]
    disposition: str
    source_pages: list[str]
    urls: list[str]


class _IndexLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    @override
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        self._href = next((value for name, value in attrs if name == "href"), None)
        self._text = []

    @override
    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    @override
    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or self._href is None:
            return
        self.links.append((" ".join("".join(self._text).split()), self._href))
        self._href = None
        self._text = []


_REQUIRED = (
    _RequiredArtifact(
        "036",
        "036 - Ejercicio 2021 y siguientes (actualizado 13-05-2021) (102 KB - xlsx )",
        "DR_01_99/archivos/DR036v35.xlsx",
        "h01",
    ),
    _RequiredArtifact(
        "036",
        "036 - Ejercicio 2021 y siguientes (actualizado 11-04-2023) (106 KB - xlsx )",
        "DR_01_99/archivos/DR036v40.xlsx",
        "h01",
    ),
    _RequiredArtifact(
        "036",
        "036 - Diseño de Registro del modelo M036 (Ejercicio 2023 y siguientes) (107 KB - xlsx )",
        "DR_01_99/archivos/DR036v41.xlsx",
        "h01",
    ),
    _RequiredArtifact(
        "036",
        "036 - Diseño de Registro del modelo M036 (03-02-2025 y siguientes). PROVISIONAL (107 KB - xlsx )",
        "DR_01_99/archivos/DR036v42.xlsx",
        "h01",
    ),
    _RequiredArtifact(
        "036",
        "036 - Diseño de Registro del modelo M036 (03-02-2025 y siguientes) (124 KB - xlsx )",
        "DR_01_99/archivos/DR036v43.xlsx",
        "01",
    ),
    _RequiredArtifact(
        "038",
        "038 - Orden HAC/66/2002, de 15 de enero (actualizado a 18/01/2012)",
        "DR_01_99/archivos/dr038_2005.pdf",
        "h01",
    ),
    _RequiredArtifact(
        "038",
        "038 - Diseño de registro actualizado 28/06/2024",
        "DR_01_99/archivos/dr038_2024.pdf",
        "01",
    ),
    _RequiredArtifact(
        "100",
        "100 - Esquema XSD Ejercicio 2025 - Actualizado 24-06-2026 (793 KB - Ejecutable)",
        "DR_100_199/Renta2025.xsd",
        "100",
    ),
    _RequiredArtifact(
        "100",
        "100 - Ejercicio 2019. Actualización 01/07/2020 (1,77 MB - xls )",
        "DR_100_199/archivos_19/DR100_2019.xls",
        "h100",
    ),
    _RequiredArtifact(
        "100",
        "100 - Esquema XSD Ejercicio 2020 - Actualizado 23-10-2024 (529 KB - Ejecutable)",
        "DR_100_199/archivos_20/Renta2020.xsd",
        "h100",
    ),
    _RequiredArtifact(
        "100",
        (
            "100 - Diccionario declaración individual (toma de datos) (Ejercicio 2020). Actualizado 30-04-2021 (452 KB "
            "- Otros ficheros)"
        ),
        "DR_100_199/archivos_20/diccionarioDlgXSD_2020.properties",
        "h100",
    ),
    _RequiredArtifact(
        "100",
        "100 - Diccionario declaración individual (Ejercicio 2020). Actualizado 03-06-2021 (296 KB - Otros ficheros)",
        "DR_100_199/archivos_20/diccionarioXSD_2020.properties",
        "h100",
    ),
    _RequiredArtifact(
        "100",
        "100 - Esquema XSD Ejercicio 2021 - Actualizado 23-10-2024 (606 KB - Ejecutable)",
        "DR_100_199/archivos_21/Renta2021.xsd",
        "h100",
    ),
    _RequiredArtifact(
        "100",
        (
            "100 - Diccionario declaración individual (toma de datos) (Ejercicio 2021) - Actualizado 18-03-2022 (689 "
            "KB "
            "- Otros ficheros)"
        ),
        "DR_100_199/archivos_21/diccionarioDlgXSD_2021.properties",
        "h100",
    ),
    _RequiredArtifact(
        "100",
        "100 - Diccionario declaración individual (Ejercicio 2021) - Actualizado 18-03-2022 (330 KB - Otros ficheros)",
        "DR_100_199/archivos_21/diccionarioXSD_2021.properties",
        "h100",
    ),
    _RequiredArtifact(
        "100",
        "100 - Esquema XSD Ejercicio 2022 - Actualizado 07-11-2024 (675 KB - Ejecutable)",
        "DR_100_199/archivos_22/Renta2022.xsd",
        "h100",
    ),
    _RequiredArtifact(
        "100",
        (
            "100 - Diccionario declaración individual (toma de datos) (Ejercicio 2022) - Actualizado 28-06-2023 (765 "
            "KB "
            "- Otros ficheros)"
        ),
        "DR_100_199/archivos_22/diccionarioDlgXSD_2022.properties",
        "h100",
    ),
    _RequiredArtifact(
        "100",
        "100 - Diccionario declaración individual (Ejercicio 2022) - Actualizado 17-05-2023 (365 KB - Otros ficheros)",
        "DR_100_199/archivos_22/diccionarioXSD_2022.properties",
        "h100",
    ),
    _RequiredArtifact(
        "100",
        "100 - Esquema XSD Ejercicio 2023 - Actualizado 19-01-2026 (709 KB - Ejecutable)",
        "DR_100_199/archivos_23/Renta2023.xsd",
        "h100",
    ),
    _RequiredArtifact(
        "100",
        (
            "100 - Diccionario declaración individual (toma de datos) (Ejercicio 2023) - Actualizado 29-01-2026 (803 "
            "KB "
            "- Otros ficheros)"
        ),
        "DR_100_199/archivos_23/diccionarioDlgXSD_2023.properties",
        "h100",
    ),
    _RequiredArtifact(
        "100",
        "100 - Diccionario declaración individual (Ejercicio 2023) - Actualizado 29-01-2026 (382 KB - Otros ficheros)",
        "DR_100_199/archivos_23/diccionarioXSD_2023.properties",
        "h100",
    ),
    _RequiredArtifact(
        "100",
        "100 - Esquema XSD Ejercicio 2024 - Actualizado 19-01-2026 (747 KB - Ejecutable)",
        "DR_100_199/archivos_24/Renta2024.xsd",
        "h100",
    ),
    _RequiredArtifact(
        "100",
        (
            "100 - Diccionario declaración individual (toma de datos) (Ejercicio 2024) - Actualizado 29-01-2026 (867 "
            "KB "
            "- Otros ficheros)"
        ),
        "DR_100_199/archivos_24/diccionarioDlgXSD_2024.properties",
        "h100",
    ),
    _RequiredArtifact(
        "100",
        "100 - Diccionario declaración individual (Ejercicio 2024) - Actualizado 29-01-2026 (393 KB - Otros ficheros)",
        "DR_100_199/archivos_24/diccionarioXSD_2024.properties",
        "h100",
    ),
    _RequiredArtifact(
        "100",
        (
            "100 - Diccionario declaración individual (toma de datos) (Ejercicio 2025) - Actualizado 14-04-2026 (944 "
            "KB "
            "- Otros ficheros)"
        ),
        "DR_100_199/diccionarioDlgXSD_2025.properties",
        "100",
    ),
    _RequiredArtifact(
        "100",
        "100 - Diccionario declaración individual (Ejercicio 2025) - Actualizado 14-04-2026 (416 KB - Otros ficheros)",
        "DR_100_199/diccionarioXSD_2025.properties",
        "100",
    ),
    _RequiredArtifact("100", "100 - Ejercicio 2011 (359 KB - pdf )", "ant_100_199/archivos/DR100_2011.pdf", "h100"),
    _RequiredArtifact("100", "100 - Ejercicio 2012 (379 KB - pdf )", "ant_100_199/archivos/DR100_2012.pdf", "h100"),
    _RequiredArtifact("100", "100 - Ejercicio 2013 (376 KB - pdf )", "ant_100_199/archivos/DR100_2013.pdf", "h100"),
    _RequiredArtifact("100", "100 - Ejercicio 2014 (417 KB - pdf )", "ant_100_199/archivos/DR100_2014.pdf", "h100"),
    _RequiredArtifact("100", "100 - Ejercicio 2015 (1,75 MB - xls )", "ant_100_199/archivos/DR100_2015.xls", "h100"),
    _RequiredArtifact("100", "100 - Ejercicio 2016 (1,90 MB - xls )", "ant_100_199/archivos/DR100_2016.xls", "h100"),
    _RequiredArtifact(
        "100",
        "100 - Ejercicio 2017. Actualización 04/04/2018 (6,98 MB - xls )",
        "ant_100_199/archivos/DR100_2017.xls",
        "h100",
    ),
    _RequiredArtifact(
        "100",
        "100 - Ejercicio 2018 - Actualización 17/09/2019 (1,80 MB - xls )",
        "ant_100_199/archivos/DR100_2018.xls",
        "h100",
    ),
    _RequiredArtifact("100", "100 - Ejercicio 2009 (205 KB - pdf )", "ant_100_199/archivos/dr100_2009.pdf", "h100"),
    _RequiredArtifact("100", "100 - Ejercicio 2010 (357 KB - pdf )", "ant_100_199/archivos/dr100_2010.pdf", "h100"),
    _RequiredArtifact(
        "111",
        "111 - Orden EHA/3127/2009 (Ejercicios 2019 y siguientes, actualizado Mayo 2021) (179 KB - xls )",
        "DR_100_199/archivos/dr111e16v18.xls",
        "100",
    ),
    _RequiredArtifact(
        "111",
        "111 - Ejercicios anteriores al 2001 (65 KB - pdf )",
        "ant_100_199/archivos/dr111_2000.pdf",
        "h100",
    ),
    _RequiredArtifact(
        "111",
        "111 - Ejercicios 2004 a 2009 (49 KB - pdf )",
        "ant_100_199/archivos/dr111_2007.pdf",
        "h100",
    ),
    _RequiredArtifact(
        "111",
        "111 - Orden EHA/3127/2009 (Ejercicios 2012 a 2015) (35 KB - pdf )",
        "ant_100_199/archivos/dr111_v16.pdf",
        "h100",
    ),
    _RequiredArtifact(
        "111",
        "111 - Orden EHA/3127/2009 (Ejercicios 2016 hasta 2018) (167 KB - xls )",
        "ant_100_199/archivos/dr111e16v17.xls",
        "h100",
    ),
    _RequiredArtifact(
        "111",
        "111 - Ejercicios 2010 a 2011 (32 KB - pdf )",
        "ant_100_199/archivos/dr111v14.pdf",
        "h100",
    ),
    _RequiredArtifact(
        "115",
        "115 - Orden EHA/3435/2007 (Ejercicios 2019 y siguientes, actualizado Febrero 2019) (172 KB - xls )",
        "DR_100_199/archivos/DR115e15v13.xls",
        "100",
    ),
    _RequiredArtifact(
        "115",
        "115 - Orden EHA/3435/2007 (Ejercicios 2014 y anteriores) (30 KB - pdf )",
        "ant_100_199/archivos/115_2008.pdf",
        "h100",
    ),
    _RequiredArtifact(
        "115",
        "115 - Orden EHA/3435/2007 (Ejercicios 2015 hasta 2018) (168 KB - xls )",
        "ant_100_199/archivos/DR115e15v12.xls",
        "h100",
    ),
    _RequiredArtifact("117", "117 - Ejercicio 2019 y siguientes", "DR_100_199/archivos_17/DR117e17v14.xls", "100"),
    _RequiredArtifact("122", "122 - Ejercicio 2016 y siguientes", "DR_100_199/archivos_18/dr122e18v13.xlsx", "100"),
    _RequiredArtifact(
        "123",
        "123 - EHA/3435/2007 (Ejercicios 2019-2023) (169 KB - xls )",
        "DR_100_199/archivos/DR123e15v13.xls",
        "h100",
    ),
    _RequiredArtifact(
        "123",
        "123 - Orden EHA/3435/2007 (Ejercicio 2024 y siguientes) (190 KB - xls )",
        "DR_100_199/archivos_24/DR123e24.xls",
        "100",
    ),
    _RequiredArtifact(
        "123",
        "123 - Orden EHA/3435/2007 (Ejercicios 2014 y anteriores) (40 KB - pdf )",
        "ant_100_199/archivos/123_2008.pdf",
        "h100",
    ),
    _RequiredArtifact(
        "123",
        "123 - Orden EHA/3435/2007 (Ejercicios 2015 hasta 2018) (164 KB - xls )",
        "ant_100_199/archivos/DR123e15v12.xls",
        "h100",
    ),
    _RequiredArtifact(
        "126",
        "126 - Ejercicio 2020 y siguientes",
        "DR_100_199/archivos_20/126v01e2020_v1.07.xlsx",
        "100",
    ),
    _RequiredArtifact(
        "126",
        "126 - Orden EHA/3435/2007 (Ejercicios 2015 a 2019)",
        "ant_100_199/archivos/DR-126e16_v1.05.pdf",
        "h100",
    ),
    _RequiredArtifact(
        "128",
        "128 - Ejercicio 2020 y siguientes",
        "DR_100_199/archivos_20/128v01e2020_v1.07.xlsx",
        "100",
    ),
    _RequiredArtifact(
        "128",
        "128 - Orden EHA/3435/2007 (Ejercicios 2015 a 2019)",
        "ant_100_199/archivos/DR-128e16_v1.05.pdf",
        "h100",
    ),
    _RequiredArtifact(
        "130",
        "130 - Orden HAP/258/2015 (Ejercicios 2019 y siguientes, actualizado Marzo 2019) (176 KB - xls )",
        "DR_100_199/archivos/DR130e15v12.xls",
        "100",
    ),
    _RequiredArtifact(
        "130",
        "130 - Orden HAP/258/2015 (Ejercicios 2015 hasta 2018) (170 KB - xls )",
        "ant_100_199/archivos/DR130e15v11.xls",
        "h100",
    ),
    _RequiredArtifact(
        "130",
        "130 - Ejercicio 2008 (Trimestre 2º, 3º y 4º) (30 KB - pdf )",
        "ant_100_199/archivos/dr130.08.pdf",
        "h100",
    ),
    _RequiredArtifact(
        "130",
        "130 - Orden EHA/580/2009 (Ejercicios 2009 a 2014) (36 KB - pdf )",
        "ant_100_199/archivos/dr130.09.pdf",
        "h100",
    ),
    _RequiredArtifact(
        "130",
        "130 - Ejercicio 2007 y 2008 (Primer Trimestre) (48 KB - pdf )",
        "ant_100_199/archivos/dr130.pdf",
        "h100",
    ),
    _RequiredArtifact(
        "131",
        "131 - Ejercicios 2019 a 2023 (116 KB - xlsx )",
        "DR_100_199/archivos_20/DR131e2020_v1.01.xlsx",
        "h100",
    ),
    _RequiredArtifact(
        "131",
        "131 - Ejercicios 2024 (actualizado 13/12/24) (180 KB - xlsx )",
        "DR_100_199/archivos_24/DR131e2024.xlsx",
        "h100",
    ),
    _RequiredArtifact(
        "131",
        "131 - Ejercicios 2025 (actualizado 11/12/25) (179 KB - xlsx )",
        "DR_100_199/archivos_25/DR131e2025.xlsx",
        "h100",
    ),
    _RequiredArtifact(
        "131",
        "131 - Ejercicios 2026 (actualizado 04/03/26) (180 KB - xlsx )",
        "DR_100_199/archivos_26/DR131_2026.xlsx",
        "100",
    ),
    _RequiredArtifact(
        "131",
        "131 - Ejercicios 2015, 2016, 2017 y 2018 (29,8 KB - pdf )",
        "ant_100_199/archivos/DR131e2015_v1.02.pdf",
        "h100",
    ),
    _RequiredArtifact(
        "131",
        "131 - Ejercicio 2008 (Trimestre 2º, 3º y 4º) (31 KB - pdf )",
        "ant_100_199/archivos/dr131.08.pdf",
        "h100",
    ),
    _RequiredArtifact(
        "131",
        "131 - Orden EHA/580/2009 (Ejercicios 2009 a 2014) (26 KB - pdf )",
        "ant_100_199/archivos/dr131.09.pdf",
        "h100",
    ),
    _RequiredArtifact(
        "131",
        "131 - Ejercicio 2008 (Primer Trimestre) (49 KB - pdf )",
        "ant_100_199/archivos/dr131.pdf",
        "h100",
    ),
    _RequiredArtifact(
        "145",
        "145 - Diseno de registro version 2.0 (31-01-2012) (PDF)",
        "DR_100_199/archivos/dr145v20.pdf",
        None,
    ),
    _RequiredArtifact("151", "151 - Ejercicio 2023 y siguientes", "DR_100_199/DR151E2023.xls", "100"),
    _RequiredArtifact(
        "151",
        "151 - Orden HAP/2783/2015 (Ejercicios 2015-2022)",
        "DR_100_199/archivos/dr151e15v12.xls",
        "h100",
    ),
    _RequiredArtifact("156", "156 - Diseño de registro vigente", "DR_100_199/archivos/156_HAC_3580_2003.pdf", "100"),
    _RequiredArtifact(
        "165",
        "165 - Orden HAP/2455/2013 (actualizado por Orden HFP/1822/2016)",
        "DR_100_199/archivos/DR165_2016.pdf",
        "h100",
    ),
    _RequiredArtifact(
        "165",
        "165 - Diseño de registro actualizado en 2023",
        "DR_100_199/archivos_23/DR_Mod_165_2023.pdf",
        "100",
    ),
    _RequiredArtifact("165", "165 - Orden HAP/2455/2013", "ant_100_199/archivos/DLogicos_mod_165.pdf", "h100"),
    _RequiredArtifact(
        "180",
        "180 - Orden HAP/1732/2014, de 24 de septiembre (105 KB - pdf )",
        "DR_100_199/archivos/180.pdf",
        "h100",
    ),
    _RequiredArtifact(
        "180",
        "180 - Orden HAP/1732/2014 (actualizado por Orden HFP/1284/2023 de 28 de noviembre) (251 KB - pdf )",
        "DR_100_199/archivos_23/DR_Mod_180_2023.pdf",
        "100",
    ),
    _RequiredArtifact(
        "180",
        "180 - Orden de 20 de noviembre de 2000 (12 KB - pdf )",
        "ant_100_199/archivos/TIPOS18000.pdf",
        "h100",
    ),
    _RequiredArtifact(
        "181",
        "181 - Orden EHA/3514/2009 (Ejercicio 2017)",
        "DR_100_199/archivos_17/DR181_2017.pdf",
        "h100",
    ),
    _RequiredArtifact(
        "181",
        "181 - Diseño de registro actualizado en 2022",
        "DR_100_199/archivos_22/DR_181_2022.pdf",
        "100",
    ),
    _RequiredArtifact(
        "181",
        "181 - Orden EHA/3514/2009 (actualizado por Orden HFP/1923/2016)",
        "ant_100_199/archivos/DR181_2016.pdf",
        "h100",
    ),
    _RequiredArtifact("181", "181 - Orden EHA/3514/2009", "ant_100_199/archivos/dr181.pdf", "h100"),
    _RequiredArtifact("182", "182 - Ejercicio 2024", "DR_100_199/DR_Modelo_182_2024.pdf", "h100"),
    _RequiredArtifact("182", "182 - Ejercicio 2025", "DR_100_199/DR_Modelo_182_2025.pdf", "100"),
    _RequiredArtifact(
        "184",
        "184 - Ejercicio 2025 y siguientes modificados por Orden HAC/1430/2025, de 3 de diciembre (365 KB - pdf)",
        "DR_100_199/DR_Modelo_184_2025.pdf",
        "100",
    ),
    _RequiredArtifact(
        "184",
        "184 - Orden HAP/2250/2015 actualizada por Orden HFP/1284/2023",
        "DR_100_199/archivos_23/DR_Mod_184_2023.pdf",
        "h100",
    ),
    _RequiredArtifact("185", "185 - Ejercicio 2026 y siguientes", "DR_100_199/DR185_2025.pdf", "100"),
    _RequiredArtifact(
        "187",
        "187 - Diseño de registro actualizado en 2022",
        "DR_100_199/DR_Modelo_187_2022.pdf",
        "100",
    ),
    _RequiredArtifact(
        "188",
        "188 - Diseño de registro actualizado en 2023",
        "DR_100_199/archivos_23/DR_Mod_188_2023.pdf",
        "100",
    ),
    _RequiredArtifact(
        "189",
        "189 - Diseño de registro actualizado en 2023",
        "DR_100_199/archivos_23/DR_Mod_189_2023.pdf",
        "100",
    ),
    _RequiredArtifact(
        "190",
        (
            "190 - Orden EHA/3127/2009, de 10 de noviembre (actualizada por Orden HFP/1286/2023, de 28 de noviembre) "
            "(377 KB - pdf )"
        ),
        "DR_100_199/DR_190_2023.pdf",
        "h100",
    ),
    _RequiredArtifact(
        "190",
        (
            "190 - Orden EHA/3127/2009, de 10 de noviembre (actualizada por Orden HAC/1432/2024, de 11 de diciembre) "
            "(1,49 MB - pdf )"
        ),
        "DR_100_199/archivos_24/DISENOS_LOGICOS_190-2024.pdf",
        "h100",
    ),
    _RequiredArtifact(
        "190",
        (
            "190 - Orden EHA/3127/2009, de 10 de noviembre (actualizada por Orden HAC/1431/2025, de 3 de diciembre) "
            "(1.085 KB - pdf )"
        ),
        "DR_100_199/archivos_25/DISENOS_LOGICOS_190_2025.pdf",
        "100",
    ),
    _RequiredArtifact(
        "190",
        "190 - Orden EHA/3127/2009 (actualizada por Orden HAC/1285/2020) (814 KB - pdf )",
        "ant_100_199/archivos/Dr_190_2020.pdf",
        "h100",
    ),
    _RequiredArtifact(
        "193",
        "193 - Diseño de registro Modelo 193 - 2023 (866 KB - pdf )",
        "DR_100_199/DR_193_2023.pdf",
        "h100",
    ),
    _RequiredArtifact(
        "193",
        "193 - Orden EHA/3377/2011 (actualizado por Orden HAC/1504/2024, de 26 de diciembre) (352 KB - pdf )",
        "DR_100_199/DR_Modelo_193_2024.pdf",
        "h100",
    ),
    _RequiredArtifact(
        "193",
        "193 - Orden EHA/3377/2011 (actualizado por Orden HAC/1430/2025, de 3 de diciembre) (357 KB - pdf )",
        "DR_100_199/DR_Modelo_193_2025.pdf",
        "100",
    ),
    _RequiredArtifact(
        "193",
        "193 - Orden EHA/3377/2011 (actualizado por Orden HAC/1276/2019) (406 KB - pdf )",
        "DR_100_199/archivos_17/DR193_2017.pdf",
        "h100",
    ),
    _RequiredArtifact(
        "193",
        "193 - Orden EHA/3377/2011 (actualizado por Orden HFP/1822/2016) (185 KB - pdf )",
        "ant_100_199/archivos/DR193_2016.pdf",
        "h100",
    ),
    _RequiredArtifact(
        "193",
        "193 - Orden HAC/56/2024 (Ejercicios 2024 y siguientes) (556 KB - pdf )",
        "ant_100_199/archivos/DR_Mod_193.pdf",
        "h100",
    ),
    _RequiredArtifact(
        "193",
        "193 - Orden EHA/3377/2011, de 1 de diciembre (512 KB - pdf )",
        "ant_100_199/archivos/Disenyos_registro_193.pdf",
        "h100",
    ),
    _RequiredArtifact(
        "194",
        "194 - Diseño de registro actualizado en 2024",
        "DR_100_199/DR_Modelo_194_2024.pdf",
        "100",
    ),
    _RequiredArtifact(
        "194",
        "194 - Orden de 18 de enero de 1999 (actualizado por Orden HAC/1276/2019)",
        "DR_100_199/archivos/DR194_2016.pdf",
        "h100",
    ),
    _RequiredArtifact(
        "194",
        "194 - Diseño de registro actualizado en 2023",
        "ant_100_199/archivos/DR_Mod_194-2023.pdf",
        "h100",
    ),
    _RequiredArtifact(
        "200",
        "200 - Ejercicio 2020 - (Actualizado 28/07/2021) (9,56 MB - xls )",
        "DR_200_299/archivos_20/DR200-2020.xls",
        "h200",
    ),
    _RequiredArtifact(
        "200",
        "200 - Ejercicio 2021 (actualizado 22/06/2022) (11,1 MB - xls )",
        "DR_200_299/archivos_21/DR200-2021.xls",
        "h200",
    ),
    _RequiredArtifact(
        "200",
        "200 - Ejercicio 2022 (actualizado 30/06/2023) (10,2 MB - xls )",
        "DR_200_299/archivos_22/DR200-2022.xls",
        "h200",
    ),
    _RequiredArtifact(
        "200",
        "200 - Ejercicio 2023 (actualizado 15/07/2024) (10,4 MB - xls )",
        "DR_200_299/archivos_23/DR200-2023.xls",
        "h200",
    ),
    _RequiredArtifact(
        "200",
        "200 - Ejercicio 2024 (actualizado 13/10/2025) (10,7 MB - xls )",
        "DR_200_299/archivos_24/DR200-2024.xls",
        "h200",
    ),
    _RequiredArtifact(
        "200",
        "200 - Ejercicio 2025 (actualizado 19-06-2026) (11,2 MB - xls )",
        "DR_200_299/archivos_25/DR200e25.xls",
        "200",
    ),
    _RequiredArtifact("200", "200 - Ejercicio 2011 (522 KB - pdf )", "ant_200_299/archivos/DR200-2011.pdf", "h200"),
    _RequiredArtifact(
        "200",
        "200 - Ejercicio 2012. Actualizado a 28/06/2013 (539 KB - pdf )",
        "ant_200_299/archivos/DR200-2012.pdf",
        "h200",
    ),
    _RequiredArtifact(
        "200",
        "200 - Ejercicio 2013. Actualizado a 27/06/2014 (548 KB - pdf )",
        "ant_200_299/archivos/DR200-2013.pdf",
        "h200",
    ),
    _RequiredArtifact("200", "200 - Ejercicio 2014 (588 KB - pdf )", "ant_200_299/archivos/DR200-2014.pdf", "h200"),
    _RequiredArtifact(
        "200",
        "200 - Ejercicio 2015. Actualizado a 05/07/2016 (7,71 MB - xls )",
        "ant_200_299/archivos/DR200-2015.xls",
        "h200",
    ),
    _RequiredArtifact("200", "200 - Ejercicio 2016 (8,22 MB - xls )", "ant_200_299/archivos/DR200-2016.xls", "h200"),
    _RequiredArtifact(
        "200",
        "200 - Ejercicio 2017 (8,40 MB - xls )",
        "ant_200_299/archivos/DR200-2017-1_00.xls",
        "h200",
    ),
    _RequiredArtifact(
        "200",
        "200 - Ejercicio 2018 - (Actualizado 28/11/2019) (8,69 MB - xls )",
        "ant_200_299/archivos/DR200-2018.xls",
        "h200",
    ),
    _RequiredArtifact(
        "200",
        "200 - Ejercicio 2019 - (Actualizado 10/06/2020) (9,43 MB - xls )",
        "ant_200_299/archivos/DR200-2019.xls",
        "h200",
    ),
    _RequiredArtifact("200", "200 - Ejercicio 2010 (472 KB - pdf )", "ant_200_299/archivos/DR200_2010.pdf", "h200"),
    _RequiredArtifact(
        "200",
        "200 - Orden EHA/1338/2010 (Actualizado a 11/06/2010) (283 KB - pdf )",
        "ant_200_299/archivos/dr200e09v20.pdf",
        "h200",
    ),
    _RequiredArtifact(
        "202",
        "202 - Ejercicio 2025 y siguientes (actualizado 17-03-26) (132 KB - xlsx )",
        "DR_200_299/DR202e25.xlsx",
        "200",
    ),
    _RequiredArtifact(
        "202",
        "202 - Orden HAC/941/2018 (Ejercicios 2019 a 2022, actualizado Mayo 2020) (132 KB - xlsx )",
        "DR_200_299/archivos_19/DR202v52.xlsx",
        "h200",
    ),
    _RequiredArtifact(
        "202",
        "202 - Ejercicio 2023 a 2024 (actualizado 16-04-24) (130 KB - xlsx )",
        "DR_200_299/archivos_23/DR202e23.xlsx",
        "h200",
    ),
    _RequiredArtifact(
        "202",
        "202 - Ejercicio 2025 y siguientes, actualizado 14/07/2026",
        "DR_200_299/archivos_25/DR202e25.xlsx",
        "200",
    ),
    _RequiredArtifact(
        "202",
        "202 - Ejercicio 2008 y 2009 - Orden EHA/3435/2007 (32 KB - pdf )",
        "ant_200_299/archivos/202_2008.pdf",
        "h200",
    ),
    _RequiredArtifact(
        "202",
        "202 - Orden HAP/523/2015 (Ejercicios 2015) (125 KB - xlsx )",
        "ant_200_299/archivos/DR202e15v42.xlsx",
        "h200",
    ),
    _RequiredArtifact(
        "202",
        "202 - Orden HAP/523/2015 (1P 2016) (124 KB - xlsx )",
        "ant_200_299/archivos/DR202e16v43.xlsx",
        "h200",
    ),
    _RequiredArtifact(
        "202",
        "202 - Orden HAP/1552/2016 (Ejercicio 2P y 3P 2016) (128 KB - xlsx )",
        "ant_200_299/archivos/DR202e16v44.xlsx",
        "h200",
    ),
    _RequiredArtifact(
        "202",
        "202 - Orden HFP/227/2017 (Ejercicio 2017 y 1P de 2018) (129 KB - xlsx )",
        "ant_200_299/archivos/DR202e17v47.xlsx",
        "h200",
    ),
    _RequiredArtifact(
        "202",
        "202 - Orden HAC/941/2018 (Ejercicio 2018 2P y 3P) (129 KB - xlsx )",
        "ant_200_299/archivos/DR202e17v48.xlsx",
        "h200",
    ),
    _RequiredArtifact(
        "202",
        "202 - Orden HAC/941/2018 (Ejercicios 2019 y siguientes, actualizado Septiembre 2019) (128 KB - xlsx )",
        "ant_200_299/archivos/DR202e17v50.xlsx",
        "h200",
    ),
    _RequiredArtifact(
        "202",
        "202 Orden EHA/664/2010. (Adaptada a la última normativa vigente) (33 KB - pdf )",
        "ant_200_299/archivos/dr202e12v13.pdf",
        "h200",
    ),
    _RequiredArtifact(
        "202",
        "202 - Orden HAP/2055/2012 (v3.2) (40 KB - pdf )",
        "ant_200_299/archivos/dr202e12v32.pdf",
        "h200",
    ),
    _RequiredArtifact(
        "202",
        "202 - Orden HAP/636/2013 (v3.3) (39 KB - pdf )",
        "ant_200_299/archivos/dr202e12v33.pdf",
        "h200",
    ),
    _RequiredArtifact(
        "202",
        "202 - Orden HAP/2214/2013 (Ejercicios 3P 2013 y 2014) (46 KB - pdf )",
        "ant_200_299/archivos/dr202e13v34.pdf",
        "h200",
    ),
    _RequiredArtifact(
        "210",
        "210 - Diseño de Registro del modelo 210 (IRNR no residentes sin establecimiento permanente) vers. 1.1",
        "DR_200_299/archivos/dr210_2011.pdf",
        "200",
    ),
    _RequiredArtifact(
        "210",
        "210 - Devengos entre 01/06/2022 y 01/01/2026",
        "DR_200_299/archivos_22/dr210e22.xls",
        "h200",
    ),
    _RequiredArtifact("210", "210 - Devengos a partir de 2026", "DR_200_299/archivos_26/dr210_2026.xlsx", "200"),
    _RequiredArtifact("216", "216 - Ejercicios 2020 a 2023", "DR_200_299/archivos_20/216v01e2020_v1.07.xlsx", "h200"),
    _RequiredArtifact("216", "216 - Ejercicio 2024 y siguientes", "DR_200_299/archivos_24/216e2024.xlsx", "200"),
    _RequiredArtifact("220", "220 - Ejercicio 2022", "DR_200_299/archivos_22/DR220e22.xlsm", "h200"),
    _RequiredArtifact("220", "220 - Ejercicio 2023", "DR_200_299/archivos_23/DR220e23.xlsm", "h200"),
    _RequiredArtifact("220", "220 - Ejercicio 2024", "DR_200_299/archivos_24/DR220e24.xlsx", "h200"),
    _RequiredArtifact("220", "220 - Ejercicio 2025", "DR_200_299/archivos_25/DR220e25.xlsx", "200"),
    _RequiredArtifact("222", "222 - Ejercicios 2023 y 2024", "DR_200_299/archivos_23/DR222e23.xlsx", "h200"),
    _RequiredArtifact("222", "222 - Ejercicio 2025 y siguientes", "DR_200_299/archivos_25/DR222e25.xlsx", "200"),
    _RequiredArtifact(
        "232",
        "232 - Orden HFP/816/2017 (Ejercicio 2016 y siguientes, actualizado 15/01/2020) (145 KB - xlsx )",
        "DR_200_299/archivos_17/dr232e17v14.xlsx",
        "200",
    ),
    _RequiredArtifact(
        "232",
        "232 - Orden HFP/816/2017 (Ejercicios 2016-2017) (146 KB - xlsx )",
        "ant_200_299/archivos/dr232e17v13.xlsx",
        "h200",
    ),
    _RequiredArtifact(
        "270",
        "270 - Diseño de registro actualizado en 2023",
        "DR_200_299/archivos/270_HAP_2368_2013.pdf",
        "200",
    ),
    _RequiredArtifact(
        "280",
        "280 - Modelo 280. Declaracion informativa anual de Planes de Ahorro a Largo Plazo. Ejercicio 2022 (PDF)",
        "DR_100_199/archivos_22/DR_280_2022.pdf",
        None,
    ),
    _RequiredArtifact("296", "296 - Ejercicio 2023", "DR_200_299/DR_296_2023.pdf", "h200"),
    _RequiredArtifact("296", "296 - Ejercicio 2024", "DR_200_299/archivos_24/DR_296_2024.pdf", "200"),
    _RequiredArtifact(
        "303",
        (
            "303 - Orden HAP/2373/2014, de 9 de diciembre (ejercicio 2021 - hasta periodo 06) - actualizado 27/04/2021 "
            "(336 KB - xlsx )"
        ),
        "DR_300_399/archivos_21/DR303e21v103.xlsx",
        "h300",
    ),
    _RequiredArtifact(
        "303",
        "303 - Orden HAC/646/2021 (ejercicio 2021 - desde periodo 07) - actualizado 22/12/2021 (334 KB - xlsx )",
        "DR_300_399/archivos_21/DR303e21v200.xlsx",
        "h300",
    ),
    _RequiredArtifact(
        "303",
        "303 - Ejercicio 2022 y siguientes (actualizado 27/12/2021) (332 KB - xlsx )",
        "DR_300_399/archivos_22/DR303e22.xlsx",
        "h300",
    ),
    _RequiredArtifact(
        "303",
        "303 - Ejercicio 2023 (actualizado 14/12/23) (376 KB - xlsx )",
        "DR_300_399/archivos_23/DR303e23.xlsx",
        "h300",
    ),
    _RequiredArtifact(
        "303",
        "303 - Ejercicio 2024 (hasta periodos 08 y 2T) (actualizado 01/04/24) (376 KB - xlsx )",
        "DR_300_399/archivos_24/DR303e24.xlsx",
        "h300",
    ),
    _RequiredArtifact(
        "303",
        "303 - Ejercicio 2024 (a partir de periodos 09 y 3T) y siguientes (actualizado 29/11/24) (381 KB - xlsx )",
        "DR_300_399/archivos_24/DR303e24v200.xlsx",
        "h300",
    ),
    _RequiredArtifact(
        "303",
        "303 - Ejercicio 2025, URL oficial vigente",
        "DR_300_399/archivos_25/DR303e25.xlsx",
        "h300",
    ),
    _RequiredArtifact(
        "303",
        "303 - Ejercicio 2026 y siguientes (actualizado 28/01/26) (378 KB - xlsx )",
        "DR_300_399/archivos_26/DR303e26v101.xlsx",
        "300",
    ),
    _RequiredArtifact(
        "303",
        "303 - Orden EHA/3786/2008 (v1.1) (36 KB - pdf )",
        "ant_300_399/archivos/DR303e12v11.pdf",
        "h300",
    ),
    _RequiredArtifact(
        "303",
        "303 - Orden HAP/2373/2014, de 9 de diciembre (ejercicio 2014) (246 KB - xlsx )",
        "ant_300_399/archivos/DR303e14v22.xlsx",
        "h300",
    ),
    _RequiredArtifact(
        "303",
        "303 - Orden HAP/2373/2014, de 9 de diciembre (ejercicio 2015 y 2016) (247 KB - xlsx )",
        "ant_300_399/archivos/DR303e15v34.xlsx",
        "h300",
    ),
    _RequiredArtifact(
        "303",
        "303 - Orden HAP/2373/2014, de 9 de diciembre (ejercicio 2017) (292 KB - xlsx )",
        "ant_300_399/archivos/DR303e17v20_04.xlsx",
        "h300",
    ),
    _RequiredArtifact(
        "303",
        (
            "303 - Orden HAP/2373/2014, de 9 de diciembre (ejercicio 2018, salvo último periodo (12M/4T) de 2018) (292 "
            "KB - xlsx )"
        ),
        "ant_300_399/archivos/DR303e18v10_10.xlsx",
        "h300",
    ),
    _RequiredArtifact(
        "303",
        "303 - Orden HAP/2373/2014, de 9 de diciembre (ejercicio 2018) (292 KB - xlsx )",
        "ant_300_399/archivos/DR303e18v10_40.xlsx",
        "h300",
    ),
    _RequiredArtifact(
        "303",
        "303 - Orden HAP/2373/2014, de 9 de diciembre (ejercicio 2019 y 2020) (290 KB - xlsx )",
        "ant_300_399/archivos/DR303e20v10_20.xlsx",
        "h300",
    ),
    _RequiredArtifact(
        "308",
        "308 - 01-308-ejercicios-2019-y-siguientes-v13.xls",
        "DR_300_399/archivos/dr308e16v13.xls",
        "100",
    ),
    _RequiredArtifact(
        "308",
        "308 - Orden EHA/1033/2011 (Ejercicios 2009 a 2011- julio)",
        "ant_300_399/archivos/dr308.xls",
        "h300",
    ),
    _RequiredArtifact(
        "308",
        "308 - Orden EHA/1033/2011 (Ejercicios 2011 - julio - a 2015)",
        "ant_300_399/archivos/dr308_2011.pdf",
        "h300",
    ),
    _RequiredArtifact(
        "308",
        "308 - Orden EHA/1033/2011 (Ejercicios 2016 hasta 2018)",
        "ant_300_399/archivos/dr308e16v12.xls",
        "h300",
    ),
    _RequiredArtifact(
        "309",
        "309 - Orden EHA/3212/2004 (Ejercicios 2018 y posteriores)",
        "DR_300_399/archivos_17/dr309e17v13.xls",
        "h300",
    ),
    _RequiredArtifact(
        "309",
        "309 - 01-309-ejercicios-2023-y-siguientes.xls",
        "DR_300_399/archivos_23/dr309e23.xls",
        "100",
    ),
    _RequiredArtifact(
        "309",
        "309 - Orden EHA/3212/2004 (Ejercicios hasta 2015)",
        "ant_300_399/archivos/dr309_2004.pdf",
        "h300",
    ),
    _RequiredArtifact(
        "309",
        "309 - Orden EHA/3212/2004 (Ejercicios 2016 y 2017)",
        "ant_300_399/archivos/dr309e16v10.xls",
        "h300",
    ),
    _RequiredArtifact("322", "322 - Ejercicio 2022 y siguientes", "DR_300_399/archivos_22/DR322e22.xls", "h300"),
    _RequiredArtifact("322", "322 - Ejercicio 2023", "DR_300_399/archivos_23/DR322e23.xls", "h300"),
    _RequiredArtifact(
        "322",
        "322 - Ejercicios 2024 y 2025, actualizado 10/12/2025",
        "DR_300_399/archivos_24/DR322e24.xls",
        "h300",
    ),
    _RequiredArtifact(
        "322",
        "322 - 01-322-ejercicio-2026-y-siguientes-actualizado-28-01-26.xlsx",
        "DR_300_399/archivos_26/DR322e26v11.xlsx",
        "100",
    ),
    _RequiredArtifact("341", "341 - Ejercicio 2016 y siguientes", "DR_300_399/archivos/dr341_2016.xls", "300"),
    _RequiredArtifact(
        "341",
        "341 - Orden EHA/3212/2004 (Ejercicios hasta 2015)",
        "ant_300_399/archivos/dr341_2005.pdf",
        "h300",
    ),
    _RequiredArtifact("345", "345 - Ejercicio 2025", "DR_100_199/DR_Modelo_345_2025.pdf", "300"),
    _RequiredArtifact(
        "345",
        "345 - Diseño de registro actualizado en 2024",
        "DR_300_399/DR_Modelo_345_2024.pdf",
        "h300",
    ),
    _RequiredArtifact(
        "345",
        "345 - Orden de actualización del ejercicio 2023",
        "DR_300_399/archivos_23/DR_345_2023.pdf",
        "h300",
    ),
    _RequiredArtifact("345", "345 - Ejercicio 2023 y siguientes", "ant_300_399/archivos/dr345.pdf", "h300"),
    _RequiredArtifact(
        "347",
        "347 - Ejercicio 2025 y siguientes. Modificados por Orden HAC/1431/2025, de 3 de diciembre (332 KB - pdf )",
        "DR_300_399/archivos/347.pdf",
        "300",
    ),
    _RequiredArtifact(
        "347",
        "347 - Ejercicio 2008 y 2009 (30 KB - pdf )",
        "ant_300_399/archivos/347-2008-TIPOS.pdf",
        "h300",
    ),
    _RequiredArtifact(
        "347",
        "347 - Orden EHA/3062/2010. Ejercicio 2010 (181 KB - pdf )",
        "ant_300_399/archivos/347_2010_TIPOSV1.0.pdf",
        "h300",
    ),
    _RequiredArtifact(
        "347",
        "347 - Orden EHA/3378/2011, de 1 de diciembre (579 KB - pdf )",
        "ant_300_399/archivos/DLogicos_Registros_347.pdf",
        "h300",
    ),
    _RequiredArtifact(
        "349",
        "349 - Orden HAC/174/2020, de 4 de febrero (Ejercicio 2020 y siguientes) (894 KB - pdf )",
        "DR_300_399/archivos_20/DR_Anexo_349.pdf",
        "300",
    ),
    _RequiredArtifact(
        "349",
        "349 - Orden EHA/769/2010 (modificada por Orden EHA/1721/2011) (43,9 KB - docx )",
        "ant_300_399/archivos/NREG-349-2016.docx",
        "h300",
    ),
    _RequiredArtifact("349", "349 - Orden HAC/360/2002 (28 KB - pdf )", "ant_300_399/archivos/TIPOS34905.pdf", "h300"),
    _RequiredArtifact("353", "353 - Ejercicios 2021 a 2025", "DR_300_399/archivos_17/DR353e21v21.xls", "h300"),
    _RequiredArtifact(
        "353",
        "353 - 01-353-ejercicio-2026-y-siguientes-actualizado-03-02-26.xlsx",
        "DR_300_399/archivos_26/DR353e26v12.xlsx",
        "100",
    ),
    _RequiredArtifact(
        "353",
        "353 - Orden HAP/1222/2014 (Ejercicios 2015 y 2016)",
        "ant_300_399/archivos/DR353e16v19.xls",
        "h300",
    ),
    _RequiredArtifact(
        "353",
        "353 -Orden EHA/3434/2007 (Ejercicio 2020)",
        "ant_300_399/archivos/DR353e17v20.xls",
        "h300",
    ),
    _RequiredArtifact(
        "353",
        "353 - Orden HAP/1222/2014 (Ejercicios 2017, 2108 y 2019)",
        "ant_300_399/archivos/DR353e17v20.xlsx",
        "h300",
    ),
    _RequiredArtifact("353", "353 - Orden EHA/3434/2007", "ant_300_399/archivos/dr353.pdf", "h300"),
    _RequiredArtifact("353", "353 - Orden EHA/3786/2008", "ant_300_399/archivos/dr353v13.pdf", "h300"),
    _RequiredArtifact("360", "360 - Orden EHA/789/2010", "DR_300_399/archivos/DR360.pdf", "300"),
    _RequiredArtifact(
        "369",
        (
            "369 - Regímenes especiales aplicables a los servicios prestados a personas que no tengan la condición de "
            "sujetos pasivos o a las ventas a distancia de bienes o determinadas entregas nacionales de bienes. "
            "Autoliquidación - actualizado 17/09/2021 (936 KB - xlsx )"
        ),
        "DR_300_399/archivos_21/DR369e21.xlsx",
        "300",
    ),
    _RequiredArtifact(
        "390",
        "390 - Ejercicio 2019 y 2020 (actualizado 23/12/2020) (485 KB - xlsx )",
        "DR_300_399/archivos_19/dr390e2019v101.xlsx",
        "h300",
    ),
    _RequiredArtifact(
        "390",
        "390 - Ejercicio 2021 (actualizado 25/11/2021) (486 KB - xlsx )",
        "DR_300_399/archivos_21/dr390e2021.xlsx",
        "h300",
    ),
    _RequiredArtifact(
        "390",
        "390 - Ejercicio 2022 (actualizado 04/01/23) (491 KB - xlsx )",
        "DR_300_399/archivos_22/dr390e2022.xlsx",
        "h300",
    ),
    _RequiredArtifact(
        "390",
        "390 - Ejercicio 2023 y siguientes (489 KB - xlsx )",
        "DR_300_399/archivos_23/dr390e2023v100.xlsx",
        "h300",
    ),
    _RequiredArtifact(
        "390",
        "390 - Ejercicio 2024 (actualizado 18/12/24) (544 KB - xlsx )",
        "DR_300_399/archivos_24/dr390e2024.xlsx",
        "h300",
    ),
    _RequiredArtifact("390", "390 - Ejercicio 2025", "DR_300_399/archivos_25/dr390e2025.xlsx", "300"),
    _RequiredArtifact(
        "390",
        "390 - Ejercicio 2015 (103 KB - pdf )",
        "ant_300_399/archivos/390v01e2015_v1.00.pdf",
        "h300",
    ),
    _RequiredArtifact(
        "390",
        "390 - Ejercicio 2016 (22-12-2016) (505 KB - xlsx )",
        "ant_300_399/archivos/390v01e2016_v1.00.xlsx",
        "h300",
    ),
    _RequiredArtifact(
        "390",
        "390 y 392 - Ejercicio 2004, 2005 y 2006 (37 KB - Ejecutable)",
        "ant_300_399/archivos/IVA2006.xsd",
        "h300",
    ),
    _RequiredArtifact(
        "390",
        "390 y 392 - Ejercicio 2007 (35 KB - Ejecutable)",
        "ant_300_399/archivos/IVA2007.xsd",
        "h300",
    ),
    _RequiredArtifact(
        "390",
        "390/392 - Ejercicio 2008 (38 KB - Ejecutable)",
        "ant_300_399/archivos/IVA2008.xsd",
        "h300",
    ),
    _RequiredArtifact("390", "390 - Ejercicio 2009 (40 KB - Ejecutable)", "ant_300_399/archivos/IVA2009.xsd", "h300"),
    _RequiredArtifact("390", "390 - Ejercicio 2010 (43 KB - Ejecutable)", "ant_300_399/archivos/IVA2010.xsd", "h300"),
    _RequiredArtifact("390", "390 - Ejercicio 2011 (43 KB - Ejecutable)", "ant_300_399/archivos/IVA2011.xsd", "h300"),
    _RequiredArtifact("390", "390 - Ejercicio 2012 (46 KB - Ejecutable)", "ant_300_399/archivos/IVA2012.xsd", "h300"),
    _RequiredArtifact("390", "390 - Ejercicio 2013 (45 KB - Ejecutable)", "ant_300_399/archivos/IVA2013.xsd", "h300"),
    _RequiredArtifact("390", "390 - Ejercicio 2014 (47,1 KB - Ejecutable)", "ant_300_399/archivos/IVA2014.xsd", "h300"),
    _RequiredArtifact("390", "390 - Ejercicio 2017 (492 KB - xlsx )", "ant_300_399/archivos/dr390e2017v3.xlsx", "h300"),
    _RequiredArtifact(
        "390",
        "390 - Ejercicio 2018 (488 KB - xlsx )",
        "ant_300_399/archivos/dr390e2018v101.xlsx",
        "h300",
    ),
    _RequiredArtifact(
        "490",
        "490 - Orden HAC/590/2021 (Ejercicio 2021 y 2022 hasta periodo 1T)",
        "DR_Resto_Mod/archivos/dr490e21.xlsx",
        "hresto",
    ),
    _RequiredArtifact(
        "490",
        "490 - Orden HAC/590/2021 (Ejercicio 2022 periodo 2T-4T)",
        "DR_Resto_Mod/archivos/dr490e22.xlsx",
        "hresto",
    ),
    _RequiredArtifact("490", "490 - Ejercicio 2023 y siguientes", "DR_Resto_Mod/archivos/dr490e23.xlsx", "resto"),
    _RequiredArtifact("576", "576 - Diseño de registro vigente", "DR_Resto_Mod/archivos/dr576.xlsx", "resto"),
    _RequiredArtifact("604", "604 - Ejercicios 2021 a 2023", "DR_Resto_Mod/archivos/DR604_2021.xlsx", "resto"),
    _RequiredArtifact("604", "604 - Ejercicio 2024", "DR_Resto_Mod/archivos/DR604_2024.xlsx", "resto"),
    _RequiredArtifact("604", "604 - Diseño de registro ATF en español", "DR_Resto_Mod/archivos/DR_ATF.pdf", "resto"),
    _RequiredArtifact(
        "604",
        "604 - Diseño de registro ATF en inglés",
        "DR_Resto_Mod/archivos/DR_ATF_Ingles.pdf",
        "resto",
    ),
    _RequiredArtifact("714", "714 - Ejercicio 2024", "DR_Resto_Mod/DR714_2024.xls", "hresto"),
    _RequiredArtifact("714", "714 - Ejercicio 2025 (820 KB - xls)", "DR_Resto_Mod/DR714_2025.xls", "resto"),
    _RequiredArtifact(
        "714",
        "714 - Ejercicio 2021. Actualizacion 29/04/2022",
        "DR_Resto_Mod/archivos/DR714_2021.xls",
        "hresto",
    ),
    _RequiredArtifact("714", "714 - Ejercicio 2022", "DR_Resto_Mod/archivos/DR714_2022.xls", "hresto"),
    _RequiredArtifact("714", "714 - Ejercicio 2023", "DR_Resto_Mod/archivos/DR714_2023.xls", "hresto"),
    _RequiredArtifact("720", "720 (599 KB - pdf )", "DR_Resto_Mod/archivos/modelo_720.pdf", "resto"),
    _RequiredArtifact(
        "763",
        "763 - Desde 2018 4T y siguientes, actualizado en 2023",
        "DR_Resto_Mod/archivos/DR763e18.xlsx",
        "resto",
    ),
    _RequiredArtifact(
        "763",
        "763 - Orden EHA/1881/2011 (Ejercicios 2T/3T 2012, 2013 y 2014)",
        "ant_resto_mod/archivos/dr763e2011v11.pdf",
        "hresto",
    ),
    _RequiredArtifact(
        "763",
        "763 - Ejercicios 2015 a 2018 hasta 3T",
        "ant_resto_mod/archivos/dr763e2015v11.xlsx",
        "hresto",
    ),
    _RequiredArtifact("840", "840 - Orden HAC/2572/2003 (99 KB - pdf )", "DR_Resto_Mod/archivos/dr840.pdf", "resto"),
)


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


def _load_manifests() -> dict[str, _Manifest]:
    manifests: dict[str, _Manifest] = {}
    for model_dir in scan_directory(_CORPUS, pattern="modelo_*"):
        path = model_dir / "manifest.json"
        if path.exists():
            manifests[model_dir.name.removeprefix("modelo_")] = json.loads(path.read_text(encoding=_UTF_8))
    return manifests


def _payload_paths(corpus_root: Path) -> tuple[PurePosixPath, ...]:
    """Return the bounded payload candidates owned by this synchronizer.

    Project declarations and extractor outputs are intentionally outside this
    acquisition boundary: the catalog compiler assigns payload roles here,
    while their disposition and derivation contracts remain with their owners
    until the later migration steps.  This function discovers candidates only;
    it does not decide whether they have an acceptable acquisition identity.
    """
    paths: list[PurePosixPath] = []
    for model_dir in scan_directory(corpus_root, pattern="modelo_*"):
        for candidate in sorted(model_dir.rglob("*")):
            if (
                not candidate.is_file()
                or candidate.name in _DECLARATION_NAMES
                or candidate.name.endswith(_DERIVED_SUFFIXES)
            ):
                continue
            paths.append(PurePosixPath(candidate.relative_to(corpus_root).as_posix()))
    return tuple(paths)


def _catalogue_diagnostic_message(diagnostic: ArtifactDiagnostic) -> str:
    """Render a typed catalog finding at this CLI's existing failure boundary."""
    path = "<unknown>" if diagnostic.path is None else diagnostic.path.as_posix()
    return f"artifact catalog {diagnostic.kind.value}: {path}: {diagnostic.message}"


def _record_design_catalogue(
    manifests: dict[str, _Manifest],
    corpus_root: Path,
) -> tuple[ArtifactCatalogue | None, list[str]]:
    """Compile manifest acquisition identity for this synchronizer's payloads.

    The compiler owns the canonical path join and payload classification.  The
    synchronizer deliberately retains byte rehashing and retrieval checks;
    catalog compilation is an identity/role projection, not a replacement for
    either.  Production ``check`` always fails closed on an incomplete
    identity row.
    """
    derived_paths = {derivative.path for derivative in _EXTRACTION_SIDECAR_DERIVATIONS}
    identities = []
    failures: list[str] = []
    for modelo, manifest in sorted(manifests.items()):
        manifest_path = PurePosixPath(f"modelo_{modelo}/{_MANIFEST_NAME}")
        try:
            identities.extend(
                identity
                for identity in record_design_manifest_identities(manifest, manifest_path=manifest_path)
                if identity.path not in derived_paths
            )
        except (TypeError, ValueError) as error:
            failures.append(f"manifest acquisition identity is malformed: M{modelo}: {error}")
    if failures:
        return None, failures
    catalogue = compile_artifact_catalogue(
        known_paths=_payload_paths(corpus_root),
        official_identities=identities,
        derived_artifacts=_EXTRACTION_SIDECAR_DERIVATIONS,
    )
    return catalogue, []


def unattested_corpus_files(corpus_root: Path) -> tuple[str, ...]:
    """Corpus files under ``corpus_root`` that no manifest declares.

    :func:`check` walks the manifests and confirms every declared artefact
    is on disk with the recorded size and digest. That direction cannot see
    a file the manifests do not mention, and the manifest has no way to say
    'present but not yet attested': an artefact is either a fully described
    entry or absent. So a run that writes payload bytes and stops before
    rewriting the manifests, or a partial revert of a bulk removal, leaves
    corpus content carrying no source URL, licence, digest or retrieval date
    while every count in every manifest still reconciles.

    Under-declaration of exactly this kind is silent, which is why the walk
    runs in both directions.

    Args:
        corpus_root: Directory holding the ``modelo_*`` corpus directories.

    Returns:
        Corpus-root-relative POSIX paths, sorted, of every present file that
        is neither a declaration, a known derivative, nor a declared artefact.
    """
    unattested: list[str] = []
    for model_dir in scan_directory(corpus_root, pattern="modelo_*"):
        manifest_path = model_dir / _MANIFEST_NAME
        if not manifest_path.exists():
            continue
        manifest = json.loads(manifest_path.read_text(encoding=_UTF_8))
        declared = {model_dir / artifact["stored_path"] for artifact in manifest["artefacts"]}
        for candidate in sorted(model_dir.rglob("*")):
            if not candidate.is_file() or candidate.name in _DECLARATION_NAMES:
                continue
            if candidate.name.endswith(_DERIVED_SUFFIXES):
                continue
            if candidate not in declared:
                unattested.append(candidate.relative_to(corpus_root).as_posix())
    return tuple(sorted(unattested))


def _load_historical_exclusions() -> _HistoricalExclusions:
    """Read the classified historical-URL exclusions.

    The file's ``support_years`` window does NOT describe what the corpus
    actually ships, and the discrepancy is not theoretical: ``DR714_2022.xls``
    is bundled and represented in ``modelo_714/manifest.json`` while sitting
    outside the declared ``[2023, 2024, 2025, 2026]`` window, so the stated rule
    already has a live counter-example. Reading the window as the reason a URL is
    absent will therefore mislead: ``DR714_2021.xls`` was excluded under it, was
    then found to be genuinely published and fit, and was bundled. Treat the
    ``urls`` list as the authority for what is classified out, and the window as
    prose that has drifted from it.
    """
    # `json.loads` is typed `Any`; the cast states the shape this endpoint
    # is documented to return, in one place instead of at every use.
    return cast(
        "_HistoricalExclusions",
        json.loads(_HISTORICAL_EXCLUSIONS_PATH.read_text(encoding=_UTF_8)),
    )


def _artifact_urls(artifact: _Artifact) -> set[str]:
    return {str(artifact["url"]), *(str(url) for url in artifact.get("url_aliases", []))}


def _index_links(html: str, source_page: str) -> tuple[tuple[str, str], ...]:
    parser = _IndexLinkParser()
    parser.feed(html)
    return tuple((title, urljoin(source_page, href)) for title, href in parser.links)


def _supported_modelo_from_title(title: str, supported_modelos: set[str]) -> str | None:
    match = re.match(r"^(\d{2,3})\b", title)
    if match is None:
        return None
    modelo = str(match.group(1)).zfill(3)
    return modelo if modelo in supported_modelos else None


def _raw_artifact_for_url(manifest: _Manifest, url: str) -> _Artifact | None:
    url_suffix = Path(urlparse(url).path).suffix.lower()
    return next(
        (
            artifact
            for artifact in manifest["artefacts"]
            if url in _artifact_urls(artifact) and Path(str(artifact["stored_path"])).suffix.lower() == url_suffix
        ),
        None,
    )


def _supported_index_urls(
    links_by_page: dict[str, dict[str, str]],
    page_keys: tuple[str, ...],
    supported_modelos: set[str],
) -> dict[str, str]:
    urls: dict[str, str] = {}
    for page_key in page_keys:
        for url, title in links_by_page[_PAGES[page_key]].items():
            modelo = _supported_modelo_from_title(title, supported_modelos)
            suffix = Path(urlparse(url).path).suffix.lower()
            if modelo is None or "/Disenyo_registro/" not in url or suffix not in _RECORD_DESIGN_SUFFIXES:
                continue
            urls[url] = modelo
    return urls


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


def _write_root_manifest(root: dict[str, object]) -> None:
    (_CORPUS / "manifest.json").write_bytes((json.dumps(root, ensure_ascii=False, indent=2) + "\n").encode())


def _regenerate_root_aggregate() -> None:
    """Rewrite the root manifest's census from the per-modelo manifests, offline.

    The census is derived from files already on disk, so repairing it needs
    no network. Before this path existed the only writer was ``--pull``, and
    a purely local number could drift with no local way to correct it: it did,
    and the offline check stayed red against an unreachable repair.

    ``retrieved_at`` is deliberately NOT touched. Nothing was retrieved, and
    advancing a retrieval date to record a recount would assert a freshness
    this run did not establish.
    """
    manifests = _load_manifests()
    root = cast("dict[str, object]", json.loads((_CORPUS / "manifest.json").read_text(encoding=_UTF_8)))
    aggregate = _root_aggregate(manifests)
    drifted = sorted(field for field, value in aggregate.items() if root.get(field) != value)
    if not drifted:
        print("OK: root manifest census already agrees with the per-modelo manifests")
        return
    root.update(aggregate)
    _write_root_manifest(root)
    print(f"REGENERATED root manifest census: {', '.join(drifted)}")


def _write_manifests(manifests: dict[str, _Manifest]) -> None:
    for modelo, manifest in manifests.items():
        artifacts = manifest["artefacts"]
        manifest["artefact_count"] = len(artifacts)
        path = _CORPUS / f"modelo_{modelo}" / "manifest.json"
        path.write_bytes((json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode())

    root = cast("dict[str, object]", json.loads((_CORPUS / "manifest.json").read_text(encoding=_UTF_8)))
    root["retrieved_at"] = _RETRIEVED_AT
    root.update(_root_aggregate(manifests))
    _write_root_manifest(root)


def _pull() -> None:
    manifests = _load_manifests()
    with httpx.Client(
        follow_redirects=True,
        timeout=90,
        headers={"User-Agent": "cadrumo-corpus-hydration/1.0"},
    ) as client:
        for index, required in enumerate(_REQUIRED, 1):
            manifest = manifests.get(required.modelo)
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
                    continue

            response = client.get(required.url)
            response.raise_for_status()
            data = response.content
            extension = Path(urlparse(str(response.url)).path).suffix.lower()
            if not _valid_signature(extension, data):
                raise RuntimeError(f"Unexpected signature for {required.url}")
            digest = _sha256_bytes(data)
            print(f"FETCH {index:02d}/{len(_REQUIRED)} M{required.modelo} {len(data):>9} {digest[:12]}")

            model_dir = _CORPUS / f"modelo_{required.modelo}"
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
                continue

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
    _write_manifests(manifests)


def _authority_failures(
    manifests: dict[str, _Manifest],
    catalogue: ArtifactCatalogue | None = None,
) -> list[str]:
    """Report manifest artefacts that lack one official catalog identity.

    The catalog owns the complete immutable acquisition identity, including
    documents acquired from a non-AEAT publisher.  The synchronizer retains
    byte rehashing; catalogued derivatives retain their exact input identity.
    """
    failures: list[str] = []
    catalogue_is_local = catalogue is None
    if catalogue_is_local:
        derived_paths = {derivative.path for derivative in _EXTRACTION_SIDECAR_DERIVATIONS}
        identities = []
        for modelo, manifest in sorted(manifests.items()):
            try:
                identities.extend(
                    identity
                    for identity in record_design_manifest_identities(
                        manifest,
                        manifest_path=PurePosixPath(f"modelo_{modelo}/{_MANIFEST_NAME}"),
                    )
                    if identity.path not in derived_paths
                )
            except (TypeError, ValueError) as error:
                failures.append(f"manifest acquisition identity is malformed: M{modelo}: {error}")
        catalogue = compile_artifact_catalogue(
            known_paths=tuple(identity.path for identity in identities)
            + tuple(derivative.path for derivative in _EXTRACTION_SIDECAR_DERIVATIONS),
            official_identities=identities,
            derived_artifacts=_EXTRACTION_SIDECAR_DERIVATIONS,
        )
    if catalogue_is_local:
        failures.extend(_catalogue_diagnostic_message(diagnostic) for diagnostic in catalogue.diagnostics)
    for modelo, manifest in sorted(manifests.items()):
        for artifact in manifest["artefacts"]:
            path = f"modelo_{modelo}/{artifact['stored_path']}"
            catalog_role = catalogue.roles.get(PurePosixPath(path))
            if catalog_role is ArtifactRole.DERIVED_ARTIFACT:
                continue
            catalog_identity = catalogue.identities.get(PurePosixPath(path))
            if catalog_identity is None or catalog_role is not ArtifactRole.OFFICIAL_ARTIFACT:
                failures.append(f"artefact does not bind an official catalog identity: M{modelo} {path}")
                continue
            # A catalog identity proves provenance, but not reproducibility by
            # the acquisition writer: `_pull` names files from the response URL
            # extension. A divergent stored suffix therefore remains a failure.
            stored_suffix = PurePosixPath(artifact["stored_path"]).suffix.lower()
            url_suffix = PurePosixPath(urlparse(artifact["url"]).path).suffix.lower()
            if stored_suffix != url_suffix:
                failures.append(
                    f"artefact is not reproducible from its declared URL: M{modelo} {path} "
                    f"stored {stored_suffix or '<none>'} but {artifact['url']} serves {url_suffix or '<none>'}"
                )
    return failures


def check() -> None:
    """Verify required official URLs, manifests, and local artifact bytes offline."""
    manifests = _load_manifests()
    historical_exclusions = _load_historical_exclusions()
    failures = []
    catalogue, catalogue_failures = _record_design_catalogue(manifests, _CORPUS)
    failures.extend(catalogue_failures)
    if catalogue is not None:
        failures.extend(
            _catalogue_diagnostic_message(diagnostic)
            for diagnostic in catalogue.diagnostics
            if diagnostic.kind is not ArtifactDiagnosticKind.UNKNOWN_FILE
        )
    for required in _REQUIRED:
        manifest = manifests.get(required.modelo)
        if manifest is None or not any(required.url in _artifact_urls(artifact) for artifact in manifest["artefacts"]):
            failures.append(f"missing official URL: M{required.modelo} {required.url}")
    for modelo, manifest in manifests.items():
        model_dir = _CORPUS / f"modelo_{modelo}"
        for artifact in manifest["artefacts"]:
            path = model_dir / artifact["stored_path"]
            if not path.is_file():
                failures.append(f"missing artifact: {path}")
                continue
            if path.stat().st_size != artifact["bytes"]:
                failures.append(f"byte mismatch: {path}")
            if sha256_path(path) != artifact["sha256"]:
                failures.append(f"sha256 mismatch: {path}")
    root = json.loads((_CORPUS / "manifest.json").read_text(encoding=_UTF_8))
    aggregate = _root_aggregate(manifests)
    expected_models = aggregate["supported_corpus_modelos"]
    expected_artifact_count = aggregate["artefact_count"]
    expected_rows = aggregate["modelos"]
    # Each staleness report names the observed and expected values. "is stale"
    # alone states that something drifted and withholds what, so the reader
    # cannot tell a one-artefact addition from a wholesale corpus change, and
    # the cheapest response to an unactionable verdict is to regenerate blindly.
    recorded_models = root.get("supported_corpus_modelos")
    if recorded_models != expected_models:
        missing = sorted(set(expected_models) - set(recorded_models or []))
        extra = sorted(set(recorded_models or []) - set(expected_models))
        failures.append(f"root manifest supported_corpus_modelos is stale: missing {missing}, unexpected {extra}")
    if root.get("model_count") != len(expected_models):
        failures.append(
            f"root manifest model_count is stale: records {root.get('model_count')}, "
            f"corpus holds {len(expected_models)}"
        )
    if root.get("artefact_count") != expected_artifact_count:
        failures.append(
            f"root manifest artefact_count is stale: records {root.get('artefact_count')}, "
            f"corpus holds {expected_artifact_count}"
        )
    if root.get("modelos") != expected_rows:
        recorded_counts = {row["modelo"]: row["artefact_count"] for row in root.get("modelos") or []}
        expected_counts = {row["modelo"]: row["artefact_count"] for row in expected_rows}
        drifted = [
            f"{modelo} records {recorded_counts.get(modelo)} holds {expected_counts.get(modelo)}"
            for modelo in sorted(set(recorded_counts) | set(expected_counts))
            if recorded_counts.get(modelo) != expected_counts.get(modelo)
        ]
        failures.append("root manifest per-model counts are stale: " + "; ".join(drifted))
    if any(failure.startswith("root manifest") for failure in failures):
        failures.append("repair the root manifest census offline with --regenerate-aggregate")
    exclusion_urls = historical_exclusions.get("urls", [])
    expected_historical_pages = [_PAGES[key] for key in _HISTORICAL_PAGE_KEYS]
    if historical_exclusions.get("schema_version") != 1:
        failures.append("historical exclusion schema_version is stale")
    if historical_exclusions.get("support_years") != [2023, 2024, 2025, 2026]:
        failures.append("historical exclusion support_years is stale")
    if historical_exclusions.get("disposition") != "outside-supported-window-or-superseded":
        failures.append("historical exclusion disposition is stale")
    if historical_exclusions.get("source_pages") != expected_historical_pages:
        failures.append("historical exclusion source_pages are stale")
    if len(exclusion_urls) != len(set(exclusion_urls)):
        failures.append("historical exclusion URLs are not unique")
    represented_urls = {
        url for manifest in manifests.values() for artifact in manifest["artefacts"] for url in _artifact_urls(artifact)
    }
    conflicting_exclusions = sorted(set(exclusion_urls) & represented_urls)
    if conflicting_exclusions:
        failures.append(f"historical exclusions are already represented: {conflicting_exclusions[:5]!r}")
    observed_unattested = (
        tuple(
            diagnostic.path.as_posix()
            for diagnostic in catalogue.diagnostics
            if diagnostic.kind is ArtifactDiagnosticKind.UNKNOWN_FILE and diagnostic.path is not None
        )
        if catalogue is not None
        else unattested_corpus_files(_CORPUS)
    )
    if observed_unattested != _UNATTESTED_CORPUS_FILES:
        appeared = sorted(set(observed_unattested) - set(_UNATTESTED_CORPUS_FILES))
        attested = sorted(set(_UNATTESTED_CORPUS_FILES) - set(observed_unattested))
        failures.append(
            "corpus files carrying no manifest entry have changed: "
            f"newly unattested {appeared}, no longer unattested {attested}"
        )
    required_urls = {required.url for required in _REQUIRED}
    required_exclusions = sorted(set(exclusion_urls) & required_urls)
    if required_exclusions:
        failures.append(f"required URLs are classified as historical exclusions: {required_exclusions[:5]!r}")
    failures.extend(
        _authority_failures(
            manifests,
            catalogue,
        )
    )
    if failures:
        raise SystemExit("\n".join(failures))
    print(f"OK: {len(_REQUIRED)} required official URLs and {len(manifests)} manifests")


#: Exit status for "the question could not be asked", as distinct from a pass or
#: a drift finding. AEAT republishes on its own schedule and its site is not
#: always reachable; a run that could not read the official pages has learned
#: NOTHING about staleness, and reporting that as either outcome would be a lie
#: in one direction or the other. Callers key on this status rather than parsing
#: the message.
LIVE_CHECK_UNAVAILABLE: Final[int] = 75


def _live_check() -> None:
    """Compare the captured corpus against the live official pages.

    Three outcomes, deliberately distinguished. The corpus matches; the corpus
    has drifted and the differences are named; or the official source could not
    be read at all, which is reported as a LIMITATION and never as either of the
    other two.
    """
    try:
        _live_check_against_official_pages()
    except (httpx.TransportError, httpx.HTTPStatusError) as unreachable:
        status = getattr(getattr(unreachable, "response", None), "status_code", None)
        if isinstance(unreachable, httpx.HTTPStatusError) and status is not None and status < 500:
            # A 4xx on a URL the corpus expects is a finding about the corpus,
            # not about the network: the official page stopped serving it.
            raise SystemExit(f"official URL no longer served ({status}): {unreachable.request.url}") from unreachable
        print(
            f"LIMITATION: the official source could not be read ({type(unreachable).__name__}); "
            f"staleness is UNKNOWN, not clean",
            file=sys.stderr,
        )
        raise SystemExit(LIVE_CHECK_UNAVAILABLE) from unreachable


def _live_check_against_official_pages() -> None:
    manifests = _load_manifests()
    historical_exclusions = _load_historical_exclusions()
    root = json.loads((_CORPUS / "manifest.json").read_text(encoding=_UTF_8))
    supported_modelos = {str(modelo) for modelo in root["supported_corpus_modelos"]}
    links_by_page: dict[str, dict[str, str]] = {}
    failures: list[str] = []

    with httpx.Client(
        follow_redirects=True,
        timeout=90,
        headers={"User-Agent": "cadrumo-corpus-currentness/1.0"},
    ) as client:
        for source_page in _PAGES.values():
            response = client.get(source_page)
            response.raise_for_status()
            links_by_page[source_page] = {url: title for title, url in _index_links(response.text, source_page)}

        # A declaration with no established index page cannot be asked whether
        # it is still indexed: there is no page to look on. Reporting that as a
        # pass would claim a check that did not run, and as a failure would
        # claim drift that was never observed, so it is counted and named.
        unadjudicated = [required for required in _REQUIRED if required.source_page is None]
        for required in _REQUIRED:
            if required.source_page is None:
                continue
            if required.url not in links_by_page[required.source_page]:
                failures.append(f"required URL no longer indexed: M{required.modelo} {required.url}")

        current_urls = _supported_index_urls(links_by_page, _CURRENT_PAGE_KEYS, supported_modelos)
        historical_urls = _supported_index_urls(links_by_page, _HISTORICAL_PAGE_KEYS, supported_modelos)
        represented_urls = {
            url
            for manifest in manifests.values()
            for artifact in manifest["artefacts"]
            for url in _artifact_urls(artifact)
        }
        expected_exclusions = set(historical_exclusions["urls"])
        actual_exclusions = set(historical_urls) - represented_urls
        for url in sorted(actual_exclusions - expected_exclusions):
            failures.append(f"unclassified historical official URL: M{historical_urls[url]} {url}")
        for url in sorted(expected_exclusions - actual_exclusions):
            failures.append(f"stale historical URL exclusion: {url}")

        for url, modelo in sorted(current_urls.items()):
            manifest = manifests[modelo]
            artifact = _raw_artifact_for_url(manifest, url)
            if artifact is None:
                failures.append(f"unrepresented current official URL: M{modelo} {url}")
                continue
            response = client.get(url)
            response.raise_for_status()
            data = response.content
            if len(data) != artifact["bytes"] or _sha256_bytes(data) != artifact["sha256"]:
                failures.append(f"current official bytes drifted: M{modelo} {url}")

    if failures:
        raise SystemExit("\n".join(failures))
    print(
        f"OK live: {len(current_urls)} current raw URLs and {len(_REQUIRED) - len(unadjudicated)} "
        f"required indexed URLs plus {len(historical_urls)} classified historical URLs "
        f"across {len(_PAGES)} pages",
    )
    if unadjudicated:
        print(
            f"LIMITATION: {len(unadjudicated)} required URLs carry no established index page and were "
            f"not checked for continued indexing: "
            + ", ".join(f"M{required.modelo} {required.url}" for required in unadjudicated),
        )


def main() -> None:
    """Run the offline integrity check, optionally pulling official sources first."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--pull", action="store_true")
    parser.add_argument(
        "--regenerate-aggregate",
        action="store_true",
        help="Recompute the root manifest census from the per-modelo manifests without fetching.",
    )
    parser.add_argument("--live-check", action="store_true")
    args = parser.parse_args()
    if args.pull:
        _pull()
    if args.regenerate_aggregate:
        _regenerate_root_aggregate()
    check()
    if args.live_check:
        _live_check()


if __name__ == "__main__":
    main()
