"""The browser archives this build trusts: each one's path, sources, size and SHA-256, per platform.

Playwright publishes no content hashes for the archives its installer
downloads, and the Chrome for Testing builds carry no code signature. The
repository therefore pins every archive ``playwright install chromium`` fetches
for the bundled Playwright driver, on every platform the browser item supports,
in ``_data/dependencies/browser_archives.toml``. A development command
generates the table from the driver's own dry-run listing and one download of
each archive, and a gate refuses a table that disagrees with the locked driver.

Setup downloads only pinned archives and refuses any byte that does not match
its pin, so a substituted archive is never extracted or launched. The pins
prove the bytes are the ones this release was built against; they cannot prove
the publisher's copy was genuine when it was pinned.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, Final, Literal

from pydantic import BaseModel, Field, PositiveInt, StringConstraints, field_validator, model_validator

from ..core.errors.hierarchy import pydantic_validation_boundary
from ..core.models import STRICT_FROZEN_CONFIG
from ..core.resources.bundled_data import packaged_data
from ..core.toml import parse_toml
from ..core.type_guards import is_object_list

__all__ = [
    "BROWSER_ARCHIVE_PINS_RESOURCE",
    "BrowserArchivePin",
    "BrowserArchivePins",
    "BrowserArchivePlatform",
    "BrowserBuildDirectoryName",
    "load_browser_archive_pins",
]

#: Where the table lives under the bundled data root.
BROWSER_ARCHIVE_PINS_RESOURCE: Final = ("dependencies", "browser_archives.toml")

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
    @pydantic_validation_boundary
    def _urls_from_toml_array(cls, value: object) -> object:
        return tuple(value) if is_object_list(value) else value

    @model_validator(mode="after")
    @pydantic_validation_boundary
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
    @pydantic_validation_boundary
    def _archives_from_toml_array(cls, value: object) -> object:
        return tuple(value) if is_object_list(value) else value

    @model_validator(mode="after")
    @pydantic_validation_boundary
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

        ``None`` means this build cannot authenticate what the installed
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
    """Return the bundled pin table, or the one ``text`` holds; ``None`` when this build carries none.

    Raises:
        pydantic.ValidationError: When the table is present but malformed.
    """
    if text is None:
        resource = packaged_data(*BROWSER_ARCHIVE_PINS_RESOURCE)
        if not resource.is_file():
            return None
        text = resource.read_text(encoding="utf-8")
    return BrowserArchivePins.model_validate(parse_toml(text))
