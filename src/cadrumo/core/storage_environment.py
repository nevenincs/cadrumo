"""Import-light storage root declaration shared by application and development bootstrap.

:data:`STORAGE_ROOT` is this command line's declaration of its storage root:
its variable, the per-platform per-user default and the refusals.
:func:`child_environment` builds the environment of a child this command line
starts itself. Every other Python module reads these values instead of spelling
a root variable or default.

A packaged image receives its environment from the package that built it, which
pins the root before Python starts; Python then reads that pin and never
re-resolves it. Nothing here declares what a package passes to its images.

The root is an absolute ``CADRUMO_STORAGE_ROOT`` when one is set and the
per-user, per-channel default otherwise. It is the one control over where the
product stores anything: every member beneath it sits at a fixed relative
subpath. Nothing here knows of the tree the product was built from, and nothing
reads the working directory, ``sys.argv`` or a settings value to choose a root.

The module stays import-light (standard library and the product identity only;
its records are named tuples, as in :mod:`core.product_identity`)
because development bootstrap imports it before anything else; the taxonomy
and settings owners are imported lazily by the functions that need them.
"""

from __future__ import annotations

import os
import stat
import sys
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from enum import StrEnum
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath
from typing import TYPE_CHECKING, Final, NamedTuple, NoReturn

from .product_identity import PRODUCT_IDENTITY

if TYPE_CHECKING:
    from uuid import UUID


class StoragePlatform(StrEnum):
    """Operating-system families with a declared installed default root."""

    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"


class StorageRootRefusal(StrEnum):
    """Why a storage root cannot be resolved; the resolver never guesses instead."""

    RELATIVE_OVERRIDE_INSTALLED = "relative_override_installed"
    INSTALLED_BASE_UNAVAILABLE = "installed_base_unavailable"
    HOME_UNAVAILABLE = "home_unavailable"
    UNSUPPORTED_PLATFORM = "unsupported_platform"
    NON_ABSOLUTE_PIN = "non_absolute_pin"
    INVALID_PATH_INPUT = "invalid_path_input"
    FILESYSTEM_PATH_REFUSED = "filesystem_path_refused"


class StoragePathRules(NamedTuple):
    """Host path eligibility; existing modes are never changed by preparation."""

    unicode_required: bool
    normalize_absolute: bool
    refuse_links: bool
    enforce_existing_permissions: bool


STORAGE_PATH_RULES: Final[StoragePathRules] = StoragePathRules(True, True, True, False)


class ChildEnvironmentProfile(StrEnum):
    """Which of this command line's settings a child it starts takes from its parent.

    An ``OPERATOR`` child (a profile worker) takes the parent's proxy settings,
    so the browser and network requests it starts follow the operator's route. A
    ``STRICT`` child takes none of them. Both take the parent's registry
    authority root, so parent and child read one authority generation, and both
    are pinned to the storage root the launcher resolved.
    """

    OPERATOR = "operator"
    STRICT = "strict"


class InstalledBaseCandidate(NamedTuple):
    """One environment variable that can supply the installed base directory.

    The value counts only when it is non-blank and absolute; ``subpath`` is
    joined beneath it before the product directory name.
    """

    variable: str
    subpath: tuple[str, ...] = ()


class InstalledDefaultRule(NamedTuple):
    """The ordered base lookup for one platform's installed default root."""

    platform: StoragePlatform
    candidates: tuple[InstalledBaseCandidate, ...]
    home_variable: str
    """Variable a leading ``~`` in an override expands against on this platform."""


