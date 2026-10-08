"""Import-light storage root declaration shared by application and development bootstrap.

:data:`STORAGE_ROOT` is the one declaration of the storage root: its variables
and their precedence, the checkout default, the per-platform installed default,
the relative-override rule and the refusals. :data:`PROCESS_ENVIRONMENT`
declares how a child process environment is built from it. Every other module,
the native contract generator included, reads these values instead of spelling
a root variable or default.

Mode is decided by where this module lives, never by the working directory,
``sys.argv`` or a settings value: beside ``pyproject.toml`` in a source checkout
is development, anywhere else is installed. Every process that imports the same
package tree therefore gets the same answer, whichever executable started it.

The module stays import-light (standard library and the product identity only;
its records are named tuples, as in :mod:`core.product_identity`)
because development bootstrap imports it before anything else; the taxonomy
and settings owners are imported lazily by the functions that need them.
"""

from __future__ import annotations

import os
import stat
import sys
from collections.abc import Mapping
from enum import StrEnum
from functools import cache
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath
from typing import Final, NamedTuple, NoReturn

from .product_identity import PRODUCT_IDENTITY


class StorageMode(StrEnum):
    """Whether the running package is a source checkout or an installed tree."""

    DEVELOPMENT = "development"
    INSTALLED = "installed"


class StoragePlatform(StrEnum):
    """Operating-system families with a declared installed default root."""

    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"


class RelativeRootOverride(StrEnum):
    """What a relative root override means in one mode."""

    ANCHOR_AT_CHECKOUT = "anchor_at_checkout"
    REFUSE = "refuse"


class StorageRootRefusal(StrEnum):
    """Why a storage root cannot be resolved; the resolver never guesses instead."""

    RELATIVE_OVERRIDE_INSTALLED = "relative_override_installed"
    INSTALLED_BASE_UNAVAILABLE = "installed_base_unavailable"
    HOME_UNAVAILABLE = "home_unavailable"
    CHECKOUT_UNAVAILABLE = "checkout_unavailable"
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
    """How much of a received environment a child process may keep.

    ``OPERATOR`` children (CLI passthrough, desktop terminals, profile workers)
    keep allowlisted operator overrides. ``STRICT`` children (the runtime
    manager, the KDF worker) keep none and receive only the pinned set.
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
    """The storage root anchor: variables, defaults, override and refusal rules.

    The root is not a taxonomy member; every root-scoped member resolves
    beneath it. ``variable`` is the settings-owned name a native host pins.
    ``development_variable`` is the lower-precedence name honoured only in a
    checkout. Blank values are unset in every mode.
    """

    variable: str
    development_variable: str
    development_default: tuple[str, ...]
    checkout_marker: str
    checkout_module: tuple[str, ...]
    installed_defaults: tuple[InstalledDefaultRule, ...]
    product_directory: str
    stable_channel: str
    channel_separator: str
    development_relative_override: RelativeRootOverride
    installed_relative_override: RelativeRootOverride
    posix_directory_mode: int

    @property
    def precedence(self) -> tuple[str, ...]:
        """Every root variable, highest precedence first."""
        return (self.variable, self.development_variable)

    def root_variables(self, mode: StorageMode) -> tuple[str, ...]:
        """Root variables honoured in ``mode``, highest precedence first."""
        return self.precedence if mode is StorageMode.DEVELOPMENT else (self.variable,)

    def relative_override(self, mode: StorageMode) -> RelativeRootOverride:
        """Return the declared meaning of a relative root override in ``mode``."""
        if mode is StorageMode.DEVELOPMENT:
            return self.development_relative_override
        return self.installed_relative_override

    def installed_rule(self, platform: StoragePlatform) -> InstalledDefaultRule:
        """Return the installed default rule declared for ``platform``."""
        return next(rule for rule in self.installed_defaults if rule.platform is platform)

    def channel_directory(self, channel: str) -> str:
        """Name the per-channel root directory; the stable channel uses the bare product name."""
        if channel == self.stable_channel:
            return self.product_directory
        return f"{self.product_directory}{self.channel_separator}{channel}"


STORAGE_ROOT: Final[StorageRootDeclaration] = StorageRootDeclaration(
    variable="CADRUMO_LOCAL_STORAGE_ROOT",
    development_variable="CADRUMO_STORAGE_ROOT",
    development_default=("var", "storage"),
    checkout_marker="pyproject.toml",
    checkout_module=("src", PRODUCT_IDENTITY.python_package, "core", "storage_environment.py"),
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
    development_relative_override=RelativeRootOverride.ANCHOR_AT_CHECKOUT,
    installed_relative_override=RelativeRootOverride.REFUSE,
    posix_directory_mode=0o700,
)
"""The one storage root declaration. Python resolves only the stable channel:
a native package pins the root for its own channel before Python runs."""


class ProcessEnvironmentDeclaration(NamedTuple):
    """Classes of variables a launcher clears, pins or passes to a child.

    ``cleared_prefixes`` and ``cleared_names`` are removed from every child,
    as is every ``namespace_prefix`` name and every reserved settings name
    outside the product allowlist. ``temporary_variables`` are pinned to the
    child's temporary-files member beside the root variable.
    ``host_inherited`` names are set by a native host before Python starts and
    are passed through unchanged in both profiles when the parent received
    them; ``windows_host_inherited`` adds the names only the Windows host pins.
    """

    cleared_prefixes: tuple[str, ...]
    cleared_names: tuple[str, ...]
    namespace_prefix: str
    temporary_variables: tuple[str, ...]
    host_inherited: tuple[str, ...]
    windows_host_inherited: tuple[str, ...]
    inherited_fields: tuple[InheritedEnvironmentField, ...]

    def inherited_names(self, platform: StoragePlatform | None) -> tuple[str, ...]:
        """Host pins a child inherits on ``platform``."""
        if platform is StoragePlatform.WINDOWS:
            return (*self.host_inherited, *self.windows_host_inherited)
        return self.host_inherited

    def inherited_kind(self, name: str) -> InheritedEnvironmentValueKind:
        """Declared value kind, independent of the variable's spelling."""
        return next(field.kind for field in self.inherited_fields if field.name == name)


