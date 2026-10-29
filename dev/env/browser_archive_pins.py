"""Generate and check the browser archive pins the product's browser setup trusts.

``just pin-browser-archives`` regenerates ``native/component-pins/
browser_archives.toml``. For every supported platform it asks the locked
Playwright driver which archives ``install chromium`` would download (the
driver's own ``--dry-run`` with its platform override, so nothing about the
selection is re-implemented here), downloads each archive once over HTTPS from
the declared browser hosts, and records its path, sources, size and SHA-256.
Run it after every Playwright upgrade, and review the diff: the pins are the
only content authority for the browser, so a pin is a statement that these
bytes are the ones this release ships against. The native component engine
downloads only pinned archives and refuses any byte that does not match its
pin, so a substituted archive is never extracted or launched; the pins cannot
prove the publisher's copy was genuine when it was pinned.

``--check`` downloads nothing. It compares the table with the locked driver's
listings and the declared hosts and exits non-zero on any difference; the gate
test runs it, so a Playwright upgrade without new pins fails the suite.

Exit codes follow :mod:`dev.exit_codes`: ``OK``, ``DRIFT`` when ``--check``
finds a difference, and ``FAILED`` when a download or listing fails.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Final, Literal
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, Field, PositiveInt, StringConstraints, field_validator, model_validator

from cadrumo.core.models import STRICT_FROZEN_CONFIG
from cadrumo.core.toml import parse_toml
from cadrumo.core.type_guards import is_object_list
from dev import exit_codes
from dev._paths import COMPONENT_PINS_ROOT, REPO_ROOT, prepare_temp_root
from dev.packaging.command_execution import run_command
from dev.packaging.playwright_driver import installed_playwright_driver_version

#: The only hosts the browser item's archives may be fetched from; the table names them for the engine.
BROWSER_HOSTS: Final[tuple[str, ...]] = (
    "cdn.playwright.dev",
    "playwright.download.prss.microsoft.com",
    "storage.googleapis.com",
)

#: The table's file name in the component pins folder, committed and staged under the same name.
PINS_FILE: Final = "browser_archives.toml"

#: The table the native component engine reads, beside the other component pins.
PINS_PATH: Final = COMPONENT_PINS_ROOT / PINS_FILE

#: The browser item's platform keys and the driver's own name for one representative host of each.
#: The Chromium, headless-shell and FFmpeg archives do not vary by Linux distribution or macOS release.
PLAYWRIGHT_HOST_PLATFORMS: Final[Mapping[str, str]] = {
    "win-x64": "win64",
    "linux-x64": "ubuntu24.04-x64",
    "linux-arm64": "ubuntu24.04-arm64",
    "mac-x64": "mac15",
    "mac-arm64": "mac15-arm64",
}

#: The browser item's platform keys; each names one vendor build family.
type BrowserArchivePlatform = Literal["win-x64", "linux-x64", "linux-arm64", "mac-x64", "mac-arm64"]

type BrowserBuildDirectoryName = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]*-\d+$", max_length=96)]

type _ArchivePath = Annotated[
    str, StringConstraints(pattern=r"^builds(?:/[A-Za-z0-9][A-Za-z0-9._-]*)+\.zip$", max_length=512)
]
type _ArchiveUrl = Annotated[str, StringConstraints(pattern=r"^https://[a-z0-9.-]+/\S+$", max_length=2048)]
type _Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
type _Host = Annotated[str, StringConstraints(pattern=r"^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$", max_length=253)]


class BrowserArchivePin(BaseModel):
    """One archive the installer fetches on one platform, and the exact bytes it must be.

    ``path`` is where the installer asks for the archive under its download
    host; each of ``urls`` is that path under one of the vendor's mirrors, in
    the order the installer tries them.
    """

    model_config = STRICT_FROZEN_CONFIG

    platform: BrowserArchivePlatform
    directory_name: BrowserBuildDirectoryName
    path: _ArchivePath
    urls: tuple[_ArchiveUrl, ...] = Field(min_length=1)
    download_bytes: PositiveInt
    sha256: _Sha256

    @field_validator("urls", mode="before")
    @classmethod
    def _urls_from_toml_array(cls, value: object) -> object:
        return tuple(value) if is_object_list(value) else value

    @model_validator(mode="after")
    def _validate_pin(self) -> BrowserArchivePin:
        if ".." in self.path.split("/"):
            raise ValueError("an archive path stays under the download host")
        if any(not url.endswith(f"/{self.path}") for url in self.urls):
            raise ValueError("every source of an archive serves its pinned path")
        if len(set(self.urls)) != len(self.urls):
            raise ValueError("an archive names each source once")
        return self


class BrowserArchivePins(BaseModel):
    """Every pinned archive of one Playwright driver version, across the supported platforms.

    ``hosts`` are the declared browser hosts, the only ones a download may pass
    through; the native component engine reads them from this table.
    """

    model_config = STRICT_FROZEN_CONFIG

    playwright_driver: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    hosts: tuple[_Host, ...] = Field(min_length=1)
    archives: tuple[BrowserArchivePin, ...] = Field(min_length=1)

    @field_validator("hosts", "archives", mode="before")
    @classmethod
    def _tuple_from_toml_array(cls, value: object) -> object:
        return tuple(value) if is_object_list(value) else value

    @model_validator(mode="after")
    def _validate_table(self) -> BrowserArchivePins:
        directories = [(pin.platform, pin.directory_name) for pin in self.archives]
        paths = [(pin.platform, pin.path) for pin in self.archives]
        if len(set(directories)) != len(directories) or len(set(paths)) != len(paths):
            raise ValueError("a platform pins each build directory and each path once")
        if len(set(self.hosts)) != len(self.hosts):
            raise ValueError("the table names each host once")
        return self

    def for_platform(self, platform: str) -> tuple[BrowserArchivePin, ...]:
        """Return the archives pinned for ``platform``, in table order; empty when none are."""
        return tuple(pin for pin in self.archives if pin.platform == platform)

    def covering(
        self, platform: str, driver_version: str | None, directory_names: Sequence[str]
    ) -> tuple[BrowserArchivePin, ...] | None:
        """Return ``platform``'s archives when they belong to ``driver_version`` and cover every named build.

        ``None`` means this table cannot authenticate what the installed
        driver would download: another driver version, or a build directory
        the table does not pin for this platform.
        """
        if driver_version != self.playwright_driver:
            return None
        pins = self.for_platform(platform)
        pinned = {pin.directory_name for pin in pins}
        if not pins or not set(directory_names) <= pinned:
            return None
        return pins


def load_browser_archive_pins(text: str | None = None) -> BrowserArchivePins | None:
    """Return the committed pin table, or the one ``text`` holds; ``None`` when none is committed.

    Raises:
        pydantic.ValidationError: When the table is present but malformed.
    """
    if text is None:
        if not PINS_PATH.is_file():
            return None
        text = PINS_PATH.read_text(encoding="utf-8")
    return BrowserArchivePins.model_validate(parse_toml(text))


#: A download host that cannot resolve, so the listing prints each archive's path beneath it.
_PATH_PROBE_HOST: Final = "https://pin.invalid"
_LISTING_TIMEOUT_S: Final = 60.0
_DOWNLOAD_TIMEOUT_S: Final = 120.0
_CHUNK_BYTES: Final = 1024 * 1024


@dataclass(frozen=True, slots=True)
class ListedArchive:
    """One archive the driver lists: its build directory, path and sources in the driver's order."""

    platform: str
    directory_name: str
    path: str
    urls: tuple[str, ...]


