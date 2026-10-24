"""Generate and check the local AI program pins the product's component engine trusts.

``just pin-local-ai`` regenerates ``src/cadrumo/_data/dependencies/
local_ai_program.toml``. It reads one Ollama release from the publisher's
release listing, downloads every platform's official standalone archive once
over HTTPS from the declared model-runtime hosts, and records its address,
archive format, executable, size and SHA-256. A digest is accepted only when
the downloaded bytes, the size the listing states and the digest the listing
publishes all agree. Review the diff: the pins are the only content authority
for the program, so a pin is a statement that these bytes are the ones this
release ships against.

Where the format allows it without a decompressor outside the standard
library, the executable named for a platform is read from the archive itself:
a ZIP's central directory and a gzip tar's member list. A zstd tar's layout is
the publisher's documented one (``bin/ollama``); the engine still refuses an
installed archive that does not contain its pinned executable.

``--check`` downloads nothing. It validates the committed table, its hosts
against the declared group, and that it is exactly what the renderer writes.

Exit codes follow :mod:`dev.exit_codes`: ``OK``, ``DRIFT`` when ``--check``
finds a difference, and ``FAILED`` when a listing or download fails.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import tarfile
import zipfile
from collections.abc import Buffer, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Annotated, Final, Literal, override
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, Field, PositiveInt, StringConstraints, field_validator, model_validator

from cadrumo.core.external_constants import load_external_constants
from cadrumo.core.models import STRICT_FROZEN_CONFIG
from cadrumo.core.toml import parse_toml
from cadrumo.core.type_guards import is_object_list
from dev import exit_codes
from dev._paths import REPO_ROOT

PINS_PATH: Final = REPO_ROOT / "src" / "cadrumo" / "_data" / "dependencies" / "local_ai_program.toml"

#: The declared host group the program archives are fetched from.
HOST_GROUP: Final = "model_runtime"

_RELEASES_API: Final = "https://api.github.com/repos/ollama/ollama/releases"
_DOWNLOAD_PREFIX: Final = "https://github.com/ollama/ollama/releases/download"
_TIMEOUT_S: Final = 120.0
_CHUNK_BYTES: Final = 1024 * 1024

type ArchiveFormat = Literal["zip", "tar.gz", "tar.zst"]
type Platform = Literal["win-x64", "linux-x64", "linux-arm64", "mac-x64", "mac-arm64"]


@dataclass(frozen=True, slots=True)
class ReleaseAsset:
    """Which release asset serves one platform, its format, and the executable inside it."""

    name: str
    format: ArchiveFormat
    executable: str


#: The component engine's platform keys (the browser item's) and the release asset each installs.
#: The macOS archive is universal, so both macOS platforms install the same bytes.
PLATFORM_ASSETS: Final[Mapping[Platform, ReleaseAsset]] = {
    "win-x64": ReleaseAsset("ollama-windows-amd64.zip", "zip", "ollama.exe"),
    "linux-x64": ReleaseAsset("ollama-linux-amd64.tar.zst", "tar.zst", "bin/ollama"),
    "linux-arm64": ReleaseAsset("ollama-linux-arm64.tar.zst", "tar.zst", "bin/ollama"),
    "mac-x64": ReleaseAsset("ollama-darwin.tgz", "tar.gz", "ollama"),
    "mac-arm64": ReleaseAsset("ollama-darwin.tgz", "tar.gz", "ollama"),
}

type _Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
type _Url = Annotated[str, StringConstraints(pattern=r"^https://[a-z0-9.-]+/\S+$", max_length=2048)]
type _Relative = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*$", max_length=256)]
type _Version = Annotated[str, StringConstraints(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")]
type _Host = Annotated[str, StringConstraints(pattern=r"^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$", max_length=253)]


class ProgramArchivePin(BaseModel):
    """One platform's program archive and the exact bytes the engine accepts for it."""

    model_config = STRICT_FROZEN_CONFIG

    platform: Platform
    url: _Url
    format: ArchiveFormat
    executable: _Relative
    download_bytes: PositiveInt
    sha256: _Sha256

    @field_validator("executable")
    @classmethod
    def _executable_inside_the_archive(cls, value: str) -> str:
        if any(part in {".", ".."} for part in value.split("/")):
            raise ValueError("the executable is a plain path inside the archive")
        return value


