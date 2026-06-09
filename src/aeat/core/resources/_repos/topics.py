"""TopicCatalogueRepository: singleton topic catalogue."""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from .._repository import ResourceCacheRepository

if TYPE_CHECKING:
    from ...topics import TopicCatalogue


class TopicCatalogueRepository(ResourceCacheRepository["TopicCatalogue", None]):
    """Singleton-keyed repository for the topic catalogue.

    Wraps :func:`aeat.core.topics.load_topic_catalogue`.
    """

    @override
    def _load(self, key: None) -> TopicCatalogue:
        from ...topics import load_topic_catalogue

        return load_topic_catalogue()

    @property
    def singleton(self) -> TopicCatalogue:
        return self.get(None)
