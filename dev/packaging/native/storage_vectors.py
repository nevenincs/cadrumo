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
    invalid_environment: tuple[str, ...] = ()
    invalid_checkout: bool = False
    invalid_known_folder: bool = False

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
            "invalid_environment": list(self.invalid_environment),
            "invalid_checkout": self.invalid_checkout,
            "invalid_known_folder": self.invalid_known_folder,
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
    invalid_environment: tuple[str, ...] = (),
    invalid_checkout: bool = False,
    invalid_known_folder: bool = False,
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
        invalid_environment=invalid_environment,
        invalid_checkout=invalid_checkout,
        invalid_known_folder=invalid_known_folder,
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
        *_path_input_vectors(),
    )


INVALID_NATIVE_PATH_BYTES = (0xFF,)
INVALID_NATIVE_PATH_UTF16 = (0xD800,)


def invalid_native_path_value(platform: StoragePlatform) -> str:
    """Independent native-input fixture encoding; never replacement decoding."""
    if platform is StoragePlatform.WINDOWS:
        return b"".join(value.to_bytes(2, "little") for value in INVALID_NATIVE_PATH_UTF16).decode(
            "utf-16-le", "surrogatepass"
        )
    return bytes(INVALID_NATIVE_PATH_BYTES).decode("utf-8", "surrogateescape")


def _path_input_vectors() -> tuple[StorageRootVector, ...]:
    """Authored Unicode/normalization/tilde/precedence expectations, independent of the resolver."""
    cases: list[StorageRootVector] = []
    local, shared = STORAGE_ROOT.precedence
    invalid = StorageRootRefusal.INVALID_PATH_INPUT
    non_absolute = StorageRootRefusal.NON_ABSOLUTE_PIN
    for platform in StoragePlatform:
        windows = platform is StoragePlatform.WINDOWS
        checkout = _WINDOWS_CHECKOUT if windows else _POSIX_CHECKOUT
        root = "D:\\datos con ñ" if windows else "/datos con ñ"
        dotted = "D:\\unused\\..\\datos con ñ\\." if windows else "/unused/../datos con ñ/."
        home_variable = "USERPROFILE" if windows else "HOME"
        home = "C:\\Users\\ada" if windows else "/home/ada"
        prefix = platform.value
        cases.extend(
            (
                _vector(f"{prefix}-absolute-normalized", platform, StorageMode.INSTALLED, {local: dotted}, root=root),
                _vector(
                    f"{prefix}-relative-normalized",
                    platform,
                    StorageMode.DEVELOPMENT,
                    {local: "unused/../state"},
                    checkout=checkout,
                    root=checkout + ("\\state" if windows else "/state"),
                ),
                _vector(
                    f"{prefix}-invalid-selected",
                    platform,
                    StorageMode.DEVELOPMENT,
                    {shared: root},
                    checkout=checkout,
                    invalid_environment=(local,),
                    refusal=invalid,
                ),
                _vector(
                    f"{prefix}-invalid-effective-lower",
                    platform,
                    StorageMode.DEVELOPMENT,
                    {local: " "},
                    checkout=checkout,
                    invalid_environment=(shared,),
                    refusal=invalid,
                ),
                _vector(
                    f"{prefix}-valid-higher-ignores-invalid-lower",
                    platform,
                    StorageMode.DEVELOPMENT,
                    {local: root},
                    checkout=checkout,
                    invalid_environment=(shared,),
                    root=root,
                ),
                _vector(
                    f"{prefix}-installed-ignores-invalid-development",
                    platform,
                    StorageMode.INSTALLED,
                    {local: root},
                    invalid_environment=(shared,),
                    root=root,
                ),
                _vector(
                    f"{prefix}-invalid-home",
                    platform,
                    StorageMode.INSTALLED,
                    {local: "~/state"},
                    invalid_environment=(home_variable,),
                    refusal=invalid,
                ),
                _vector(
                    f"{prefix}-relative-home",
                    platform,
                    StorageMode.INSTALLED,
                    {local: "~/state", home_variable: "relative"},
                    refusal=StorageRootRefusal.HOME_UNAVAILABLE,
                ),
                _vector(
                    f"{prefix}-named-user-refused",
                    platform,
                    StorageMode.INSTALLED,
                    {local: "~ada/state", home_variable: home},
                    refusal=invalid,
                ),
                _vector(
                    f"{prefix}-home-only", platform, StorageMode.INSTALLED, {local: "~", home_variable: home}, root=home
                ),
                _vector(
                    f"{prefix}-relative-checkout",
                    platform,
                    StorageMode.DEVELOPMENT,
                    {},
                    checkout="relative",
                    refusal=non_absolute,
                ),
                _vector(
                    f"{prefix}-invalid-checkout",
                    platform,
                    StorageMode.DEVELOPMENT,
                    {},
                    checkout=checkout,
                    invalid_checkout=True,
                    refusal=invalid,
                ),
            )
        )
    cases.extend(
        (
            _vector(
                "windows-drive-relative",
                StoragePlatform.WINDOWS,
                StorageMode.DEVELOPMENT,
                {local: "C:state"},
                checkout=_WINDOWS_CHECKOUT,
                refusal=non_absolute,
            ),
            _vector(
                "windows-rooted-development",
                StoragePlatform.WINDOWS,
                StorageMode.DEVELOPMENT,
                {local: "\\state"},
                checkout=_WINDOWS_CHECKOUT,
                refusal=non_absolute,
            ),
            _vector(
                "windows-unc-normalized",
                StoragePlatform.WINDOWS,
                StorageMode.INSTALLED,
                {local: "\\\\server\\share\\unused\\..\\state"},
                root="\\\\server\\share\\state",
            ),
            _vector(
                "windows-invalid-known-folder",
                StoragePlatform.WINDOWS,
                StorageMode.INSTALLED,
                {},
                invalid_environment=("LOCALAPPDATA",),
                invalid_known_folder=True,
                refusal=invalid,
            ),
            _vector(
                "linux-invalid-effective-base",
                StoragePlatform.LINUX,
                StorageMode.INSTALLED,
                {"HOME": "/home/ada"},
                invalid_environment=("XDG_DATA_HOME",),
                refusal=invalid,
            ),
            _vector(
                "linux-valid-base-ignores-invalid-home",
                StoragePlatform.LINUX,
                StorageMode.INSTALLED,
                {"XDG_DATA_HOME": "/data"},
                invalid_environment=("HOME",),
                root="/data/cadrumo",
            ),
            _vector(
                "macos-invalid-base",
                StoragePlatform.MACOS,
                StorageMode.INSTALLED,
                {},
                invalid_environment=("HOME",),
                refusal=invalid,
            ),
            _vector(
                "linux-tilde-backslash-literal",
                StoragePlatform.LINUX,
                StorageMode.DEVELOPMENT,
                {local: "~\\state", "HOME": "/home/ada"},
                checkout=_POSIX_CHECKOUT,
                root="/src/checkout/~\\state",
            ),
            _vector(
                "linux-backslash-literal",
                StoragePlatform.LINUX,
                StorageMode.INSTALLED,
                {local: "/data\\state"},
                root="/data\\state",
            ),
            _vector(
                "linux-above-root-parent",
                StoragePlatform.LINUX,
                StorageMode.INSTALLED,
                {local: "/../../state"},
                root="/state",
            ),
            _vector(
                "linux-home-repeated-separator",
                StoragePlatform.LINUX,
                StorageMode.INSTALLED,
                {local: "~//state", "HOME": "/home/ada"},
                root="/home/ada/state",
            ),
            _vector(
                "windows-home-repeated-separator",
                StoragePlatform.WINDOWS,
                StorageMode.INSTALLED,
                {local: "~//state", "USERPROFILE": "C:\\Users\\ada"},
                root="C:\\Users\\ada\\state",
            ),
            _vector(
                "windows-above-root-parent",
                StoragePlatform.WINDOWS,
                StorageMode.INSTALLED,
                {local: "D:\\..\\..\\state"},
                root="D:\\state",
            ),
        )
    )
    return tuple(cases)


