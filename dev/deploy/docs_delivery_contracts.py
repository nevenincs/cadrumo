"""Canonical documentation mounts, release identity, and delivery credentials."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from dev._paths import UTF_8
from dev.deploy.cloudflare_api import (
    CloudflareAccount,
    WorkerRoute,
)
from dev.deploy.docs_asset_manifest import (
    STATIC_SCRIPT,
)
from dev.deploy.r2_objects import R2Bucket

CANONICAL_DOCS_BASE_URL = "https://cadrumo.neve.md/docs"


CANONICAL_SITE_DOMAIN = "cadrumo.neve.md"


#: The mirror mount serves the same release below the neve.md site.
MIRROR_DOCS_BASE_URL = "https://neve.md/cadrumo/docs"


MIRROR_SITE_DOMAIN = "neve.md"


DOCS_ZONE = "neve.md"


WORKER_SCRIPT = "cadrumo-docs"


#: Every Worker response carries the release id it served under this header.
RELEASE_HEADER = "x-cadrumo-docs-release"


RELEASE_PREFIX = "releases/"


DELIVERY_ROUTES: Final[tuple[WorkerRoute, ...]] = (
    WorkerRoute(pattern=f"{CANONICAL_SITE_DOMAIN}/docs", script=STATIC_SCRIPT),
    WorkerRoute(pattern=f"{CANONICAL_SITE_DOMAIN}/docs/*", script=STATIC_SCRIPT),
    WorkerRoute(pattern=f"{MIRROR_SITE_DOMAIN}/cadrumo/docs", script=STATIC_SCRIPT),
    WorkerRoute(pattern=f"{MIRROR_SITE_DOMAIN}/cadrumo/docs/*", script=STATIC_SCRIPT),
)


_CACHE_CONTROL = "public, max-age=300, must-revalidate"


_UTF_8: Final[str] = UTF_8


#: What one published language root must carry. The pages differ per language,
#: so these are required per root; the search bundle is not among them because
#: the site has one index and it lives at the apex
#: (:data:`_REQUIRED_SITE_SEARCH_ARTIFACTS`).
_REQUIRED_ROOT_ARTIFACTS = (
    "index.html",
    "404.html",
    "sitemap.xml",
)


#: What the site's apex must carry so any language's page can search. One copy
#: for the whole site: every root's pages resolve the bundle here, so a missing
#: file is every language's search gone, not one root's.
_REQUIRED_SITE_SEARCH_ARTIFACTS = (
    "pagefind/pagefind-entry.json",
    "pagefind/pagefind.js",
    "pagefind/pagefind-ui.js",
    "pagefind/pagefind-ui.css",
)


_DOCTREE_EXCLUDES = (".doctrees/*", "*/.doctrees/*")


# Automation markers every hosted and self-hosted runner sets.
_CI_MARKERS = ("CI", "GITHUB_ACTIONS")


#: Cloudflare delivery credentials, read from the process environment by the
#: publisher, never by the product settings model. They are scoped to
#: Cadrumo's documentation bucket and Worker only.
DELIVERY_CREDENTIAL_ENV: Final[tuple[str, ...]] = (
    "CLOUDFLARE_ACCOUNT_ID",
    "CLOUDFLARE_API_TOKEN",
    "CADRUMO_DOCS_R2_BUCKET",
    "CADRUMO_DOCS_R2_ACCESS_KEY_ID",
    "CADRUMO_DOCS_R2_SECRET_ACCESS_KEY",
)


_RELEASE_LABEL_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")


_RELEASE_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}-[0-9]{8}T[0-9]{6}Z")


_ENDPOINT_TIMEOUT_SECONDS = 20


_RELEASE_WAIT_SECONDS = 180


_RELEASE_POLL_SECONDS = 5


_MISSING_DOCS_PATH = "__cadrumo-delivery-missing__.html"


#: A page every language root carries and the apex never does, so a request for
#: it at the apex proves the redirect to the source-language root.
_APEX_DEEP_LINK = "search.html"


@dataclass(frozen=True)
class DeliveryCredentials:
    """The Cloudflare account, API token and R2 key a publish runs with."""

    account: CloudflareAccount
    bucket: R2Bucket
