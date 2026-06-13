"""One-shot sourcing of a licence-clean evidence corpus from Wikimedia Commons.

Downloads real public-domain / CC0 / CC-BY invoice images into the test evidence
corpus and writes a provenance sidecar per file (per the fixture-provenance rule:
``real_corpus`` plus the source URL, licence, and sha256). Run with
``uv run --no-sync python dev/_build_evidence_corpus.py``. This is a dev tooling
script, not shipped or imported by ``src/aeat``.
"""

from __future__ import annotations

import hashlib
import json
import urllib.parse
import urllib.request
from pathlib import Path

_CORPUS = Path("src/aeat/application/ledger/tests/_evidence_corpus")
_UA = "aeat-fixtures/1.0 (evidence test corpus; contact: maintainers)"
_CLEAN_LICENCES = {"public domain", "cc0", "cc-by", "cc-by-sa", "pd", "pd-old", "cc-pd-mark"}
_MAX_BYTES = 4_000_000


def _api(params: dict[str, str]) -> dict[str, object]:
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": _UA})  # noqa: S310 — https Commons API
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def _download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})  # noqa: S310
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
        return resp.read(_MAX_BYTES + 1)


def _licence_is_clean(short: str) -> bool:
    low = short.strip().lower()
    return any(low.startswith(c) for c in _CLEAN_LICENCES)


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
    pages = data.get("query", {}).get("pages", {})  # type: ignore[union-attr]
    for page in pages.values():  # type: ignore[union-attr]
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {}) or {}
        short = (meta.get("LicenseShortName", {}) or {}).get("value", "")
        mime = info.get("mime", "")
        url = info.get("url", "")
        if not url or not mime.startswith(mime_prefixes):
            continue
        if not _licence_is_clean(short):
            continue
        out.append({"title": page.get("title", ""), "url": url, "mime": mime, "licence": short})
    return out


def _save(name: str, data: bytes, *, source_url: str, licence: str, title: str, kind: str) -> None:
    _CORPUS.mkdir(parents=True, exist_ok=True)
    target = _CORPUS / name
    target.write_bytes(data)
    sidecar = target.with_suffix(target.suffix + ".provenance.json")
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
        encoding="utf-8",
    )
    print(f"saved {name} ({len(data)} bytes, {licence}) <- {title}")


def main() -> None:
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
