"""TopicCatalogueRepository: singleton topic catalogue."""

from __future__ import annotations

from .._repository import ResourceCacheRepository


class TopicCatalogueRepository(ResourceCacheRepository[object, type(None)]):
    """Singleton-keyed repository for the topic catalogue.

    Wraps :func:`aeat.application.topics.load_topic_catalogue`.
    """

    def _load(self, key: None) -> object:
        from ....application.topics import load_topic_catalogue

        return load_topic_catalogue()

    @property
    def singleton(self) -> object:
        return self.get(None)
