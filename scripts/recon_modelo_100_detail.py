"""Stage-3 recon: open one Modelo 100 expediente detail page.

Discovery results so far (scripts/recon_modelo_100.py):
    - Kent has 3 Modelo 100 filings, expedientes
      `202310013522456T`, `202210013522538B`, `202110013520233F`
      (IRPF 2023, 2022, 2021 — most recent first).
    - Each links via per-year endpoint
      ``/wlpl/DASR-CORE/AccesoDR<YYYY>RVlt?exp=<expediente_id>``
      with an onclick handler ``lanzarTewvForm(this, 12)`` that
      wraps a hidden POST form submission.

This script navigates to the most recent (2023) expediente detail
and captures the resulting page. If ``lanzarTewvForm`` hides the
real submission in a form post, we'll see the POST in
``network.jsonl`` and can capture the response.
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
MODELO_100_ANCHOR_TEXT = "Modelo 100- Modelo 102"
TARGET_EXPEDIENTE_TEXT = "202310013522456T"  # IRPF 2023


def _find_storage_state(settings: Any) -> Path:
    token_dir: Path = settings.aeat_token_dir
    profile = settings.aeat_default_profile_name
    for c in (
        token_dir / f"{profile}-clave-movil-storage.json",
        token_dir / f"{profile}-certificate-storage.json",
        token_dir / f"{profile}-storage.json",
    ):
        if c.exists():
            return c
    raise SystemExit("no cached session; run `aeat auth login` first")


async def _dump(page: Page, outdir: Path, label: str) -> None:
    d = outdir / label
    d.mkdir(parents=True, exist_ok=True)
    (d / "url.txt").write_text(f"{page.url}\n", encoding="utf-8")
    try:
        (d / "page.html").write_text(await page.content(), encoding="utf-8")
    except Exception as exc:
        (d / "html-error.txt").write_text(f"{exc}", encoding="utf-8")
    try:
        await page.screenshot(path=str(d / "page.png"), full_page=True)
    except Exception as exc:
        (d / "screenshot-error.txt").write_text(f"{exc}", encoding="utf-8")
    log.info("dumped %s", d)


def _install_network_logger(context: BrowserContext, outdir: Path) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    log_path = outdir / "network.jsonl"
    handle = log_path.open("a", encoding="utf-8")

    def record(payload: dict[str, Any]) -> None:
        payload["at"] = datetime.now(UTC).isoformat()
        handle.write(json.dumps(payload, default=str) + "\n")
        handle.flush()

    context.on(
        "request",
        lambda req: record(
            {
                "kind": "request",
                "method": req.method,
                "url": req.url,
                "post_data": req.post_data,
            }
        ),
    )
    context.on(
        "response",
        lambda res: record({"kind": "response", "status": int(res.status or 0), "url": res.url}),
    )


async def run() -> Path:
    settings = load_settings()
    storage_state = _find_storage_state(settings)

    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    outdir = Path("scratch") / "recon-100-detail" / ts
    outdir.mkdir(parents=True, exist_ok=True)

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
            # Expand the Modelo 100 subtree.
            await page.evaluate(
                """
                (txt) => {
                    const a = Array.from(document.querySelectorAll('a'))
                        .find(a => (a.textContent || '').includes(txt));
                    if (a) a.click();
                }
                """,
                MODELO_100_ANCHOR_TEXT,
            )
            await page.wait_for_load_state("networkidle", timeout=10_000)
            await _dump(page, outdir, "01-modelo-100-expanded")

            # Click the target expediente by its visible label.
            clicked = await page.evaluate(
                """
                (txt) => {
                    const a = Array.from(document.querySelectorAll('a'))
                        .find(a => (a.textContent || '').trim() === txt);
                    if (!a) return false;
                    a.click();
                    return true;
                }
                """,
                TARGET_EXPEDIENTE_TEXT,
            )
            if not clicked:
                (outdir / "click-error.txt").write_text(
                    f"expediente anchor {TARGET_EXPEDIENTE_TEXT!r} not found\n",
                    encoding="utf-8",
                )
                return outdir

            # lanzarTewvForm submits a hidden form; wait for navigation or
            # network-idle so the new detail page settles.
            with contextlib.suppress(Exception):
                await page.wait_for_load_state("networkidle", timeout=15_000)
            await _dump(page, outdir, "02-expediente-detail")
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
