"""Check public documentation availability without deployment credentials."""

from __future__ import annotations

import json
from http.client import HTTPSConnection
from urllib.parse import urlsplit

BASES = ("https://cadrumo.neve.md/docs", "https://neve.md/cadrumo/docs")


def probe(url: str, *, redirect_release: str | None = None) -> tuple[dict[str, str], bytes]:
    """Read a successful HTTPS response with a consistent monitoring identity."""
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Health checks require HTTPS")
    connection = HTTPSConnection(parsed.hostname, timeout=20)
    try:
        connection.request("GET", parsed.path, headers={"User-Agent": "cadrumo-docs-health"})
        response = connection.getresponse()
        body = response.read()
        if response.status == 302 and redirect_release:
            target = response.getheader("location", "")
            expected = f"https://cadrumo-docs-search.neve.md/releases/{redirect_release}/"
            if not target.startswith(expected):
                raise ValueError(f"Unexpected search release destination: {url}")
            return probe(target)
        if response.status != 200:
            raise ValueError(f"Documentation failed: {url}: HTTP {response.status}")
        return {name.lower(): value for name, value in response.getheaders()}, body
    finally:
        connection.close()


def check() -> None:
    """Require consistent release markers and usable search indexes on both mounts."""
    releases: set[str] = set()
    for base in BASES:
        for path in ("/", "/en/", "/es/", "/ca/", "/hu/"):
            headers, _ = probe(base + path)
            release = headers.get("x-cadrumo-docs-release")
            if not release:
                raise ValueError(f"Missing release identity: {base}{path}")
            if headers.get("x-cadrumo-docs-delivery") != "static":
                raise ValueError(f"Documentation is not on native static delivery: {base}{path}")
            releases.add(release)
            if path != "/":
                for kind in ("index", "fragment"):
                    _, payload = probe(base + f"/_health{path}{kind}", redirect_release=release)
                    if not payload:
                        raise ValueError(f"Empty public search payload: {base}{path}{kind}")
        _, body = probe(base + "/en/pagefind/pagefind-entry.json")
        entry = json.loads(body)
        if not any(row.get("page_count", 0) > 0 for row in entry.get("languages", {}).values()):
            raise ValueError(f"Search index is empty: {base}")
    if len(releases) != 1:
        raise ValueError("Documentation mounts serve inconsistent releases")
    print(f"Documentation health passed: {next(iter(releases))}")


if __name__ == "__main__":
    check()
