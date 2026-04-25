"""Discovery recon: drive the post-auth AEAT sede for modelo 303.

Once a Cl@ve-móvil (or certificate) session has been cached to
``.tokens/`` via ``aeat auth login``, this script reuses that session's
storage_state to navigate the authenticated sede and dump ground truth
for every page we touch:

    ``scratch/recon-303/<utc-timestamp>/``
        01-resumenvlt/           — "Mis expedientes" listing
            url.txt
            page.html
            page.png              (full-page screenshot)
            network.jsonl         (request + response log)
        02-expediente-<id>/      — first modelo-303 expediente detail
            url.txt
            page.html
            page.png
            network.jsonl

Intent: this replaces every speculative URL / selector / response-shape
assumption in ``aeat.remote`` with real captured state. Run it after a
successful ``aeat auth login --provider clave_movil``.

Usage:
    uv run python scripts/recon_modelo_303.py [--modelo 303] [--max-hops 2]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from playwright.async_api import BrowserContext, Page, async_playwright

from aeat.browser import Profile
from aeat.browser.session import BrowserSession
from aeat.config import load_settings
from aeat.logging import get_logger

log = get_logger(__name__)


CLAVE_STORAGE_RELPATH = "default-profile-clave-movil-storage.json"
CERT_STORAGE_CANDIDATES = (
    "default-profile-certificate-storage.json",
    "default-profile-storage.json",
)

# AEAT post-auth targets. `www6` is the Cl@ve-dispatched subdomain; the
# authenticator records the actual landing URL per-session but direct
# goto with valid cookies also works.
SEDE_BASE = "https://www6.agenciatributaria.gob.es"
EXPEDIENTES_URL = f"{SEDE_BASE}/wlpl/TEWV-CORE/ResumenVlt"


def _find_storage_state(settings: Any) -> Path:
    """Locate the most recent cached session on disk."""
    token_dir: Path = settings.aeat_token_dir
    profile = settings.aeat_default_profile_name
    candidates = [
        token_dir / f"{profile}-clave-movil-storage.json",
        token_dir / f"{profile}-certificate-storage.json",
        token_dir / f"{profile}-storage.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    tried = "\n  - ".join(str(c) for c in candidates)
    raise SystemExit("No cached AEAT session found. Run `aeat auth login` first. Tried:\n  - " + tried)


async def _dump_page(page: Page, outdir: Path, label: str) -> None:
    """Dump URL, HTML, and a full-page PNG for the current page state."""
    stage_dir = outdir / label
    stage_dir.mkdir(parents=True, exist_ok=True)
    url = page.url
    (stage_dir / "url.txt").write_text(f"{url}\n", encoding="utf-8")
    try:
        html = await page.content()
        (stage_dir / "page.html").write_text(html, encoding="utf-8")
    except Exception as exc:
        (stage_dir / "html-error.txt").write_text(f"{type(exc).__name__}: {exc}\n", encoding="utf-8")
    try:
        await page.screenshot(path=str(stage_dir / "page.png"), full_page=True)
    except Exception as exc:
        (stage_dir / "screenshot-error.txt").write_text(f"{type(exc).__name__}: {exc}\n", encoding="utf-8")
    log.info("recon: dumped %s → %s", label, stage_dir)


def _install_network_logger(context: BrowserContext, outdir: Path) -> None:
    """Append every request/response to a JSONL log for offline inspection."""
    outdir.mkdir(parents=True, exist_ok=True)
    log_path = outdir / "network.jsonl"
    handle = log_path.open("a", encoding="utf-8")

    def _record(payload: dict[str, Any]) -> None:
        payload["at"] = datetime.now(UTC).isoformat()
        handle.write(json.dumps(payload, default=str) + "\n")
        handle.flush()

    def on_request(req: Any) -> None:
        _record({"kind": "request", "method": req.method, "url": req.url, "resource_type": req.resource_type})

    def on_response(res: Any) -> None:
        try:
            status = int(res.status)
        except Exception:
            status = 0
        _record({"kind": "response", "status": status, "url": res.url})

    context.on("request", on_request)
    context.on("response", on_response)


async def _find_first_modelo_link(page: Page, modelo: str) -> tuple[str, str] | None:
    """Return ``(expediente_id, href)`` for the first modelo row on the listing.

    Best-effort: inspects every ``<a>`` whose href or text mentions the
    modelo code. The result feeds the Phase-2 follow-up that navigates
    into the expediente detail page.
    """
    hrefs = await page.eval_on_selector_all(
        "a",
        """
        (nodes, modelo) => nodes
            .filter(a => (a.textContent || "").includes(modelo) || (a.href || "").includes("modelo=" + modelo))
            .map(a => ({href: a.href, text: (a.textContent || "").trim()}))
        """,
        modelo,
    )
    if not hrefs:
        return None
    first = hrefs[0]
    href = first.get("href") or ""
    exp_id_match = re.search(r"(?:expediente|exp|EXP)=([A-Za-z0-9_-]+)", href)
    exp_id = exp_id_match.group(1) if exp_id_match else "unknown"
    return exp_id, href


async def run(*, modelo: str, max_hops: int) -> Path:
    settings = load_settings()
    storage_state = _find_storage_state(settings)
    log.info("recon: using storage_state=%s", storage_state)

    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    outdir = Path("scratch") / f"recon-{modelo}" / ts
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "session.txt").write_text(f"storage_state={storage_state}\n", encoding="utf-8")

    profile = Profile(
        name=settings.aeat_default_profile_name,
        storage_state_path=storage_state,
    )
    async with async_playwright() as pw:
        browser_session = BrowserSession(pw, settings, profile)
        context = await browser_session.create_context(storage_state_path=storage_state)
        try:
            _install_network_logger(context, outdir)
            page = await context.new_page()

            await page.goto(EXPEDIENTES_URL, wait_until="domcontentloaded")
            await _dump_page(page, outdir, "01-resumenvlt")

            if max_hops < 2:
                return outdir

            hit = await _find_first_modelo_link(page, modelo)
            if hit is None:
                (outdir / "01-resumenvlt" / "no-modelo-link.txt").write_text(
                    f"No <a> element referencing modelo {modelo} found on the listing.\n",
                    encoding="utf-8",
                )
                return outdir
            exp_id, href = hit
            log.info("recon: navigating to first modelo %s entry → %s", modelo, href)
            await page.goto(href, wait_until="domcontentloaded")
            await _dump_page(page, outdir, f"02-expediente-{exp_id}")

            return outdir
        finally:
            try:
                await context.close()
            finally:
                await browser_session.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--modelo", default="303", help="Modelo code to look up (default: 303).")
    parser.add_argument(
        "--max-hops",
        type=int,
        default=2,
        help="How many pages to navigate: 1 = listing only, 2 = listing + first detail (default).",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    outdir = asyncio.run(run(modelo=args.modelo, max_hops=args.max_hops))
    import sys

    sys.stdout.write(f"recon complete -> {outdir}\n")


if __name__ == "__main__":
    main()
