"""Translation rendering primitives shared across the codebase.

The application and adapter layers import :func:`tr` from here so they
can render translatable keys without reaching into the CLI entrypoints.
``python-i18n`` is initialised lazily on first call.
"""

from __future__ import annotations

import importlib.resources  # nosemgrep
import os
import re
from collections.abc import Callable, Mapping
from contextvars import ContextVar
from functools import lru_cache

import i18n
import yaml

from ..config import PROJECT_ROOT, _settings_override, load_settings
from ..errors import CoreError
from ..external_constants import DEFAULT_OUTPUT_LANGUAGE, OUTPUT_LANGUAGE_ENV_VAR, SUPPORTED_OUTPUT_LANGUAGES
from ..logging import get_logger

_log = get_logger(__name__)
_INITIALISED = False
_PLACEHOLDER_RE = re.compile(r"%\{(?P<name>[A-Za-z_][A-Za-z0-9_]*)\}")
_SURVIVING_PLACEHOLDER_RE = re.compile(r"\{(?P<name>[A-Za-z_][A-Za-z0-9_]*)\}")
_OUTPUT_LANGUAGE_CACHE_VERSION = 0

# Test-scope flag: when True, _interpolate raises UnmatchedPlaceholderError for
# any {name} token that survives substitution.  Production code leaves this False.
_I18N_STRICT_PLACEHOLDERS: ContextVar[bool] = ContextVar("aeat_i18n_strict_placeholders", default=False)


class UnmatchedPlaceholderError(CoreError):
    """Raised in strict-placeholder mode when a locale value retains a {name} token.

    Indicates that a ``tr()`` call site supplies a key whose locale value
    contains a placeholder not covered by the supplied kwargs (ORPHAN), or
    that the locale value was never interpolated at all.

    Attributes:
        key: The locale translation key that triggered the error.
        name: The placeholder name that survived substitution.
        rendered: The partially-rendered string at the time of detection.
    """

    def __init__(self, *, key: str, name: str, rendered: str) -> None:
        """Initialise with the translation key, placeholder name, and partial render.

        Args:
            key: The locale translation key that triggered the error.
            name: The placeholder name that survived substitution.
            rendered: The partially-rendered string at the time of detection.
        """
        super().__init__(f"unmatched placeholder {{{name!r}}} in locale key {key!r}: {rendered!r}")
        self.key = key
        self.name = name
        self.rendered = rendered


# Application-layer hook: set by aeat.application at startup to allow the i18n
# layer to read the active-profile output language without importing application
# modules directly. Remains None until explicitly registered.
_profile_language_resolver: Callable[[], str | None] | None = None


def register_profile_language_resolver(fn: Callable[[], str | None]) -> None:
    """Register a callback that resolves the active-profile output language.

    The application layer calls this once at startup so ``core.i18n`` can
    read profile-level language preferences without importing application
    modules directly.
    """
    global _profile_language_resolver
    _profile_language_resolver = fn


def _ensure_initialised() -> None:
    """Lazy-initialise the ``python-i18n`` backend on first call."""
    global _INITIALISED
    if _INITIALISED:
        return
    i18n.load_path.append(str(importlib.resources.files("aeat").joinpath("locales")))
    i18n.set("filename_format", "{locale}.{format}")
    i18n.set("file_format", "yml")
    i18n.set("skip_locale_root_data", True)
    _INITIALISED = True


def _normalise_supported_language(value: object) -> str | None:
    raw = str(value).lower().strip()
    if raw in SUPPORTED_OUTPUT_LANGUAGES:
        return raw
    return None


def output_language() -> str:
    """Resolve the operator-facing output language.

    An explicit ``aeat_output_language`` value on the active Settings
    (env var, ``override_settings`` block, or ``.env`` file) wins for
    one-off sessions and automation. Otherwise the active profile's
    ``output.language`` key is used. The settings default remains the
    final fallback and defaults to Spanish for a clean install.

    Returns:
        The resolved ISO 639-1 language code.
    """
    return _cached_output_language(_output_language_cache_key())