class StoragePathVector(NamedTuple):
    """Host filesystem fixture rooted at a fresh absolute test directory."""

    name: str
    components: tuple[str, ...]
    directories: tuple[str, ...]
    files: tuple[str, ...]
    links: tuple[tuple[str, str], ...]
    expected_components: tuple[str, ...] | None
    refusal: StorageRootRefusal | None

    def as_contract(self) -> dict[str, object]:
        """Project fixture operations and independently authored outcomes."""
        return {
            "name": self.name,
            "components": list(self.components),
            "directories": list(self.directories),
            "files": list(self.files),
            "links": [list(link) for link in self.links],
            "expected_components": None if self.expected_components is None else list(self.expected_components),
            "refusal": None if self.refusal is None else self.refusal.value,
        }


def storage_path_vectors() -> tuple[StoragePathVector, ...]:
    """Link evidence is checked on the original and normalized paths, without creation."""
    refused = StorageRootRefusal.FILESYSTEM_PATH_REFUSED
    return (
        StoragePathVector("missing-parent-normalized", ("missing", "..", "selected"), (), (), (), ("selected",), None),
        StoragePathVector(
            "original-link-parent-refused",
            ("link", "..", "selected"),
            ("target",),
            (),
            (("link", "target"),),
            None,
            refused,
        ),
        StoragePathVector(
            "normalized-link-refused",
            ("missing", "..", "link", "child"),
            ("target",),
            (),
            (("link", "target"),),
            None,
            refused,
        ),
        StoragePathVector("dangling-link-refused", ("link", "child"), (), (), (("link", "absent"),), None, refused),
        StoragePathVector("regular-file-component-refused", ("file", "child"), (), ("file",), (), None, refused),
    )
