"""Deploy the documentation Worker and manage its zone wiring through the Cloudflare API.

The Worker is a single JavaScript module uploaded as it stands, so the deploy
is one multipart API call and needs no bundler, no Wrangler and no Node on the
publishing host. Every call here states its intent in a verb and refuses any
answer the API does not mark successful.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import httpx

_API: Final[str] = "https://api.cloudflare.com/client/v4"
_TIMEOUT_SECONDS: Final[float] = 60.0


@dataclass(frozen=True)
class CloudflareAccount:
    """The account and the API token calls are made with."""

    account_id: str
    api_token: str


@dataclass(frozen=True)
class WorkerRoute:
    """One route pattern and the Worker it must invoke."""

    pattern: str
    script: str


def _call(account: CloudflareAccount, method: str, path: str, **kwargs: Any) -> Any:
    """Send one API request and return its ``result``, refusing any failure."""
    headers = {"Authorization": f"Bearer {account.api_token}", **kwargs.pop("headers", {})}
    try:
        response = httpx.request(method, f"{_API}{path}", headers=headers, timeout=_TIMEOUT_SECONDS, **kwargs)
    except httpx.HTTPError as exc:
        raise SystemExit(f"Cloudflare API {method} {path} could not be reached: {exc}") from exc
    try:
        document = response.json()
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Cloudflare API {method} {path} answered HTTP {response.status_code} without JSON.") from exc
    if not document.get("success"):
        errors = "; ".join(f"{error.get('code')}: {error.get('message')}" for error in document.get("errors", []))
        raise SystemExit(f"Cloudflare API {method} {path} refused (HTTP {response.status_code}): {errors}")
    return document.get("result")


def zone_id(account: CloudflareAccount, zone_name: str) -> str:
    """Return the id of the one zone named ``zone_name``."""
    zones = _call(account, "GET", "/zones", params={"name": zone_name, "account.id": account.account_id})
    if not isinstance(zones, list) or len(zones) != 1:
        raise SystemExit(f"Expected exactly one Cloudflare zone named {zone_name!r}.")
    return str(zones[0]["id"])


def deploy_worker(
    account: CloudflareAccount,
    *,
    script: str,
    module: Path,
    compatibility_date: str,
    bindings: Sequence[Mapping[str, str]],
) -> None:
    """Upload ``module`` as the Worker ``script`` with ``bindings``, then close its workers.dev URL.

    The workers.dev URL is closed on every deploy rather than once: it is a
    per-script setting, and a Worker reachable there would serve every
    release outside the declared hosts.
    """
    metadata = {
        "main_module": module.name,
        "compatibility_date": compatibility_date,
        "bindings": list(bindings),
        "observability": {"enabled": True},
    }
    files = {
        "metadata": (None, json.dumps(metadata), "application/json"),
        module.name: (module.name, module.read_bytes(), "application/javascript+module"),
    }
    base = f"/accounts/{account.account_id}/workers/scripts/{script}"
    _call(account, "PUT", base, files=files)
    _call(account, "POST", f"{base}/subdomain", json={"enabled": False, "previews_enabled": False})


def worker_release(account: CloudflareAccount, *, script: str) -> str | None:
    """Return the ``RELEASE_ID`` binding the deployed Worker carries, or ``None``."""
    settings = _call(account, "GET", f"/accounts/{account.account_id}/workers/scripts/{script}/settings")
    for binding in settings.get("bindings", []) if isinstance(settings, dict) else []:
        if binding.get("name") == "RELEASE_ID":
            return str(binding.get("text"))
    return None


def ensure_routes(account: CloudflareAccount, zone: str, routes: Sequence[WorkerRoute]) -> None:
    """Make every route exist on ``zone`` and invoke its declared Worker."""
    existing = {route["pattern"]: route for route in _call(account, "GET", f"/zones/{zone}/workers/routes")}
    for route in routes:
        current = existing.get(route.pattern)
        body = {"pattern": route.pattern, "script": route.script}
        if current is None:
            _call(account, "POST", f"/zones/{zone}/workers/routes", json=body)
            print(f"Created route {route.pattern} -> {route.script}", flush=True)
        elif current.get("script") != route.script:
            _call(account, "PUT", f"/zones/{zone}/workers/routes/{current['id']}", json=body)
            print(f"Repointed route {route.pattern} -> {route.script}", flush=True)


def ensure_proxied(account: CloudflareAccount, zone: str, record_name: str) -> None:
    """Route ``record_name`` through Cloudflare so Worker routes on it take effect.

    Only the proxy flag changes; the record keeps its type and target, so the
    host's existing origin goes on answering every path no route claims.
    """
    records = _call(account, "GET", f"/zones/{zone}/dns_records", params={"name": record_name})
    if not isinstance(records, list) or len(records) != 1:
        raise SystemExit(f"Expected exactly one DNS record for {record_name!r}; found {len(records or [])}.")
    record = records[0]
    if record.get("proxied"):
        return
    _call(account, "PATCH", f"/zones/{zone}/dns_records/{record['id']}", json={"proxied": True})
    print(f"Proxied {record_name} ({record['type']} -> {record['content']}) through Cloudflare", flush=True)


def disable_redirect_rules(account: CloudflareAccount, zone: str, *, source_prefix: str) -> None:
    """Disable, never delete, every redirect rule whose expression names ``source_prefix``.

    Redirect rules run before Workers, so a rule still sending the mirror mount
    elsewhere would hide the Worker entirely. Disabling keeps the rule on
    record, so reverting the cutover is re-enabling it.
    """
    ruleset = _call(account, "GET", f"/zones/{zone}/rulesets/phases/http_request_dynamic_redirect/entrypoint")
    for rule in ruleset.get("rules", []):
        if source_prefix not in rule.get("expression", "") or not rule.get("enabled", True):
            continue
        body = {key: rule[key] for key in ("expression", "action", "action_parameters", "description") if key in rule}
        body["enabled"] = False
        _call(account, "PATCH", f"/zones/{zone}/rulesets/{ruleset['id']}/rules/{rule['id']}", json=body)
        print(f"Disabled redirect rule {rule['id']} ({rule.get('expression')})", flush=True)
