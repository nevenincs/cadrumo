"""Tests for the topic catalogue loader and i18n key coverage.

The suite pins :mod:`~core.topics` as a backend catalogue resource: topic TOML
files load into strict :class:`~core.topics.Topic` records, their locale keys
resolve through :func:`~core.i18n.tr`, their legal references resolve against
the committed registry authority, and the package exports no CLI/rendering
surface.

See Also:
    :class:`~core.topics.TopicCatalogue`
        Closed catalogue loaded from ``registry/aeat/topics``.
    :class:`~core.resources._repos.topics.TopicCatalogueRepository`
        Resource repository consumed by tests and application registry services.
    :mod:`~application.registry._corpus`
        Registry citation projection service that consumes topic records for
        operator-facing reports.
    Governing vault records
        ``2026-05-08-aeat-cli-gap-closure-plan`` introduced the conceptual topic
        catalogue, while ``2026-05-13-cli-workflow-redesign-epic-plan`` moved
        topic exposure under registry-owned citation services.
"""

from __future__ import annotations

import inspect
import sys

import pytest
from pydantic import ValidationError

from ...resources import resources
from .. import Topic, TopicCatalogue, TopicNotFoundError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

assert __package__ is not None
topics_module = sys.modules[__package__.removesuffix(".tests")]

_EXPECTED_TOPICS = frozenset(
    {
        "iva-regime",
        "irpf-regime",
        "modelos",
        "casilla",
        "pago-fraccionado",
        "recargo-extemporaneo",
        "sii",
        "verifactu",
        "authentication",
        "profile",
        "calendar",
        "formats",
        "providers",
        "regimens",
    },
)


def test_catalogue_loads_all_current_audit_named_topics() -> None:
    """Every audit-named slug must be registered in the canonical catalogue."""
    catalogue = resources().topics.singleton
    assert isinstance(catalogue, TopicCatalogue)
    slugs = set(catalogue.slugs())
    missing = _EXPECTED_TOPICS - slugs
    assert not missing, f"audit-named topics missing from catalogue: {missing}"
    assert "sii-verifactu" not in slugs


def test_catalogue_topic_lookup_returns_typed_record() -> None:
    """Lookup by slug returns the typed :class:`Topic`."""
    catalogue = resources().topics.singleton
    topic = catalogue.topic("iva-regime")
    assert topic.slug == "iva-regime"
    assert topic.title_key == "topic.iva-regime.title"
    assert topic.body_key == "topic.iva-regime.body"


def test_catalogue_rejects_unknown_slug_with_typed_error() -> None:
    """Unknown slugs raise :class:`TopicNotFoundError`."""
    catalogue = resources().topics.singleton
    with pytest.raises(TopicNotFoundError, match=r"topic|not|found"):
        catalogue.topic("not-a-real-topic")


def test_every_topic_renders_title_and_body_in_default_locale() -> None:
    """Every registered topic must resolve to non-empty title/body text.

    Translation keys default to ``topic.<slug>.title`` and
    ``topic.<slug>.body``. The locale catalogue must carry these
    entries for at least the default ``es`` locale so the CLI does
    not render bare keys.
    """
    from ...i18n import tr

    catalogue = resources().topics.singleton
    for topic in catalogue.topics:
        title = tr(topic.title_key)
        body = tr(topic.body_key)
        assert title and title != topic.title_key, f"topic {topic.slug!r}: title missing in default locale"
        assert body and body != topic.body_key, f"topic {topic.slug!r}: body missing in default locale"


def test_every_topic_legal_ref_resolves_against_real_legal_catalogue() -> None:
    """Topic citation links must resolve through the committed legal catalogue."""
    catalogue = resources().topics.singleton
    legal_ids = set(resources().modelos.authority.catalogues.legal)
    ungrounded = sorted(topic.slug for topic in catalogue.topics if not topic.legal_refs)
    missing = sorted(
        f"{topic.slug}: {legal_ref}"
        for topic in catalogue.topics
        for legal_ref in topic.legal_refs
        if legal_ref not in legal_ids
    )

    assert ungrounded == []
    assert missing == []


def test_topic_requires_legal_refs() -> None:
    """A topic cannot be registered without legal grounding."""

    with pytest.raises(ValidationError) as raised:
        Topic.model_validate(
            {
                "slug": "ungrounded-topic",
                "title_key": "topic.ungrounded-topic.title",
                "body_key": "topic.ungrounded-topic.body",
            },
        )

    assert "legal_refs" in str(raised.value)


_EXPECTED_PUBLIC_EXPORTS = frozenset(
    {
        "Topic",
        "TopicCatalogue",
        "TopicNotFoundError",
        "load_topic_catalogue",
    },
)
_FORBIDDEN_MODULE_ROOTS: frozenset[str] = frozenset({"click", "rich", "typer"})
_FORBIDDEN_RENDERING_EXPORTS: frozenset[str] = frozenset(
    {"_emit", "emit_json_document", "emit_json_success", "render_command_output"},
)


def test_topic_catalogue_package_has_no_cli_or_rendering_surface(capsys: pytest.CaptureFixture[str]) -> None:
    """Topics are backend catalogue records; CLI exposure belongs to registry."""

    public_exports = frozenset(topics_module.__all__)
    leaked_exports = public_exports & _FORBIDDEN_RENDERING_EXPORTS
    bound_cli_modules = {
        name: value.__name__
        for name, value in vars(topics_module).items()
        if inspect.ismodule(value) and value.__name__.split(".", 1)[0] in _FORBIDDEN_MODULE_ROOTS
    }
    bound_entrypoint_modules = {
        name: value.__name__
        for name, value in vars(topics_module).items()
        if inspect.ismodule(value) and value.__name__.startswith("aeat.entrypoints")
    }

    catalogue = resources().topics.singleton
    assert catalogue.slugs()
    assert catalogue.topic("iva-regime").slug == "iva-regime"
    captured = capsys.readouterr()

    assert public_exports == _EXPECTED_PUBLIC_EXPORTS
    assert leaked_exports == frozenset()
    assert bound_cli_modules == {}
    assert bound_entrypoint_modules == {}
    assert captured.out == ""
    assert captured.err == ""
