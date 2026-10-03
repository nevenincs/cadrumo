"""Declared official acquisition inventory and corpus classification policy."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Final

from dev.corpus.artifact_catalogue import DerivedArtifact

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