def clear_output_language_cache() -> None:
    """Invalidate cached language resolution after profile/config writes."""
    global _OUTPUT_LANGUAGE_CACHE_VERSION
    _OUTPUT_LANGUAGE_CACHE_VERSION += 1
    _cached_output_language.cache_clear()


_OUTPUT_LANGUAGE_KEY_ENV_VARS: tuple[str, ...] = (
    OUTPUT_LANGUAGE_ENV_VAR,
    "AEAT_DATABASE_URL",
    "AEAT_SECRET_STORE_BACKEND",
    "AEAT_ALLOW_UNENCRYPTED",
)


def _output_language_cache_key() -> tuple[object, ...]:
    override = _settings_override.get()
    if override is not None:
        return ("override", id(override), _OUTPUT_LANGUAGE_CACHE_VERSION)
    env_file = PROJECT_ROOT / "env" / ".env"
    try:
        env_mtime_ns = env_file.stat().st_mtime_ns
    except OSError:
        env_mtime_ns = None
    # The cache key is computed from raw ``os.environ`` plus the ``.env``
    # file mtime — the two inputs Pydantic merges into ``Settings``. The
    # prior implementation constructed a full ``Settings`` instance on
    # every ``tr()`` call purely to read four field values; a help-screen
    # render fires ~100 ``tr()`` calls, so that was ~100 Settings builds
    # (the disaster-ADR Ruling 4 fast-path regression for ``--help``).
    # Sampling the raw env vars + the ``.env`` mtime varies the key
    # whenever either input changes, so a cache miss still rebuilds
    # ``Settings`` inside ``_cached_output_language`` with the correct
    # .env+os.environ merge order. The key only needs to *change* when
    # the effective value could change; it does not need the merged value.
    # os.environ.get allowlist: the reads below compute a cache-key signature,
    # not a settings value.  Constructing a full Settings instance on every
    # tr() call is prohibitively expensive (~100 calls per --help render).
    # The variables sampled here are exactly those Pydantic-settings merges
    # from os.environ; reading them raw to detect *change* does not bypass the
    # merge order — the cache miss path still builds Settings normally.
    env_signature = tuple(os.environ.get(name) for name in _OUTPUT_LANGUAGE_KEY_ENV_VARS)
    return (
        "env",
        *env_signature,
        env_mtime_ns,
        _OUTPUT_LANGUAGE_CACHE_VERSION,
    )


@lru_cache(maxsize=128)
def _cached_output_language(_cache_key: tuple[object, ...]) -> str:
    try:
        settings = load_settings()
    except (KeyError, ValueError, AttributeError) as exc:
        _log.debug(
            "i18n: unable to load settings for output language; falling back to default (%s)",
            type(exc).__name__,
            exc_info=True,
        )
        return DEFAULT_OUTPUT_LANGUAGE
    if "aeat_output_language" in settings.model_fields_set:
        explicit = _normalise_supported_language(settings.aeat_output_language)
        if explicit is not None:
            return explicit
    profile_language = _active_profile_output_language()
    if profile_language is not None:
        return profile_language
    return _normalise_supported_language(settings.aeat_output_language) or DEFAULT_OUTPUT_LANGUAGE


def _active_profile_output_language() -> str | None:
    """Return active profile language without mutating workflow state.

    Delegates to the application-registered resolver if one has been
    provided via :func:`register_profile_language_resolver`. Falls back
    gracefully to ``None`` (settings-level language) when no resolver is
    registered or the resolver raises.
    """
    resolver = _profile_language_resolver
    if resolver is None:
        return None
    try:
        return _normalise_supported_language(resolver() or "")
    except Exception as exc:
        _log.debug(
            "i18n: unable to resolve active-profile output language; falling back to settings (%s)",
            type(exc).__name__,
            exc_info=True,
        )
        return None