class InheritedEnvironmentValueKind(StrEnum):
    """Path-valued host pins require Unicode/absolute input; opaque values do not."""

    DIRECTORY_PATH = "directory_path"
    OPAQUE = "opaque"


class InheritedEnvironmentField(NamedTuple):
    """One declared host pin and the eligibility of its value."""

    name: str
    kind: InheritedEnvironmentValueKind


_INHERITED_FIELDS: Final[tuple[InheritedEnvironmentField, ...]] = (
    InheritedEnvironmentField("CADRUMO_AUTHORITY_ROOT", InheritedEnvironmentValueKind.DIRECTORY_PATH),
)


PROCESS_ENVIRONMENT: Final[ProcessEnvironmentDeclaration] = ProcessEnvironmentDeclaration(
    cleared_prefixes=("PYTHON", "LD_", "DYLD_"),
    cleared_names=("VIRTUAL_ENV", "CONDA_PREFIX", "CONDA_DEFAULT_ENV", "__PYVENV_LAUNCHER__"),
    namespace_prefix=PRODUCT_IDENTITY.environment_prefix,
    temporary_variables=("TEMP", "TMP", "TMPDIR"),
    host_inherited=tuple(field.name for field in _INHERITED_FIELDS),
    # The packaged pywin32 cache resolves from the pinned root through its own
    # taxonomy member, so the Windows host pins nothing beyond the shared set.
    windows_host_inherited=(),
    inherited_fields=_INHERITED_FIELDS,
)
"""The one declaration of child-process environment classes."""


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


class StorageModeEvidence(NamedTuple):
    """The mode of one package tree and, in development, its checkout."""

    mode: StorageMode
    checkout: Path | None