def _browser_hosts() -> tuple[str, ...]:
    """Return the hosts the browser item's archives may come from."""
    return BROWSER_HOSTS


def _driver_paths() -> tuple[Path, Path]:
    from playwright._impl._driver import compute_driver_executable

    node, cli = compute_driver_executable()
    return Path(node), Path(cli)


def locked_driver_version() -> str | None:
    """Return the version of the Playwright driver this environment has locked."""
    return installed_playwright_driver_version(_driver_paths()[1].parent / "browsers.json")


def _dry_run(host_platform: str, *, download_host: str | None) -> str:
    node, cli = _driver_paths()
    environment = {
        name: value
        for name, value in os.environ.items()
        if not name.upper().startswith(("PLAYWRIGHT_", "PW_", "NODE_", "NPM_CONFIG_"))
    }
    environment["PLAYWRIGHT_HOST_PLATFORM_OVERRIDE"] = host_platform
    if download_host is not None:
        environment["PLAYWRIGHT_DOWNLOAD_HOST"] = download_host
    with tempfile.TemporaryDirectory(prefix="browser-pins-", dir=prepare_temp_root()) as root:
        environment["PLAYWRIGHT_BROWSERS_PATH"] = root
        completed = run_command(
            [str(node), str(cli), "install", "--dry-run", "chromium"],
            cwd=REPO_ROOT,
            environment=environment,
            timeout_seconds=_LISTING_TIMEOUT_S,
            errors="replace",
        )
    if completed.returncode != 0:
        raise RuntimeError(f"the driver's dry run for {host_platform} exited {completed.returncode}")
    return completed.stdout


