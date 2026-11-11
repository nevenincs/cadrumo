"""Declared official acquisition inventory and corpus classification policy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

#: The day this run retrieves the designs, which the manifests it writes record.
RETRIEVED_AT = datetime.now(UTC).date().isoformat()


STATIC = "https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro"


_INDEX = "https://sede.agenciatributaria.gob.es/Sede/ayuda/disenos-registro"


PAGES = {
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


CURRENT_PAGE_KEYS = ("01", "100", "200", "300", "resto")


HISTORICAL_PAGE_KEYS = ("h01", "h100", "h200", "h300", "hresto")


RECORD_DESIGN_SUFFIXES = frozenset({".pdf", ".xls", ".xlsx", ".xlsm", ".xsd"})


@dataclass(frozen=True)
class RequiredArtifact:
    """A required official record-design artefact with its title, URL and index page key."""

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
        """Return the absolute AEAT URL of the artefact."""
        return f"{STATIC}/{self.relative_url}"

    @property
    def source_page(self) -> str | None:
        """Return the official index page URL the artefact was found on, or None if unrecorded."""
        return None if self.page_key is None else PAGES[self.page_key]