def detect_storage_mode(module_file: Path) -> StorageModeEvidence:
    """Classify the package tree containing ``module_file``.

    Development means ``module_file`` is the declared module path inside a
    directory that also holds the checkout marker; anything else is installed.
    """
    source = module_file.resolve()
    depth = len(STORAGE_ROOT.checkout_module)
    if len(source.parents) >= depth:
        root = source.parents[depth - 1]
        if source == root.joinpath(*STORAGE_ROOT.checkout_module) and (root / STORAGE_ROOT.checkout_marker).is_file():
            return StorageModeEvidence(StorageMode.DEVELOPMENT, root)
    return StorageModeEvidence(StorageMode.INSTALLED, None)


@cache
def storage_mode() -> StorageModeEvidence:
    """Return the mode of the package tree this process imported."""
    return detect_storage_mode(Path(__file__))


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


def configured_root_value(
    environ: Mapping[str, str], mode: StorageMode, *, platform: StoragePlatform | None = None
) -> str | None:
    """Return the highest-precedence non-blank root override honoured in ``mode``."""
    for name in STORAGE_ROOT.root_variables(mode):
        if (value := _environment_value(environ, name, platform)) is not None:
            return value
    return None


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
    home_variable = "HOME" if platform is None else STORAGE_ROOT.installed_rule(platform).home_variable
    home = _environment_value(environ, home_variable, platform)
    if home is None or not path_type(home).is_absolute():
        _refuse(
            StorageRootRefusal.HOME_UNAVAILABLE,
            f"{STORAGE_ROOT.variable} starts with '~' but {home_variable} is not an absolute path.",
        )
    return path_type(home).joinpath(*(part for part in tail.split("/") if part))


def _anchored_storage_root(
    *,
    platform: StoragePlatform | None,
    mode: StorageMode,
    environ: Mapping[str, str],
    checkout: PurePath | str | None = None,
    channel: str | None = None,
    path_type: type[PurePath] | None = None,
) -> PurePath:
    """Apply the declaration to explicit inputs; the pure resolver both runtimes mirror.

    An absolute override wins in every mode. A relative override follows the
    mode's declared rule. Without an override, development resolves the
    checkout default and installed resolves the per-user default; a checkout
    never carries a channel. Only the installed default needs a declared
    ``platform``; ``None`` resolves a checkout on any operating system.
    ``path_type`` defaults to the platform's own path syntax; a host resolver
    passes its own.
    """
    path_type = _path_type(platform) if path_type is None else path_type
    raw = configured_root_value(environ, mode, platform=platform)
    if raw is not None:
        candidate = _expand_home(raw, platform, environ, path_type)
        if candidate.is_absolute():
            return candidate
        if STORAGE_ROOT.relative_override(mode) is RelativeRootOverride.REFUSE:
            _refuse(
                StorageRootRefusal.RELATIVE_OVERRIDE_INSTALLED,
                f"{STORAGE_ROOT.variable} must be an absolute directory when Cadrumo is installed.",
            )
        if candidate.drive or candidate.root:
            _refuse(StorageRootRefusal.NON_ABSOLUTE_PIN, "A relative root override cannot replace its checkout anchor.")
        return _checkout_anchor(path_type, checkout) / candidate
    if mode is StorageMode.DEVELOPMENT:
        return _checkout_anchor(path_type, checkout).joinpath(*STORAGE_ROOT.development_default)
    return _anchored_installed_default_root(platform, environ, channel=channel, path_type=path_type)


def _checkout_anchor(path_type: type[PurePath], checkout: PurePath | str | None) -> PurePath:
    if checkout is None:
        _refuse(
            StorageRootRefusal.CHECKOUT_UNAVAILABLE,
            "A development storage root needs the source checkout that anchors it.",
        )
    anchor = path_type(_checked_path_value(str(checkout)))
    if not anchor.is_absolute():
        _refuse(StorageRootRefusal.NON_ABSOLUTE_PIN, "The source checkout anchor must be absolute.")
    return anchor


