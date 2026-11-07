"""Generate and check the llama.cpp release pins the native package build stages.

This regenerates ``native/llamacpp-pins.json``, a build input read beside
``native/toolchain.json``. The package bundles the upstream ``llama-server``
program: it is staged at assembly from one pinned release archive per target
and is never provisioned on the person's machine. The pins cover the program
archive per build target only; models are never bundled. The generator reads
one upstream build tag from the publisher's release listing, downloads every
target's archive once over HTTPS from the declared hosts, and records its
address, archive format, backend, executable, size and SHA-256. A digest is
accepted only when the downloaded bytes, the size the listing states and the
digest the listing publishes all agree. Review the diff: the pins are the only
content authority for the bundled program.

Upstream tags ``vX.Y.Z`` hold no binaries; the binary releases are the numbered
build tags ``bNNNNN``. The listing is searched for the newest build tag that
publishes every archive this tool installs, or ``--tag`` names one.

Each archive is read in memory. Its executable is found by name in the member
list and must be a single regular file. Nothing is extracted or written.

``--check`` downloads nothing. It validates the committed file, its hosts
against their declared group, and that it is exactly what its renderer writes.

Exit codes follow :mod:`dev.exit_codes`: ``OK``, ``DRIFT`` when ``--check``
finds a difference, and ``FAILED`` when a listing or download fails.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import tarfile
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Annotated, Final, Literal
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, Field, PositiveInt, StringConstraints, field_validator, model_validator

from cadrumo.core.models import STRICT_FROZEN_CONFIG
from cadrumo.core.type_guards import is_object_list
from dev import exit_codes
from dev.paths import REPO_ROOT

PINS_PATH: Final = REPO_ROOT / "native" / "llamacpp-pins.json"

#: The only hosts the archives may be fetched from; the file names them for the build.
PROGRAM_HOSTS: Final[tuple[str, ...]] = ("github.com", "release-assets.githubusercontent.com")

_REPOSITORY: Final = "ggml-org/llama.cpp"
_RELEASES_API: Final = f"https://api.github.com/repos/{_REPOSITORY}/releases"
_DOWNLOAD_PREFIX: Final = f"https://github.com/{_REPOSITORY}/releases/download"
_LISTING_PAGE_SIZE: Final = 30
_TIMEOUT_S: Final = 120.0
_CHUNK_BYTES: Final = 1024 * 1024
_TAG_PATTERN: Final = r"^b[0-9]+$"
_SERVER_STEM: Final = "llama-server"

type ArchiveFormat = Literal["zip", "tar.gz"]
type Backend = Literal["vulkan", "metal", "cpu"]
#: The canonical distribution target names ``native/toolchain.json`` uses, plus the Intel macOS
#: target, which has no build preset yet but whose archive is pinned with the others.
type Target = Literal["windows-x86-64", "linux-x86-64", "linux-aarch64", "macos-arm64", "macos-x86-64"]


@dataclass(frozen=True, slots=True)
class ReleaseAsset:
    """Which release asset serves one target, its format and backend, and the executable's name."""

    template: str
    format: ArchiveFormat
    backend: Backend
    executable: str

    def name(self, tag: str) -> str:
        """Return the asset's file name in the release ``tag``."""
        return self.template.format(tag=tag)


#: The release asset each build target stages. Vulkan builds include the CPU backends; the Intel
#: macOS build has no GPU backend upstream, and the Apple silicon build carries Metal.
TARGET_ASSETS: Final[Mapping[Target, ReleaseAsset]] = {
    "windows-x86-64": ReleaseAsset("llama-{tag}-bin-win-vulkan-x64.zip", "zip", "vulkan", "llama-server.exe"),
    "linux-x86-64": ReleaseAsset("llama-{tag}-bin-ubuntu-vulkan-x64.tar.gz", "tar.gz", "vulkan", "llama-server"),
    "linux-aarch64": ReleaseAsset("llama-{tag}-bin-ubuntu-vulkan-arm64.tar.gz", "tar.gz", "vulkan", "llama-server"),
    "macos-arm64": ReleaseAsset("llama-{tag}-bin-macos-arm64.tar.gz", "tar.gz", "metal", "llama-server"),
    "macos-x86-64": ReleaseAsset("llama-{tag}-bin-macos-x64.tar.gz", "tar.gz", "cpu", "llama-server"),
}

