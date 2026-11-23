"""The network guard fails a test that reaches past loopback, in its own process and in a worker it starts.

Each case runs a real nested pytest over a generated module that loads only the
guard plugin, so a guarded test failing is the observable. The browser cases
launch a real Chromium: one directly in the nested test process, and one in a
child started with the environment a profile worker receives from its runtime,
which has nothing of the guard but that environment.
"""

from __future__ import annotations

import os
import sys
import textwrap
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from defusedxml import ElementTree

from ..core.config import Settings
from .aeat_literal_fixtures import SEDE_ROOT_URL_FIXTURE
from .audited_process import ensure_text_completed_process, run_audited_process
from .network_guard import GUARD, PROXY_URL_VARIABLE, is_loopback_host, network_guard_armed

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SEDE_HOST = urlsplit(SEDE_ROOT_URL_FIXTURE).netloc

_CONFTEST = """\
pytest_plugins = ("cadrumo.tests.network_guard",)
"""

_INI = """\
[pytest]
addopts =
markers =
    aeat_live: opt-in tests that read from a real external service
"""

_MODULE = '''
import asyncio
import os
import socket
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from playwright.async_api import async_playwright

from cadrumo.core.config import Settings
from cadrumo.core.storage_environment import ChildEnvironmentProfile, child_environment
from cadrumo.tests.collection_storage_root import link_installed_component
from cadrumo.tests.aeat_literal_fixtures import SEDE_ROOT_URL_FIXTURE
from cadrumo.tests.network_guard import GUARD, PROXY_URL_VARIABLE, NetworkGuardRefusedError, network_guard_armed

SEDE = SEDE_ROOT_URL_FIXTURE

WORKER = """
import asyncio

from cadrumo.adapters.outbound.aeat.browser.factory import create_browser_session
from cadrumo.adapters.outbound.aeat.browser.profile import Profile
from cadrumo.core.config import Settings
from cadrumo.tests.aeat_literal_fixtures import SEDE_ROOT_URL_FIXTURE


async def main():
    settings = Settings()
    print("proxy", settings.cadrumo_proxy_url, flush=True)
    session = await create_browser_session(settings, Profile(name="network-guard-worker"))
    try:
        context = await session.create_context()
        page = await context.new_page()
        try:
            await page.goto(SEDE_ROOT_URL_FIXTURE, timeout=20000)
            print("reached", flush=True)
        except Exception as error:
            print("refused", str(error).splitlines()[0], flush=True)
        await context.close()
    finally:
        await session.close()


asyncio.run(main())
"""


class Page(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"<title>loopback</title>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        del args


async def visit(urls):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        try:
            page = await browser.new_page()
            outcomes = []
            for url in urls:
                try:
                    await page.goto(url, timeout=20000)
                    outcomes.append(await page.title())
                except Exception as error:
                    outcomes.append("refused " + str(error).splitlines()[0])
            return outcomes
        finally:
            await browser.close()


def test_sede_navigation():
    [outcome] = asyncio.run(visit([SEDE]))
    assert outcome.startswith("refused"), outcome


def test_data_and_loopback():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Page)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        titles = asyncio.run(
            visit(["data:text/html,<title>inline</title>", f"http://127.0.0.1:{port}/", f"http://localhost:{port}/"])
        )
        with socket.create_connection(("127.0.0.1", port), timeout=5):
            pass
    finally:
        server.shutdown()
        server.server_close()
    assert titles == ["inline", "loopback", "loopback"]


def test_non_loopback_socket():
    with pytest.raises(NetworkGuardRefusedError):
        socket.create_connection(("192.0.2.1", 443), timeout=1)


def test_worker_environment(tmp_path):
    root = tmp_path / "worker-root"
    # A worker finds its browser build under its storage root, as the suite's private roots do.
    link = root / "components" / "playwright"
    link_installed_component(root, "components/playwright", Path(os.environ["PLAYWRIGHT_BROWSERS_PATH"]))
    environment = child_environment(ChildEnvironmentProfile.OPERATOR, root)
    try:
        completed = subprocess.run(
            [sys.executable, "-c", WORKER], env=environment, capture_output=True, text=True, timeout=300, check=False
        )
    finally:
        # Removes the link itself, never the installed tree it names.
        if link.is_symlink():
            link.unlink()
        elif link.is_junction():
            os.rmdir(link)
    assert completed.returncode == 0, completed.stderr
    lines = completed.stdout.splitlines()
    assert lines[0] == "proxy " + GUARD.proxy_url, completed.stdout
    assert lines[1].startswith("refused"), completed.stdout


def test_ordinary_test_is_guarded():
    assert network_guard_armed()
    assert os.environ[PROXY_URL_VARIABLE] == GUARD.proxy_url
    assert Settings().cadrumo_proxy_url == GUARD.proxy_url


@pytest.mark.aeat_live
def test_live():
    assert not network_guard_armed()
    assert os.environ.get(PROXY_URL_VARIABLE) != GUARD.proxy_url
'''