class StorageRootDeclaration(NamedTuple):
    """The storage root anchor: its variable, per-user defaults and refusal rules.

    The root is not a taxonomy member; every root-scoped member resolves
    beneath it. ``variable`` is the settings-owned name a native host pins and
    the only root override; it must be absolute. A blank value is unset.
    """

    variable: str
    installed_defaults: tuple[InstalledDefaultRule, ...]
    product_directory: str
    stable_channel: str
    channel_separator: str
    posix_directory_mode: int

    def installed_rule(self, platform: StoragePlatform) -> InstalledDefaultRule:
        """Return the installed default rule declared for ``platform``."""
        return next(rule for rule in self.installed_defaults if rule.platform is platform)

    def channel_directory(self, channel: str) -> str:
        """Name the per-channel root directory; the stable channel uses the bare product name."""
        if channel == self.stable_channel:
            return self.product_directory
        return f"{self.product_directory}{self.channel_separator}{channel}"


STORAGE_ROOT: Final[StorageRootDeclaration] = StorageRootDeclaration(
    variable="CADRUMO_STORAGE_ROOT",
    installed_defaults=(
        InstalledDefaultRule(
            platform=StoragePlatform.WINDOWS,
            candidates=(InstalledBaseCandidate("LOCALAPPDATA"),),
            home_variable="USERPROFILE",
        ),
        InstalledDefaultRule(
            platform=StoragePlatform.LINUX,
            candidates=(
                InstalledBaseCandidate("XDG_DATA_HOME"),
                InstalledBaseCandidate("HOME", (".local", "share")),
            ),
            home_variable="HOME",
        ),
        InstalledDefaultRule(
            platform=StoragePlatform.MACOS,
            candidates=(InstalledBaseCandidate("HOME", ("Library", "Application Support")),),
            home_variable="HOME",
        ),
    ),
    product_directory=PRODUCT_IDENTITY.python_package,
    stable_channel="stable",
    channel_separator="-",
    posix_directory_mode=0o700,
)
"""The one storage root declaration. Python resolves only the stable channel:
a native package pins the root for its own channel before Python runs."""


TEMPORARY_VARIABLES: Final[tuple[str, ...]] = ("TEMP", "TMP", "TMPDIR")
"""The names Python's :mod:`tempfile` reads; a child's scratch is pinned beneath its root through them."""


TEMPORARY_FILES_SUBPATH: Final[str] = "tmp"
"""Where the temporary-files member sits beneath the root, declared here rather than in the taxonomy.

Development bootstrap prepares the temporary root before any project
dependency is installed, so this declaration must be readable without the
taxonomy's models; the taxonomy member reads its subpath from it."""


def _refuse(refusal: StorageRootRefusal, message: str) -> NoReturn:
    from .errors.hierarchy import CoreValidationError

    raise CoreValidationError(message, context={"storage_root_refusal": refusal.value})


def declared_platform(sys_platform: str | None = None) -> StoragePlatform | None:
    """Map a :data:`sys.platform` value onto a declared platform, or ``None`` when none is declared."""
    value = sys.platform if sys_platform is None else sys_platform
    if value == "win32":
        return StoragePlatform.WINDOWS
    if value == "darwin":
        return StoragePlatform.MACOS
    if value.startswith("linux"):
        return StoragePlatform.LINUX
    return None


def _path_type(platform: StoragePlatform | None) -> type[PurePath]:
    if platform is None:
        return _host_path_type()
    return PureWindowsPath if platform is StoragePlatform.WINDOWS else PurePosixPath


def _host_path_type() -> type[PurePath]:
    return PureWindowsPath if os.name == "nt" else PurePosixPath


def _checked_path_value(value: str) -> str:
    if STORAGE_PATH_RULES.unicode_required:
        try:
            value.encode("utf-8")
        except UnicodeError:
            _refuse(StorageRootRefusal.INVALID_PATH_INPUT, "Storage path input must contain valid Unicode.")
    if "\0" in value:
        _refuse(StorageRootRefusal.INVALID_PATH_INPUT, "Storage path input contains a null character.")
    return value


def _environment_value(environ: Mapping[str, str], name: str, platform: StoragePlatform | None = None) -> str | None:
    if platform is StoragePlatform.WINDOWS:
        value = next((value for key, value in environ.items() if key.upper() == name), "")
    else:
        value = environ.get(name, "")
    return _checked_path_value(value).strip() or None