type _Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
type _Url = Annotated[str, StringConstraints(pattern=r"^https://[a-z0-9.-]+/\S+$", max_length=2048)]
type _Relative = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*$", max_length=256)]
type _Tag = Annotated[str, StringConstraints(pattern=_TAG_PATTERN)]
type _Host = Annotated[str, StringConstraints(pattern=r"^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$", max_length=253)]


class ServerArchivePin(BaseModel):
    """One target's server archive and the exact bytes the package assembly accepts for it."""

    model_config = STRICT_FROZEN_CONFIG

    target: Target
    url: _Url
    format: ArchiveFormat
    backend: Backend
    executable: _Relative
    download_bytes: PositiveInt
    sha256: _Sha256

    @field_validator("executable")
    @classmethod
    def _executable_inside_the_archive(cls, value: str) -> str:
        if any(part in {".", ".."} for part in value.split("/")):
            raise ValueError("the executable is a plain path inside the archive")
        return value


class ServerPins(BaseModel):
    """Every pinned archive of one upstream build, and the hosts their downloads may pass."""

    model_config = STRICT_FROZEN_CONFIG

    program: Literal["llama-server"]
    repository: Literal["ggml-org/llama.cpp"]
    tag: _Tag
    hosts: tuple[_Host, ...] = Field(min_length=1)
    archives: tuple[ServerArchivePin, ...] = Field(min_length=1)

    @field_validator("hosts", "archives", mode="before")
    @classmethod
    def _tuple_from_json_array(cls, value: object) -> object:
        return tuple(value) if is_object_list(value) else value

    @model_validator(mode="after")
    def _validate_table(self) -> ServerPins:
        targets = [pin.target for pin in self.archives]
        if len(set(targets)) != len(targets):
            raise ValueError("a target pins one archive")
        if list(self.hosts) != sorted(set(self.hosts)):
            raise ValueError("the hosts are listed once each, in order")
        for pin in self.archives:
            if (urlsplit(pin.url).hostname or "") not in self.hosts:
                raise ValueError(f"{pin.target} is served from a host the file does not name")
            if not pin.url.startswith(f"{_DOWNLOAD_PREFIX}/{self.tag}/"):
                raise ValueError(f"{pin.target} is not an archive of build {self.tag}")
        return self


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    document: dict[str, object] = {}
    for key, value in pairs:
        if key in document:
            raise ValueError(f"the pin file repeats the key {key!r}")
        document[key] = value
    return document


def load_server_pins(text: str | None = None) -> ServerPins:
    """Validate the committed file, or the one ``text`` holds."""
    source = PINS_PATH.read_text(encoding="utf-8") if text is None else text
    return ServerPins.model_validate(json.loads(source, object_pairs_hook=_reject_duplicate_keys))


def render_pins(pins: ServerPins) -> str:
    """Render the file as the JSON the package build reads, in a stable order."""
    document = {
        "program": pins.program,
        "repository": pins.repository,
        "tag": pins.tag,
        "hosts": list(pins.hosts),
        "archives": [
            {
                "target": pin.target,
                "url": pin.url,
                "format": pin.format,
                "backend": pin.backend,
                "executable": pin.executable,
                "download_bytes": pin.download_bytes,
                "sha256": pin.sha256,
            }
            for pin in pins.archives
        ],
    }
    return json.dumps(document, indent=2) + "\n"


