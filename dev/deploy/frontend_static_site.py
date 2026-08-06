"""Publish the Cadrumo landing page to the documentation stack from a local AWS session."""

from __future__ import annotations

import argparse
import os
import re
import shutil
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Final

from dev.deploy.docs_static_site import (
    _CI_MARKERS,
    CANONICAL_DOCS_BASE_URL,
    CANONICAL_SITE_DOMAIN,
    STACK_REGION,
    DeploymentTarget,
    _authenticated_account_id,
    _aws_base_command,
    _endpoint_response,
    _invalidate_distribution_paths,
    _published_body,
    _repo_root,
    _required_executable,
    _run,
    _stack_target,
    _verify_distribution_alias,
)

_UTF_8: Final[str] = "utf-8"
CANONICAL_SITE_URL = f"https://{CANONICAL_SITE_DOMAIN}"
_PAGE_CACHE_CONTROL = "public, max-age=300, must-revalidate"
# Vite content-hashes everything under assets/, so those objects never change
# in place and can be cached forever without invalidation.
_ASSET_CACHE_CONTROL = "public, max-age=31536000, immutable"
#: An ``assets/`` bundle referenced by the built page, captured by filename. The
#: served document is required to reference the same names, which is what
#: separates "the site answered" from "the site serves what was just published".
_ASSET_REFERENCE_RE = re.compile(r"""(?:src|href)=["'][^"']*?assets/([A-Za-z0-9._-]+\.(?:js|css))["']""")
_DEPLOYMENT_BUILD_OUTPUT = "build"
_REQUIRED_ARTIFACTS = (
    "index.html",
    "404.html",
    "favicon.png",
    "og-image.jpg",
    "robots.txt",
    "sitemap.xml",
)
# The landing page shares the documentation bucket; its sync must never touch
# the documentation prefix the docs publisher owns.
_PROTECTED_PREFIX_EXCLUDES = ("docs/*",)
# Hashed assets/* objects are immutable and never listed here: a new build
# writes new object keys, so only the mutable page documents need purging.
_INVALIDATION_PATHS = (
    "/",
    "/index.html",
    "/404.html",
    "/favicon.png",
    "/og-image.jpg",
    "/robots.txt",
    "/sitemap.xml",
)


def _build_site(repo_root: Path) -> Path:
    """Build the landing page and return its distributable root."""
    npm = _required_executable("npm")
    frontend_root = repo_root / "frontend"
    _run(
        [npm, "run", "build"],
        cwd=frontend_root,
        env={**os.environ, "CADRUMO_FRONTEND_BUILD_OUTPUT": _DEPLOYMENT_BUILD_OUTPUT},
        stream_output=True,
    )
    return frontend_root / _DEPLOYMENT_BUILD_OUTPUT


def _validate_site_artifacts(dist_root: Path) -> None:
    """Require the artifacts the landing page cannot serve without."""
    missing = [artifact for artifact in _REQUIRED_ARTIFACTS if not (dist_root / artifact).is_file()]
    if missing:
        raise SystemExit("Landing page build is missing required artifacts: " + ", ".join(missing))
    assets = dist_root / "assets"
    if not any(assets.glob("*.js")) or not any(assets.glob("*.css")):
        raise SystemExit(
            f"Landing page build is missing bundled assets under {_DEPLOYMENT_BUILD_OUTPUT}/assets/.",
        )
    # "Some bundle exists" is not "the page's bundles exist". A build whose
    # index.html names a file that was never written passes the check above so
    # long as any .js and .css are present -- including leftovers from an
    # earlier build -- and then serves a blank page. The references are what the
    # browser actually requests, so they are what must resolve.
    referenced = _referenced_asset_names((dist_root / "index.html").read_text(encoding=_UTF_8, errors="replace"))
    if not referenced:
        raise SystemExit(
            f"Landing page index.html references no bundled assets under {_DEPLOYMENT_BUILD_OUTPUT}/assets/; "
            "the preflight cannot prove visitors will receive a working page.",
        )
    unresolved = sorted(name for name in referenced if not (assets / name).is_file())
    if unresolved:
        raise SystemExit(
            f"Landing page index.html references bundle(s) {unresolved} that do not exist under "
            f"{_DEPLOYMENT_BUILD_OUTPUT}/assets/; the published page would request them and render blank.",
        )


