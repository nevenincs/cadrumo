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
    :mod:`~application.registry.corpus`
        Registry citation projection service that consumes topic records for
        operator-facing reports.
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....domain.calculations.registry.authority import bundled_authority
from ...resources._registry import resources
from ..catalogue import Topic, TopicCatalogue, TopicCatalogueEmptyError, TopicNotFoundError, load_topic_catalogue

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

assert __package__ is not None
topics_module = sys.modules[__package__.removesuffix(".tests") + ".catalogue"]

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
    """An unknown slug refuses through the registered key and the slug fact.

    The refusal carries no authored sentence: the operator-facing text is
    resolved from the registered locale key and the rejected slug travels as a
    machine fact on the error context, so the message is translated in every
    locale rather than pinned to English at the raise site.

    Pinning the key and the facts alone stays green even if English prose is
    passed alongside the key, because message resolution prefers the key. The
    prose does not stay hidden: ``str(exc)`` prefers the positional message, so
    it still reaches tracebacks, logs, and every boundary rendering the
    exception directly. Asserting the absence is what makes re-introducing a
    sentence at this raise site fail.
    """
    from ...errors.error_codes import get_registered_error_code, resolve_error_message

    catalogue = resources().topics.singleton
    with pytest.raises(TopicNotFoundError) as raised:
        catalogue.topic("not-a-real-topic")

    error = raised.value
    assert error.translated_message == "errors.refused.refused_topic_not_found"
    assert error.context == {"slug": "not-a-real-topic"}
    assert get_registered_error_code(error).code == "REFUSED_TOPIC_NOT_FOUND"
    assert str(error) == error.translated_message, f"the raise site carries an authored sentence: {str(error)!r}"
    resolved = resolve_error_message(error)
    assert resolved and resolved != error.translated_message


def test_empty_catalogue_directory_refuses_with_its_own_locale_key(tmp_path: Path) -> None:
    """An empty registry directory refuses distinctly from a missing slug.

    A bundled catalogue carrying no TOML is a different failure from a slug the
    operator mistyped, so it carries its own registered code rather than
    borrowing the not-found identity. The loader runs against a real empty
    directory rather than a patched fingerprint.

    As with the missing-slug refusal, the key and facts alone would stay green
    against re-introduced English prose; ``str(exc)`` degrading to the key is
    what proves this raise site authors no sentence.
    """
    from ...errors.error_codes import get_registered_error_code, resolve_error_message

    with pytest.raises(TopicCatalogueEmptyError) as raised:
        load_topic_catalogue(tmp_path)

    error = raised.value
    assert error.translated_message == "errors.refused.refused_topic_catalogue_empty"
    assert error.context == {"catalogue_root": str(tmp_path.resolve()), "topic_count": 0}
    assert get_registered_error_code(error).code == "REFUSED_TOPIC_CATALOGUE_EMPTY"
    assert str(error) == error.translated_message, f"the raise site carries an authored sentence: {str(error)!r}"
    resolved = resolve_error_message(error)
    assert resolved and resolved != error.translated_message


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
    legal_ids = set(bundled_authority().catalogues.legal)
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
        "TopicCatalogueEmptyError",
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
        if inspect.ismodule(value) and value.__name__.startswith("cadrumo.entrypoints")
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
