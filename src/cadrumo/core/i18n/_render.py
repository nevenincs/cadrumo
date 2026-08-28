"""Translation rendering primitives shared across the codebase.

The application and adapter layers import :func:`tr` from here so they
can render translatable keys without reaching into the CLI entrypoints.
``python-i18n`` is initialised lazily on first call.
"""

from __future__ import annotations

import importlib.resources  # nosemgrep
import os
import re
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path
from string import Formatter
from typing import IO, TYPE_CHECKING

import i18n
import yaml

from .._config_state_root import FormerProductStateError
from ..config import _settings_override, coerce_output_language_setting, load_settings
from ..errors import CoreError
from ..external_constants import DEFAULT_OUTPUT_LANGUAGE, OUTPUT_LANGUAGE_ENV_VAR, SUPPORTED_OUTPUT_LANGUAGES
from ..logging import get_logger
from ..product_identity import PRODUCT_IDENTITY, normalise_product_identity_references

if TYPE_CHECKING:
    from ._lazy_catalogue import LazyLocaleCatalogue

_log = get_logger(__name__)
_INITIALISED = False
_PLACEHOLDER_RE = re.compile(r"%\{(?P<name>[A-Za-z_][A-Za-z0-9_]*)\}")
_FORMAT_FIELD_ROOT_RE = re.compile(r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)(?=$|[.\[])")
_FORMATTER = Formatter()
_OUTPUT_LANGUAGE_CACHE_VERSION = 0

# Test-scope flag: when True, tr raises UnmatchedPlaceholderError for any
# declared placeholder not supplied by the caller. Production leaves this False.
_I18N_STRICT_PLACEHOLDERS: ContextVar[bool] = ContextVar("cadrumo_i18n_strict_placeholders", default=False)

# Test-scope flag: when True, tr raises MissingTranslationError for a key the
# catalogue does not carry, instead of returning a humanised fallback. A caller
# supplying an explicit `default` has opted into a fallback and never raises.
# Production leaves this False so a missing string can never abort a filing.
_I18N_STRICT_MISSING_KEYS: ContextVar[bool] = ContextVar("cadrumo_i18n_strict_missing_keys", default=False)


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


class MissingTranslationError(CoreError):
    """Raised in strict-missing-key mode when a catalogue does not carry a key.

    Indicates that a ``tr()`` call site names a key absent from the locale, or
    one whose value is the key itself (the scaffold placeholder for "not
    translated yet"). Outside strict mode both cases fall back to a humanised
    label, so a missing string never aborts a filing.

    Attributes:
        key: The locale translation key that could not be resolved.
        locale: The locale whose catalogue was consulted.
    """

    def __init__(self, *, key: str, locale: str) -> None:
        """Initialise with the unresolved translation key and its locale.

        Args:
            key: The locale translation key that could not be resolved.
            locale: The locale whose catalogue was consulted.
        """
        super().__init__(
            f"locale key {key!r} is not translated in {locale!r}; "
            f"declare it in the locale catalogues and set a real translation for {locale!r}"
        )
        self.key = key
        self.locale = locale


# Application-layer hook: set by cadrumo.application at startup to allow the i18n
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
    i18n.load_path.append(str(importlib.resources.files(PRODUCT_IDENTITY.python_package).joinpath("locales")))
    i18n.set("filename_format", "{locale}.{format}")
    i18n.set("file_format", "yml")
    i18n.set("skip_locale_root_data", True)
    _INITIALISED = True


def _normalise_supported_language(value: object) -> str | None:
    language = coerce_output_language_setting(str(value))
    return language.value if language is not None else None


def output_language() -> str:
    """Resolve the operator-facing output language.

    An explicit ``cadrumo_output_language`` value on the active Settings
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


def clear_output_language_cache_for_settings_override() -> None:
    """Invalidate at an ``override_settings`` boundary the resolver does not own.

    ``override_settings`` invalidates at both of its boundaries because the
    cache keys an override block by ``id(override)`` and a GC'd block's address
    can be reused. That is right for every block an operator or a command
    opens, and wrong for exactly one: resolving the active profile's language
    scopes its own read with ``override_settings(cadrumo_active_profile=...)``,
    so the resolution invalidated the very entry it was about to store.

    The version is part of the cache key, so each resolution left the next call
    keyed to a dead version — a cache that could never serve a hit while a
    bucket session was bound. Every ``tr()`` then paid a full encrypted profile
    read and three ``Settings`` constructions, which is roughly 44 ms each on
    Windows, where a construction resolves 28 configured paths. One manager
    repaint resolves a few hundred strings, so re-wording the page after a
    language change cost around thirteen seconds.

    Suppressing the boundary only while a resolution is in flight is what
    separates the two cases: the profile-write, registration, and CLI-init
    invalidations all go through :func:`clear_output_language_cache` and are
    never suppressed, so a write that genuinely moves the language is still
    seen. The flag is a :class:`~contextvars.ContextVar`, so a resolution
    running on one task cannot silence another's boundary, and a thread that
    never resolved sees the default and invalidates normally.
    """
    if _RESOLVING_OUTPUT_LANGUAGE.get():
        return
    clear_output_language_cache()


_OUTPUT_LANGUAGE_KEY_ENV_VARS: tuple[str, ...] = (
    OUTPUT_LANGUAGE_ENV_VAR,
    "CADRUMO_DATABASE_URL",
    "CADRUMO_SECRET_STORE_BACKEND",
    "CADRUMO_ALLOW_UNENCRYPTED",
)


def _output_language_cache_key() -> tuple[object, ...]:
    override = _settings_override.get()
    if override is not None:
        return ("override", id(override), _OUTPUT_LANGUAGE_CACHE_VERSION)
    # The key is built from in-memory inputs ONLY — no filesystem call. It
    # samples the raw env vars Pydantic merges into ``Settings`` so a cache
    # miss still rebuilds ``Settings`` normally (with the correct
    # .env+os.environ merge order); the key only needs to *change* when the
    # effective value could change, never to carry the merged value itself.
    #
    # This deliberately does NOT stat ``env/.env``. An earlier revision put
    # that file's mtime in the key as a freshness probe, which cost one
    # ``stat`` syscall per ``tr()`` call — measured at 77% of all time spent
    # in ``tr()``, on a function whose own catalogue lookup is 0.4us. A
    # translated string is rendered dozens of times per TUI frame and ~100
    # times per ``--help``, so the probe dominated every rendering path in
    # the app.
    #
    # Dropping it is safe because a ``.env`` edit cannot change the effective
    # language without one of: an ``override_settings`` block (keyed above by
    # override identity, and invalidated at both boundaries), a mutation of
    # the stored profile language, or a process restart. The first two call
    # ``clear_output_language_cache`` explicitly — registration, the profile
    # repository, workflow persistence, CLI init, and language activation all
    # do — and nothing else in the app hot-reloads ``.env`` mid-process
    # either, so honouring it here alone was an inconsistency, not a feature.
    #
    # os.environ.get allowlist: these reads compute a cache-key signature, not
    # a settings value, and do not bypass the Pydantic merge order.
    env_signature = tuple(os.environ.get(name) for name in _OUTPUT_LANGUAGE_KEY_ENV_VARS)
    return (
        "env",
        *env_signature,
        _OUTPUT_LANGUAGE_CACHE_VERSION,
    )


_RESOLVING_OUTPUT_LANGUAGE: ContextVar[bool] = ContextVar("cadrumo_i18n_resolving_output_language", default=False)
"""Whether this context is inside :func:`_resolve_output_language`.

Read by :func:`clear_output_language_cache_for_settings_override` to tell a
resolution's own scoping block from every other override boundary.
"""


@lru_cache(maxsize=128)
def _cached_output_language(_cache_key: tuple[object, ...]) -> str:
    token = _RESOLVING_OUTPUT_LANGUAGE.set(True)
    try:
        return _resolve_output_language()
    finally:
        _RESOLVING_OUTPUT_LANGUAGE.reset(token)


def _resolve_output_language() -> str:
    """Resolve the language from settings and the active profile, uncached."""
    try:
        settings = load_settings()
    except (CoreError, FormerProductStateError, KeyError, ValueError, AttributeError) as exc:
        _log.debug(
            "i18n: unable to load settings for output language; falling back to default (%s)",
            type(exc).__name__,
            exc_info=True,
        )
        return DEFAULT_OUTPUT_LANGUAGE
    if "cadrumo_output_language" in settings.model_fields_set:
        explicit = _normalise_supported_language(settings.cadrumo_output_language)
        if explicit is not None:
            return explicit
    profile_language = _active_profile_output_language()
    if profile_language is not None:
        return profile_language
    return _normalise_supported_language(settings.cadrumo_output_language) or DEFAULT_OUTPUT_LANGUAGE


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
        MissingTranslationError: When strict-missing-key mode is active,
            the catalogue does not carry ``translation_key``, and no
            explicit ``default`` was supplied.
    """
    if "locale" not in kwargs or kwargs["locale"] is None:
        kwargs["locale"] = output_language()
    locale = _normalise_supported_language(kwargs["locale"]) or "en"
    default = kwargs.pop("default", None)
    looked_up = _lookup_translation(locale, translation_key, default=default)
    interpolation = {key: value for key, value in kwargs.items() if key not in {"locale", "default"}}
    if interpolation:
        interpolated, format_succeeded = _interpolate_with_status(translation_key, looked_up, interpolation)
    else:
        interpolated, format_succeeded = looked_up, True
    rendered = normalise_product_identity_references(interpolated)
    if _I18N_STRICT_PLACEHOLDERS.get():
        _enforce_strict_placeholders(
            translation_key,
            looked_up=looked_up,
            interpolated=interpolated,
            rendered=rendered,
            interpolation=interpolation,
            format_succeeded=format_succeeded,
        )
    return rendered


def _enforce_strict_placeholders(
    translation_key: str,
    *,
    looked_up: str,
    interpolated: str,
    rendered: str,
    interpolation: Mapping[str, object],
    format_succeeded: bool,
) -> None:
    """Raise when a declared placeholder survived rendering in strict mode.

    ``looked_up`` is the pre-interpolation locale value (its residual
    ``%{name}``/``{name}`` tokens define the unmatched set); ``interpolated`` is
    the post-interpolation value whose surviving format roots are inspected only
    when the format pass failed; ``rendered`` is the fully normalised value
    reported on the raised error.
    """
    unmatched_placeholders = sorted(extract_placeholders(looked_up) - interpolation.keys())
    failed_format_placeholders = sorted(_extract_format_placeholder_roots(interpolated)) if not format_succeeded else []
    if unmatched_placeholders or failed_format_placeholders:
        raise UnmatchedPlaceholderError(
            key=translation_key,
            name=(unmatched_placeholders or failed_format_placeholders)[0],
            rendered=rendered,
        )


def extract_placeholders(value: str) -> frozenset[str]:
    """Return interpolation names consumed by the production renderer.

    The renderer first replaces ``%{name}`` tokens and then delegates
    ``{name}`` tokens to :meth:`str.format`. Parsing the second form through
    :class:`string.Formatter` preserves conversions and specifications. Root
    kwargs consumed by attribute and index fields are returned, and nested
    replacement fields inside format specifications are inspected recursively.
    Escaped braces and brace-delimited prose are excluded. For malformed
    strings, independently valid fields are recovered without representing the
    malformed format string itself as complete or renderable.

    Args:
        value: Locale scalar to inspect.

    Returns:
        The unique placeholder names used by either interpolation pass.
    """
    names = {_match_group_text(match, "name") for match in _PLACEHOLDER_RE.finditer(value)}
    without_percent_tokens = _PLACEHOLDER_RE.sub(lambda match: " " * len(match.group(0)), value)
    names.update(_extract_format_placeholder_roots(without_percent_tokens))
    return frozenset(names)


def _extract_format_placeholder_roots(value: str) -> frozenset[str]:
    """Return named root kwargs consumed by the format pass.

    Malformed strings are scanned for independently valid replacement fields
    so strict mode can still reject supported tokens around the damaged region.
    The recovery path never treats the malformed whole as a valid format.
    """
    parsed = _parse_format_placeholder_roots(value)
    if parsed is not None:
        return frozenset(parsed)
    return frozenset(_recover_format_placeholder_roots(value))


def _match_group_text(match: re.Match[str], name: str) -> str:
    """Return a regex capture after enforcing the text-node invariant."""
    value = match.group(name)
    assert isinstance(value, str)
    return value


def _parse_format_placeholder_roots(value: str) -> set[str] | None:
    """Parse one valid format fragment, or return ``None`` when malformed."""
    try:
        fields = tuple(_FORMATTER.parse(value))
    except ValueError:
        return None

    names: set[str] = set()
    for _literal, field_name, format_spec, _conversion in fields:
        if field_name is not None:
            root = _FORMAT_FIELD_ROOT_RE.match(field_name)
            if root is not None:
                names.add(_match_group_text(root, "name"))
        if format_spec:
            nested = _parse_format_placeholder_roots(format_spec)
            if nested is None:
                names.update(_recover_format_placeholder_roots(format_spec))
            else:
                names.update(nested)
    return names


def _recover_format_placeholder_roots(value: str) -> set[str]:
    """Recover valid fields surrounding malformed brace syntax."""
    names: set[str] = set()
    index = 0
    while index < len(value):
        if value.startswith("{{", index):
            index += 2
            continue
        if value[index] != "{":
            index += 1
            continue

        recovered_end: int | None = None
        for closing in range(index + 1, len(value)):
            if value[closing] != "}":
                continue
            fragment = value[index : closing + 1]
            parsed = _parse_format_placeholder_roots(fragment)
            if parsed is None:
                continue
            names.update(parsed)
            recovered_end = closing + 1
            break
        index = recovered_end if recovered_end is not None else index + 1
    return names


_I18N_LOCALES_ROOT: ContextVar[Path | None] = ContextVar("cadrumo_i18n_locales_root", default=None)


@contextmanager
def _override_locales_root(root: Path) -> Iterator[None]:
    """Resolve catalogues from ``root`` instead of the packaged resources.

    The renderer's miss semantics — an absent key and a key-echo value are
    both misses (:func:`_lookup_translation`) — can only be exercised
    against a catalogue that carries the defect, and the shipped
    catalogues are gated echo-free. This override is the sanctioned seam
    for pointing resolution at a fixture catalogue, mirroring
    ``override_settings()``; the packaged resources stay the sole source
    otherwise.
    """
    token = _I18N_LOCALES_ROOT.set(root)
    try:
        yield
    finally:
        _I18N_LOCALES_ROOT.reset(token)


def _locale_map(locale: str) -> Mapping[str, str | None]:
    from ._lazy_catalogue import LazyLocaleCatalogue

    override = _I18N_LOCALES_ROOT.get()
    if override is not None:
        shard_dir = override / locale
        if shard_dir.is_dir():
            return LazyLocaleCatalogue(locale, shard_dir=shard_dir)
        monolith = override / f"{locale}.yml"
        if monolith.is_file():
            with monolith.open("r", encoding="utf-8") as handle:
                return _flatten_translations(_load_locale_yaml(handle))
    return _packaged_locale_map(locale)


@lru_cache(maxsize=len(SUPPORTED_OUTPUT_LANGUAGES))
def _packaged_locale_map(locale: str) -> LazyLocaleCatalogue:
    from ._lazy_catalogue import LazyLocaleCatalogue

    resource = importlib.resources.files(PRODUCT_IDENTITY.python_package).joinpath("locales")
    locales_root = Path(str(resource))
    shard_dir = locales_root / locale
    return LazyLocaleCatalogue(locale, shard_dir=shard_dir)


def _load_locale_yaml(handle: IO[str]) -> object:
    # CSafeLoader C-accelerates only scanning/parsing; PyYAML's higher-level
    # "construct Python objects from the parsed node tree" step is always
    # pure Python and scales with node count. The packaged catalogues now
    # carry a large modelo.schema.* block (compiled casilla labels/help,
    # see domain.calculations.registry._modelo_localization), so even this
    # accelerated path costs ~800 ms per process -- both loaders apply
    # identical safe-load semantics. _packaged_locale_map's on-disk flat-map
    # cache (._catalogue_cache) is what actually avoids paying this on every
    # process start; this function is the (correct, still-necessary) slow
    # path a cache miss falls back to.
    if hasattr(yaml, "CSafeLoader"):
        return yaml.load(handle, Loader=yaml.CSafeLoader) or {}
    return yaml.safe_load(handle) or {}


def _flatten_translations(value: object, prefix: str = "") -> dict[str, str | None]:
    if isinstance(value, Mapping):
        flattened: dict[str, str | None] = {}
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            flattened.update(_flatten_translations(child, child_prefix))
        return flattened
    return {prefix: None if value is None else str(value)}


def lookup_translation(translation_key: str, /, *, locale: str) -> str | None:
    """Return one authored locale scalar without humanising a missing value.

    ``None`` and the catalogue scaffold convention ``value == key`` both mean
    that the selected locale has no authored value.  Domain resolvers use this
    primitive when they own a stricter fallback policy than the operator-facing
    :func:`tr` convenience surface.
    """
    _present, value = lookup_translation_entry(translation_key, locale=locale)
    return value


def lookup_translation_entry(translation_key: str, /, *, locale: str) -> tuple[bool, str | None]:
    """Return catalogue membership separately from its optional scalar value."""
    normalized_locale = _normalise_supported_language(locale)
    if normalized_locale is None:
        return False, None
    try:
        locale_map = _locale_map(normalized_locale)
    except (OSError, yaml.YAMLError, IndexError):
        return False, None
    if translation_key not in locale_map:
        return False, None
    rendered = locale_map[translation_key]
    if rendered is None or rendered == translation_key:
        return True, None
    return True, rendered


def _lookup_translation(locale: str, translation_key: str, *, default: object | None = None) -> str:
    rendered: str | None
    try:
        rendered = _locale_map(locale).get(translation_key)
    except (OSError, yaml.YAMLError, IndexError) as exc:
        _log.debug(
            "i18n: unable to load locale %s; falling back to python-i18n (%s)",
            locale,
            type(exc).__name__,
            exc_info=True,
        )
        _ensure_initialised()
        fallback = i18n.t(translation_key, locale=locale)
        rendered = fallback if isinstance(fallback, str) else None
    # A value equal to its own key is the scaffold placeholder for "declared
    # but not translated yet", so it is a miss just as an absent key is.
    if rendered is None or rendered == translation_key:
        return _missing_translation(locale, translation_key, default=default)
    return rendered


def _missing_translation(locale: str, translation_key: str, *, default: object | None = None) -> str:
    """Resolve a key the catalogue does not carry, or refuse it in strict mode.

    An explicit ``default`` is the caller opting into a fallback, so it is
    honoured even under strict mode. Otherwise strict mode refuses and
    production returns a humanised label — a missing string must never abort
    a filing.

    Raises:
        MissingTranslationError: When strict-missing-key mode is active and
            the caller supplied no explicit ``default``.
    """
    if default is not None:
        return str(default)
    if _I18N_STRICT_MISSING_KEYS.get():
        raise MissingTranslationError(key=translation_key, locale=locale)
    return _humanise_key(translation_key)


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
    rendered, _format_succeeded = _interpolate_with_status(translation_key, rendered, values)
    return rendered


def _interpolate_with_status(
    translation_key: str,
    rendered: str,
    values: Mapping[str, object],
) -> tuple[str, bool]:
    """Interpolate a value and report whether the format pass completed."""

    def _replace(match: re.Match[str]) -> str:
        name = _match_group_text(match, "name")
        if name not in values:
            return match.group(0)
        return str(values[name])

    rendered = _PLACEHOLDER_RE.sub(_replace, rendered)
    try:
        return rendered.format(**values), True
    except (KeyError, IndexError, ValueError) as exc:
        _log.debug(
            "i18n: unable to interpolate locale key %s; returning partially rendered value (%s)",
            translation_key,
            type(exc).__name__,
            exc_info=True,
        )
        return rendered, False


__all__ = [
    "DEFAULT_OUTPUT_LANGUAGE",
    "SUPPORTED_OUTPUT_LANGUAGES",
    "MissingTranslationError",
    "UnmatchedPlaceholderError",
    "extract_placeholders",
    "output_language",
    "register_profile_language_resolver",
    "tr",
]