def parse_listing(text: str) -> dict[str, tuple[str, ...]]:
    """Return each listed build directory's download sources, primary first, in the driver's order."""
    listed: dict[str, list[str]] = {}
    directory: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        label, _, value = line.partition(":")
        value = value.strip()
        if label == "Install location":
            directory = Path(value).name
            listed.setdefault(directory, [])
        elif directory is not None and (label == "Download url" or label.startswith("Download fallback")):
            listed[directory].append(value)
        elif not line:
            directory = None
    return {name: tuple(urls) for name, urls in listed.items() if urls}


def listed_archives() -> list[ListedArchive]:
    """Ask the locked driver what ``install chromium`` downloads on every supported platform."""
    archives: list[ListedArchive] = []
    for platform, host_platform in PLAYWRIGHT_HOST_PLATFORMS.items():
        sources = parse_listing(_dry_run(host_platform, download_host=None))
        paths = parse_listing(_dry_run(host_platform, download_host=_PATH_PROBE_HOST))
        for directory, urls in sources.items():
            (probe,) = paths[directory]
            path = probe.removeprefix(f"{_PATH_PROBE_HOST}/")
            archives.append(ListedArchive(platform=platform, directory_name=directory, path=path, urls=urls))
    return archives


def check_pins(pins: BrowserArchivePins | None, listed: Sequence[ListedArchive], driver: str | None) -> list[str]:
    """Return every way the pin table differs from the driver's listings and the declared hosts."""
    if pins is None:
        return ["the pin table is missing"]
    problems: list[str] = []
    if pins.playwright_driver != driver:
        problems.append(f"pins are for driver {pins.playwright_driver}, the locked driver is {driver}")
    if pins.hosts != _browser_hosts():
        problems.append("the pinned hosts are not the declared browser hosts")
    problems.extend(_archive_pin_problems(pins, listed))
    problems.extend(_source_pin_problems(pins))
    return problems


def _archive_pin_problems(pins: BrowserArchivePins, listed: Sequence[ListedArchive]) -> list[str]:
    """Compare the complete driver archive population and each pinned source list."""
    problems: list[str] = []
    expected: dict[tuple[str, str], tuple[str, tuple[str, ...]]] = {
        (a.platform, a.directory_name): (a.path, a.urls) for a in listed
    }
    actual: dict[tuple[str, str], tuple[str, tuple[str, ...]]] = {
        (p.platform, p.directory_name): (p.path, p.urls) for p in pins.archives
    }
    for key in sorted(expected.keys() - actual.keys()):
        problems.append(f"{key[0]} {key[1]} is listed by the driver but not pinned")
    for key in sorted(actual.keys() - expected.keys()):
        problems.append(f"{key[0]} {key[1]} is pinned but not listed by the driver")
    for key in sorted(expected.keys() & actual.keys()):
        if expected[key] != actual[key]:
            problems.append(f"{key[0]} {key[1]} is pinned at another path or with other sources")
    return problems


def _source_pin_problems(pins: BrowserArchivePins) -> list[str]:
    """Report each pinned URL outside the declared browser hosts."""
    problems: list[str] = []
    declared = set(_browser_hosts())
    for pin in pins.archives:
        for url in pin.urls:
            if (urlsplit(url).hostname or "") not in declared:
                problems.append(f"{pin.platform} {pin.directory_name} names an undeclared source {url}")
    return problems