def _sync_pass(
    aws: str,
    repo_root: Path,
    dist_root: Path,
    destination: str,
    filters: tuple[tuple[str, str], ...],
    cache_control: str,
    *,
    dry_run: bool,
) -> None:
    """Run one filtered sync pass and refuse any dry-run touch of docs/*."""
    command = [
        *_aws_base_command(aws),
        "s3",
        "sync",
        str(dist_root),
        destination,
        "--delete",
        "--cache-control",
        cache_control,
    ]
    for flag, pattern in filters:
        command.extend([flag, pattern])
    if dry_run:
        command.append("--dryrun")
    completed = _run(command, cwd=repo_root)
    if dry_run and f"{destination}docs/" in completed.stdout:
        raise SystemExit("Root sync dry run would mutate protected docs/* objects.")


def _sync_site(
    aws: str,
    repo_root: Path,
    dist_root: Path,
    bucket: str,
    *,
    dry_run: bool = False,
) -> None:
    """Synchronise the site root while leaving the documentation prefix intact."""
    destination = f"s3://{bucket}/"
    protected = tuple(("--exclude", pattern) for pattern in _PROTECTED_PREFIX_EXCLUDES)
    # Pass 1: mutable page documents, short TTL. Assets are excluded so the
    # delete phase cannot see (or remove) the immutable tree.
    _sync_pass(
        aws,
        repo_root,
        dist_root,
        destination,
        (*protected, ("--exclude", "assets/*")),
        _PAGE_CACHE_CONTROL,
        dry_run=dry_run,
    )
    # Pass 2: content-hashed assets only, cached forever; stale hashes from
    # earlier builds are deleted within the assets/ scope alone.
    _sync_pass(
        aws,
        repo_root,
        dist_root,
        destination,
        (*protected, ("--exclude", "*"), ("--include", "assets/*")),
        _ASSET_CACHE_CONTROL,
        dry_run=dry_run,
    )


def _invalidate_site(aws: str, repo_root: Path, distribution_id: str) -> None:
    """Invalidate the published landing paths and wait for completion."""
    _invalidate_distribution_paths(aws, repo_root, distribution_id, _INVALIDATION_PATHS)


def _referenced_asset_names(index_html: str) -> frozenset[str]:
    """Return the ``assets/`` filenames an ``index.html`` loads.

    Matches the hashed bundle names the build stamps into ``src``/``href``. Names
    only, not paths, so the same set is comparable between the built file and the
    served page regardless of how each spells the prefix.
    """
    return frozenset(match.group(1) for match in _ASSET_REFERENCE_RE.finditer(index_html))


def _verify_published_landing_page(
    dist_root: Path,
    *,
    base_url: str = CANONICAL_SITE_URL,
    fetch: Callable[[str], bytes] = _published_body,
) -> None:
    """Fetch the published landing root and require it to be the page just built.

    Args:
        dist_root: The build the publish uploaded from.
        base_url: DI seam. Production uses the canonical site URL.
        fetch: DI seam for the HTTPS body read, so the comparison can be proven
            against a real build without standing up a TLS endpoint.
    """
    served = fetch(f"{base_url}/").decode("utf-8", errors="replace")
    _verify_served_page_is_the_built_page(dist_root, page=served)


def _verify_served_page_is_the_built_page(dist_root: Path, *, page: str) -> None:
    """Require the served landing page to load the bundles this build produced.

    The status checks establish that something answered 200. They cannot tell a
    working page from one whose bundles 404 -- a blank landing page answers 200
    exactly like a correct one. Comparing the asset references proves the page a
    visitor receives is the page that was just built and validated, which also
    catches a stale cached document surviving the invalidation.

    Derived from the built ``index.html`` rather than a hardcoded marker string,
    so the check cannot rot when the page copy changes.
    """
    built = dist_root / "index.html"
    expected = _referenced_asset_names(built.read_text(encoding=_UTF_8, errors="replace"))
    if not expected:
        raise SystemExit(
            f"Built landing page {built} references no bundled assets; there is nothing to verify "
            "the served page against, so the delivery check would prove nothing.",
        )
    missing = sorted(name for name in expected if name not in page)
    if missing:
        raise SystemExit(
            f"The served landing page does not reference the bundle(s) {missing} this build produced. "
            "A visitor is being served a different document than the one just published — most likely a "
            "stale cached page — so the page may render blank while every endpoint check still answers 200.",
        )