def storage_root_for(
    environ: Mapping[str, str],
    evidence: StorageModeEvidence,
    *,
    sys_platform: str | None = None,
) -> Path:
    """Resolve this host's storage root for ``evidence`` and ``environ``."""
    platform = declared_platform(sys_platform)
    resolved = _anchored_storage_root(
        platform=platform,
        mode=evidence.mode,
        environ=environ,
        checkout=evidence.checkout,
        path_type=_host_path_type(),
    )
    return normalize_storage_path(Path(resolved))


def host_installed_default_root(environ: Mapping[str, str], *, sys_platform: str | None = None) -> Path:
    """Return this host's stable-channel installed default root."""
    platform = declared_platform(sys_platform)
    return normalize_storage_path(
        Path(_anchored_installed_default_root(platform, environ, path_type=_host_path_type()))
    )


def configured_storage_root(
    *,
    environ: Mapping[str, str] | None = None,
    repository_root: Path | None = None,
) -> Path:
    """Resolve the storage root for this process.

    ``repository_root`` names a checkout explicitly, which selects development
    mode; otherwise the mode of this package tree applies.
    """
    environment = os.environ if environ is None else environ
    evidence = (
        storage_mode() if repository_root is None else StorageModeEvidence(StorageMode.DEVELOPMENT, repository_root)
    )
    return storage_root_for(environment, evidence)


