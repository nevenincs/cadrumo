"""Verify candidate and public delivery identities, redirects, and search records."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from http.client import HTTPException, HTTPSConnection
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from dev.deploy.cloudflare_api import (
    CloudflareAccount,
)
from dev.deploy.cloudflare_api import _call as cloudflare_call
from dev.deploy.docs_asset_delivery import (
    CANDIDATE_SCRIPT,
)
from dev.docs import i18n as _docs_i18n

from .docs_delivery_contracts import (
    _APEX_DEEP_LINK,
    _ENDPOINT_TIMEOUT_SECONDS,
    _MISSING_DOCS_PATH,
    _RELEASE_POLL_SECONDS,
    _RELEASE_WAIT_SECONDS,
    CANONICAL_DOCS_BASE_URL,
    CANONICAL_SITE_DOMAIN,
    MIRROR_DOCS_BASE_URL,
    RELEASE_HEADER,
)
from .docs_site_languages import localized_languages


def _endpoint_response(url: str) -> tuple[int, dict[str, str]]:
    """Return one public endpoint's unredirected HTTP status and headers."""
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname is None:
        raise SystemExit(f"Endpoint check requires a complete HTTPS URL: {url}")
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    connection = HTTPSConnection(parsed.hostname, port=parsed.port, timeout=_ENDPOINT_TIMEOUT_SECONDS)
    try:
        connection.request("GET", path, headers={"User-Agent": "cadrumo-docs-delivery-check"})
        response = connection.getresponse()
        headers = {name.lower(): value for name, value in response.getheaders()}
        response.read()
        return response.status, headers
    except (HTTPException, TimeoutError, OSError) as exc:
        raise SystemExit(f"Endpoint check could not reach {url}: {exc}") from exc
    finally:
        connection.close()


def public_delivery_checks() -> tuple[tuple[str, int], ...]:
    """Return the post-publish endpoint checks as ``(url, expected status)`` pairs.

    Named separately from the run so the deployment-parity gate can assert the
    published surface is covered on both mounts -- every localized root among
    them -- without reaching the network. Every URL here is answered by the
    Worker and must carry the release header.
    """
    checks: list[tuple[str, int]] = []
    for base_url in (CANONICAL_DOCS_BASE_URL, MIRROR_DOCS_BASE_URL):
        checks.append((f"{base_url}/", 200))
        checks.extend((f"{base_url}/{language}/", 200) for language in localized_languages())
        checks.append((f"{base_url}/{_MISSING_DOCS_PATH}", 404))
        checks.append((base_url, 301))
        checks.append((f"{base_url}?cadrumo_delivery_check=1", 301))
        checks.append((f"{base_url}/{_APEX_DEEP_LINK}", 301))
    return tuple(checks)


def expected_redirect(url: str) -> str:
    """Return where a redirecting delivery check must point.

    The bare mount redirects to its directory; an apex page redirects to the same
    page under the source-language root.
    """
    parsed = urlsplit(url)
    path = parsed.path
    query = f"?{parsed.query}" if parsed.query else ""
    if path.endswith(f"/{_APEX_DEEP_LINK}"):
        mount = path[: -len(_APEX_DEEP_LINK) - 1]
        return f"{mount}/{_docs_i18n.DEFAULT_SOURCE_LANGUAGE}/{_APEX_DEEP_LINK}{query}"
    return f"{path}/{query}"


def _published_body(url: str) -> bytes:
    """Return one published artefact's body, under the same HTTPS guard as the status checks.

    Shared by both publishers: the status checks in :func:`_endpoint_response`
    deliberately discard the body, so a content assertion needs its own read.
    """
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname is None:
        raise SystemExit(f"Endpoint check requires a complete HTTPS URL: {url}")
    path = parsed.path or "/"
    connection = HTTPSConnection(parsed.hostname, port=parsed.port, timeout=_ENDPOINT_TIMEOUT_SECONDS)
    try:
        connection.request("GET", path, headers={"User-Agent": "cadrumo-docs-delivery-check"})
        response = connection.getresponse()
        body = response.read()
        if response.status != 200:
            raise SystemExit(f"Published artefact is not served at {url}: HTTP {response.status}.")
        return body
    except (HTTPException, TimeoutError, OSError) as exc:
        raise SystemExit(f"Endpoint check could not reach {url}: {exc}") from exc
    finally:
        connection.close()


def _indexed_entry_counts(payload: bytes, *, origin: str) -> dict[str, int]:
    """Return ``{language: page_count}`` from a ``pagefind-entry.json`` body."""
    try:
        document = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{origin} is not valid JSON: {exc}") from exc
    languages = document.get("languages") if isinstance(document, dict) else None
    if not isinstance(languages, dict) or not languages:
        raise SystemExit(f"{origin} declares no index languages; it is not a Pagefind entry document.")
    return {str(name): int(split["page_count"]) for name, split in languages.items()}


def _assert_served_index_matches_build(*, built: Path, served: bytes, label: str) -> None:
    """Require the served index to carry exactly what the validated build carried.

    The preflight has already refused a record-free build, so the local entry is
    known to carry records. Requiring the SERVED counts to equal the BUILT counts
    therefore proves the published index carries them too -- without hardcoding a
    record total that would rot on the next corpus change.

    This is the check the status codes cannot make. A root serving a record-free
    index answers 200 on every URL the delivery checks probe, which is exactly
    how a pages-only index shipped and stayed shipped: everything answered, and
    nothing read what it answered with.
    """
    if not built.is_file():
        raise SystemExit(f"{label}: no built Pagefind entry at {built} to compare the published one against.")
    expected = _indexed_entry_counts(built.read_bytes(), origin=f"{label} built entry {built}")
    actual = _indexed_entry_counts(served, origin=f"{label} published entry")
    if actual != expected:
        raise SystemExit(
            f"{label}: the published search index does not match the build that was validated. "
            f"Built {expected}, published {actual}. A published count below the built one means the "
            "upload is incomplete or a stale index is being served; either way a reader is searching "
            "an index this publish never approved.",
        )


