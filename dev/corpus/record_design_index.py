"""Parse official record-design indexes and match declared payload URLs."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path
from typing import override
from urllib.parse import urljoin, urlparse

from dev.corpus.record_design_inventory import (
    _PAGES,
    _RECORD_DESIGN_SUFFIXES,
)

from .record_design_manifests import _Artifact, _artifact_urls, _Manifest


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
