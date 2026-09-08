"""One-shot sourcing of a licence-clean evidence corpus from Wikimedia Commons.

Downloads real public-domain / CC0 / CC-BY invoice images into the test evidence
corpus and writes a provenance sidecar per file (per the fixture-provenance rule:
``real_corpus`` plus the source URL, licence, and sha256). Run with
``uv run --no-sync python -m dev.corpus.build_evidence_corpus``. This is a dev tooling
script, not shipped or imported by ``src/cadrumo``.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import re
import urllib.parse
from pathlib import Path
from typing import Final, cast

from .._paths import UTF_8

_UTF_8: Final[str] = UTF_8
_CORPUS = Path("src/cadrumo/application/ledger/tests/_evidence_corpus")
_UA = "cadrumo-fixtures/1.0 (evidence test corpus; contact: maintainers)"
_CLEAN_LICENCE_PATTERN = re.compile(
    r"(?:public domain|cc0|cc[- ]by(?:[- ]sa)?|pd(?:-old(?:-\d+)?)?|cc-pd-mark)(?:\s+\d+(?:\.\d+)*)?",
)
_MAX_BYTES = 4_000_000
_COMMONS_API_HOST = "commons.wikimedia.org"
_COMMONS_DOWNLOAD_HOSTS = frozenset({_COMMONS_API_HOST, "upload.wikimedia.org"})


def _validated_https_target(url: str, *, allowed_hosts: frozenset[str]) -> tuple[str, str]:
    parsed = urllib.parse.urlsplit(url)
    hostname = parsed.hostname
    if (
        parsed.scheme != "https"
        or hostname is None
        or hostname.casefold() not in allowed_hosts
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port is not None
        or parsed.fragment
    ):
        raise ValueError(f"unexpected Wikimedia URL: {url!r}")
    target = parsed.path or "/"
    if parsed.query:
        target += f"?{parsed.query}"
    return hostname, target


def _get_https(url: str, *, timeout: float, allowed_hosts: frozenset[str], maximum_bytes: int | None) -> bytes:
    hostname, target = _validated_https_target(url, allowed_hosts=allowed_hosts)
    connection = http.client.HTTPSConnection(hostname, timeout=timeout)
    try:
        connection.request("GET", target, headers={"User-Agent": _UA})
        response = connection.getresponse()
        if not 200 <= response.status < 300:
            raise OSError(f"Wikimedia request returned HTTP {response.status}")
        return response.read() if maximum_bytes is None else response.read(maximum_bytes)
    finally:
        connection.close()


def _api(params: dict[str, str]) -> dict[str, object]:
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
    payload = _get_https(url, timeout=30, allowed_hosts=frozenset({_COMMONS_API_HOST}), maximum_bytes=None)
    # `json.loads` is typed `Any`; the cast states the shape this endpoint
    # is documented to return, in one place instead of at every use.
    return cast("dict[str, object]", json.loads(payload.decode(_UTF_8)))


def _download(url: str) -> bytes:
    return _get_https(
        url,
        timeout=60,
        allowed_hosts=_COMMONS_DOWNLOAD_HOSTS,
        maximum_bytes=_MAX_BYTES + 1,
    )


def _licence_is_clean(short: str) -> bool:
    normalized = " ".join(short.strip().lower().split())
    return _CLEAN_LICENCE_PATTERN.fullmatch(normalized) is not None


def _json_str(value: object) -> str:
    """Return *value* when the payload carried a string there, else the empty string."""
    return value if isinstance(value, str) else ""


def _json_object(value: object, field: str) -> dict[str, object]:
    """Return *value* as a JSON object, or refuse naming the field that lied."""
    if not isinstance(value, dict):
        raise TypeError(f"the Commons API returned a non-object under `{field}`")
    return cast("dict[str, object]", value)


def _search(query: str, mime_prefixes: tuple[str, ...], limit: int = 20) -> list[dict[str, str]]:
    data = _api(
        {
            "action": "query",
            "format": "json",
            "prop": "imageinfo",
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": "6",
            "gsrlimit": str(limit),
            "iiprop": "url|mime|size|extmetadata",
        },
    )
    out: list[dict[str, str]] = []
    # The API nests pages two levels down and every level is `object` to the
    # checker. Refusing a malformed payload is better than silencing the reads:
    # an `assert` would vanish under -O, and the previous ignore comments turned
    # a wrong-shaped response into an AttributeError far from its cause.
    pages = _json_object(_json_object(data.get("query", {}), "query").get("pages", {}), "pages")
    for entry in pages.values():
        page = _json_object(entry, "pages[]")
        image_info = page.get("imageinfo")
        first = image_info[0] if isinstance(image_info, list) and image_info else {}
        info = _json_object(first, "imageinfo[]")
        meta = _json_object(info.get("extmetadata") or {}, "extmetadata")
        licence = _json_object(meta.get("LicenseShortName") or {}, "LicenseShortName")
        short = _json_str(licence.get("value"))
        mime = _json_str(info.get("mime"))
        url = _json_str(info.get("url"))
        if not url or not mime.startswith(mime_prefixes):
            continue
        if not _licence_is_clean(short):
            continue
        out.append(
            {
                "title": _json_str(page.get("title")),
                "url": url,
                "mime": mime,
                "licence": short,
            }
        )
    return out


PROVENANCE_SIDECAR_SUFFIX: Final[str] = ".provenance.json"
"""The suffix :func:`_save` appends to a payload name to make its sidecar."""


def orphaned_provenance_sidecars(root: Path) -> tuple[str, ...]:
    """Sidecars under *root* whose payload is not there.

    The direction nothing walked. Every existing gate over this corpus starts
    from the payload files and asks whether each carries a sidecar, and the
    listing that feeds them filters the sidecars out by suffix -- so a
    sidecar left behind by a payload that went away is invisible to all of
    them, in the tree whose whole purpose is to say where evidence came from.

    The pair is removed together and restored together only if whoever
    restores it knows there are two halves. This corpus has already been
    through one full removal and re-add of eight payloads with their
    sidecars; it survived because both halves moved in the same commit.
    Nothing enforced that.

    A licence, a source URL and a content address for a file that no longer
    exists is not harmless bookkeeping: it is an attestation with nothing
    under it, and the next fixture added at that name inherits it.

    Args:
        root: The corpus directory to walk.

    Returns:
        Sidecar names, sorted, whose payload is absent.
    """
    if not root.is_dir():
        return ()
    orphans = [
        sidecar.name
        for sidecar in sorted(root.glob(f"*{PROVENANCE_SIDECAR_SUFFIX}"))
        if not root.joinpath(sidecar.name.removesuffix(PROVENANCE_SIDECAR_SUFFIX)).is_file()
    ]
    return tuple(orphans)


def _save(name: str, data: bytes, *, source_url: str, licence: str, title: str, kind: str) -> None:
    _CORPUS.mkdir(parents=True, exist_ok=True)
    target = _CORPUS / name
    target.write_bytes(data)
    sidecar = target.with_suffix(target.suffix + PROVENANCE_SIDECAR_SUFFIX)
    sidecar.write_text(
        json.dumps(
            {
                "provenance": "real_corpus",
                "kind": kind,
                "source": "wikimedia-commons",
                "source_url": source_url,
                "commons_title": title,
                "licence": licence,
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
            },
            indent=2,
        )
        + "\n",
        encoding=_UTF_8,
        newline="\n",
    )
    print(f"saved {name} ({len(data)} bytes, {licence}) <- {title}")


def main() -> None:
    """Download licensed evidence images and write their provenance sidecars."""
    # Image invoices (png/jpeg) -> exercise the on-host image/vision evidence path.
    images = _search("invoice OR receipt OR factura filetype:bitmap", ("image/png", "image/jpeg"))
    saved_images = 0
    for hit in images:
        if saved_images >= 2:
            break
        try:
            data = _download(hit["url"])
        except Exception as exc:
            print(f"skip {hit['title']}: {exc}")
            continue
        if len(data) > _MAX_BYTES or len(data) < 1000:
            continue
        ext = ".png" if hit["mime"] == "image/png" else ".jpg"
        _save(
            f"commons_invoice_{saved_images + 1}{ext}",
            data,
            source_url=hit["url"],
            licence=hit["licence"],
            title=hit["title"],
            kind="image_invoice",
        )
        saved_images += 1

    # Text-layer PDF invoices -> exercise the pdfplumber text-extraction path.
    pdfs = _search("invoice OR factura filetype:office OR rechnung", ("application/pdf",), limit=25)
    saved_pdf = 0
    for hit in pdfs:
        if saved_pdf >= 1:
            break
        try:
            data = _download(hit["url"])
        except Exception as exc:
            print(f"skip {hit['title']}: {exc}")
            continue
        if len(data) > _MAX_BYTES or len(data) < 1000:
            continue
        _save(
            f"commons_invoice_doc_{saved_pdf + 1}.pdf",
            data,
            source_url=hit["url"],
            licence=hit["licence"],
            title=hit["title"],
            kind="pdf_invoice",
        )
        saved_pdf += 1

    print(f"\nsourced: {saved_images} image(s), {saved_pdf} pdf(s)")


if __name__ == "__main__":
    main()