class ProgramPins(BaseModel):
    """Every pinned archive of one program version, and the hosts their downloads may pass."""

    model_config = STRICT_FROZEN_CONFIG

    program: Literal["ollama"]
    version: _Version
    hosts: tuple[_Host, ...] = Field(min_length=1)
    archives: tuple[ProgramArchivePin, ...] = Field(min_length=1)

    @field_validator("hosts", "archives", mode="before")
    @classmethod
    def _tuple_from_toml_array(cls, value: object) -> object:
        return tuple(value) if is_object_list(value) else value

    @model_validator(mode="after")
    def _validate_table(self) -> ProgramPins:
        platforms = [pin.platform for pin in self.archives]
        if len(set(platforms)) != len(platforms):
            raise ValueError("a platform pins one archive")
        if list(self.hosts) != sorted(set(self.hosts)):
            raise ValueError("the hosts are listed once each, in order")
        for pin in self.archives:
            if (urlsplit(pin.url).hostname or "") not in self.hosts:
                raise ValueError(f"{pin.platform} is served from a host the table does not name")
            if not pin.url.startswith(f"{_DOWNLOAD_PREFIX}/v{self.version}/"):
                raise ValueError(f"{pin.platform} is not an archive of version {self.version}")
        return self


def load_program_pins(text: str | None = None) -> ProgramPins:
    """Validate the committed table, or the one ``text`` holds."""
    return ProgramPins.model_validate(parse_toml(PINS_PATH.read_text(encoding="utf-8") if text is None else text))


def render_pins(pins: ProgramPins) -> str:
    """Render the table as the TOML the engine reads, in a stable order."""
    lines = [
        "# Generated by `just pin-local-ai`; do not edit by hand.",
        "# The local AI program's official standalone archive per platform, and the exact",
        "# bytes the component engine accepts for it.",
        "",
        f"program = {json.dumps(pins.program)}",
        f"version = {json.dumps(pins.version)}",
        "hosts = [",
        *(f"  {json.dumps(host)}," for host in pins.hosts),
        "]",
    ]
    for pin in pins.archives:
        lines += [
            "",
            "[[archives]]",
            f"platform = {json.dumps(pin.platform)}",
            f"url = {json.dumps(pin.url)}",
            f"format = {json.dumps(pin.format)}",
            f"executable = {json.dumps(pin.executable)}",
            f"download_bytes = {pin.download_bytes}",
            f"sha256 = {json.dumps(pin.sha256)}",
        ]
    return "\n".join(lines) + "\n"


def declared_hosts() -> frozenset[str]:
    """Return the hosts the program's downloads are declared to pass through."""
    return frozenset(load_external_constants().dependency_hosts.hosts_for(HOST_GROUP))


def check_pins(pins: ProgramPins, rendered: str) -> list[str]:
    """Return every way the committed table differs from the declarations and the renderer."""
    problems: list[str] = []
    undeclared = sorted(set(pins.hosts) - declared_hosts())
    if undeclared:
        problems.append(f"the table names undeclared hosts {undeclared}")
    missing = sorted(set(PLATFORM_ASSETS) - {pin.platform for pin in pins.archives})
    if missing:
        problems.append(f"no archive is pinned for {missing}")
    for pin in pins.archives:
        asset = PLATFORM_ASSETS[pin.platform]
        if not pin.url.endswith(f"/{asset.name}") or (pin.format, pin.executable) != (asset.format, asset.executable):
            problems.append(f"{pin.platform} pins another asset, format or executable than this tool installs")
    if render_pins(pins) != rendered:
        problems.append("the table is not what the generator renders")
    return problems