def _verify_published_search_index(
    html_root: Path,
    *,
    base_url: str = CANONICAL_DOCS_BASE_URL,
    fetch: Callable[[str], bytes] = _published_body,
) -> None:
    """Require the published site to serve the search index its build produced.

    One read, at the apex, because the site has ONE index and every language's
    pages load it from there: the entry this fetches is the entry every reader
    of every language gets. It was one read per language root while there were
    four indexes, and reading only the default root was a defect then; with one
    index there is no second entry a reader could be served instead.

    Args:
        html_root: The built site root the publish uploaded from, which is the
            site's apex.
        base_url: DI seam. Production uses the canonical docs URL.
        fetch: DI seam for the HTTPS body read, so the comparison can be proven
            against real built artefacts without standing up a TLS endpoint.
    """
    served = fetch(f"{base_url}/pagefind/pagefind-entry.json")
    _assert_served_index_matches_build(
        built=html_root / "pagefind" / "pagefind-entry.json",
        served=served,
        label="the documentation site",
    )


def _await_release_served(release: str) -> None:
    """Wait until both mounts answer with ``release`` after a Worker deploy."""
    deadline = time.monotonic() + _RELEASE_WAIT_SECONDS
    pending = {f"{CANONICAL_DOCS_BASE_URL}/", f"{MIRROR_DOCS_BASE_URL}/"}
    while True:
        for url in sorted(pending):
            _status, headers = _endpoint_response(url)
            if headers.get(RELEASE_HEADER) == release:
                pending.discard(url)
        if not pending:
            return
        if time.monotonic() > deadline:
            raise SystemExit(
                f"Release {release} was deployed but {', '.join(sorted(pending))} did not serve it within "
                f"{_RELEASE_WAIT_SECONDS}s. Check the Worker routes, the DNS proxy on {CANONICAL_SITE_DOMAIN} "
                "and any redirect rule ahead of the Worker.",
            )
        time.sleep(_RELEASE_POLL_SECONDS)


def _delivery_mismatch(url: str, expected_status: int, release: str) -> str | None:
    """Return why ``url`` does not yet answer as declared from ``release``, or ``None``."""
    actual_status, headers = _endpoint_response(url)
    if actual_status != expected_status:
        return f"expected HTTP {expected_status}, received HTTP {actual_status}"
    if expected_status != 301 and headers.get(RELEASE_HEADER) != release:
        return f"answered from release {headers.get(RELEASE_HEADER)!r}, not {release!r}"
    if expected_status == 301 and urljoin(url, headers.get("location", "")) != urljoin(url, expected_redirect(url)):
        return f"redirected to {headers.get('location')!r}, not to {expected_redirect(url)!r}"
    return None


def _verify_public_delivery(release: str) -> None:
    """Require every checked URL on both mounts to answer as declared, from ``release``.

    A deploy reaches Cloudflare's edge progressively, so one request can meet an
    edge that has not converged yet. Each check is therefore retried until it
    holds or the wait expires; a check still failing at the deadline is a
    delivery failure, never a pass.
    """
    deadline = time.monotonic() + _RELEASE_WAIT_SECONDS
    for url, expected_status in public_delivery_checks():
        while (mismatch := _delivery_mismatch(url, expected_status, release)) is not None:
            if time.monotonic() > deadline:
                raise SystemExit(f"Endpoint check failed for {url}: {mismatch}.")
            time.sleep(_RELEASE_POLL_SECONDS)
    landing_status, _ = _endpoint_response(f"https://{CANONICAL_SITE_DOMAIN}/")
    if landing_status != 200:
        raise SystemExit(f"The {CANONICAL_SITE_DOMAIN} landing page answered HTTP {landing_status} after the deploy.")


def _verify_candidate(account: CloudflareAccount, release: str) -> None:
    """Exercise both mount layouts on the unpublished candidate service."""
    subdomain = cloudflare_call(account, "GET", f"/accounts/{account.account_id}/workers/subdomain")["subdomain"]
    host = f"https://{CANDIDATE_SCRIPT}.{subdomain}.workers.dev"
    deadline = time.monotonic() + _RELEASE_WAIT_SECONDS
    for url, expected in public_delivery_checks():
        parsed = urlsplit(url)
        candidate = host + parsed.path + (f"?{parsed.query}" if parsed.query else "")
        while (mismatch := _delivery_mismatch(candidate, expected, release)) is not None:
            if time.monotonic() > deadline:
                raise ValueError(f"Candidate verification failed for {candidate}: {mismatch}")
            time.sleep(_RELEASE_POLL_SECONDS)


def _await_static_delivery(release: str) -> None:
    """Distinguish a static cutover from the same release on the preceding proxy."""
    deadline = time.monotonic() + _RELEASE_WAIT_SECONDS
    for base in (CANONICAL_DOCS_BASE_URL, MIRROR_DOCS_BASE_URL):
        while True:
            status, headers = _endpoint_response(base + "/")
            if (
                status == 200
                and headers.get(RELEASE_HEADER) == release
                and headers.get("x-cadrumo-docs-delivery") == "static"
            ):
                break
            if time.monotonic() > deadline:
                raise ValueError(f"Native static delivery did not become active at {base}")
            time.sleep(_RELEASE_POLL_SECONDS)
