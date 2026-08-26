"""Public locale-catalogue capture over one stable catalogue window.

This module owns the capture contract for the shipped translation catalogues.
It resolves nothing of its own: catalogue loading, the scaffold-null
suppression convention and key membership all come from
:mod:`cadrumo.core.i18n._render`, and the catalogue fingerprint comes from
:func:`~cadrumo.core.i18n._catalogue_cache.compute_directory_source_digest`.
There is no second catalogue reader, digest, cache or routing rule here, and
none may be added.

The per-locale Spanish fallback and the modelo key-identity chain are owned by
``resolve_modelo_localization`` one layer above this one. This module
deliberately does not reimplement them: it captures the catalogue state that
resolver reads, so a caller can prove the value it resolved and the catalogue
it resolved against belong to the same window.

See Also:
    :func:`~cadrumo.core.i18n.tr`
        The operator-facing translation surface resolving through the same
        catalogue this module captures.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from secrets import token_bytes
from threading import RLock

from ..errors import CoreError
from ._catalogue_cache import compute_directory_source_digest
from ._render import _locale_map, _normalise_supported_language, lookup_translation_entry

_LOCALE_CATALOGUE_CAPTURE_MAX_ATTEMPTS = 8
_locale_catalogue_process_pid = os.getpid()
_locale_catalogue_process_nonce = token_bytes(32)
_locale_catalogue_domains: set[str] = set()
_locale_catalogue_lock = RLock()
_locale_catalogue_generations: dict[str, tuple[tuple[str, ...], int]] = {}
_locale_catalogue_generation = 0


class LocaleCatalogueCaptureError(CoreError):
    """Raised when a locale catalogue cannot be captured over one stable window."""


@dataclass(frozen=True, slots=True)
class LocaleCatalogueCapture:
    """One catalogue entry and the currentness coordinate it was read under.

    ``present`` and ``value`` are exactly what the catalogue reader returned,
    including its convention that a scaffolded-but-untranslated key is present
    with no value. The catalogue root, its shard digest and the process
    incarnation are folded into the opaque comparison domain and never exposed.
    """

    locale: str
    translation_key: str
    present: bool
    value: str | None
    comparison_domain: str
    generation: int

    def require_current(self, current: LocaleCatalogueCurrentCoordinate) -> LocaleCatalogueCapture:
        """Refuse a currentness comparison outside this owner process domain."""
        _require_locale_catalogue_process_domain(self.comparison_domain)
        current.require_current(self)
        return self


@dataclass(frozen=True, slots=True)
class LocaleCatalogueCurrentCoordinate:
    """Opaque same-process coordinate for one locale catalogue owner scope."""

    comparison_domain: str
    generation: int

    def require_current(self, captured: LocaleCatalogueCapture) -> LocaleCatalogueCurrentCoordinate:
        """Require a capture from this exact owner scope and process incarnation."""
        _require_locale_catalogue_process_domain(self.comparison_domain)
        _require_locale_catalogue_process_domain(captured.comparison_domain)
        if self.comparison_domain != captured.comparison_domain:
            raise LocaleCatalogueCaptureError(
                translated_message="errors.refused.locale_catalogue_capture_not_current",
                context={"reason": "distinct_owner_scope"},
            )
        if self.generation != captured.generation:
            raise LocaleCatalogueCaptureError(
                translated_message="errors.refused.locale_catalogue_capture_not_current",
                context={"reason": "capture_superseded"},
            )
        return self


def _require_locale_catalogue_process_domain(domain: str) -> None:
    """Refuse a coordinate domain not minted in this process incarnation."""
    if _locale_catalogue_process_pid != os.getpid():
        raise LocaleCatalogueCaptureError(
            translated_message="errors.refused.locale_catalogue_capture_not_current",
            context={"reason": "forked_process"},
        )
    with _locale_catalogue_lock:
        known = domain in _locale_catalogue_domains
    if not known:
        raise LocaleCatalogueCaptureError(
            translated_message="errors.refused.locale_catalogue_capture_not_current",
            context={"reason": "foreign_process_incarnation"},
        )


def _supported_locale(locale: str) -> str:
    """Return the normalized supported locale or refuse an unsupported one."""
    normalized = _normalise_supported_language(locale)
    if normalized is None:
        raise LocaleCatalogueCaptureError(
            translated_message="errors.refused.locale_catalogue_capture_not_current",
            context={"reason": "unsupported_locale", "locale": locale},
        )
    return normalized


def _locale_catalogue_observation(locale: str) -> tuple[str, ...]:
    """Fingerprint the shard directory backing one locale, through its own digest."""
    catalogue = _locale_map(locale)
    shard_dir = getattr(catalogue, "shard_dir", None)
    if shard_dir is None or not shard_dir.is_dir():
        raise LocaleCatalogueCaptureError(
            translated_message="errors.refused.locale_catalogue_capture_not_current",
            context={"reason": "catalogue_not_directory_backed", "locale": locale},
        )
    shards = [
        (shard.relative_to(shard_dir).as_posix(), shard.read_bytes())
        for shard in shard_dir.rglob("*.yml")
        if shard.is_file()
    ]
    return (locale, compute_directory_source_digest(shards))


def _locale_catalogue_comparison_domain(locale: str) -> str:
    """Mint the non-persisted coordinate domain for one locale owner scope."""
    from ..hashing import content_hash_hex

    domain = content_hash_hex(
        {
            "owner": "core.i18n.locale_catalogue",
            "namespace": "locales.catalogue",
            "locale": locale,
            "process_incarnation": _locale_catalogue_process_nonce.hex(),
        }
    )
    with _locale_catalogue_lock:
        _locale_catalogue_domains.add(domain)
    return domain


def _locale_catalogue_generation_for(domain: str, observation: tuple[str, ...]) -> int:
    """Assign one injective, order-preserving generation per distinct observation."""
    global _locale_catalogue_generation
    with _locale_catalogue_lock:
        recorded = _locale_catalogue_generations.get(domain)
        if recorded is not None and recorded[0] == observation:
            return recorded[1]
        _locale_catalogue_generation += 1
        _locale_catalogue_generations[domain] = (observation, _locale_catalogue_generation)
        return _locale_catalogue_generation


def read_locale_catalogue_current_coordinate(*, locale: str) -> LocaleCatalogueCurrentCoordinate:
    """Return the typed current coordinate for same-domain capture validation."""
    normalized = _supported_locale(locale)
    observation = _locale_catalogue_observation(normalized)
    domain = _locale_catalogue_comparison_domain(normalized)
    return LocaleCatalogueCurrentCoordinate(
        comparison_domain=domain,
        generation=_locale_catalogue_generation_for(domain, observation),
    )


def capture_locale_catalogue(translation_key: str, /, *, locale: str) -> LocaleCatalogueCapture:
    """Read one catalogue entry over a window in which the catalogue did not move.

    The shard digest is taken either side of the sole
    :func:`~cadrumo.core.i18n.lookup_translation_entry` reader, so a catalogue
    rewritten mid-read is retried rather than published as an entry paired with
    a coordinate from another catalogue state.
    """
    normalized = _supported_locale(locale)
    for _attempt in range(_LOCALE_CATALOGUE_CAPTURE_MAX_ATTEMPTS):
        before = _locale_catalogue_observation(normalized)
        present, value = lookup_translation_entry(translation_key, locale=normalized)
        after = _locale_catalogue_observation(normalized)
        if before != after:
            continue
        domain = _locale_catalogue_comparison_domain(normalized)
        return LocaleCatalogueCapture(
            locale=normalized,
            translation_key=translation_key,
            present=present,
            value=value,
            comparison_domain=domain,
            generation=_locale_catalogue_generation_for(domain, after),
        )
    raise LocaleCatalogueCaptureError(
        translated_message="errors.refused.locale_catalogue_capture_not_current",
        context={"reason": "contended", "attempts": _LOCALE_CATALOGUE_CAPTURE_MAX_ATTEMPTS},
    )


__all__ = [
    "LocaleCatalogueCapture",
    "LocaleCatalogueCaptureError",
    "LocaleCatalogueCurrentCoordinate",
    "capture_locale_catalogue",
    "read_locale_catalogue_current_coordinate",
]
