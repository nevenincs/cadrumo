"""Reject incomplete documentation releases and preserve static delivery paths."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from dev.deploy import docs_asset_delivery, r2_objects
from dev.deploy.docs_asset_delivery import verify_inventory
from dev.deploy.docs_asset_manifest import LANGUAGES, asset_layout, build_manifest, delivery_config, verify_bytes
from dev.deploy.r2_objects import R2Bucket, deployment_lock

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]
RELEASE = "fixture-20260927T000000Z"


def fixture_release(root: Path) -> dict[str, Any]:
    """Build real files with separate search runtime and generated payloads."""
    files = {"index.html": "language entry", "404.html": '<a href="/docs/en/">Docs</a>'}
    for language in LANGUAGES:
        files.update(
            {
                f"{language}/index.html": language,
                f"{language}/search.html": "Search",
                f"{language}/pagefind/pagefind.js": "export default {};",
                f"{language}/pagefind/pagefind-entry.json": "{}",
                f"{language}/pagefind/fragment/a.pf_fragment": "fragment",
                f"{language}/pagefind/index/a.pf_index": "index",
            }
        )
    for key, body in files.items():
        path = root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return build_manifest(root, RELEASE)


def test_static_delivery_preserves_both_mounts_and_local_search_runtime(tmp_path: Path) -> None:
    document = fixture_release(tmp_path)
    assets, sources = asset_layout(document)
    config = delivery_config(document)
    for mount in ("/docs", "/cadrumo/docs"):
        assert f"{mount}/en/search.html" in assets
        assert f"{mount}/en/pagefind/pagefind.js" in assets
        assert f"{mount}/en/pagefind/fragment/a.pf_fragment" not in assets
        assert f"{mount}/en/ {mount}/en/index.html 200" in config["_redirects"]
        assert f"{mount}/search.html {mount}/en/search.html 301" in config["_redirects"]
        assert f"{mount}/en/pagefind/index/* https://" in config["_redirects"]
    assert assets["/docs/404.html"]["hash"] != assets["/cadrumo/docs/404.html"]["hash"]
    assert sources["/cadrumo/docs/404.html"] == "@mirror:404.html"
    assert 'href="/cadrumo/docs/en/"' in document["mirror_errors"]["404.html"]
    assert config["html_handling"] == "none"
    assert config["run_worker_first"] is False


def test_manifest_detects_changed_bytes_and_missing_search(tmp_path: Path) -> None:
    document = fixture_release(tmp_path)
    with pytest.raises(ValueError, match="content differs"):
        verify_bytes(b"wrong", document["objects"]["index.html"], "index.html")
    (tmp_path / "en/pagefind/index/a.pf_index").unlink()
    with pytest.raises(ValueError, match="Missing en search index"):
        build_manifest(tmp_path, RELEASE)


def test_inventory_refuses_missing_extra_and_corrupt_objects(tmp_path: Path) -> None:
    document = fixture_release(tmp_path)
    expected = {f"releases/{RELEASE}/{key}": (row["size"], row["etag"]) for key, row in document["objects"].items()}
    verify_inventory(document, expected)
    for actual in ({}, {**expected, "extra": (1, "bad")}, {**expected, f"releases/{RELEASE}/index.html": (1, "bad")}):
        with pytest.raises(ValueError, match="inventory differs"):
            verify_inventory(document, actual)


def test_static_limits_fail_before_upload(tmp_path: Path) -> None:
    document = fixture_release(tmp_path)
    document["objects"]["index.html"]["size"] = 25 * 1024 * 1024 + 1
    with pytest.raises(ValueError, match="25 MiB"):
        asset_layout(document)
    document = fixture_release(tmp_path)
    row = document["objects"]["index.html"]
    document["objects"].update({f"extra/{index}.html": row for index in range(10_001)})
    with pytest.raises(ValueError, match="file allowance"):
        asset_layout(document)


def test_recovery_refuses_unsealed_release_before_deployment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(*_args: Any) -> bytes:
        raise ValueError("Cannot read release object: HTTP 404")

    monkeypatch.setattr(docs_asset_delivery, "read_object", missing)
    with pytest.raises(ValueError, match="404"):
        docs_asset_delivery.load_release(R2Bucket("account", "private", "key", "secret"), RELEASE, tmp_path)


def test_publish_lock_blocks_overlap_and_releases_after_error(monkeypatch: pytest.MonkeyPatch) -> None:
    state: dict[str, bytes] = {}

    def request(_bucket: R2Bucket, *, method: str, path: str, body: bytes = b"", **_kwargs: Any) -> tuple[int, bytes]:
        if method == "PUT":
            if path in state:
                return 412, b""
            state[path] = body
            return 200, b""
        if method == "GET":
            return 200, state[path]
        del state[path]
        return 204, b""

    monkeypatch.setattr(r2_objects, "_request", request)
    bucket = R2Bucket("account", "private", "key", "secret")
    with pytest.raises(RuntimeError, match="failed verification"), deployment_lock(bucket):
        assert json.loads(next(iter(state.values())))["owner"]
        with pytest.raises(ValueError, match="locked"), deployment_lock(bucket):
            pytest.fail("A second publisher acquired the active lock")
        raise RuntimeError("failed verification")
    assert not state


def test_manifest_cannot_escape_recovery_directory(tmp_path: Path) -> None:
    document = fixture_release(tmp_path)
    document["objects"]["../escape"] = document["objects"]["index.html"]
    with pytest.raises(ValueError, match="Unsafe release path"):
        asset_layout(document)