def _verify_public_delivery(target: DeploymentTarget) -> None:
    """Require the landing root, intact docs, and a private origin."""
    checks = (
        (f"{CANONICAL_SITE_URL}/", 200),
        (f"{CANONICAL_SITE_URL}/__cadrumo-delivery-missing__.html", 404),
        (f"{CANONICAL_DOCS_BASE_URL}/", 200),
        (f"https://{target.bucket}.s3.{STACK_REGION}.amazonaws.com/index.html", 403),
    )
    for url, expected_status in checks:
        actual_status, _headers = _endpoint_response(url)
        if actual_status != expected_status:
            raise SystemExit(
                f"Endpoint check failed for {url}: expected HTTP {expected_status}, received HTTP {actual_status}.",
            )


def _require_human_publish_environment(*, environment: Mapping[str, str] | None = None) -> None:
    """Refuse a landing publish from any automated environment, unconditionally.

    The documentation publisher now accepts a provisioned automated authority.
    This one has none and is not merely waiting for one: the two publishers are
    deliberately independent verbs, no workflow publishes the landing page, and
    no deploy role is scoped to it. There is consequently no automated identity
    here for a conditional permission to be granted to, so the refusal stays
    absolute rather than mirroring the documentation guard's shape.

    Keeping the two guards separate is the point. Sharing one would silently
    extend the documentation site's automated authority to a surface that was
    never granted any, which is exactly the surprise publish both guards exist
    to prevent.

    Args:
        environment: DI seam for tests. When ``None`` (production), the
            check reads the real process environment; a test passes an
            explicit mapping without mutating real process state.
    """
    env = environment if environment is not None else os.environ
    markers = tuple(name for name in _CI_MARKERS if name in env)
    if markers:
        raise SystemExit(
            "Refusing Cadrumo landing publish from an automated environment "
            f"({', '.join(markers)}): the landing page has no automated publish authority "
            "and is published only from a local human session.",
        )


def _publish(aws: str, repo_root: Path) -> int:
    """Build, validate, upload, and invalidate the fixed Cadrumo landing page."""
    _require_human_publish_environment()
    _authenticated_account_id(aws, repo_root)
    target = _stack_target(aws, repo_root)
    _verify_distribution_alias(aws, repo_root, target.distribution_id)
    dist_root = _build_site(repo_root)
    _validate_site_artifacts(dist_root)
    _sync_site(aws, repo_root, dist_root, target.bucket)
    _invalidate_site(aws, repo_root, target.distribution_id)
    _verify_public_delivery(target)
    _verify_published_landing_page(dist_root)
    print(f"Published {CANONICAL_SITE_URL}/", flush=True)
    return 0


def _dry_run(aws: str, repo_root: Path) -> int:
    """Build and inspect the exact root sync without changing the bucket."""
    _require_human_publish_environment()
    _authenticated_account_id(aws, repo_root)
    target = _stack_target(aws, repo_root)
    _verify_distribution_alias(aws, repo_root, target.distribution_id)
    dist_root = _build_site(repo_root)
    _validate_site_artifacts(dist_root)
    _sync_site(aws, repo_root, dist_root, target.bucket, dry_run=True)
    print("Verified root sync dry run leaves docs/* unchanged.", flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    """Publish the fixed Cadrumo landing page."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    publish = commands.add_parser("publish", help="Build and publish the fixed landing page.")
    publish.add_argument(
        "--confirm",
        choices=("publish-cadrumo-frontend",),
        required=True,
        help="Required literal acknowledgement for the local publishing.",
    )
    commands.add_parser("dry-run", help="Build and inspect the exact root sync without changing S3.")
    args = parser.parse_args(argv)

    _require_human_publish_environment()

    repo_root = _repo_root()
    if shutil.which("npm") is None:
        raise SystemExit("npm is required to build the landing page.")
    aws = _required_executable("aws")
    if args.command == "dry-run":
        return _dry_run(aws, repo_root)
    return _publish(aws, repo_root)


if __name__ == "__main__":
    raise SystemExit(main())
