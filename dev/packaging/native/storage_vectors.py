"""Independent conformance vectors for Python and native storage resolvers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import NamedTuple

from cadrumo.core.storage_environment import STORAGE_ROOT, StorageMode, StoragePlatform, StorageRootRefusal


class StorageRootVector(NamedTuple):
    """One conformance case every storage root resolver must reproduce.

    ``environment`` is the full variable map; ``known_folder`` is the value a
    Windows resolver reads from ``FOLDERID_LocalAppData`` instead of the
    environment (``None`` when that lookup fails). Exactly one of
    ``expected_root`` and ``refusal`` is set.
    """

    name: str
    platform: StoragePlatform
    mode: StorageMode
    environment: tuple[tuple[str, str], ...]
    checkout: str | None
    known_folder: str | None
    channel: str
    expected_root: str | None
    refusal: StorageRootRefusal | None

    def as_contract(self) -> dict[str, object]:
        """Project the vector onto the JSON shape the native contract carries."""
        return {
            "name": self.name,
            "platform": self.platform.value,
            "mode": self.mode.value,
            "environment": dict(self.environment),
            "checkout": self.checkout,
            "known_folder": self.known_folder,
            "channel": self.channel,
            "expected_root": self.expected_root,
            "refusal": None if self.refusal is None else self.refusal.value,
        }


_WINDOWS_BASE = "C:\\Users\\ada\\AppData\\Local"
_WINDOWS_CHECKOUT = "C:\\src\\checkout"
_POSIX_CHECKOUT = "/src/checkout"


def _vector(
    name: str,
    platform: StoragePlatform,
    mode: StorageMode,
    environment: Mapping[str, str],
    *,
    known_folder: str | None = None,
    checkout: str | None = None,
    channel: str = "stable",
    root: str | None = None,
    refusal: StorageRootRefusal | None = None,
) -> StorageRootVector:
    return StorageRootVector(
        name=name,
        platform=platform,
        mode=mode,
        environment=tuple(sorted(environment.items())),
        checkout=checkout,
        known_folder=known_folder,
        channel=channel,
        expected_root=root,
        refusal=refusal,
    )


def storage_root_vectors() -> tuple[StorageRootVector, ...]:
    """Return the authored conformance vectors for every storage root resolver.

    Expected roots and refusals are written out by hand, independently of the
    resolver, so replaying them tests the resolver rather than echoing it. The
    native contract generator projects them through
    :meth:`StorageRootVector.as_contract`; the Python and Rust resolvers replay them.
    """
    windows, linux, macos = (StoragePlatform.WINDOWS, StoragePlatform.LINUX, StoragePlatform.MACOS)
    installed, development = (StorageMode.INSTALLED, StorageMode.DEVELOPMENT)
    local, shared = (STORAGE_ROOT.variable, STORAGE_ROOT.development_variable)
    base = {"LOCALAPPDATA": _WINDOWS_BASE}
    no_base = StorageRootRefusal.INSTALLED_BASE_UNAVAILABLE
    relative = StorageRootRefusal.RELATIVE_OVERRIDE_INSTALLED
    return (
        _vector(
            "windows-installed-default",
            windows,
            installed,
            base,
            known_folder=_WINDOWS_BASE,
            root="C:\\Users\\ada\\AppData\\Local\\cadrumo",
        ),
        _vector(
            "windows-installed-preview",
            windows,
            installed,
            base,
            known_folder=_WINDOWS_BASE,
            channel="preview",
            root="C:\\Users\\ada\\AppData\\Local\\cadrumo-preview",
        ),
        _vector("windows-installed-base-missing", windows, installed, {}, refusal=no_base),
        _vector(
            "windows-installed-base-relative", windows, installed, {"LOCALAPPDATA": "AppData\\Local"}, refusal=no_base
        ),
        _vector(
            "windows-installed-absolute-override",
            windows,
            installed,
            {local: "D:\\cadrumo-data"},
            root="D:\\cadrumo-data",
        ),
        _vector(
            "windows-installed-override-wins-over-base",
            windows,
            installed,
            {**base, local: "D:\\cadrumo-data"},
            known_folder=_WINDOWS_BASE,
            root="D:\\cadrumo-data",
        ),
        _vector(
            "windows-installed-relative-override",
            windows,
            installed,
            {**base, local: "data\\storage"},
            known_folder=_WINDOWS_BASE,
            refusal=relative,
        ),
        _vector(
            "windows-installed-rooted-without-drive",
            windows,
            installed,
            {**base, local: "\\data"},
            known_folder=_WINDOWS_BASE,
            refusal=relative,
        ),
        _vector(
            "windows-installed-blank-override",
            windows,
            installed,
            {**base, local: " \t"},
            known_folder=_WINDOWS_BASE,
            root="C:\\Users\\ada\\AppData\\Local\\cadrumo",
        ),
        _vector(
            "windows-installed-ignores-shared-variable",
            windows,
            installed,
            {**base, shared: "D:\\shared"},
            known_folder=_WINDOWS_BASE,
            root="C:\\Users\\ada\\AppData\\Local\\cadrumo",
        ),
        _vector(
            "windows-installed-home-override",
            windows,
            installed,
            {**base, "USERPROFILE": "C:\\Users\\ada", local: "~\\cadrumo-data"},
            known_folder=_WINDOWS_BASE,
            root="C:\\Users\\ada\\cadrumo-data",
        ),
        _vector(
            "windows-development-default",
            windows,
            development,
            base,
            known_folder=_WINDOWS_BASE,
            checkout=_WINDOWS_CHECKOUT,
            channel="preview",
            root="C:\\src\\checkout\\var\\storage",
        ),
        _vector(
            "windows-development-relative",
            windows,
            development,
            {local: "var\\alternate"},
            checkout=_WINDOWS_CHECKOUT,
            root="C:\\src\\checkout\\var\\alternate",
        ),
        _vector(
            "windows-development-shared",
            windows,
            development,
            {shared: "D:\\shared"},
            checkout=_WINDOWS_CHECKOUT,
            root="D:\\shared",
        ),
        _vector(
            "windows-development-precedence",
            windows,
            development,
            {shared: "D:\\shared", local: "D:\\local"},
            checkout=_WINDOWS_CHECKOUT,
            root="D:\\local",
        ),
        _vector(
            "windows-development-blank-falls-through",
            windows,
            development,
            {local: " ", shared: "var\\alternate"},
            checkout=_WINDOWS_CHECKOUT,
            root="C:\\src\\checkout\\var\\alternate",
        ),
        _vector(
            "linux-installed-xdg",
            linux,
            installed,
            {"XDG_DATA_HOME": "/data/ada", "HOME": "/home/ada"},
            root="/data/ada/cadrumo",
        ),
        _vector("linux-installed-home", linux, installed, {"HOME": "/home/ada"}, root="/home/ada/.local/share/cadrumo"),
        _vector(
            "linux-installed-relative-xdg",
            linux,
            installed,
            {"XDG_DATA_HOME": "data", "HOME": "/home/ada"},
            root="/home/ada/.local/share/cadrumo",
        ),
        _vector(
            "linux-installed-preview",
            linux,
            installed,
            {"HOME": "/home/ada"},
            channel="preview",
            root="/home/ada/.local/share/cadrumo-preview",
        ),
        _vector("linux-installed-base-missing", linux, installed, {}, refusal=no_base),
        _vector("linux-installed-relative-home", linux, installed, {"HOME": "home/ada"}, refusal=no_base),
        _vector(
            "linux-installed-relative-override",
            linux,
            installed,
            {"HOME": "/home/ada", local: "data"},
            refusal=relative,
        ),
        _vector("linux-installed-absolute-override", linux, installed, {local: "/srv/cadrumo"}, root="/srv/cadrumo"),
        _vector(
            "linux-installed-home-override",
            linux,
            installed,
            {"HOME": "/home/ada", local: "~/data"},
            root="/home/ada/data",
        ),
        _vector(
            "linux-development-default",
            linux,
            development,
            {"HOME": "/home/ada"},
            checkout=_POSIX_CHECKOUT,
            root="/src/checkout/var/storage",
        ),
        _vector(
            "macos-installed-default",
            macos,
            installed,
            {"HOME": "/Users/ada"},
            root="/Users/ada/Library/Application Support/cadrumo",
        ),
        _vector(
            "macos-installed-ignores-xdg",
            macos,
            installed,
            {"HOME": "/Users/ada", "XDG_DATA_HOME": "/x"},
            root="/Users/ada/Library/Application Support/cadrumo",
        ),
        _vector("macos-installed-base-missing", macos, installed, {"XDG_DATA_HOME": "/x"}, refusal=no_base),
        _vector(
            "macos-development-default",
            macos,
            development,
            {"HOME": "/Users/ada"},
            checkout=_POSIX_CHECKOUT,
            root="/src/checkout/var/storage",
        ),
    )