class _Client:
    """An HTTPS client that follows redirects only through the declared hosts and records them."""

    def __init__(self, hosts: frozenset[str]) -> None:
        self._client = httpx.Client(follow_redirects=True, trust_env=False, timeout=_TIMEOUT_S)
        self._hosts = hosts
        self.visited: set[str] = set()

    def close(self) -> None:
        self._client.close()

    def _admit(self, response: httpx.Response) -> None:
        for hop in (*response.history, response):
            if hop.url.scheme != "https" or hop.url.host not in self._hosts:
                raise RuntimeError(f"a download left the declared hosts at {hop.url.host}")
            self.visited.add(hop.url.host)

    def stream(self, url: str, sink: Callable[[bytes], None], headers: Mapping[str, str] | None = None) -> None:
        with self._client.stream("GET", url, headers={"Accept-Encoding": "identity", **(headers or {})}) as response:
            self._admit(response)
            response.raise_for_status()
            for chunk in response.iter_raw(_CHUNK_BYTES):
                sink(chunk)

    def fetch(self, url: str, headers: Mapping[str, str]) -> bytes:
        parts: list[bytes] = []
        self.stream(url, parts.append, headers)
        return b"".join(parts)


class _RangeFile(io.RawIOBase):
    """A read-only, seekable view of a remote file through HTTP range requests."""

    def __init__(self, client: _Client, url: str, size: int) -> None:
        super().__init__()
        self._client = client
        self._url = url
        self._size = size
        self._position = 0

    @override
    def readable(self) -> bool:
        return True

    @override
    def seekable(self) -> bool:
        return True

    @override
    def tell(self) -> int:
        return self._position

    @override
    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        base = {io.SEEK_SET: 0, io.SEEK_CUR: self._position, io.SEEK_END: self._size}[whence]
        self._position = max(0, base + offset)
        return self._position

    @override
    def readinto(self, buffer: Buffer) -> int:
        view = memoryview(buffer).cast("B")
        end = min(self._size, self._position + len(view))
        if end <= self._position:
            return 0
        data = self._client.fetch(self._url, {"Range": f"bytes={self._position}-{end - 1}"})
        if len(data) != end - self._position:
            raise RuntimeError("a range request answered another length")
        view[: len(data)] = data
        self._position = end
        return len(data)


@dataclass(frozen=True, slots=True)
class _Listed:
    url: str
    size: int
    sha256: str


def _release(client: httpx.Client, version: str | None) -> tuple[str, dict[str, _Listed]]:
    endpoint = f"{_RELEASES_API}/latest" if version is None else f"{_RELEASES_API}/tags/v{version.removeprefix('v')}"
    response = client.get(endpoint, headers={"Accept": "application/vnd.github+json"})
    response.raise_for_status()
    document = response.json()
    tag = str(document["tag_name"])
    assets: dict[str, _Listed] = {}
    for asset in document["assets"]:
        digest = str(asset.get("digest") or "")
        if not digest.startswith("sha256:"):
            continue
        name = str(asset["name"])
        assets[name] = _Listed(url=f"{_DOWNLOAD_PREFIX}/{tag}/{name}", size=int(asset["size"]), sha256=digest[7:])
    return tag.removeprefix("v"), assets


class _Hashing(io.RawIOBase):
    """A forward-only reader over a download that hashes and counts every byte it yields."""

    def __init__(self, chunks: list[bytes]) -> None:
        super().__init__()
        self._chunks = chunks

    @override
    def readable(self) -> bool:
        return True

    @override
    def readinto(self, buffer: Buffer) -> int:
        view = memoryview(buffer).cast("B")
        if not self._chunks:
            return 0
        chunk = self._chunks.pop(0)
        if len(chunk) > len(view):
            self._chunks.insert(0, chunk[len(view) :])
            chunk = chunk[: len(view)]
        view[: len(chunk)] = chunk
        return len(chunk)