def declared_hosts() -> frozenset[str]:
    """Return the hosts the archive downloads are declared to pass through."""
    return frozenset(PROGRAM_HOSTS)


def check_pins(pins: ServerPins, rendered: str) -> list[str]:
    """Return every way the committed file differs from the declarations and the renderer."""
    problems: list[str] = []
    undeclared = sorted(set(pins.hosts) - declared_hosts())
    if undeclared:
        problems.append(f"the file names undeclared hosts {undeclared}")
    missing = sorted(set(TARGET_ASSETS) - {pin.target for pin in pins.archives})
    if missing:
        problems.append(f"no archive is pinned for {missing}")
    for pin in pins.archives:
        asset = TARGET_ASSETS[pin.target]
        if not pin.url.endswith(f"/{asset.name(pins.tag)}") or (pin.format, pin.backend) != (
            asset.format,
            asset.backend,
        ):
            problems.append(f"{pin.target} pins another asset, format or backend than this tool stages")
        if PurePosixPath(pin.executable).name != asset.executable:
            problems.append(f"{pin.target} pins an executable other than {asset.executable}")
    if render_pins(pins) != rendered:
        problems.append("the file is not what the generator renders")
    return problems


@dataclass(frozen=True, slots=True)
class _Listed:
    url: str
    size: int
    sha256: str


def _admit(response: httpx.Response, hosts: frozenset[str]) -> None:
    for hop in (*response.history, response):
        if hop.url.scheme != "https" or hop.url.host not in hosts:
            raise RuntimeError(f"a download left the declared hosts at {hop.url.host}")


def _listing(api: httpx.Client, tag: str | None) -> list[dict[str, object]]:
    if tag is not None:
        response = api.get(f"{_RELEASES_API}/tags/{tag}", headers={"Accept": "application/vnd.github+json"})
        response.raise_for_status()
        return [response.json()]
    response = api.get(
        _RELEASES_API,
        params={"per_page": _LISTING_PAGE_SIZE},
        headers={"Accept": "application/vnd.github+json"},
    )
    response.raise_for_status()
    return list(response.json())


def _listed_assets(release: Mapping[str, object]) -> dict[str, _Listed]:
    tag = str(release["tag_name"])
    assets: dict[str, _Listed] = {}
    raw = release["assets"]
    if not is_object_list(raw):
        raise RuntimeError(f"release {tag} lists no assets")
    for asset in raw:
        if not isinstance(asset, dict):
            continue
        digest = str(asset.get("digest") or "")
        if not digest.startswith("sha256:"):
            continue
        name = str(asset["name"])
        assets[name] = _Listed(url=f"{_DOWNLOAD_PREFIX}/{tag}/{name}", size=int(asset["size"]), sha256=digest[7:])
    return assets


def select_release(releases: Sequence[Mapping[str, object]]) -> tuple[str, dict[str, _Listed]]:
    """Return the newest build tag that publishes a digest for every archive this tool stages.

    Upstream marks every automated build a pre-release, so that flag is no signal; drafts are skipped.
    """
    for release in releases:
        tag = str(release.get("tag_name", ""))
        if re.fullmatch(_TAG_PATTERN, tag) is None or release.get("draft"):
            continue
        assets = _listed_assets(release)
        if all(asset.name(tag) in assets for asset in TARGET_ASSETS.values()):
            return tag, assets
    raise RuntimeError("no build tag publishes every archive this tool stages")


def executable_in(members: Mapping[str, bool], name: str, asset: str) -> str:
    """Return the one regular-file member called ``name``; ``members`` maps path to regular-file."""
    found = [path for path, regular in members.items() if regular and PurePosixPath(path).name == name]
    if len(found) != 1:
        raise RuntimeError(f"{asset} holds {len(found)} regular files called {name}, not one")
    return found[0]


