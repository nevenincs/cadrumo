# ruff: noqa: T201  # CLI script: print statements are the intended output.
"""Fetch + hash-verify L1 public AEAT / BOE anchor PDFs (EPIC #305 cluster C).

Reads ``tests/fixtures/pdf_corpus/l1_public_anchors/_manifest.json`` and,
for each entry, ensures the SHA-256-pinned PDF is cached at
``.cache/l1_anchors/<sha256>.pdf``. Prints a summary and exits non-zero
on any mismatch.

Usage:

    uv run python scripts/fetch_l1_anchors.py
    uv run python scripts/fetch_l1_anchors.py --check-drift

Options:

    --check-drift: fetch URLs unconditionally and compare against the
        pinned SHA-256; exits non-zero on mismatch. Run weekly via
        ``.github/workflows/l1-anchor-drift.yml``.

Environment:

    AEAT_FIXTURE_OFFLINE=1: never attempt network fetch; hard-fail if
        any pinned anchor is missing from the local cache. Honoured by
        CI to deselect L1 tests when the network is unavailable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "tests" / "fixtures" / "pdf_corpus" / "l1_public_anchors" / "_manifest.json"
CACHE_DIR = REPO_ROOT / ".cache" / "l1_anchors"


class L1Entry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    url: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    fetched_at: str
    license: str
    modelo: str | None = None
    año: int | None = None
    template_revision: str | None = None
    purpose: str = Field(min_length=1)


class L1Manifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str
    description: str
    entries: tuple[L1Entry, ...]


def _load_manifest() -> L1Manifest:
    if not MANIFEST_PATH.exists():
        raise SystemExit(f"L1 manifest not found: {MANIFEST_PATH}")
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return L1Manifest.model_validate(payload)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fetch_bytes(url: str) -> bytes:
    # Manifest entries are hash-pinned; mismatched bytes are rejected
    # downstream via SHA-256 verification before we write them to cache.
    if not (url.startswith("https://") or url.startswith("http://")):
        raise ValueError(f"only http(s) URLs permitted in the L1 manifest, got {url!r}")
    request = urllib.request.Request(url, headers={"User-Agent": "aeat-l1-fetcher/1.0"})  # noqa: S310
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
        return response.read()


def _ensure_cached(entry: L1Entry, *, offline: bool) -> tuple[bool, str]:
    """Ensure the entry's pinned PDF is at ``CACHE_DIR/<sha256>.pdf``.

    Returns ``(ok, reason)`` where ``ok`` is True when the PDF is present
    with a matching hash; ``reason`` is a short explanatory string.
    """
    target = CACHE_DIR / f"{entry.sha256}.pdf"
    if target.exists():
        actual = _sha256_bytes(target.read_bytes())
        if actual == entry.sha256:
            return True, f"cached ({entry.id})"
        return False, f"cache corruption for {entry.id}: expected {entry.sha256} got {actual}"

    if offline:
        return False, f"offline mode and {entry.id} not in cache"

    try:
        data = _fetch_bytes(entry.url)
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        return False, f"fetch failed for {entry.id} ({entry.url}): {exc}"

    actual = _sha256_bytes(data)
    if actual != entry.sha256:
        return False, f"drift for {entry.id}: manifest {entry.sha256} vs upstream {actual}"

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return True, f"fetched ({entry.id})"


def _check_drift(entry: L1Entry) -> tuple[bool, str]:
    """Fetch the entry unconditionally; compare the upstream SHA-256 to the pin."""
    try:
        data = _fetch_bytes(entry.url)
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        return False, f"fetch failed for {entry.id}: {exc}"
    actual = _sha256_bytes(data)
    if actual != entry.sha256:
        return False, f"DRIFT for {entry.id}: manifest {entry.sha256} vs upstream {actual}"
    return True, f"pinned ({entry.id})"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.add_argument(
        "--check-drift",
        action="store_true",
        help="Fetch upstream unconditionally and fail on SHA-256 mismatch.",
    )
    args = parser.parse_args(argv)

    offline = os.environ.get("AEAT_FIXTURE_OFFLINE") == "1"
    manifest = _load_manifest()
    if not manifest.entries:
        print("L1 manifest is empty; nothing to do.")
        return 0

    failures: list[str] = []
    for entry in manifest.entries:
        if args.check_drift:
            ok, reason = _check_drift(entry)
        else:
            ok, reason = _ensure_cached(entry, offline=offline)
        status = "OK   " if ok else "FAIL "
        print(f"{status}{reason}")
        if not ok:
            failures.append(reason)

    if failures:
        print(f"\n{len(failures)} L1 anchor(s) failed:")
        for reason in failures:
            print(f"  - {reason}")
        return 1
    print(f"\n{len(manifest.entries)} L1 anchor(s) verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