def tr(translation_key: str, /, **kwargs: object) -> str:
    """Render an abstract translation key in the configured output language.

    Args:
        translation_key: The abstract namespace key to render
            (e.g., ``"cli.auth.purpose"``). Positional-only so callers
            can pass interpolation kwargs named ``key`` without
            collision.
        **kwargs: Interpolation arguments for ``python-i18n``.

    Returns:
        The translated string.

    Raises:
        UnmatchedPlaceholderError: When strict-placeholder mode is
            active and the rendered string still contains an
            un-interpolated ``{name}`` token.
    """
    if "locale" not in kwargs or kwargs["locale"] is None:
        kwargs["locale"] = output_language()
    locale = _normalise_supported_language(kwargs["locale"]) or "en"
    default = kwargs.pop("default", None)
    rendered = _lookup_translation(locale, translation_key, default=default)
    interpolation = {key: value for key, value in kwargs.items() if key not in {"locale", "default"}}
    if interpolation:
        rendered = _interpolate(translation_key, rendered, interpolation)
    if _I18N_STRICT_PLACEHOLDERS.get() and (match := _SURVIVING_PLACEHOLDER_RE.search(rendered)):
        raise UnmatchedPlaceholderError(
            key=translation_key,
            name=match.group("name"),
            rendered=rendered,
        )
    return rendered


@lru_cache(maxsize=len(SUPPORTED_OUTPUT_LANGUAGES))
def _locale_map(locale: str) -> dict[str, str]:
    resource = importlib.resources.files("aeat").joinpath("locales", f"{locale}.yml")
    with resource.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    return _flatten_translations(loaded)


def _flatten_translations(value: object, prefix: str = "") -> dict[str, str]:
    if isinstance(value, Mapping):
        flattened: dict[str, str] = {}
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            flattened.update(_flatten_translations(child, child_prefix))
        return flattened
    return {prefix: str(value)}


def _lookup_translation(locale: str, translation_key: str, *, default: object | None = None) -> str:
    fallback = str(default) if default is not None else _humanise_key(translation_key)
    try:
        rendered = _locale_map(locale).get(translation_key, fallback)
    except (OSError, yaml.YAMLError, IndexError) as exc:
        _log.debug(
            "i18n: unable to load locale %s; falling back to python-i18n (%s)",
            locale,
            type(exc).__name__,
            exc_info=True,
        )
        _ensure_initialised()
        rendered = i18n.t(translation_key, locale=locale)
    if rendered == translation_key:
        return fallback
    return rendered


def _humanise_key(translation_key: str) -> str:
    """Derive an operator-readable fallback from a dotted translation key.

    The catalogue contains scaffolded self-referencing placeholders
    where the value equals the key (e.g. ``cli.config.google.folder.help:
    cli.config.google.folder.help``). Surfacing those raw to users
    leaks internal namespaces into typer help output. When no explicit
    ``default`` is supplied, derive a sentence-cased label from the
    final segment so the help screen stays operator-readable until a
    real translation is written.
    """
    last = translation_key.rsplit(".", 1)[-1]
    stripped = last.removesuffix("_help")
    if not stripped:
        return translation_key
    return stripped.replace("_", " ").capitalize()


def _interpolate(translation_key: str, rendered: str, values: Mapping[str, object]) -> str:
    def _replace(match: re.Match[str]) -> str:
        name = match.group("name")
        if name not in values:
            return match.group(0)
        return str(values[name])

    rendered = _PLACEHOLDER_RE.sub(_replace, rendered)
    try:
        return rendered.format(**values)
    except (KeyError, IndexError, ValueError) as exc:
        _log.debug(
            "i18n: unable to interpolate locale key %s; returning partially rendered value (%s)",
            translation_key,
            type(exc).__name__,
            exc_info=True,
        )
        return rendered


__all__ = [
    "DEFAULT_OUTPUT_LANGUAGE",
    "SUPPORTED_OUTPUT_LANGUAGES",
    "UnmatchedPlaceholderError",
    "output_language",
    "register_profile_language_resolver",
    "tr",
]
