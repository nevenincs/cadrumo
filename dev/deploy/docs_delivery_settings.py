"""Reconcile only documentation-owned Cloudflare delivery configuration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dev.deploy.cloudflare_api import CloudflareAccount, _call
from dev.deploy.docs_asset_manifest import PUBLIC_BUCKET, PUBLIC_HOST

DOCS_EXPRESSION = (
    '((http.host eq "cadrumo.neve.md" and (http.request.uri.path eq "/docs" or '
    'starts_with(http.request.uri.path, "/docs/"))) or (http.host eq "neve.md" and '
    '(http.request.uri.path eq "/cadrumo/docs" or starts_with(http.request.uri.path, "/cadrumo/docs/"))))'
)


def optional_get(account: CloudflareAccount, path: str) -> Any:
    """Treat only an explicit missing resource as absent."""
    try:
        return _call(account, "GET", path)
    except SystemExit as exc:
        if "HTTP 404" not in str(exc):
            raise
        return None


def prepare_storage(account: CloudflareAccount) -> None:
    """Create an isolated search bucket without exposing the private archive."""
    base = f"/accounts/{account.account_id}/r2/buckets"
    if optional_get(account, f"{base}/{PUBLIC_BUCKET}") is None:
        _call(account, "POST", base, json={"name": PUBLIC_BUCKET, "locationHint": "weur"})


def reconcile_rule(account: CloudflareAccount, zone: str, phase: str, rule: dict[str, Any]) -> None:
    """Upsert one owned rule while retaining every unrelated zone rule."""
    base = f"/zones/{zone}/rulesets"
    current = optional_get(account, f"{base}/phases/{phase}/entrypoint")
    if current is None:
        _call(
            account,
            "POST",
            base,
            json={"name": "Documentation delivery", "kind": "zone", "phase": phase, "rules": [rule]},
        )
        return
    existing = next((item for item in current["rules"] if item.get("ref") == rule["ref"]), None)
    path = f"{base}/{current['id']}/rules"
    _call(account, "PATCH" if existing else "POST", f"{path}/{existing['id']}" if existing else path, json=rule)


def configure_delivery(account: CloudflareAccount, zone: str, snapshot: Path) -> None:
    """Snapshot and apply scoped cache, anonymous CORS, and transport settings."""
    snapshot.mkdir(parents=True, exist_ok=False)
    base = f"/accounts/{account.account_id}/r2/buckets/{PUBLIC_BUCKET}"
    phases = (
        "http_config_settings",
        "http_request_cache_settings",
        "http_response_headers_transform",
        "http_request_firewall_custom",
        "http_request_dynamic_redirect",
    )
    before = {phase: optional_get(account, f"/zones/{zone}/rulesets/phases/{phase}/entrypoint") for phase in phases}
    before["cors"] = optional_get(account, f"{base}/cors")
    before["domains"] = _call(account, "GET", f"{base}/domains/custom")
    before["tls"] = _call(account, "GET", f"/zones/{zone}/hostnames/settings/min_tls_version")
    before["tiered"] = _call(account, "GET", f"/zones/{zone}/cache/tiered_cache_smart_topology_enable")
    (snapshot / "before.json").write_text(json.dumps(before, indent=2), encoding="utf-8")
    _call(
        account,
        "PUT",
        f"{base}/cors",
        json={
            "rules": [
                {
                    "id": "public-search-read",
                    "allowed": {"origins": ["*"], "methods": ["GET", "HEAD"], "headers": ["Range", "If-None-Match"]},
                    "exposeHeaders": ["ETag", "Content-Length", "Content-Range", "Cache-Control"],
                    "maxAgeSeconds": 86400,
                }
            ]
        },
    )
    if not any(item["domain"] == PUBLIC_HOST for item in before["domains"]["domains"]):
        _call(
            account,
            "POST",
            f"{base}/domains/custom",
            json={"domain": PUBLIC_HOST, "enabled": True, "zoneId": zone, "minTLS": "1.2"},
        )
    public = f'(http.host eq "{PUBLIC_HOST}" and starts_with(http.request.uri.path, "/releases/"))'
    reconcile_rule(
        account,
        zone,
        "http_config_settings",
        {
            "ref": "cadrumo_docs_identity",
            "description": "Preserve documentation validators",
            "expression": DOCS_EXPRESSION,
            "action": "set_config",
            "enabled": True,
            "action_parameters": {"email_obfuscation": False, "automatic_https_rewrites": False},
        },
    )
    reconcile_rule(
        account,
        zone,
        "http_config_settings",
        {
            "ref": "cadrumo_origin_tls",
            "description": "Validate Cadrumo origin certificates",
            "expression": '(http.host eq "cadrumo.neve.md")',
            "action": "set_config",
            "enabled": True,
            "action_parameters": {"ssl": "strict"},
        },
    )
    reconcile_rule(
        account,
        zone,
        "http_request_cache_settings",
        {
            "ref": "cadrumo_search_cache",
            "description": "Cache immutable public search objects",
            "expression": public,
            "action": "set_cache_settings",
            "enabled": True,
            "action_parameters": {
                "cache": True,
                "edge_ttl": {"mode": "bypass_by_default"},
                "browser_ttl": {"mode": "respect_origin"},
                "respect_strong_etags": True,
            },
        },
    )
    reconcile_rule(
        account,
        zone,
        "http_response_headers_transform",
        {
            "ref": "cadrumo_search_cors",
            "description": "Preserve anonymous search reads on cache hits",
            "expression": public,
            "action": "rewrite",
            "enabled": True,
            "action_parameters": {
                "headers": {
                    "access-control-allow-origin": {"operation": "set", "value": "*"},
                    "access-control-expose-headers": {
                        "operation": "set",
                        "value": "ETag,Content-Length,Content-Range,Cache-Control,CF-Cache-Status",
                    },
                    "timing-allow-origin": {"operation": "set", "value": "*"},
                    "x-content-type-options": {"operation": "set", "value": "nosniff"},
                }
            },
        },
    )
    reconcile_rule(
        account,
        zone,
        "http_response_headers_transform",
        {
            "ref": "cadrumo_docs_no_speculation",
            "description": "Avoid unsupported prefetches on docs delivery routes",
            "expression": DOCS_EXPRESSION,
            "action": "rewrite",
            "enabled": True,
            "action_parameters": {"headers": {"speculation-rules": {"operation": "remove"}}},
        },
    )
    # Per-host handshake minimums require Advanced Certificate Manager. Enforce
    # modern TLS at the request boundary without changing unrelated zone hosts.
    reconcile_rule(
        account,
        zone,
        "http_request_firewall_custom",
        {
            "ref": "cadrumo_modern_tls",
            "description": "Reject obsolete TLS on Cadrumo documentation",
            "expression": "(" + DOCS_EXPRESSION + ' and ssl and not cf.tls_version in {"TLSv1.2" "TLSv1.3"})',
            "action": "block",
            "enabled": True,
        },
    )
    _call(account, "PATCH", f"/zones/{zone}/cache/tiered_cache_smart_topology_enable", json={"value": "on"})
    # Exact Worker routes do not match a bare mount with a query string.
    # Keep those requests off the unrelated origin without matching /docsfoo.
    reconcile_rule(
        account,
        zone,
        "http_request_dynamic_redirect",
        {
            "ref": "cadrumo_bare_mount_query",
            "description": "Preserve queries when normalizing bare documentation mounts",
            "expression": '(http.request.uri.query ne "" and ((http.host eq "cadrumo.neve.md" '
            'and http.request.uri.path eq "/docs") or (http.host eq "neve.md" '
            'and http.request.uri.path eq "/cadrumo/docs")))',
            "action": "redirect",
            "enabled": True,
            "action_parameters": {
                "from_value": {
                    "target_url": {"expression": 'concat("https://", http.host, http.request.uri.path, "/")'},
                    "status_code": 301,
                    "preserve_query_string": True,
                }
            },
        },
    )