def _nested_run(package: Path, report: Path, *args: str, live: bool) -> Mapping[str, str]:
    """Run the generated module under the guard and return each test's outcome and failure text."""
    environment = {**os.environ, "CADRUMO_LIVE_TESTS_ENABLED": "1" if live else ""}
    completed = ensure_text_completed_process(
        run_audited_process(
            [
                sys.executable,
                "-m",
                "pytest",
                "-p",
                "no:cacheprovider",
                "-c",
                str(package / "pytest.ini"),
                f"--junitxml={report}",
                *args,
                str(package / "test_generated.py"),
            ],
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
            check=False,
        )
    )
    assert report.is_file(), completed.stdout + completed.stderr
    outcomes: dict[str, str] = {}
    for case in ElementTree.parse(report).iter("testcase"):
        problems = [
            f"{child.tag}: {child.get('message', '')} {child.text or ''}"
            for child in case
            if child.tag in {"failure", "error", "skipped"}
        ]
        outcomes[str(case.get("name"))] = "passed" if not problems else "\n".join(problems)
    return outcomes


@pytest.fixture(scope="module")
def guarded_package(tmp_path_factory: pytest.TempPathFactory) -> Path:
    package = tmp_path_factory.mktemp("network-guard")
    (package / "pytest.ini").write_text(_INI, encoding="utf-8")
    (package / "conftest.py").write_text(_CONFTEST, encoding="utf-8")
    (package / "test_generated.py").write_text(textwrap.dedent(_MODULE), encoding="utf-8")
    return package


@pytest.fixture(scope="module")
def without_opt_in(guarded_package: Path) -> Mapping[str, str]:
    return _nested_run(guarded_package, guarded_package / "without-opt-in.xml", live=False)


@pytest.fixture(scope="module")
def with_opt_in(guarded_package: Path) -> Mapping[str, str]:
    return _nested_run(guarded_package, guarded_package / "with-opt-in.xml", "-k", "live or ordinary_test", live=True)


def _guard_failure(outcome: str, host: str, barrier: str) -> None:
    assert outcome != "passed", "the guarded test must fail"
    assert "network guard: this test reached non-loopback host(s)" in outcome, outcome
    assert f"{host} ({barrier})" in outcome, outcome


def test_this_suite_runs_under_the_armed_guard() -> None:
    assert network_guard_armed()
    assert os.environ[PROXY_URL_VARIABLE] == GUARD.proxy_url
    assert Settings().cadrumo_proxy_url == GUARD.proxy_url
    assert is_loopback_host("127.0.0.1")
    assert not is_loopback_host(_SEDE_HOST)


def test_a_browser_navigation_to_the_sede_fails_the_test_naming_the_host(without_opt_in: Mapping[str, str]) -> None:
    _guard_failure(without_opt_in["test_sede_navigation"], _SEDE_HOST, "browser proxy")


def test_data_and_loopback_pages_and_loopback_sockets_pass(without_opt_in: Mapping[str, str]) -> None:
    assert without_opt_in["test_data_and_loopback"] == "passed"
    assert without_opt_in["test_ordinary_test_is_guarded"] == "passed"


def test_a_non_loopback_socket_is_refused_and_fails_the_test(without_opt_in: Mapping[str, str]) -> None:
    _guard_failure(without_opt_in["test_non_loopback_socket"], "192.0.2.1", "socket.connect")


def test_a_worker_started_with_the_relayed_environment_cannot_leave_through_its_browser(
    without_opt_in: Mapping[str, str],
) -> None:
    _guard_failure(without_opt_in["test_worker_environment"], _SEDE_HOST, "browser proxy")


def test_a_live_test_without_the_opt_in_is_refused(without_opt_in: Mapping[str, str]) -> None:
    outcome = without_opt_in["test_live"]
    assert outcome != "passed"
    assert "requires CADRUMO_LIVE_TESTS_ENABLED=1" in outcome, outcome


def test_the_opt_in_disarms_only_the_live_test(with_opt_in: Mapping[str, str]) -> None:
    assert with_opt_in == {"test_ordinary_test_is_guarded": "passed", "test_live": "passed"}