def _download(archive: ListedArchive, hosts: frozenset[str]) -> tuple[int, str]:
    """Return the size and SHA-256 of the archive as its primary source serves it."""
    url = archive.urls[0]
    with (
        httpx.Client(follow_redirects=True, trust_env=False, timeout=_DOWNLOAD_TIMEOUT_S) as client,
        client.stream("GET", url, headers={"Accept-Encoding": "identity"}) as response,
    ):
        hops = [*response.history, response]
        if any(hop.url.scheme != "https" or hop.url.host not in hosts for hop in hops):
            raise RuntimeError(f"{url} left the declared hosts")
        response.raise_for_status()
        digest = hashlib.sha256()
        size = 0
        for chunk in response.iter_raw(_CHUNK_BYTES):
            digest.update(chunk)
            size += len(chunk)
    return size, digest.hexdigest()


def render_pins(pins: BrowserArchivePins) -> str:
    """Render the table as the TOML the product reads, in a stable order."""
    lines = [
        "# Generated by `just pin-browser-archives`; do not edit by hand.",
        "# Every archive `playwright install chromium` fetches for this driver, per platform,",
        "# and the exact bytes the product's browser setup accepts for it.",
        "",
        f"playwright_driver = {json.dumps(pins.playwright_driver)}",
        "hosts = [",
        *(f"  {json.dumps(host)}," for host in pins.hosts),
        "]",
    ]
    for pin in pins.archives:
        lines += [
            "",
            "[[archives]]",
            f"platform = {json.dumps(pin.platform)}",
            f"directory_name = {json.dumps(pin.directory_name)}",
            f"path = {json.dumps(pin.path)}",
            "urls = [",
            *(f"  {json.dumps(url)}," for url in pin.urls),
            "]",
            f"download_bytes = {pin.download_bytes}",
            f"sha256 = {json.dumps(pin.sha256)}",
        ]
    return "\n".join(lines) + "\n"


def generate() -> BrowserArchivePins:
    """Download every listed archive once and return the pins that describe it."""
    driver = locked_driver_version()
    if driver is None:
        raise RuntimeError("the locked Playwright driver's version is unreadable")
    hosts = frozenset(_browser_hosts())
    pins: list[BrowserArchivePin] = []
    for archive in sorted(listed_archives(), key=lambda a: (a.platform, a.directory_name)):
        print(f"browser-pins: {archive.platform} {archive.directory_name}", file=sys.stderr, flush=True)
        size, sha256 = _download(archive, hosts)
        pins.append(
            BrowserArchivePin.model_validate(
                {
                    "platform": archive.platform,
                    "directory_name": archive.directory_name,
                    "path": archive.path,
                    "urls": archive.urls,
                    "download_bytes": size,
                    "sha256": sha256,
                }
            )
        )
    return BrowserArchivePins(playwright_driver=driver, hosts=_browser_hosts(), archives=tuple(pins))


def run_check() -> int:
    """Compare the committed table with the locked driver; return the exit code."""
    driver = locked_driver_version()
    problems = check_pins(load_browser_archive_pins(), listed_archives(), driver)
    for problem in problems:
        print(f"browser-pins: {problem}", file=sys.stderr)
    if problems:
        print("browser-pins: run 'just pin-browser-archives' and review the new pins", file=sys.stderr)
        return exit_codes.DRIFT
    return exit_codes.OK


def main(argv: Sequence[str] | None = None) -> int:
    """Generate the pin table, or with ``--check`` verify it against the locked driver."""
    parser = argparse.ArgumentParser(prog="browser_archive_pins", description=__doc__)
    parser.add_argument("--check", action="store_true", help="compare without downloading")
    arguments = parser.parse_args(argv)
    if arguments.check:
        return run_check()
    try:
        pins = generate()
    except (httpx.HTTPError, OSError, RuntimeError) as error:
        print(f"browser-pins: {error}", file=sys.stderr)
        return exit_codes.FAILED
    PINS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PINS_PATH.write_text(render_pins(pins), encoding="utf-8", newline="\n")
    print(f"browser-pins: wrote {len(pins.archives)} archives to {PINS_PATH.relative_to(REPO_ROOT)}")
    return exit_codes.OK


if __name__ == "__main__":
    sys.exit(main())
