"""Seal and activate documentation releases with prior-version and route restoration."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cadrumo.core.storage_environment import prepare_temporary_directory
from dev.deploy.cloudflare_api import (
    CloudflareAccount,
    disable_redirect_rules,
    ensure_proxied,
    ensure_routes,
    zone_id,
)
from dev.deploy.cloudflare_api import _call as cloudflare_call
from dev.deploy.docs_asset_delivery import (
    CANDIDATE_SCRIPT,
    active_version,
    deploy_assets,
    load_release,
    restore_version,
    save_active_release,
    seal_release,
    verify_inventory,
)
from dev.deploy.docs_asset_manifest import (
    MANIFEST_NAME,
    PUBLIC_BUCKET,
    STATIC_SCRIPT,
    search_payload,
    validate_manifest,
    verify_bytes,
)
from dev.deploy.r2_objects import deployment_lock, list_keys, object_inventory, read_object, upload_tree

from .docs_delivery_contracts import (
    _CACHE_CONTROL,
    _DOCTREE_EXCLUDES,
    _RELEASE_ID_RE,
    CANONICAL_DOCS_BASE_URL,
    CANONICAL_SITE_DOMAIN,
    DELIVERY_ROUTES,
    DOCS_ZONE,
    MIRROR_DOCS_BASE_URL,
    MIRROR_SITE_DOMAIN,
    RELEASE_PREFIX,
    WORKER_SCRIPT,
    DeliveryCredentials,
)
from .docs_delivery_policy import (
    _delivery_credentials,
    _local_release_label,
    _require_authorized_publish_environment,
    _require_local_session,
    release_id,
)
from .docs_delivery_probe import (
    _await_release_served,
    _await_static_delivery,
    _verify_candidate,
    _verify_public_delivery,
    _verify_published_search_index,
)
from .docs_site_build import _build_site_roots
from .docs_site_download import _refresh_download_latest
from .docs_site_preflight import _validate_built_site


def _snapshot_documentation_routes(account: CloudflareAccount, zone: str) -> tuple[list[dict[str, Any]], set[str], str]:
    """Snapshot documentation routes."""
    patterns = {route.pattern for route in DELIVERY_ROUTES}
    legacy = {f"{CANONICAL_SITE_DOMAIN}/docs*", f"{MIRROR_SITE_DOMAIN}/cadrumo/docs*"}
    route_base = f"/zones/{zone}/workers/routes"
    before = [row for row in cloudflare_call(account, "GET", route_base) if row["pattern"] in patterns | legacy]
    if any(row.get("script") not in {WORKER_SCRIPT, STATIC_SCRIPT} for row in before):
        raise ValueError("Documentation route has an unexpected owner")
    return (before, legacy, route_base)


def _upload_release(credentials: DeliveryCredentials, html_root: Path, release: str) -> None:
    """Upload the built site as one release prefix and prove every object landed."""
    prefix = f"{RELEASE_PREFIX}{release}/"
    if list_keys(credentials.bucket, prefix):
        raise SystemExit(f"Release prefix {prefix} already holds objects; a release is never overwritten.")

    def report(done: int, total: int) -> None:
        if done == total or done % 500 == 0:
            print(f"Uploaded {done}/{total} objects to {prefix}", flush=True)

    written = upload_tree(
        credentials.bucket,
        html_root,
        prefix=prefix,
        cache_control=_CACHE_CONTROL,
        excludes=_DOCTREE_EXCLUDES,
        report=report,
    )
    landed = list_keys(credentials.bucket, prefix)
    if landed != written:
        raise SystemExit(
            f"Release {release} is incomplete in R2: wrote {len(written)} objects, listed {len(landed)}; "
            "the Worker was not moved to it.",
        )


def _wire_zone(credentials: DeliveryCredentials, zone: str) -> None:
    """Proxy the canonical host and retire the mirror redirect; idempotent.

    The canonical host keeps its existing origin for every path outside
    ``/docs``; only the proxy flag on its record changes. The redirect rules
    that sent the mirror mount to the canonical host are disabled, not
    deleted, so re-enabling them reverts it.
    """
    ensure_proxied(credentials.account, zone, CANONICAL_SITE_DOMAIN)
    disable_redirect_rules(credentials.account, zone, source_prefix=f"{MIRROR_SITE_DOMAIN}/cadrumo/docs")


def _provision(*, environment: Mapping[str, str] | None = None) -> int:
    """Route both docs mounts to the Worker: one-time zone wiring, local only.

    Run it once a release is live on the Worker routes (``publish --cutover``
    does exactly that): retiring the mirror redirect earlier would leave the
    mirror mount with nothing behind it.
    """
    env = environment if environment is not None else os.environ
    _require_local_session("provision", environment=env)
    credentials = _delivery_credentials(env)
    _wire_zone(credentials, zone_id(credentials.account, DOCS_ZONE))
    print("Zone wiring is in place for both documentation mounts.", flush=True)
    return 0


def _restore_routes(account: CloudflareAccount, zone: str, before: list[dict[str, Any]]) -> None:
    """Restore only the documentation route set after an unsuccessful activation."""
    base = f"/zones/{zone}/workers/routes"
    patterns = {route.pattern for route in DELIVERY_ROUTES}
    patterns.update({f"{CANONICAL_SITE_DOMAIN}/docs*", f"{MIRROR_SITE_DOMAIN}/cadrumo/docs*"})
    current = {row["pattern"]: row for row in cloudflare_call(account, "GET", base) if row["pattern"] in patterns}
    original = {row["pattern"]: row for row in before}
    for pattern, row in current.items():
        if pattern not in original:
            cloudflare_call(account, "DELETE", f"{base}/{row['id']}")
    for pattern, row in original.items():
        _restore_documentation_route(account, base, pattern, row, current)


def _activate_static_release(
    credentials: DeliveryCredentials,
    document: dict[str, Any],
    root: Path,
    zone: str,
) -> None:
    """Stage first, then switch both mounts and restore the previous version on failure."""
    account = credentials.account
    release = document["release"]
    deploy_assets(account, document, root, script=CANDIDATE_SCRIPT)
    _verify_candidate(account, release)
    before, legacy, route_base = _snapshot_documentation_routes(account, zone)
    previous = None
    if "delivery/active.json" in list_keys(credentials.bucket, "delivery/active.json"):
        previous = json.loads(read_object(credentials.bucket, "delivery/active.json"))
    previous_version = active_version(account) if previous else None
    try:
        version = deploy_assets(account, document, root, script=STATIC_SCRIPT)
        ensure_routes(account, zone, DELIVERY_ROUTES)
        _await_release_served(release)
        _await_static_delivery(release)
        _verify_public_delivery(release)
        for base_url in (CANONICAL_DOCS_BASE_URL, MIRROR_DOCS_BASE_URL):
            _verify_published_search_index(root, base_url=base_url)
        for row in before:
            if row["pattern"] in legacy:
                cloudflare_call(account, "DELETE", f"{route_base}/{row['id']}")
        save_active_release(credentials.bucket, release, previous["release"] if previous else None, version)
    except BaseException:
        _restore_failed_activation(account, zone, before, previous_version, previous)
        raise


def _publish(
    repo_root: Path,
    *,
    release_label: str | None = None,
    cutover: bool = False,
    environment: Mapping[str, str] | None = None,
) -> int:
    """Build, validate, upload, deploy and verify one documentation release.

    Args:
        repo_root: Repository root the build commands run from.
        release_label: What the release id is labelled with; CI passes the
            release tag, a local publish defaults to the commit.
        cutover: Also wire the zone (:func:`_wire_zone`) once this release is
            live on the Worker routes, so neither mount is left without an
            origin between the old delivery and the new one. Local only.
        environment: DI seam for tests, forwarded to
            :func:`_require_authorized_publish_environment`. ``None``
            (production) reads the real process environment.
    """
    env = environment if environment is not None else os.environ
    _require_authorized_publish_environment(environment=env)
    if cutover:
        _require_local_session("publish --cutover", environment=env)
    credentials = _delivery_credentials(env)
    zone = zone_id(credentials.account, DOCS_ZONE)
    release = release_id(release_label or _local_release_label(repo_root), now=datetime.now(UTC))
    _refresh_download_latest(repo_root)
    html_root = _build_site_roots(repo_root)
    _validate_built_site(html_root)
    with deployment_lock(credentials.bucket):
        _upload_release(credentials, html_root, release)
        document = seal_release(credentials.bucket, html_root, release)
        if cutover:
            _wire_zone(credentials, zone)
        _activate_static_release(credentials, document, html_root, zone)
    print(f"Published release {release} at {CANONICAL_DOCS_BASE_URL}/ and {MIRROR_DOCS_BASE_URL}/", flush=True)
    return 0


def _rollback(release: str, *, environment: Mapping[str, str] | None = None) -> int:
    """Verify and restore an earlier completed release, preserving the current one on failure."""
    env = environment if environment is not None else os.environ
    _require_authorized_publish_environment(environment=env)
    if _RELEASE_ID_RE.fullmatch(release) is None:
        raise SystemExit(f"{release!r} is not a release id.")
    credentials = _delivery_credentials(env)
    with (
        deployment_lock(credentials.bucket),
        tempfile.TemporaryDirectory(prefix="cadrumo-docs-rollback-", dir=prepare_temporary_directory()) as directory,
    ):
        root = Path(directory)
        document = load_release(credentials.bucket, release, root)
        _activate_static_release(credentials, document, root, zone_id(credentials.account, DOCS_ZONE))
    print(f"Rolled back to release {release}", flush=True)
    return 0


def _activate_existing(release: str, root: Path) -> int:
    """Activate an already sealed release from locally verified static bytes."""
    _require_local_session("activate", environment=os.environ)
    if _RELEASE_ID_RE.fullmatch(release) is None:
        raise ValueError("Invalid release identity")
    credentials = _delivery_credentials(os.environ)
    with deployment_lock(credentials.bucket):
        document = validate_manifest(json.loads(read_object(credentials.bucket, f"delivery/{release}/{MANIFEST_NAME}")))
        if document["release"] != release:
            raise ValueError("Release manifest identity mismatch")
        prefix = f"releases/{release}/"
        verify_inventory(document, object_inventory(credentials.bucket, prefix))
        verify_inventory(
            document, object_inventory(replace(credentials.bucket, name=PUBLIC_BUCKET), prefix), public=True
        )
        for key, row in document["objects"].items():
            if not search_payload(key):
                verify_bytes((root / key).read_bytes(), row, key)
        _activate_static_release(credentials, document, root, zone_id(credentials.account, DOCS_ZONE))
    return 0


def _restore_documentation_route(
    account: CloudflareAccount, base: str, pattern: str, row: dict[str, Any], current: dict[str, dict[str, Any]]
) -> None:
    """Restore documentation route."""
    body = {name: row[name] for name in ("pattern", "script", "request_limit_fail_open") if name in row}
    if pattern in current:
        cloudflare_call(account, "PUT", f"{base}/{current[pattern]['id']}", json=body)
    else:
        cloudflare_call(account, "POST", base, json=body)


def _restore_failed_activation(
    account: CloudflareAccount,
    zone: str,
    before: list[dict[str, Any]],
    previous_version: str | None,
    previous: dict[str, Any] | None,
) -> None:
    """Restore the prior version and routes before reraising an activation failure."""
    if previous_version:
        restore_version(account, previous_version)
    _restore_routes(account, zone, before)
    if previous:
        _await_release_served(previous["release"])
        _verify_public_delivery(previous["release"])