def _members(content: bytes, archive_format: ArchiveFormat) -> dict[str, bool]:
    if archive_format == "zip":
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            return {info.filename: not info.is_dir() for info in archive.infolist()}
    with tarfile.open(fileobj=io.BytesIO(content), mode="r:gz") as tar:
        return {member.name.removeprefix("./"): member.isfile() for member in tar}


def verify_archive(content: bytes, listed: _Listed, asset: ReleaseAsset, name: str) -> str:
    """Check the bytes against the listing and return the executable's path inside the archive."""
    if len(content) != listed.size or hashlib.sha256(content).hexdigest() != listed.sha256:
        raise RuntimeError(f"{name} does not match the size and digest its release publishes")
    return executable_in(_members(content, asset.format), asset.executable, name)


def _fetch(client: httpx.Client, url: str, hosts: frozenset[str], visited: set[str]) -> bytes:
    parts: list[bytes] = []
    with client.stream("GET", url, headers={"Accept-Encoding": "identity"}) as response:
        _admit(response, hosts)
        for hop in (*response.history, response):
            visited.add(hop.url.host)
        response.raise_for_status()
        parts.extend(response.iter_bytes(_CHUNK_BYTES))
    return b"".join(parts)


def generate(tag: str | None) -> ServerPins:
    """Download every target's archive once and return the pins that describe it."""
    hosts = declared_hosts()
    with httpx.Client(follow_redirects=False, trust_env=False, timeout=_TIMEOUT_S) as api:
        resolved, assets = select_release(_listing(api, tag))
    visited: set[str] = set()
    archives: list[ServerArchivePin] = []
    with httpx.Client(follow_redirects=True, trust_env=False, timeout=_TIMEOUT_S) as client:
        for target, asset in sorted(TARGET_ASSETS.items()):
            name = asset.name(resolved)
            listed = assets.get(name)
            if listed is None:
                raise RuntimeError(f"build {resolved} publishes no digest for {name}")
            print(f"llamacpp-pins: {name}", file=sys.stderr, flush=True)
            executable = verify_archive(_fetch(client, listed.url, hosts, visited), listed, asset, name)
            archives.append(
                ServerArchivePin(
                    target=target,
                    url=listed.url,
                    format=asset.format,
                    backend=asset.backend,
                    executable=executable,
                    download_bytes=listed.size,
                    sha256=listed.sha256,
                )
            )
    return ServerPins(
        program="llama-server",
        repository=_REPOSITORY,
        tag=resolved,
        hosts=tuple(sorted(visited)),
        archives=tuple(archives),
    )


def run_check() -> int:
    """Validate the committed file; return the exit code."""
    rendered = PINS_PATH.read_text(encoding="utf-8")
    problems = check_pins(load_server_pins(rendered), rendered)
    for problem in problems:
        print(f"llamacpp-pins: {problem}", file=sys.stderr)
    return exit_codes.DRIFT if problems else exit_codes.OK


def _write_pins(tag: str | None) -> None:
    pins = generate(tag)
    PINS_PATH.write_text(render_pins(pins), encoding="utf-8", newline="\n")
    print(f"llamacpp-pins: wrote {len(pins.archives)} archives of {pins.tag} to {PINS_PATH.relative_to(REPO_ROOT)}")


def main(argv: Sequence[str] | None = None) -> int:
    """Generate the llama.cpp pin file, or with ``--check`` validate the committed one."""
    parser = argparse.ArgumentParser(prog="llamacpp_pins", description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate without downloading")
    parser.add_argument("--tag", help="the build tag to pin, such as b12184 (default: the newest complete build)")
    arguments = parser.parse_args(argv)
    if arguments.check:
        return run_check()
    try:
        _write_pins(arguments.tag)
    except (httpx.HTTPError, OSError, RuntimeError, ValueError, tarfile.TarError, zipfile.BadZipFile) as error:
        print(f"llamacpp-pins: {error}", file=sys.stderr)
        return exit_codes.FAILED
    return exit_codes.OK


if __name__ == "__main__":
    sys.exit(main())
