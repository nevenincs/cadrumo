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
from pathlib import Path
from typing import Final, NotRequired, TypedDict, override
from urllib.parse import urljoin, urlparse

import httpx

_UTF_8: Final[str] = "utf-8"
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if not __package__:
    __package__ = "dev.corpus"

from cadrumo.core.directory_scan import iter_directory, scan_directory  # noqa: E402

from ..packaging._hashing import sha256_path  # noqa: E402

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


@dataclass(frozen=True)
class _RequiredArtifact:
    modelo: str
    title: str
    relative_url: str
    page_key: str

    @property
    def url(self) -> str:
        return f"{_STATIC}/{self.relative_url}"

    @property
    def source_page(self) -> str:
        return _PAGES[self.page_key]


class _Artifact(TypedDict):
    modelo: str
    title: str
    source_page: str
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
        "038", "038 - Diseño de registro actualizado 28/06/2024", "DR_01_99/archivos/dr038_2024.pdf", "01"
    ),
    _RequiredArtifact(
        "038",
        "038 - Orden HAC/66/2002, de 15 de enero (actualizado a 18/01/2012)",
        "DR_01_99/archivos/dr038_2005.pdf",
        "h01",
    ),
    _RequiredArtifact("117", "117 - Ejercicio 2019 y siguientes", "DR_100_199/archivos_17/DR117e17v14.xls", "100"),
    _RequiredArtifact("122", "122 - Ejercicio 2016 y siguientes", "DR_100_199/archivos_18/dr122e18v13.xlsx", "100"),
    _RequiredArtifact(
        "126", "126 - Ejercicio 2020 y siguientes", "DR_100_199/archivos_20/126v01e2020_v1.07.xlsx", "100"
    ),
    _RequiredArtifact(
        "128", "128 - Ejercicio 2020 y siguientes", "DR_100_199/archivos_20/128v01e2020_v1.07.xlsx", "100"
    ),
    _RequiredArtifact("151", "151 - Ejercicio 2023 y siguientes", "DR_100_199/DR151E2023.xls", "100"),
    _RequiredArtifact("156", "156 - Diseño de registro vigente", "DR_100_199/archivos/156_HAC_3580_2003.pdf", "100"),
    _RequiredArtifact(
        "165", "165 - Diseño de registro actualizado en 2023", "DR_100_199/archivos_23/DR_Mod_165_2023.pdf", "100"
    ),
    _RequiredArtifact(
        "181", "181 - Diseño de registro actualizado en 2022", "DR_100_199/archivos_22/DR_181_2022.pdf", "100"
    ),
    _RequiredArtifact("182", "182 - Ejercicio 2025", "DR_100_199/DR_Modelo_182_2025.pdf", "100"),
    _RequiredArtifact("185", "185 - Ejercicio 2026 y siguientes", "DR_100_199/DR185_2025.pdf", "100"),
    _RequiredArtifact(
        "187", "187 - Diseño de registro actualizado en 2022", "DR_100_199/DR_Modelo_187_2022.pdf", "100"
    ),
    _RequiredArtifact(
        "188", "188 - Diseño de registro actualizado en 2023", "DR_100_199/archivos_23/DR_Mod_188_2023.pdf", "100"
    ),
    _RequiredArtifact(
        "189", "189 - Diseño de registro actualizado en 2023", "DR_100_199/archivos_23/DR_Mod_189_2023.pdf", "100"
    ),
    _RequiredArtifact(
        "194", "194 - Diseño de registro actualizado en 2024", "DR_100_199/DR_Modelo_194_2024.pdf", "100"
    ),
    _RequiredArtifact(
        "202",
        "202 - Ejercicio 2025 y siguientes, actualizado 14/07/2026",
        "DR_200_299/archivos_25/DR202e25.xlsx",
        "200",
    ),
    _RequiredArtifact("210", "210 - Devengos a partir de 2026", "DR_200_299/archivos_26/dr210_2026.xlsx", "200"),
    _RequiredArtifact("216", "216 - Ejercicio 2024 y siguientes", "DR_200_299/archivos_24/216e2024.xlsx", "200"),
    _RequiredArtifact("220", "220 - Ejercicio 2025", "DR_200_299/archivos_25/DR220e25.xlsx", "200"),
    _RequiredArtifact("222", "222 - Ejercicio 2025 y siguientes", "DR_200_299/archivos_25/DR222e25.xlsx", "200"),
    _RequiredArtifact(
        "270", "270 - Diseño de registro actualizado en 2023", "DR_200_299/archivos/270_HAP_2368_2013.pdf", "200"
    ),
    _RequiredArtifact("296", "296 - Ejercicio 2024", "DR_200_299/archivos_24/DR_296_2024.pdf", "200"),
    _RequiredArtifact("341", "341 - Ejercicio 2016 y siguientes", "DR_300_399/archivos/dr341_2016.xls", "300"),
    _RequiredArtifact("345", "345 - Ejercicio 2025", "DR_100_199/DR_Modelo_345_2025.pdf", "300"),
    _RequiredArtifact("360", "360 - Orden EHA/789/2010", "DR_300_399/archivos/DR360.pdf", "300"),
    _RequiredArtifact("390", "390 - Ejercicio 2025", "DR_300_399/archivos_25/dr390e2025.xlsx", "300"),
    _RequiredArtifact("490", "490 - Ejercicio 2023 y siguientes", "DR_Resto_Mod/archivos/dr490e23.xlsx", "resto"),
    _RequiredArtifact("576", "576 - Diseño de registro vigente", "DR_Resto_Mod/archivos/dr576.xlsx", "resto"),
    _RequiredArtifact("604", "604 - Diseño de registro ATF en español", "DR_Resto_Mod/archivos/DR_ATF.pdf", "resto"),
    _RequiredArtifact(
        "604", "604 - Diseño de registro ATF en inglés", "DR_Resto_Mod/archivos/DR_ATF_Ingles.pdf", "resto"
    ),
    _RequiredArtifact("604", "604 - Ejercicio 2024", "DR_Resto_Mod/archivos/DR604_2024.xlsx", "resto"),
    _RequiredArtifact("604", "604 - Ejercicios 2021 a 2023", "DR_Resto_Mod/archivos/DR604_2021.xlsx", "resto"),
    _RequiredArtifact(
        "763", "763 - Desde 2018 4T y siguientes, actualizado en 2023", "DR_Resto_Mod/archivos/DR763e18.xlsx", "resto"
    ),
    _RequiredArtifact("182", "182 - Ejercicio 2024", "DR_100_199/DR_Modelo_182_2024.pdf", "h100"),
    _RequiredArtifact(
        "184",
        "184 - Orden HAP/2250/2015 actualizada por Orden HFP/1284/2023",
        "DR_100_199/archivos_23/DR_Mod_184_2023.pdf",
        "h100",
    ),
    _RequiredArtifact(
        "126",
        "126 - Orden EHA/3435/2007 (Ejercicios 2015 a 2019)",
        "ant_100_199/archivos/DR-126e16_v1.05.pdf",
        "h100",
    ),
    _RequiredArtifact(
        "128",
        "128 - Orden EHA/3435/2007 (Ejercicios 2015 a 2019)",
        "ant_100_199/archivos/DR-128e16_v1.05.pdf",
        "h100",
    ),
    _RequiredArtifact(
        "181",
        "181 - Orden EHA/3514/2009",
        "ant_100_199/archivos/dr181.pdf",
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
        "181 - Orden EHA/3514/2009 (actualizado por Orden HFP/1923/2016)",
        "ant_100_199/archivos/DR181_2016.pdf",
        "h100",
    ),
    _RequiredArtifact(
        "165",
        "165 - Orden HAP/2455/2013",
        "ant_100_199/archivos/DLogicos_mod_165.pdf",
        "h100",
    ),
    _RequiredArtifact(
        "165",
        "165 - Orden HAP/2455/2013 (actualizado por Orden HFP/1822/2016)",
        "DR_100_199/archivos/DR165_2016.pdf",
        "h100",
    ),
    _RequiredArtifact(
        "151", "151 - Orden HAP/2783/2015 (Ejercicios 2015-2022)", "DR_100_199/archivos/dr151e15v12.xls", "h100"
    ),
    _RequiredArtifact(
        "194", "194 - Diseño de registro actualizado en 2023", "ant_100_199/archivos/DR_Mod_194-2023.pdf", "h100"
    ),
    _RequiredArtifact(
        "194",
        "194 - Orden de 18 de enero de 1999 (actualizado por Orden HAC/1276/2019)",
        "DR_100_199/archivos/DR194_2016.pdf",
        "h100",
    ),
    _RequiredArtifact(
        "210", "210 - Devengos entre 01/06/2022 y 01/01/2026", "DR_200_299/archivos_22/dr210e22.xls", "h200"
    ),
    _RequiredArtifact("216", "216 - Ejercicios 2020 a 2023", "DR_200_299/archivos_20/216v01e2020_v1.07.xlsx", "h200"),
    _RequiredArtifact("220", "220 - Ejercicio 2022", "DR_200_299/archivos_22/DR220e22.xlsm", "h200"),
    _RequiredArtifact("220", "220 - Ejercicio 2023", "DR_200_299/archivos_23/DR220e23.xlsm", "h200"),
    _RequiredArtifact("220", "220 - Ejercicio 2024", "DR_200_299/archivos_24/DR220e24.xlsx", "h200"),
    _RequiredArtifact("222", "222 - Ejercicios 2023 y 2024", "DR_200_299/archivos_23/DR222e23.xlsx", "h200"),
    _RequiredArtifact("296", "296 - Ejercicio 2023", "DR_200_299/DR_296_2023.pdf", "h200"),
    _RequiredArtifact(
        "303", "303 - Ejercicio 2025, URL oficial vigente", "DR_300_399/archivos_25/DR303e25.xlsx", "h300"
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
    _RequiredArtifact(
        "309",
        "309 - Orden EHA/3212/2004 (Ejercicios 2018 y posteriores)",
        "DR_300_399/archivos_17/dr309e17v13.xls",
        "h300",
    ),
    _RequiredArtifact("322", "322 - Ejercicio 2022 y siguientes", "DR_300_399/archivos_22/DR322e22.xls", "h300"),
    _RequiredArtifact("322", "322 - Ejercicio 2023", "DR_300_399/archivos_23/DR322e23.xls", "h300"),
    _RequiredArtifact(
        "322", "322 - Ejercicios 2024 y 2025, actualizado 10/12/2025", "DR_300_399/archivos_24/DR322e24.xls", "h300"
    ),
    _RequiredArtifact("345", "345 - Ejercicio 2023 y siguientes", "ant_300_399/archivos/dr345.pdf", "h300"),
    _RequiredArtifact(
        "345", "345 - Orden de actualización del ejercicio 2023", "DR_300_399/archivos_23/DR_345_2023.pdf", "h300"
    ),
    _RequiredArtifact(
        "345", "345 - Diseño de registro actualizado en 2024", "DR_300_399/DR_Modelo_345_2024.pdf", "h300"
    ),
    _RequiredArtifact("353", "353 - Ejercicios 2021 a 2025", "DR_300_399/archivos_17/DR353e21v21.xls", "h300"),
    _RequiredArtifact("353", "353 - Orden EHA/3434/2007", "ant_300_399/archivos/dr353.pdf", "h300"),
    _RequiredArtifact("353", "353 - Orden EHA/3786/2008", "ant_300_399/archivos/dr353v13.pdf", "h300"),
    _RequiredArtifact(
        "353",
        "353 - Orden HAP/1222/2014 (Ejercicios 2015 y 2016)",
        "ant_300_399/archivos/DR353e16v19.xls",
        "h300",
    ),
    _RequiredArtifact(
        "353",
        "353 - Orden HAP/1222/2014 (Ejercicios 2017, 2108 y 2019)",
        "ant_300_399/archivos/DR353e17v20.xlsx",
        "h300",
    ),
    _RequiredArtifact(
        "353",
        "353 -Orden EHA/3434/2007 (Ejercicio 2020)",
        "ant_300_399/archivos/DR353e17v20.xls",
        "h300",
    ),
    _RequiredArtifact(
        "341",
        "341 - Orden EHA/3212/2004 (Ejercicios hasta 2015)",
        "ant_300_399/archivos/dr341_2005.pdf",
        "h300",
    ),
    _RequiredArtifact("714", "714 - Ejercicio 2022", "DR_Resto_Mod/archivos/DR714_2022.xls", "hresto"),
    _RequiredArtifact("714", "714 - Ejercicio 2023", "DR_Resto_Mod/archivos/DR714_2023.xls", "hresto"),
    _RequiredArtifact("714", "714 - Ejercicio 2024", "DR_Resto_Mod/DR714_2024.xls", "hresto"),
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
    _RequiredArtifact(
        "763",
        "763 - Orden EHA/1881/2011 (Ejercicios 2T/3T 2012, 2013 y 2014)",
        "ant_resto_mod/archivos/dr763e2011v11.pdf",
        "hresto",
    ),
    _RequiredArtifact(
        "763", "763 - Ejercicios 2015 a 2018 hasta 3T", "ant_resto_mod/archivos/dr763e2015v11.xlsx", "hresto"
    ),
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
    return json.loads(_HISTORICAL_EXCLUSIONS_PATH.read_text(encoding=_UTF_8))


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
    modelo = match.group(1).zfill(3)
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


def _write_manifests(manifests: dict[str, _Manifest]) -> None:
    for modelo, manifest in manifests.items():
        artifacts = manifest["artefacts"]
        manifest["artefact_count"] = len(artifacts)
        path = _CORPUS / f"modelo_{modelo}" / "manifest.json"
        path.write_bytes((json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode())

    root_path = _CORPUS / "manifest.json"
    root = json.loads(root_path.read_text(encoding=_UTF_8))
    modelos = sorted(manifests)
    root["retrieved_at"] = _RETRIEVED_AT
    root["supported_corpus_modelos"] = modelos
    root["model_count"] = len(modelos)
    root["artefact_count"] = sum(len(manifests[m]["artefacts"]) for m in modelos)
    root["modelos"] = [{"modelo": modelo, "artefact_count": len(manifests[modelo]["artefacts"])} for modelo in modelos]
    root_path.write_bytes((json.dumps(root, ensure_ascii=False, indent=2) + "\n").encode())


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


def check() -> None:
    """Verify required official URLs, manifests, and local artifact bytes offline."""
    manifests = _load_manifests()
    historical_exclusions = _load_historical_exclusions()
    failures = []
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
    expected_models = sorted(manifests)
    expected_artifact_count = sum(len(manifests[modelo]["artefacts"]) for modelo in expected_models)
    expected_rows = [
        {
            "modelo": modelo,
            "artefact_count": len(manifests[modelo]["artefacts"]),
        }
        for modelo in expected_models
    ]
    if root.get("supported_corpus_modelos") != expected_models:
        failures.append("root manifest supported_corpus_modelos is stale")
    if root.get("model_count") != len(expected_models):
        failures.append("root manifest model_count is stale")
    if root.get("artefact_count") != expected_artifact_count:
        failures.append("root manifest artefact_count is stale")
    if root.get("modelos") != expected_rows:
        failures.append("root manifest per-model counts are stale")
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
    required_urls = {required.url for required in _REQUIRED}
    required_exclusions = sorted(set(exclusion_urls) & required_urls)
    if required_exclusions:
        failures.append(f"required URLs are classified as historical exclusions: {required_exclusions[:5]!r}")
    if failures:
        raise SystemExit("\n".join(failures))
    print(f"OK: {len(_REQUIRED)} required official URLs and {len(manifests)} manifests")


def _live_check() -> None:
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

        for required in _REQUIRED:
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
        f"OK live: {len(current_urls)} current raw URLs and {len(_REQUIRED)} required indexed URLs "
        f"plus {len(historical_urls)} classified historical URLs across {len(_PAGES)} pages",
    )


def main() -> None:
    """Run the offline integrity check, optionally pulling official sources first."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--pull", action="store_true")
    parser.add_argument("--live-check", action="store_true")
    args = parser.parse_args()
    if args.pull:
        _pull()
    check()
    if args.live_check:
        _live_check()


if __name__ == "__main__":
    main()
