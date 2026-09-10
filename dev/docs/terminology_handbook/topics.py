"""Development-only loader for authored registry terminology topics."""

from __future__ import annotations

import tomllib
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.external_constants import UTF_8_ENCODING
from cadrumo.core.models import STRICT_FROZEN_CONFIG
from cadrumo.core.paths import file_stat_fingerprint
from cadrumo.core.resources.bundled_data import bundled_path

_TOPIC_REGISTRY_ROOT = bundled_path("registry", "aeat", "topics")


class Topic(BaseModel):
    """One topic authored for the terminology handbook."""

    model_config = STRICT_FROZEN_CONFIG

    slug: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9\-]*$")
    title_key: str = Field(min_length=1, max_length=128)
    body_key: str = Field(min_length=1, max_length=128)
    see_also: tuple[str, ...] = Field(default=())
    legal_refs: tuple[str, ...] = Field(min_length=1)


class TopicCatalogue(BaseModel):
    """Closed set of terminology topics."""

    model_config = STRICT_FROZEN_CONFIG

    topics: tuple[Topic, ...] = Field(min_length=1)


def load_topic_catalogue(root: Path | None = None) -> TopicCatalogue:
    """Load authored registry topics for development documentation."""
    target = root if root is not None else _TOPIC_REGISTRY_ROOT
    resolved = target.resolve()
    paths = scan_directory(resolved, pattern="*.toml")
    fingerprint = tuple(file_stat_fingerprint(path) for path in paths)
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
        raw = tomllib.loads(path.read_text(encoding=UTF_8_ENCODING))
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
        raise ValueError(f"terminology topic catalogue is empty: {target}")
    return TopicCatalogue(topics=tuple(topics))


__all__ = ["Topic", "TopicCatalogue", "load_topic_catalogue"]
