"""TopicCatalogueRepository: singleton :class:`TopicCatalogue` lookup."""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from .._repository import ResourceCacheRepository

if TYPE_CHECKING:
    from ...topics.catalogue import TopicCatalogue


class TopicCatalogueRepository(ResourceCacheRepository["TopicCatalogue", None]):
    """Singleton-keyed repository for the topic catalogue.

    Wraps :func:`cadrumo.core.topics.load_topic_catalogue` and exposes
    the resulting :class:`TopicCatalogue` through ``singleton``.
    """

    @override
    def _load(self, key: None) -> TopicCatalogue:
        from ...topics.catalogue import load_topic_catalogue

        return load_topic_catalogue()

    @property
    def singleton(self) -> TopicCatalogue:
        return self.get(None)