def _download(client: _Client, listed: _Listed, asset: ReleaseAsset) -> None:
    """Hash the whole archive and, where the standard library can read it, find the executable in it."""
    digest = hashlib.sha256()
    size = 0
    members: set[str] = set()
    if asset.format == "tar.gz":
        chunks: list[bytes] = []

        def sink(chunk: bytes) -> None:
            nonlocal size
            digest.update(chunk)
            size += len(chunk)
            chunks.append(chunk)

        client.stream(listed.url, sink)
        with tarfile.open(fileobj=io.BufferedReader(_Hashing(chunks)), mode="r|gz") as archive:
            members = {member.name.removeprefix("./") for member in archive}
    else:

        def hashed(chunk: bytes) -> None:
            nonlocal size
            digest.update(chunk)
            size += len(chunk)

        client.stream(listed.url, hashed)
        if asset.format == "zip":
            with zipfile.ZipFile(io.BufferedReader(_RangeFile(client, listed.url, listed.size), 1 << 20)) as archive:
                members = set(archive.namelist())
    if size != listed.size or digest.hexdigest() != listed.sha256:
        raise RuntimeError(f"{asset.name} does not match the size and digest its release publishes")
    if asset.format != "tar.zst" and asset.executable not in members:
        raise RuntimeError(f"{asset.name} does not contain {asset.executable}")


def generate(version: str | None) -> ProgramPins:
    """Download every platform's archive once and return the pins that describe it."""
    hosts = declared_hosts()
    with httpx.Client(follow_redirects=False, trust_env=False, timeout=_TIMEOUT_S) as api:
        resolved, assets = _release(api, version)
    client = _Client(hosts)
    try:
        verified: set[str] = set()
        archives: list[ProgramArchivePin] = []
        for platform, asset in sorted(PLATFORM_ASSETS.items()):
            listed = assets.get(asset.name)
            if listed is None:
                raise RuntimeError(f"release {resolved} publishes no digest for {asset.name}")
            if asset.name not in verified:
                print(f"local-ai-pins: {asset.name}", file=sys.stderr, flush=True)
                _download(client, listed, asset)
                verified.add(asset.name)
            archives.append(
                ProgramArchivePin(
                    platform=platform,
                    url=listed.url,
                    format=asset.format,
                    executable=asset.executable,
                    download_bytes=listed.size,
                    sha256=listed.sha256,
                )
            )
        visited = tuple(sorted(client.visited))
    finally:
        client.close()
    return ProgramPins(program="ollama", version=resolved, hosts=visited, archives=tuple(archives))


def run_check() -> int:
    """Validate the committed table; return the exit code."""
    rendered = PINS_PATH.read_text(encoding="utf-8")
    problems = check_pins(load_program_pins(rendered), rendered)
    for problem in problems:
        print(f"local-ai-pins: {problem}", file=sys.stderr)
    return exit_codes.DRIFT if problems else exit_codes.OK


def main(argv: Sequence[str] | None = None) -> int:
    """Generate the program pin table, or with ``--check`` validate the committed one."""
    parser = argparse.ArgumentParser(prog="local_ai_pins", description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate without downloading")
    parser.add_argument("--version", help="the release to pin, such as 0.40.10 (default: the latest)")
    arguments = parser.parse_args(argv)
    if arguments.check:
        return run_check()
    try:
        pins = generate(arguments.version)
    except (httpx.HTTPError, OSError, RuntimeError, tarfile.TarError, zipfile.BadZipFile) as error:
        print(f"local-ai-pins: {error}", file=sys.stderr)
        return exit_codes.FAILED
    PINS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PINS_PATH.write_text(render_pins(pins), encoding="utf-8", newline="\n")
    print(f"local-ai-pins: wrote {len(pins.archives)} archives of {pins.version} to {PINS_PATH.relative_to(REPO_ROOT)}")
    return exit_codes.OK


if __name__ == "__main__":
    sys.exit(main())
