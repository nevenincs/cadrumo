"""Discovery recon: drive the authenticated sede down into Kent's Modelo 100.

Kent's real expediente corpus on AEAT is:
    - 3x Modelo 100 (IRPF declaración anual)  ← we navigate here
    - 1x IVA "Regularización por falta de presentación"
    - 11x Certificados, 18x Sancionador, 3x Recursos, 10x Otros

The Mis Expedientes page is a lazy-loaded tree; the category anchors
fire ``javascript:mostrarListado(...)`` which AJAX-loads the list of
expedientes below them. We click the "Modelo 100 — Modelo 102" anchor,
wait for the subtree, then open the first (most recent) expediente.

Usage:
    uv run python scripts/recon_modelo_100.py
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from playwright.async_api import BrowserContext, Page, async_playwright

from aeat.browser import Profile
from aeat.browser.session import BrowserSession
from aeat.config import load_settings
from aeat.logging import get_logger

log = get_logger(__name__)


SEDE_BASE = "https://www6.agenciatributaria.gob.es"
EXPEDIENTES_URL = f"{SEDE_BASE}/wlpl/TEWV-CORE/ResumenVlt"

# Anchor text on the ResumenVlt tree we just captured live.
MODELO_100_ANCHOR_TEXT = "Modelo 100- Modelo 102"


def _find_storage_state(settings: Any) -> Path:
    token_dir: Path = settings.aeat_token_dir
    profile = settings.aeat_default_profile_name
    candidates = [
        token_dir / f"{profile}-clave-movil-storage.json",
        token_dir / f"{profile}-certificate-storage.json",
        token_dir / f"{profile}-storage.json",
    ]
    for c in candidates:
        if c.exists():
            return c
    raise SystemExit("no cached session; run `aeat auth login` first")


async def _dump_page(page: Page, outdir: Path, label: str) -> None:
    stage_dir = outdir / label
    stage_dir.mkdir(parents=True, exist_ok=True)
    (stage_dir / "url.txt").write_text(f"{page.url}\n", encoding="utf-8")
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
    outdir.mkdir(parents=True, exist_ok=True)
    log_path = outdir / "network.jsonl"
    handle = log_path.open("a", encoding="utf-8")

    def _record(payload: dict[str, Any]) -> None:
        payload["at"] = datetime.now(UTC).isoformat()
        handle.write(json.dumps(payload, default=str) + "\n")
        handle.flush()

    def on_req(req: Any) -> None:
        _record({"kind": "request", "method": req.method, "url": req.url, "rt": req.resource_type})

    def on_res(res: Any) -> None:
        try:
            status = int(res.status)
        except Exception:
            status = 0
        _record({"kind": "response", "status": status, "url": res.url})

    context.on("request", on_req)
    context.on("response", on_res)


async def run() -> Path:
    settings = load_settings()
    storage_state = _find_storage_state(settings)
    log.info("recon: using storage_state=%s", storage_state)

    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    outdir = Path("scratch") / "recon-100" / ts
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

            # Locate the Modelo 100 anchor by its visible text.
            # Tree branches are CSS-hidden until the parent is expanded,
            # but the onclick JS fires without requiring visibility.
            # Dispatch the click via DOM.click() to bypass Playwright's
            # visibility enforcement.
            clicked = await page.evaluate(
                """
                (anchorText) => {
                    const anchor = Array.from(document.querySelectorAll('a'))
                        .find(a => (a.textContent || '').includes(anchorText));
                    if (!anchor) return false;
                    anchor.click();
                    return true;
                }
                """,
                MODELO_100_ANCHOR_TEXT,
            )
            if not clicked:
                (outdir / "locate-error.txt").write_text(
                    f"could not find anchor with text containing {MODELO_100_ANCHOR_TEXT!r}\n",
                    encoding="utf-8",
                )
                return outdir

            # Let the AJAX subtree load. The tree mutates in place; we don't
            # navigate, so we wait for networkidle instead of load.
            with contextlib.suppress(Exception):
                await page.wait_for_load_state("networkidle", timeout=10_000)
            await _dump_page(page, outdir, "02-modelo-100-expanded")

            # Try to find a first expediente row under the expanded node.
            # AEAT typically renders rows as <a> with an expediente id in
            # the onclick or as links to a SvExpediente-style detail.
            candidates = await page.eval_on_selector_all(
                "a",
                """
                nodes => nodes
                    .map(a => ({
                        text: (a.textContent || '').trim(),
                        href: a.href || '',
                        onclick: a.getAttribute('onclick') || ''
                    }))
                    .filter(r =>
                        (r.onclick.includes('mostrar') || r.href.includes('Expediente'))
                        && (r.text.length > 0)
                    )
                """,
            )
            (outdir / "candidate-anchors.json").write_text(
                json.dumps(candidates, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            log.info("recon: found %d candidate anchors under Modelo 100", len(candidates))

            # Prefer a link that looks like an individual expediente: href
            # contains 'Expediente' but no '#' (tree-toggle anchors are '#').
            first_real = next(
                (c for c in candidates if "Expediente" in c["href"] and not c["href"].endswith("#")),
                None,
            )
            if first_real is None:
                (outdir / "no-expediente-link.txt").write_text(
                    "No concrete expediente <a> link found; the subtree may still be a grouping.\n"
                    "Inspect candidate-anchors.json and page.html to decide the next hop.\n",
                    encoding="utf-8",
                )
                return outdir
            await page.goto(first_real["href"], wait_until="domcontentloaded")
            await _dump_page(page, outdir, "03-expediente-detail")
            return outdir
        finally:
            try:
                await context.close()
            finally:
                await browser_session.close()


def main() -> None:
    outdir = asyncio.run(run())
    sys.stdout.write(f"recon complete -> {outdir}\n")


if __name__ == "__main__":
    main()
