"""Describe verified documentation files and their static public routes."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path, PurePosixPath
from typing import Any

from dev.deploy.r2_objects import content_type_for, files_to_publish

STATIC_SCRIPT = "cadrumo-docs-static"
PUBLIC_BUCKET = "cadrumo-docs-search"
PUBLIC_HOST = "cadrumo-docs-search.neve.md"
MOUNTS = ("/docs", "/cadrumo/docs")
LANGUAGES = ("en", "es", "ca", "hu")
MANIFEST_SCHEMA = "cadrumo.docs-release.v1"
MANIFEST_NAME = "delivery-manifest.json"


def _require_release_path(key: str) -> None:
    """Require release path."""
    if (
        not isinstance(key, str)
        or not key
        or key.startswith("/")
        or "\\" in key
        or ":" in key
        or _release_path_contains_control_characters(key)
        or any(part in {"", ".", ".."} for part in key.split("/"))
    ):
        raise ValueError("Unsafe release path")


def _release_path_contains_control_characters(key: str) -> bool:
    """Recognize whitespace and control bytes after the string-shape checks."""
    return any(character.isspace() or ord(character) < 32 for character in key)


def _require_release_population(objects: dict[str, Any]) -> None:
    """Require release population.

    A page is required per language, because the pages differ by language. The
    search runtime is required once, at the apex: the site has ONE index and
    every language's pages load it from there.
    """
    required = {"index.html", "404.html", "pagefind/pagefind.js", "pagefind/pagefind-entry.json"}
    required.update(f"{language}/index.html" for language in LANGUAGES)
    for kind in ("fragment", "index"):
        if not any(key.startswith(f"pagefind/{kind}/") for key in objects):
            raise ValueError(f"Missing site search {kind}")
    if not required.issubset(objects):
        raise ValueError("Release lacks required pages or search runtime")


def _require_mirror_error_pages(document: dict[str, Any], objects: dict[str, Any]) -> None:
    """Require mirror error pages."""
    mirrors = document.get("mirror_errors")
    error_pages = {key for key in objects if key == "404.html" or key.endswith("/404.html")}
    if (
        not isinstance(mirrors, dict)
        or set(mirrors) != error_pages
        or not all(isinstance(text, str) for text in mirrors.values())
    ):
        raise ValueError("Missing or invalid mirror error pages")


def search_payload(key: str) -> bool:
    """Identify the large generated search trees without moving the search runtime.

    One pair of trees for the whole site, at the apex: the site has ONE index,
    so these keys no longer begin with a language.
    """
    parts = PurePosixPath(key).parts
    return len(parts) == 3 and parts[0] == "pagefind" and parts[1] in {"fragment", "index"}


def validate_manifest(document: Any) -> dict[str, Any]:
    """Reject incomplete, unsafe, or inconsistent recovery manifests."""
    if not isinstance(document, dict) or document.get("schema") != MANIFEST_SCHEMA:
        raise ValueError("Unknown documentation release manifest")
    release = document.get("release", "")
    if (
        not isinstance(release, str)
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}-[0-9]{8}T[0-9]{6}Z", release) is None
    ):
        raise ValueError("Invalid release identity")
    objects = document.get("objects")
    if not isinstance(objects, dict) or not objects:
        raise ValueError("Empty release manifest")
    _require_release_population(objects)
    for key, row in objects.items():
        _require_release_object(key, row)
    _require_mirror_error_pages(document, objects)
    return document


def build_manifest(root: Path, release: str) -> dict[str, Any]:
    """Hash every publishable byte before a release can be activated."""
    objects = {}
    for key, path in sorted(files_to_publish(root, excludes=(".doctrees/*", "*/.doctrees/*")).items()):
        body = path.read_bytes()
        objects[key] = {
            "size": len(body),
            "etag": hashlib.md5(body, usedforsecurity=False).hexdigest(),
            "sha256": hashlib.sha256(body).hexdigest(),
            "content_type": content_type_for(path),
        }
    mirrors = {
        key: (root / key).read_text(encoding="utf-8").replace('"/docs/', '"/cadrumo/docs/')
        for key in objects
        if key == "404.html" or key.endswith("/404.html")
    }
    return validate_manifest(
        {"schema": MANIFEST_SCHEMA, "release": release, "objects": objects, "mirror_errors": mirrors}
    )


def verify_bytes(body: bytes, row: dict[str, Any], key: str) -> None:
    """Refuse bytes that differ from their sealed release identity."""
    if len(body) != row["size"] or hashlib.sha256(body).hexdigest() != row["sha256"]:
        raise ValueError(f"Release content differs: {key}")


def asset_layout(document: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    """Map both mounts into one assets-only deployment, preserving HTML URLs."""
    validate_manifest(document)
    manifest: dict[str, dict[str, Any]] = {}
    sources: dict[str, str] = {}
    for key, row in document["objects"].items():
        if search_payload(key):
            continue
        if row["size"] > 25 * 1024 * 1024:
            raise ValueError(f"Static asset exceeds 25 MiB: {key}")
        for mount in MOUNTS:
            path = f"{mount}/{key}"
            manifest[path] = {"hash": row["etag"], "size": row["size"]}
            sources[path] = key
            if mount == MOUNTS[1] and key in document.get("mirror_errors", {}):
                body = document["mirror_errors"][key].encode("utf-8")
                manifest[path] = {"hash": hashlib.md5(body, usedforsecurity=False).hexdigest(), "size": len(body)}
                sources[path] = f"@mirror:{key}"
    # Both mount-local error pages are present; the root is the platform fallback.
    manifest["/404.html"] = manifest["/docs/404.html"]
    sources["/404.html"] = "404.html"
    if len(manifest) > 20_000:
        raise ValueError(f"Static manifest exceeds the Free file allowance: {len(manifest)}")
    return manifest, sources


def delivery_config(document: dict[str, Any]) -> dict[str, Any]:
    """Generate bounded native redirects and headers, without executable code."""
    objects = document["objects"]
    redirects: list[str] = []
    for mount in MOUNTS:
        _append_mount_redirects(mount, document, objects, redirects)

    # Cloudflare treats every rule after the first dynamic rule as dynamic,
    # including exact paths for the second mount. Partition globally first.
    def is_dynamic(row: str) -> bool:
        return "*" in row.split()[0] or ":" in row.split()[0]

    redirects.sort(key=is_dynamic)
    dynamic = sum(is_dynamic(row) for row in redirects)
    if dynamic > 100 or len(redirects) - dynamic > 2000:
        raise ValueError("Static redirects exceed platform limits")
    headers = (
        "/*\n"
        "  Cache-Control: public, max-age=300, must-revalidate, no-transform\n"
        "  X-Content-Type-Options: nosniff\n"
        "  Referrer-Policy: strict-origin-when-cross-origin\n"
        "  Strict-Transport-Security: max-age=31536000\n"
        f"  X-Cadrumo-Docs-Release: {document['release']}\n"
        "  X-Cadrumo-Docs-Delivery: static\n"
    )
    return {
        "html_handling": "none",
        "not_found_handling": "404-page",
        "run_worker_first": False,
        "_redirects": "\n".join(redirects) + "\n",
        "_headers": headers,
    }


def _require_release_object(key: str, row: Any) -> None:
    """Require release object."""
    _require_release_path(key)
    if not isinstance(row, dict) or type(row.get("size")) is not int or row["size"] < 0:
        raise ValueError(f"Invalid size: {key}")
    for name, length in (("sha256", 64), ("etag", 32)):
        if not isinstance(row.get(name), str) or re.fullmatch(f"[0-9a-f]{{{length}}}", row[name]) is None:
            raise ValueError(f"Invalid {name}: {key}")
    if not isinstance(row.get("content_type"), str) or not row["content_type"]:
        raise ValueError(f"Missing content type: {key}")


def _append_mount_redirects(
    mount: str, document: dict[str, Any], objects: dict[str, Any], redirects: list[str]
) -> None:
    """Append mount redirects."""
    redirects.append(f"{mount} {mount}/ 301")
    for key in objects:
        _append_directory_redirects(mount, key, redirects)
    _append_site_search_redirects(mount, document, objects, redirects)
    roots = sorted({key.split("/")[1] for key in objects if key.startswith("en/")})
    for root in roots:
        _append_english_root_redirects(mount, root, objects, redirects)


def _append_directory_redirects(mount: str, key: str, redirects: list[str]) -> None:
    """Append directory redirects."""
    if key == "index.html" or key.endswith("/index.html"):
        directory = key.removesuffix("index.html")
        redirects.append(f"{mount}/{directory} {mount}/{key} 200")
        if directory:
            redirects.append(f"{mount}/{directory.rstrip('/')} {mount}/{directory} 301")


def _append_site_search_redirects(
    mount: str, document: dict[str, Any], objects: dict[str, Any], redirects: list[str]
) -> None:
    """Send the site's one pair of search trees to the public bucket.

    One rule per tree for the whole site, where there was one per tree per
    language: the index these address is the site's, loaded from the apex by
    every language's pages, so a language no longer names one of its own.
    """
    for kind in ("fragment", "index"):
        path = f"pagefind/{kind}"
        redirects.append(f"{mount}/{path}/* https://{PUBLIC_HOST}/releases/{document['release']}/{path}/:splat 302")
        sample = min(key for key in objects if key.startswith(path + "/"))
        redirects.append(f"{mount}/_health/{kind} https://{PUBLIC_HOST}/releases/{document['release']}/{sample} 302")


def _append_english_root_redirects(mount: str, root: str, objects: dict[str, Any], redirects: list[str]) -> None:
    """Append english root redirects."""
    if root in {"index.html", "404.html"} or root.startswith("."):
        return
    if f"en/{root}" in objects:
        if root not in objects:
            redirects.append(f"{mount}/{root} {mount}/en/{root} 301")
    else:
        redirects.append(f"{mount}/{root}/* {mount}/en/{root}/:splat 301")
        redirects.append(f"{mount}/{root} {mount}/en/{root}/ 301")
