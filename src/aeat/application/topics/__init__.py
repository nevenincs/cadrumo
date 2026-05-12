"""Conceptual topic catalogue for ``aeat topic`` / ``aeat help <slug>``.

Closes UX-015 from the 2026-05-08 CLI gap audit. A tax-naive operator
hitting the CLI for the first time needs plain-language explanations of
concepts (``iva-regime``, ``casilla``, ``pago-fraccionado`` …) without
having to leave the terminal. The CLI exposes:

- ``aeat topic`` -> list every registered slug + one-line summary.
- ``aeat topic <slug>`` -> render the topic body + see_also pointers
  + legal references.
- ``aeat help <slug>`` -> alias of ``aeat topic <slug>``.

Topics live as TOML files under ``registry/aeat/topics/<slug>.toml``;
title and body text live in the i18n catalogue under ``topic.<slug>.*``
so translations follow the project's locale pipeline rather than
hardcoded multiline strings.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from ...core.errors import AeatError
from ...core.paths import PROJECT_ROOT

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")
_TOPIC_REGISTRY_ROOT = PROJECT_ROOT / "registry" / "aeat" / "topics"


class TopicNotFoundError(AeatError):
    """Raised when a requested slug is not registered in the catalogue."""


class Topic(BaseModel):
    """One conceptual topic.

    Attributes:
        slug: Stable kebab-case identifier (``iva-regime``).
        title_key: i18n key resolving to the topic's human-readable
            title. Convention: ``topic.<slug>.title``.
        body_key: i18n key resolving to the topic body. Convention:
            ``topic.<slug>.body``.
        see_also: Slugs of related topics for cross-referencing.
        legal_refs: Stable corpus references (``ley-58-2003:art-27``,
            ``rd-439-2007:art-110``) the topic anchors against.
    """

    model_config = _STRICT_FROZEN

    slug: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9\-]*$")
    title_key: str = Field(min_length=1, max_length=128)
    body_key: str = Field(min_length=1, max_length=128)
    see_also: tuple[str, ...] = Field(default=())
    legal_refs: tuple[str, ...] = Field(default=())


class TopicCatalogue(BaseModel):
    """Closed catalogue of registered conceptual topics."""

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
        raise TopicNotFoundError(f"topic not found: {slug!r}")

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

    Raises:
        ValueError: When the directory is empty or a TOML row is
            malformed. Pydantic validation errors propagate verbatim
            from :class:`Topic`.
    """

    target = root if root is not None else _TOPIC_REGISTRY_ROOT
    topics: list[Topic] = []
    for path in sorted(target.glob("*.toml")):
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
        slug = str(raw.get("slug") or path.stem)
        topics.append(
            Topic(
                slug=slug,
                title_key=str(raw.get("title_key") or f"topic.{slug}.title"),
                body_key=str(raw.get("body_key") or f"topic.{slug}.body"),
                see_also=tuple(str(item) for item in raw.get("see_also", ())),
                legal_refs=tuple(str(item) for item in raw.get("legal_refs", ())),
            )
        )
    if not topics:
        raise ValueError(f"topic catalogue at {target} is empty")
    return TopicCatalogue(topics=tuple(topics))


__all__ = [
    "Topic",
    "TopicCatalogue",
    "TopicNotFoundError",
    "load_topic_catalogue",
]
