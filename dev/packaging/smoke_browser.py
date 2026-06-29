"""Build and verify the AEAT browser extra in a fresh installed environment."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from .smoke_core import (
    _build_wheel,
    _executable,
    _install_wheel,
    _manifest_path,
    _requirement_name,
    _run,
    _venv_python,
    _wheel_metadata,
    _work_dir,
    _write_smoke_manifest,
)

_BROWSER_EXTRA_DEPENDENCIES = {"playwright", "playwright-stealth"}


def _assert_browser_extra_metadata(wheel: Path) -> None:
    """Verify the built wheel advertises the browser extra and its packages."""
    requires_dist, provided_extras = _wheel_metadata(wheel)
    if "browser" not in provided_extras:
        raise SystemExit(f"wheel metadata is missing the browser extra: {sorted(provided_extras)!r}")
    browser_requires = {
        _requirement_name(requirement)
        for requirement in requires_dist
        if "extra ==" in requirement.lower() and "browser" in requirement.lower()
    }
    missing = sorted(_BROWSER_EXTRA_DEPENDENCIES - browser_requires)
    if missing:
        raise SystemExit(f"wheel browser extra is missing dependencies: {missing!r}")


def _browser_env(work_dir: Path) -> dict[str, str]:
    """Return an isolated environment for browser provisioning and health."""
    browser_cache = work_dir / "playwright-browsers"
    browser_cache.mkdir(parents=True, exist_ok=True)
    storage_root = work_dir / "profile-root"
    storage_root.mkdir(parents=True, exist_ok=True)
    return {
        **os.environ,
        "AEAT_BROWSER_CHANNEL": "chromium",
        "AEAT_BROWSER_HEADLESS": "true",
        "AEAT_LOCAL_STORAGE_ROOT": str(storage_root),
        "AEAT_OUTPUT_LANGUAGE": "en",
        "PLAYWRIGHT_BROWSERS_PATH": str(browser_cache),
    }


def _install_chromium(work_dir: Path, venv: Path, *, env: dict[str, str], with_deps: bool) -> None:
    """Provision the Playwright Chromium browser binary for the installed venv."""
    command = [str(_venv_python(venv)), "-m", "playwright", "install"]
    if with_deps:
        command.append("--with-deps")
    command.append("chromium")
    _run(command, cwd=work_dir, env=env)


def _assert_browser_imports(work_dir: Path, venv: Path) -> None:
    """Verify the optional Python packages are importable from the fresh venv."""
    code = "import playwright.async_api, playwright_stealth; print('browser-extra-imports-ok')"
    _run([str(_venv_python(venv)), "-c", code], cwd=work_dir)


def _run_health(work_dir: Path, venv: Path, *, env: dict[str, str]) -> None:
    """Run the installed no-secret browser health smoke against localhost."""
    code = r"""
import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

from aeat.adapters.outbound.aeat.browser import default_browser_session_factory
from aeat.core.config import load_settings


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"<!doctype html><title>AEAT packaging smoke</title><h1>ok</h1>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
thread = Thread(target=server.serve_forever, daemon=True)
thread.start()


async def main():
    browser_session = await default_browser_session_factory(load_settings())
    try:
        context = await browser_session.create_context()
        try:
            page = await context.new_page()
            url = f"http://127.0.0.1:{server.server_port}/"
            response = await browser_session.navigate(page, url)
            if not response or not response.ok:
                raise SystemExit(f"unexpected browser health response: {response.status if response else 'none'}")
            title = await page.title()
            if title != "AEAT packaging smoke":
                raise SystemExit(f"unexpected browser health title: {title!r}")
        finally:
            await context.close()
    finally:
        await browser_session.close()
        server.shutdown()
        server.server_close()


asyncio.run(main())
print("browser-health-ok")
"""
    _run(
        [str(_venv_python(venv)), "-c", code],
        cwd=work_dir,
        env=env,
    )


def main(argv: list[str] | None = None) -> int:
    """Run the browser-extra installed-wheel packaging smoke gate."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", default="3.13", help="Python interpreter/version for the fresh venv.")
    parser.add_argument("--work-dir", help="Empty directory for wheel, venv, and browser smoke artifacts.")
    parser.add_argument(
        "--with-deps",
        action="store_true",
        help="Pass --with-deps to Playwright install; intended for Linux container/CI lanes.",
    )
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[2]
    uv = _executable("uv")
    work_dir = _work_dir(repo_root, args.work_dir, prefix="browser")
    env = _browser_env(work_dir)
    print(f"browser packaging smoke work dir: {work_dir}", flush=True)

    print("building wheel", flush=True)
    wheel = _build_wheel(repo_root, work_dir, uv)
    _assert_browser_extra_metadata(wheel)

    print("installing wheel[browser] into fresh venv", flush=True)
    venv = _install_wheel(repo_root, work_dir, wheel, uv, args.python, extras=("browser",))
    _assert_browser_imports(work_dir, venv)

    print("provisioning Playwright Chromium", flush=True)
    _install_chromium(work_dir, venv, env=env, with_deps=args.with_deps)

    print("running installed browser health check", flush=True)
    _run_health(work_dir, venv, env=env)

    manifest = _write_smoke_manifest(
        work_dir,
        lane="browser-wheel",
        artifacts={
            "wheel": _manifest_path(work_dir, wheel),
            "venv": _manifest_path(work_dir, venv),
            "playwright_browsers": _manifest_path(work_dir, Path(env["PLAYWRIGHT_BROWSERS_PATH"])),
        },
        checks=(
            "wheel tracked shipped-data payload",
            "browser extra wheel metadata",
            "fresh uv virtualenv install",
            "browser optional imports",
            "Playwright Chromium provisioning",
            "localhost browser health smoke",
        ),
        details={"python": args.python, "with_deps": args.with_deps},
    )

    print(f"browser packaging smoke passed: {wheel}", flush=True)
    print(f"packaging smoke manifest: {manifest}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
