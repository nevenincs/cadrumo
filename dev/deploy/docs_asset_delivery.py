"""Publish sealed documentation through static assets and direct R2 search."""

from __future__ import annotations

import base64
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from typing import Any

from dev.deploy.cloudflare_api import CloudflareAccount, _call
from dev.deploy.docs_asset_manifest import (
    MANIFEST_NAME,
    PUBLIC_BUCKET,
    STATIC_SCRIPT,
    asset_layout,
    build_manifest,
    delivery_config,
    search_payload,
    validate_manifest,
    verify_bytes,
)
from dev.deploy.r2_objects import (
    R2Bucket,
    copy_public_object,
    object_inventory,
    put_object,
    read_object,
)

CANDIDATE_SCRIPT = "cadrumo-docs-candidate"


def verify_inventory(document: dict[str, Any], actual: dict[str, tuple[int, str]], *, public: bool = False) -> None:
    """Compare a complete remote inventory against sealed sizes and hashes."""
    prefix = f"releases/{document['release']}/"
    expected = {
        prefix + key: (row["size"], row["etag"])
        for key, row in document["objects"].items()
        if not public or search_payload(key)
    }
    if actual != expected:
        missing = len(expected.keys() - actual.keys())
        extra = len(actual.keys() - expected.keys())
        changed = sum(actual[key] != expected[key] for key in expected.keys() & actual.keys())
        raise ValueError(f"Release inventory differs: missing={missing}, extra={extra}, changed={changed}")


def seal_release(bucket: R2Bucket, root: Path, release: str) -> dict[str, Any]:
    """Verify archive and public payloads before writing a completed-release marker."""
    document = build_manifest(root, release)
    asset_layout(document)
    delivery_config(document)
    prefix = f"releases/{release}/"
    verify_inventory(document, object_inventory(bucket, prefix))
    public_bucket = replace(bucket, name=PUBLIC_BUCKET)
    existing = object_inventory(public_bucket, prefix)
    copies = []
    for key, row in document["objects"].items():
        if not search_payload(key):
            continue
        remote = existing.get(prefix + key)
        if remote is not None and remote != (row["size"], row["etag"]):
            raise ValueError(f"Refusing to overwrite immutable search content: {key}")
        if remote is None:
            copies.append((prefix + key, row["etag"]))

    def copy(item: tuple[str, str]) -> None:
        copy_public_object(bucket, public_bucket, *item)

    with ThreadPoolExecutor(max_workers=32) as pool:
        for count, _ in enumerate(pool.map(copy, copies), 1):
            if count % 5000 == 0 or count == len(copies):
                print(f"Published search objects {count}/{len(copies)}", flush=True)
    verify_inventory(document, object_inventory(public_bucket, prefix), public=True)
    body = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    put_object(
        bucket, f"delivery/{release}/{MANIFEST_NAME}", body, content_type="application/json", cache_control="no-store"
    )
    return document


def load_release(bucket: R2Bucket, release: str, root: Path) -> dict[str, Any]:
    """Verify a completed release and recover static bytes for rollback."""
    document = validate_manifest(json.loads(read_object(bucket, f"delivery/{release}/{MANIFEST_NAME}")))
    if document["release"] != release:
        raise ValueError("Recovery manifest belongs to a different release")
    prefix = f"releases/{release}/"
    verify_inventory(document, object_inventory(bucket, prefix))
    verify_inventory(document, object_inventory(replace(bucket, name=PUBLIC_BUCKET), prefix), public=True)

    def recover(item: tuple[str, dict[str, Any]]) -> None:
        key, row = item
        if search_payload(key):
            return
        body = read_object(bucket, prefix + key)
        verify_bytes(body, row, key)
        path = root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)

    with ThreadPoolExecutor(max_workers=16) as pool:
        for _ in pool.map(recover, document["objects"].items()):
            pass
    return document


def deploy_assets(account: CloudflareAccount, document: dict[str, Any], root: Path, *, script: str) -> str:
    """Upload native assets only, returning the deployed version identifier."""
    manifest, sources = asset_layout(document)
    by_hash = {row["hash"]: sources[path] for path, row in manifest.items()}
    path = f"/accounts/{account.account_id}/workers/scripts/{script}"
    session = _call(account, "POST", f"{path}/assets-upload-session", json={"manifest": manifest})
    completion = session["jwt"] if not session["buckets"] else None
    upload_account = CloudflareAccount(account.account_id, session["jwt"])
    for group in session["buckets"]:
        files = {}
        for digest in group:
            key = by_hash[digest]
            if key.startswith("@mirror:"):
                body = document["mirror_errors"][key.removeprefix("@mirror:")].encode()
                content_type = "text/html; charset=utf-8"
            else:
                row = document["objects"][key]
                body = (root / key).read_bytes()
                verify_bytes(body, row, key)
                content_type = row["content_type"]
            if hashlib.md5(body, usedforsecurity=False).hexdigest() != digest:
                raise ValueError(f"Static asset differs from manifest: {key}")
            files[digest] = (digest, base64.b64encode(body), content_type)
        uploaded = _call(
            upload_account,
            "POST",
            f"/accounts/{account.account_id}/workers/assets/upload",
            params={"base64": "true"},
            files=files,
        )
        completion = uploaded.get("jwt", completion)
        print(f"Uploaded {len(group)} static content hashes to {script}", flush=True)
    if not completion:
        raise ValueError("Static asset upload did not complete")
    metadata = {
        "compatibility_date": "2026-09-27",
        "bindings": [],
        "assets": {"jwt": completion, "config": delivery_config(document)},
    }
    _call(account, "PUT", path, files={"metadata": (None, json.dumps(metadata), "application/json")})
    _call(account, "POST", f"{path}/subdomain", json={"enabled": script == CANDIDATE_SCRIPT, "previews_enabled": False})
    return active_version(account, script)


def active_version(account: CloudflareAccount, script: str = STATIC_SCRIPT) -> str:
    """Read the single fully active version; refuse ambiguous deployments."""
    response = _call(account, "GET", f"/accounts/{account.account_id}/workers/scripts/{script}/deployments")
    deployments = response.get("deployments", [])
    if not deployments or len(deployments[0]["versions"]) != 1:
        raise ValueError("Expected one active documentation version")
    version = deployments[0]["versions"][0]
    if version["percentage"] != 100:
        raise ValueError("Documentation deployment is split between versions")
    return str(version["version_id"])


def restore_version(account: CloudflareAccount, version: str) -> None:
    """Restore the previous native asset version after failed public verification."""
    _call(
        account,
        "POST",
        f"/accounts/{account.account_id}/workers/scripts/{STATIC_SCRIPT}/deployments",
        json={"strategy": "percentage", "versions": [{"version_id": version, "percentage": 100}]},
    )


def save_active_release(bucket: R2Bucket, release: str, previous: str | None, version: str) -> None:
    """Record recovery identities only after both public mounts pass verification."""
    body = json.dumps({"release": release, "previous_release": previous, "version": version}).encode()
    put_object(bucket, "delivery/active.json", body, content_type="application/json", cache_control="no-store")
