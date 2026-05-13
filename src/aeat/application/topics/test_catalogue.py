"""Tests for the topic catalogue loader and renderer."""

from __future__ import annotations

import pytest

from . import TopicCatalogue, TopicNotFoundError, load_topic_catalogue

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_EXPECTED_TOPICS = frozenset(
    {
        "iva-regime",
        "irpf-regime",
        "modelos",
        "casilla",
        "pago-fraccionado",
        "recargo-extemporaneo",
        "sii-verifactu",
        "authentication",
        "profile",
        "calendar",
        "formats",
        "providers",
        "regimens",
    }
)


def test_catalogue_loads_all_thirteen_audit_named_topics() -> None:
    """Every audit-named slug must be registered in the canonical catalogue."""
    catalogue = load_topic_catalogue()
    assert isinstance(catalogue, TopicCatalogue)
    slugs = set(catalogue.slugs())
    missing = _EXPECTED_TOPICS - slugs
    assert not missing, f"audit-named topics missing from catalogue: {missing}"


def test_catalogue_topic_lookup_returns_typed_record() -> None:
    """Lookup by slug returns the typed :class:`Topic`."""
    catalogue = load_topic_catalogue()
    topic = catalogue.topic("iva-regime")
    assert topic.slug == "iva-regime"
    assert topic.title_key == "topic.iva-regime.title"
    assert topic.body_key == "topic.iva-regime.body"


def test_catalogue_rejects_unknown_slug_with_typed_error() -> None:
    """Unknown slugs raise :class:`TopicNotFoundError`."""
    catalogue = load_topic_catalogue()
    with pytest.raises(TopicNotFoundError, match=r"topic|not|found"):
        catalogue.topic("not-a-real-topic")


def test_every_topic_renders_title_and_body_in_default_locale() -> None:
    """Every registered topic must resolve to non-empty title/body text.

    Translation keys default to ``topic.<slug>.title`` and
    ``topic.<slug>.body``. The locale catalogue must carry these
    entries for at least the default ``es`` locale so the CLI does
    not render bare keys.
    """
    from aeat.core.i18n import tr

    catalogue = load_topic_catalogue()
    for topic in catalogue.topics:
        title = tr(topic.title_key)
        body = tr(topic.body_key)
        assert title and title != topic.title_key, f"topic {topic.slug!r}: title missing in default locale"
        assert body and body != topic.body_key, f"topic {topic.slug!r}: body missing in default locale"