def _normalized_absolute(path: PurePath) -> PurePath:
    _checked_path_value(str(path))
    if not path.is_absolute():
        _refuse(StorageRootRefusal.NON_ABSOLUTE_PIN, "Storage path must be absolute.")
    if not STORAGE_PATH_RULES.normalize_absolute:
        return path
    parts: list[str] = []
    for part in path.parts[1:]:
        if part == "..":
            if parts:
                parts.pop()
        elif part != ".":
            parts.append(part)
    return type(path)(path.anchor, *parts)


def _refuse_links(path: Path) -> None:
    if not STORAGE_PATH_RULES.refuse_links:
        return
    for component in (path, *path.parents):
        try:
            metadata = component.lstat()
        except FileNotFoundError:
            continue
        except OSError as error:
            _refuse(StorageRootRefusal.FILESYSTEM_PATH_REFUSED, str(error))
        if (
            stat.S_ISLNK(metadata.st_mode)
            or getattr(metadata, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            _refuse(StorageRootRefusal.FILESYSTEM_PATH_REFUSED, f"Storage path contains a link: {component}")
        if component != path and not stat.S_ISDIR(metadata.st_mode):
            _refuse(StorageRootRefusal.FILESYSTEM_PATH_REFUSED, f"Storage path traverses a non-directory: {component}")


def normalize_storage_path(path: Path) -> Path:
    """Validate original links, then normalize an absolute host path without cwd/effects."""
    _checked_path_value(str(path))
    if not path.is_absolute():
        _refuse(StorageRootRefusal.NON_ABSOLUTE_PIN, "A child process requires an absolute storage root pin.")
    _refuse_links(path)
    normalized = Path(_normalized_absolute(path))
    _refuse_links(normalized)
    return normalized


def _anchored_installed_default_root(
    platform: StoragePlatform | None,
    environ: Mapping[str, str],
    *,
    channel: str | None = None,
    path_type: type[PurePath] | None = None,
) -> PurePath:
    """Return the per-user installed default root, or refuse when no base or platform rule is available.

    ``path_type`` defaults to the platform's own path syntax; a host resolver
    passes its own.
    """
    if platform is None:
        _refuse(
            StorageRootRefusal.UNSUPPORTED_PLATFORM,
            "Cadrumo declares no installed storage root for this operating system; "
            f"set {STORAGE_ROOT.variable} to an absolute directory.",
        )
    path_type = _path_type(platform) if path_type is None else path_type
    rule = STORAGE_ROOT.installed_rule(platform)
    directory = STORAGE_ROOT.channel_directory(STORAGE_ROOT.stable_channel if channel is None else channel)
    for candidate in rule.candidates:
        value = _environment_value(environ, candidate.variable, platform)
        if value is not None and path_type(value).is_absolute():
            return path_type(value).joinpath(*candidate.subpath, directory)
    names = " or ".join(candidate.variable for candidate in rule.candidates)
    _refuse(
        StorageRootRefusal.INSTALLED_BASE_UNAVAILABLE,
        f"Cadrumo cannot locate the per-user data directory: {names} is not an absolute path. "
        f"Set {STORAGE_ROOT.variable} to an absolute directory.",
    )


def configured_root_value(environ: Mapping[str, str], *, platform: StoragePlatform | None = None) -> str | None:
    """Return the non-blank root override, or ``None`` when none is set."""
    return _environment_value(environ, STORAGE_ROOT.variable, platform)


def _expand_home(
    value: str,
    platform: StoragePlatform | None,
    environ: Mapping[str, str],
    path_type: type[PurePath],
) -> PurePath:
    """Expand a leading ``~`` (the current user only) against the platform home variable.

    A platform with no declared rule uses ``HOME``.
    """
    _checked_path_value(value)
    spelling = value.replace("\\", "/") if path_type is PureWindowsPath else value
    head, _separator, tail = spelling.partition("/")
    if head != "~":
        if head.startswith("~") and (path_type is PureWindowsPath or not head.startswith("~\\")):
            _refuse(StorageRootRefusal.INVALID_PATH_INPUT, "Named-user home expansion is not supported.")
        return path_type(value)
    home = _home_base(platform, environ, path_type)
    return home.joinpath(*(part for part in tail.split("/") if part))


def _home_base(platform: StoragePlatform | None, environ: Mapping[str, str], path_type: type[PurePath]) -> PurePath:
    """Resolve only the current user home and require an absolute platform path."""
    home_variable = "HOME" if platform is None else STORAGE_ROOT.installed_rule(platform).home_variable
    home = _environment_value(environ, home_variable, platform)
    if home is None or not path_type(home).is_absolute():
        _refuse(
            StorageRootRefusal.HOME_UNAVAILABLE,
            f"{STORAGE_ROOT.variable} starts with '~' but {home_variable} is not an absolute path.",
        )
    return path_type(home)


def _anchored_storage_root(
    *,
    platform: StoragePlatform | None,
    environ: Mapping[str, str],
    channel: str | None = None,
    path_type: type[PurePath] | None = None,
) -> PurePath:
    """Apply the declaration to explicit inputs; the pure resolver both runtimes mirror.

    An absolute override wins; a relative one is refused. Without an override
    the per-user default applies, which needs a declared ``platform``.
    ``path_type`` defaults to the platform's own path syntax; a host resolver
    passes its own.
    """
    path_type = _path_type(platform) if path_type is None else path_type
    raw = configured_root_value(environ, platform=platform)
    if raw is not None:
        candidate = _expand_home(raw, platform, environ, path_type)
        if not candidate.is_absolute():
            _refuse(
                StorageRootRefusal.RELATIVE_OVERRIDE_INSTALLED,
                f"{STORAGE_ROOT.variable} must be an absolute directory.",
            )
        return candidate
    return _anchored_installed_default_root(platform, environ, channel=channel, path_type=path_type)


def storage_root_for(environ: Mapping[str, str], *, sys_platform: str | None = None) -> Path:
    """Resolve this host's storage root for ``environ``."""
    resolved = _anchored_storage_root(
        platform=declared_platform(sys_platform),
        environ=environ,
        path_type=_host_path_type(),
    )
    return normalize_storage_path(Path(resolved))


def host_installed_default_root(environ: Mapping[str, str], *, sys_platform: str | None = None) -> Path:
    """Return this host's stable-channel installed default root."""
    platform = declared_platform(sys_platform)
    return normalize_storage_path(
        Path(_anchored_installed_default_root(platform, environ, path_type=_host_path_type()))
    )


def configured_storage_root(*, environ: Mapping[str, str] | None = None) -> Path:
    """Resolve the storage root for this process, or for ``environ`` when given."""
    return storage_root_for(os.environ if environ is None else environ)


def storage_root_override(value: str | Path) -> Path:
    """Validate and normalize one explicit root; a relative root is refused."""
    anchored = _anchored_storage_root(
        platform=declared_platform(),
        environ={**os.environ, STORAGE_ROOT.variable: str(value)},
        path_type=_host_path_type(),
    )
    return normalize_storage_path(Path(anchored))


def ensure_storage_root(root: Path) -> Path:
    """Create ``root`` idempotently, owner-only on POSIX.

    Windows keeps the inherited per-user ACL of the parent directory.
    """
    root = normalize_storage_path(root)
    missing: list[Path] = []
    candidate = root
    while not candidate.exists():
        missing.append(candidate)
        candidate = candidate.parent
    try:
        for directory in reversed(missing):
            directory.mkdir(mode=STORAGE_ROOT.posix_directory_mode, exist_ok=True)
        if not root.is_dir():
            _refuse(StorageRootRefusal.FILESYSTEM_PATH_REFUSED, f"Storage path is not a directory: {root}")
    except OSError as error:
        _refuse(StorageRootRefusal.FILESYSTEM_PATH_REFUSED, str(error))
    _refuse_links(root)
    return root


def resolve_storage_path(
    value: str | Path,
    *,
    root: Path | None = None,
    received: Mapping[str, str] | None = None,
    platform: StoragePlatform | None = None,
) -> Path:
    """Anchor relative storage members beneath the configured root."""
    environment = os.environ if received is None else received
    platform = declared_platform() if platform is None else platform
    candidate = Path(_expand_home(str(value), platform, environment, _host_path_type()))
    anchor = configured_storage_root() if root is None else root
    anchor = normalize_storage_path(anchor)
    refuse_unanchored_storage_member(candidate)
    return normalize_storage_path(candidate if candidate.is_absolute() else anchor / candidate)


def refuse_unanchored_storage_member(candidate: PurePath) -> None:
    r"""Refuse a member that is neither absolute nor plainly relative to its root.

    A drive-relative spelling (``C:member``) or a rooted one without a drive
    (``\member`` on Windows) names a location on some drive rather than one
    beneath the storage root, so joining it to the root would silently
    replace the root's drive or anchor instead of placing the member below it.
    """
    if not candidate.is_absolute() and (candidate.drive or candidate.root):
        _refuse(StorageRootRefusal.NON_ABSOLUTE_PIN, "A relative storage member cannot replace its root anchor.")


def storage_directory(environment_variable: str, default: str, *, root: Path | None = None) -> Path:
    """Resolve one category override; blank values use the category default."""
    return resolve_storage_path(os.environ.get(environment_variable, "").strip() or default, root=root)


def prepare_temporary_directory() -> Path:
    """Create the controlled scratch base for callers of tempfile APIs."""
    root = configured_storage_root()
    ensure_storage_root(root)
    return ensure_storage_root(root / TEMPORARY_FILES_SUBPATH)


def _own_setting_names() -> frozenset[str]:
    from .config import Settings

    return frozenset(Settings.env_var_names())


def authority_root_setting_names() -> frozenset[str]:
    """Return the setting that names this command line's registry authority root."""
    from .config import AuthorityRootSettings

    return frozenset(name.upper() for name in AuthorityRootSettings.model_fields)


def relayed_setting_names() -> frozenset[str]:
    """Return the settings an ``OPERATOR`` child takes from its parent: storage root, authority root and proxy.

    The proxy settings reach the child so the browser and network requests it starts follow the
    operator's network route; the child withholds them from its own children
    (:func:`withheld_child_settings`). The password setting is not relayed: a
    proxy password crosses a process boundary only inside the proxy address.
    """
    from .config import Settings

    proxy = Settings.proxy_env_var_names(secret_fields=False)
    return Settings.storage_env_var_names() | authority_root_setting_names() | proxy


@contextmanager
def withheld_child_settings() -> Generator[None]:
    """Remove the credential-bearing proxy settings from this process's environment for the block.

    Enter it once this process's settings already hold the values. Every child
    process inherits ``os.environ``, and a proxy address may carry a user name
    and password; the tools that need the proxy receive it explicitly
    in their own environment instead.
    """
    from .config import Settings

    names = {name for name in os.environ if name.upper() in Settings.proxy_env_var_names()}
    withheld = {name: os.environ.pop(name) for name in names}
    try:
        yield
    finally:
        for name, value in withheld.items():
            os.environ.setdefault(name, value)


def _child_relay_settings(
    profile: ChildEnvironmentProfile, environment_in: Mapping[str, str], environment: dict[str, str]
) -> None:
    """Relay only the profile's declared settings and validate authority-root spellings."""
    authority = authority_root_setting_names()
    relayed = relayed_setting_names() if profile is ChildEnvironmentProfile.OPERATOR else authority
    for name in relayed:
        if name not in environment_in:
            continue
        value = environment_in[name]
        if name in authority:
            _normalized_absolute(_host_path_type()(_checked_path_value(value)))
        environment[name] = value


def child_environment(
    profile: ChildEnvironmentProfile,
    root: Path,
    *,
    received: Mapping[str, str] | None = None,
    base: Mapping[str, str] | None = None,
    sys_platform: str | None = None,
    profile_id: str | UUID | None = None,
) -> dict[str, str]:
    """Build the environment of a child this command line starts, inheriting ``root`` instead of re-resolving it.

    ``base`` is the ambient set the launcher keeps (by default everything
    received). Every setting this command line reads, and every other name
    under its environment prefix, is removed from it. The child then takes the
    settings its profile relays from ``received``, the root and the temporary
    variables are pinned, and the temporary directory is created. A launcher
    that starts the child for one profile passes ``profile_id``, and the child
    is told that profile's folder; a received folder is never relayed.
    """
    resolved_root = normalize_storage_path(root)
    environment_in = os.environ if received is None else received
    platform = declared_platform(sys_platform)
    ambient = environment_in if base is None else base
    if platform is StoragePlatform.WINDOWS:
        environment_in = {name.upper(): value for name, value in environment_in.items()}
        ambient = {name.upper(): value for name, value in ambient.items()}
    own = _own_setting_names()
    prefix = PRODUCT_IDENTITY.environment_prefix
    environment = {name: value for name, value in ambient.items() if not (name.startswith(prefix) or name in own)}
    _child_relay_settings(profile, environment_in, environment)
    temporary_root = resolved_root / TEMPORARY_FILES_SUBPATH
    ensure_storage_root(resolved_root)
    ensure_storage_root(temporary_root)
    environment[STORAGE_ROOT.variable] = str(resolved_root)
    environment.update({name: str(temporary_root) for name in TEMPORARY_VARIABLES})
    from .profile_root_environment import profile_root_environment

    environment.update(profile_root_environment(resolved_root, profile_id))
    return environment


TOOL_STORAGE_LOCATIONS: Mapping[str, tuple[str, str]] = {
    "PIP_CACHE_DIR": ("CADRUMO_PIP_CACHE_DIR", "development/cache/pip"),
    "npm_config_cache": ("CADRUMO_NPM_CACHE_DIR", "development/cache/npm"),
    "CARGO_HOME": ("CADRUMO_CARGO_HOME", "development/cache/cargo"),
    "CARGO_TARGET_DIR": ("CADRUMO_CARGO_TARGET_DIR", "development/build/cargo"),
    "PYTHONPYCACHEPREFIX": ("CADRUMO_PYTHON_CACHE_DIR", "development/cache/pycache"),
    "XDG_CACHE_HOME": ("CADRUMO_TOOL_CACHE_DIR", "development/cache/tools"),
    "XDG_CONFIG_HOME": ("CADRUMO_TOOL_CONFIG_DIR", "development/config/tools"),
    "XDG_DATA_HOME": ("CADRUMO_TOOL_DATA_DIR", "development/data/tools"),
    "XDG_STATE_HOME": ("CADRUMO_TOOL_STATE_DIR", "development/state/tools"),
    "RUFF_CACHE_DIR": ("CADRUMO_RUFF_CACHE_DIR", "development/cache/ruff"),
    "HOMEBREW_CACHE": ("CADRUMO_HOMEBREW_CACHE_DIR", "development/cache/homebrew"),
    "HOMEBREW_LOGS": ("CADRUMO_HOMEBREW_LOGS_DIR", "development/logs/homebrew"),
    "HOMEBREW_TEMP": ("CADRUMO_HOMEBREW_TEMP_DIR", "tmp/homebrew"),
}


def tool_storage_environment() -> dict[str, str]:
    """Bind external tool caches and bytecode to shared, overrideable storage."""
    return {
        native: str(storage_directory(variable, default))
        for native, (variable, default) in TOOL_STORAGE_LOCATIONS.items()
    }
