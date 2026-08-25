"""Conceptual topic catalogue for ``aeat app registry citations``.

A tax-naive operator hitting the CLI for the first time needs
plain-language explanations of concepts (``iva-regime``, ``casilla``,
``pago-fraccionado`` …) without having to leave the terminal. The
CLI exposes:

- ``aeat app registry citations`` -> list every registered slug + one-line summary.
- ``aeat app registry citations <slug>`` -> render the topic body + see_also
  pointers + legal references.

Topics live as TOML files under ``registry/aeat/topics/<slug>.toml``;
title and body text live in the i18n catalogue under ``topic.<slug>.*``
so translations follow the project's locale pipeline rather than
hardcoded multiline strings.

The :class:`Topic` records are core-level resources: they depend only
on core primitives and the bundled registry path. They are loaded into
a :class:`TopicCatalogue` by :func:`load_topic_catalogue` and consumed
through the
:class:`core.resources._repos.topics.TopicCatalogueRepository`
singleton, keeping ``core`` free of any import into the application
layer.
"""

from __future__ import annotations

import tomllib
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

from .. import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ..directory_scan import scan_directory as _scan_directory
from ..errors import CadrumoError as _CadrumoError
from ..external_constants import UTF_8_ENCODING as _UTF_8_ENCODING
from ..paths import file_stat_fingerprint as _file_stat_fingerprint
from ..resources import bundled_path as _bundled_path

_TOPIC_REGISTRY_ROOT = _bundled_path("registry", "aeat", "topics")


class TopicNotFoundError(_CadrumoError):
    """Raised when a requested slug is absent from a :class:`TopicCatalogue`."""


class TopicCatalogueEmptyError(_CadrumoError):
    """Raised when the bundled catalogue directory declares no topic at all.

    A directory carrying no TOML is an integrity failure of the shipped
    registry, not an operator mistyping a slug, so it carries its own
    registered code rather than borrowing the not-found identity.
    """


class Topic(BaseModel):
    """One conceptual topic.

    Attributes:
        slug: Stable kebab-case identifier (``iva-regime``).
        title_key: i18n key resolving to the topic's human-readable
            title. Convention: ``topic.<slug>.title``.
        body_key: i18n key resolving to the topic body. Convention:
            ``topic.<slug>.body``.
        see_also: Slugs of related topics for cross-referencing.
        legal_refs: Stable corpus references (``ley-58-2003:art-27.2``,
            ``rd-439-2007:art-110``) the topic anchors against.
    """

    model_config = _STRICT_FROZEN

    slug: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9\-]*$")
    title_key: str = Field(min_length=1, max_length=128)
    body_key: str = Field(min_length=1, max_length=128)
    see_also: tuple[str, ...] = Field(default=())
    legal_refs: tuple[str, ...] = Field(min_length=1)


class TopicCatalogue(BaseModel):
    """Closed catalogue of registered :class:`Topic` records."""

    model_config = _STRICT_FROZEN

    topics: tuple[Topic, ...] = Field(min_length=1)

    def topic(self, slug: str) -> Topic:
        """Return the :class:`Topic` for ``slug`` or raise.

        Args:
            slug: Kebab-case topic identifier.

        Returns:
            The matching :class:`Topic`.

        Raises:
            TopicNotFoundError: When ``slug`` is not in the catalogue.
        """
        for topic in self.topics:
            if topic.slug == slug:
                return topic
        raise TopicNotFoundError(
            context={"slug": slug},
            translated_message="errors.refused.refused_topic_not_found",
        )

    def slugs(self) -> tuple[str, ...]:
        """Return every registered slug sorted alphabetically."""
        return tuple(sorted(topic.slug for topic in self.topics))


def load_topic_catalogue(root: Path | None = None) -> TopicCatalogue:
    """Load every ``registry/aeat/topics/<slug>.toml`` into one catalogue.

    Args:
        root: Override directory (defaults to the canonical project
            registry path).

    Returns:
        A :class:`TopicCatalogue` carrying one :class:`Topic` per TOML.
    """
    target = root if root is not None else _TOPIC_REGISTRY_ROOT
    resolved = target.resolve()
    paths = _scan_directory(resolved, pattern="*.toml")
    fingerprint = tuple(_file_stat_fingerprint(path) for path in paths)
    return _load_topic_catalogue_cached(str(resolved), fingerprint)


@lru_cache(maxsize=16)
def _load_topic_catalogue_cached(
    root: str,
    fingerprint: tuple[tuple[str, int, int], ...],
) -> TopicCatalogue:
    target = Path(root)
    topics: list[Topic] = []
    for filename, _byte_count, _modified_ns in fingerprint:
        path = target / filename
        raw = tomllib.loads(path.read_text(encoding=_UTF_8_ENCODING))
        slug = str(raw.get("slug") or path.stem)
        topics.append(
            Topic(
                slug=slug,
                title_key=str(raw.get("title_key") or f"topic.{slug}.title"),
                body_key=str(raw.get("body_key") or f"topic.{slug}.body"),
                see_also=tuple(str(item) for item in raw.get("see_also", ())),
                legal_refs=tuple(str(item) for item in raw.get("legal_refs", ())),
            ),
        )
    if not topics:
        raise TopicCatalogueEmptyError(
            context={"catalogue_root": str(target), "topic_count": 0},
            translated_message="errors.refused.refused_topic_catalogue_empty",
        )
    return TopicCatalogue(topics=tuple(topics))


__all__ = [
    "Topic",
    "TopicCatalogue",
    "TopicCatalogueEmptyError",
    "TopicNotFoundError",
    "load_topic_catalogue",
]
