"""Tests for the topic catalogue loader and i18n key coverage."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from . import TopicCatalogue, TopicNotFoundError, load_topic_catalogue

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_TOPICS_PACKAGE_ROOT = Path(__file__).parent

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


def test_topic_catalogue_package_has_no_cli_or_rendering_surface() -> None:
    """Topics are backend catalogue records; CLI exposure belongs to registry."""

    forbidden_import_roots = {
        "click",
        "rich",
        "typer",
        "aeat.entrypoints",
    }
    forbidden_import_names = {
        "_emit",
        "emit_json_document",
        "emit_json_success",
        "render_command_output",
    }
    forbidden_call_names = {
        "echo",
        "print",
    }
    offenders: list[str] = []
    for module in sorted(_TOPICS_PACKAGE_ROOT.rglob("*.py")):
        relative = module.relative_to(_TOPICS_PACKAGE_ROOT)
        if "__pycache__" in relative.parts or module.name.startswith("test_"):
            continue
        tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".", 1)[0]
                    if root in forbidden_import_roots or alias.name in forbidden_import_names:
                        offenders.append(f"{relative}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                imported_module = node.module or ""
                root = imported_module.split(".", 1)[0]
                if root in forbidden_import_roots or imported_module.startswith("aeat.entrypoints"):
                    offenders.append(f"{relative}: from {imported_module} import ...")
                for alias in node.names:
                    if alias.name in forbidden_import_names:
                        offenders.append(f"{relative}: import {alias.name}")
            elif isinstance(node, ast.Call):
                callee = node.func
                if isinstance(callee, ast.Name) and callee.id in forbidden_call_names:
                    offenders.append(f"{relative}: call {callee.id}")
                elif isinstance(callee, ast.Attribute) and callee.attr in forbidden_call_names:
                    offenders.append(f"{relative}: call {callee.attr}")

    assert offenders == []