def storage_root_override(value: str | Path) -> Path:
    """Validate and normalize one explicit root using this process's checkout/home evidence."""
    evidence = storage_mode()
    anchored = _anchored_storage_root(
        platform=declared_platform(),
        mode=evidence.mode,
        environ={**os.environ, STORAGE_ROOT.variable: str(value)},
        checkout=evidence.checkout,
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
    if not candidate.is_absolute() and (candidate.drive or candidate.root):
        _refuse(StorageRootRefusal.NON_ABSOLUTE_PIN, "A relative storage member cannot replace its root anchor.")
    return normalize_storage_path(candidate if candidate.is_absolute() else anchor / candidate)


def storage_directory(environment_variable: str, default: str, *, root: Path | None = None) -> Path:
    """Resolve one category override; blank values use the category default."""
    return resolve_storage_path(os.environ.get(environment_variable, "").strip() or default, root=root)


def prepare_temporary_directory() -> Path:
    """Create the controlled scratch base for callers of tempfile APIs."""
    from .storage_taxonomy import StorageCategory
    from .storage_taxonomy_locations import storage_location

    root = configured_storage_root()
    location = storage_location(StorageCategory.TEMPORARY_FILES)
    value = location.relative_path().as_posix()
    if location.settings_field is not None:
        value = _environment_value(os.environ, location.settings_field.upper(), declared_platform()) or value
    temporary = resolve_storage_path(value, root=root, received=os.environ)
    ensure_storage_root(root)
    return ensure_storage_root(temporary)


def product_env_var_names() -> frozenset[str]:
    """Return the operator overrides a product child may receive.

    The primary root variable plus the settings field of every
    operator-overridable taxonomy member; ``FIXED`` members carry no variable.
    The development root variable is honoured only in a checkout and is not a
    product control.
    """
    from .storage_taxonomy import StorageOverridePolicy
    from .storage_taxonomy_locations import STORAGE_TAXONOMY

    names = {STORAGE_ROOT.variable}
    names.update(
        location.settings_field.upper()
        for location in STORAGE_TAXONOMY.values()
        if location.override_policy is StorageOverridePolicy.OPERATOR_OVERRIDABLE and location.settings_field
    )
    return frozenset(names)


def _reserved_setting_names() -> frozenset[str]:
    from .config import Settings

    return frozenset(Settings.env_var_names())


def _cleared(name: str, *, allowed: frozenset[str], reserved: frozenset[str]) -> bool:
    declaration = PROCESS_ENVIRONMENT
    if name.startswith(declaration.cleared_prefixes) or name in declaration.cleared_names:
        return True
    return (name.startswith(declaration.namespace_prefix) or name in reserved) and name not in allowed


def child_environment(
    profile: ChildEnvironmentProfile,
    root: Path,
    *,
    received: Mapping[str, str] | None = None,
    base: Mapping[str, str] | None = None,
    sys_platform: str | None = None,
) -> dict[str, str]:
    """Build a child environment that inherits ``root`` instead of re-resolving it.

    ``base`` is the ambient set the launcher keeps (by default everything
    received); the declared classes are cleared from it. An ``OPERATOR`` child
    also keeps allowlisted overrides from ``received``; a ``STRICT`` child keeps
    none. Host-inherited pins pass unchanged in both profiles. The root and the
    temporary variables are then pinned, and the temporary directory created.
    """
    from .storage_taxonomy import StorageCategory
    from .storage_taxonomy_locations import storage_location

    resolved_root = normalize_storage_path(root)
    environment_in = os.environ if received is None else received
    platform = declared_platform(sys_platform)
    ambient = environment_in if base is None else base
    if platform is StoragePlatform.WINDOWS:
        environment_in = {name.upper(): value for name, value in environment_in.items()}
        ambient = {name.upper(): value for name, value in ambient.items()}
    product = product_env_var_names()
    allowed = product if profile is ChildEnvironmentProfile.OPERATOR else frozenset[str]()
    reserved = _reserved_setting_names()
    environment = {
        name: value for name, value in ambient.items() if not _cleared(name, allowed=allowed, reserved=reserved)
    }
    environment.update({name: value for name, value in environment_in.items() if name in allowed})
    for name in PROCESS_ENVIRONMENT.inherited_names(platform):
        if name in environment_in:
            value = environment_in[name]
            if PROCESS_ENVIRONMENT.inherited_kind(name) is InheritedEnvironmentValueKind.DIRECTORY_PATH:
                _normalized_absolute(_host_path_type()(_checked_path_value(value)))
            environment[name] = value
    temporary = storage_location(StorageCategory.TEMPORARY_FILES)
    temporary_value = temporary.relative_path().as_posix()
    if temporary.settings_field is not None and profile is ChildEnvironmentProfile.OPERATOR:
        temporary_value = (
            _environment_value(environment_in, temporary.settings_field.upper(), platform) or temporary_value
        )
    temporary_root = resolve_storage_path(
        temporary_value, root=resolved_root, received=environment_in, platform=platform
    )
    if (
        not temporary.create_explicit_directory
        and temporary_value != temporary.relative_path().as_posix()
        and not temporary_root.is_dir()
    ):
        _refuse(StorageRootRefusal.FILESYSTEM_PATH_REFUSED, "An explicit storage member must already exist.")
    ensure_storage_root(resolved_root)
    ensure_storage_root(temporary_root)
    environment[STORAGE_ROOT.variable] = str(resolved_root)
    environment.update({name: str(temporary_root) for name in PROCESS_ENVIRONMENT.temporary_variables})
    return environment


TOOL_STORAGE_LOCATIONS: Mapping[str, tuple[str, str]] = {
    "UV_CACHE_DIR": ("CADRUMO_UV_CACHE_DIR", "development/cache/uv"),
    "UV_PYTHON_INSTALL_DIR": ("CADRUMO_UV_PYTHON_DIR", "development/python"),
    "UV_TOOL_DIR": ("CADRUMO_UV_TOOL_DIR", "development/tools/uv"),
    "UV_TOOL_BIN_DIR": ("CADRUMO_UV_TOOL_BIN_DIR", "development/tools/bin"),
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


def development_tool_env_var_names() -> frozenset[str]:
    """Return the development tool refinements; ``dev/`` and the justfile use them, the product does not."""
    return frozenset(variable for variable, _default in TOOL_STORAGE_LOCATIONS.values())


def tool_storage_environment() -> dict[str, str]:
    """Bind external tool caches and bytecode to shared, overrideable storage."""
    return {
        native: str(storage_directory(variable, default))
        for native, (variable, default) in TOOL_STORAGE_LOCATIONS.items()
    }
