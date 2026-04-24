"""Discovery recon: capture AEAT notifications / messages surface.

Targets the two notification-like endpoints observable from the
ResumenVlt page:

* ``/wlpl/IIIC-ALER/SvObtAlertas`` — "Mis alertas" (the top-right
  alerts bell that surfaces pending actions).
* AEAT's broader *Mis notificaciones* surface (Messages cluster
  #170) — URL template not yet known; walk Kent's area-personal link
  to discover it.

Output: ``scratch/recon-notifications/<ts>/`` with DOM + PNG + net log
for every page visited.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from playwright.async_api import async_playwright

from aeat.browser import Profile
from aeat.browser.session import BrowserSession
from aeat.config import load_settings
from aeat.logging import get_logger

log = get_logger(__name__)

SEDE_BASE = "https://www6.agenciatributaria.gob.es"
RESUMEN_URL = f"{SEDE_BASE}/wlpl/TEWV-CORE/ResumenVlt"
ALERTAS_URL = f"{SEDE_BASE}/wlpl/IIIC-ALER/SvObtAlertas"
AREA_PERSONAL_URL = "https://sede.agenciatributaria.gob.es/Sede/mi-area-personal.html"


async def _dump(page: Any, outdir: Path, label: str) -> None:
    stage = outdir / label
    stage.mkdir(parents=True, exist_ok=True)
    (stage / "url.txt").write_text(f"{page.url}\n", encoding="utf-8")
    with contextlib.suppress(Exception):
        (stage / "page.html").write_text(await page.content(), encoding="utf-8")
    with contextlib.suppress(Exception):
        await page.screenshot(path=str(stage / "page.png"), full_page=True)
    log.info("recon: dumped %s", label)


async def run() -> Path:
    settings = load_settings()
    storage = settings.aeat_token_dir / "default-clave-movil-storage.json"
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    outdir = Path("scratch") / "recon-notifications" / ts
    outdir.mkdir(parents=True, exist_ok=True)

    profile = Profile(name="default", storage_state_path=storage)
    async with async_playwright() as pw:
        bs = BrowserSession(pw, settings, profile)
        ctx = await bs.create_context(storage_state_path=storage)
        try:
            page = await ctx.new_page()
            await page.goto(RESUMEN_URL, wait_until="domcontentloaded")
            await _dump(page, outdir, "00-resumen-vlt")

            for label, url in (
                ("01-alertas", ALERTAS_URL),
                ("02-area-personal", AREA_PERSONAL_URL),
            ):
                with contextlib.suppress(Exception):
                    await page.goto(url, wait_until="domcontentloaded")
                    await _dump(page, outdir, label)

            # Look for notification anchors on the area-personal page.
            candidates = await page.eval_on_selector_all(
                "a",
                """
                nodes => nodes
                    .map(a => ({
                        text: (a.textContent || '').trim(),
                        href: a.href || '',
                    }))
                    .filter(r =>
                        /notific|alert|mensaj|buzón|buzon/i.test(r.text) ||
                        /notific|alert|mensaj/i.test(r.href)
                    )
                """,
            )
            (outdir / "notification-anchors.json").write_text(
                json.dumps(candidates, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            # Follow the first concrete notifications link if one exists.
            for idx, candidate in enumerate(candidates[:3]):
                href = candidate.get("href", "")
                if not href or href.startswith("#"):
                    continue
                with contextlib.suppress(Exception):
                    await page.goto(href, wait_until="domcontentloaded")
                    await _dump(page, outdir, f"03-notif-{idx}")

            return outdir
        finally:
            with contextlib.suppress(Exception):
                await ctx.close()
            await bs.close()


def main() -> None:
    outdir = asyncio.run(run())
    sys.stdout.write(f"recon-notifications complete -> {outdir}\n")


if __name__ == "__main__":
    main()
