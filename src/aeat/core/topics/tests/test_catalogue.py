"""Tests for the topic catalogue loader and i18n key coverage."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ...resources import resources
from .. import TopicCatalogue, TopicNotFoundError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

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
    },
)


def test_catalogue_loads_all_thirteen_audit_named_topics() -> None:
    """Every audit-named slug must be registered in the canonical catalogue."""
    catalogue = resources().topics.singleton
    assert isinstance(catalogue, TopicCatalogue)
    slugs = set(catalogue.slugs())
    missing = _EXPECTED_TOPICS - slugs
    assert not missing, f"audit-named topics missing from catalogue: {missing}"


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


_FORBIDDEN_IMPORT_ROOTS: frozenset[str] = frozenset({"click", "rich", "typer", "aeat.entrypoints"})
_FORBIDDEN_IMPORT_NAMES: frozenset[str] = frozenset(
    {"_emit", "emit_json_document", "emit_json_success", "render_command_output"},
)
_FORBIDDEN_CALL_NAMES: frozenset[str] = frozenset({"echo", "print"})


def test_topic_catalogue_package_has_no_cli_or_rendering_surface() -> None:
    """Topics are backend catalogue records; CLI exposure belongs to registry."""

    offenders: list[str] = []
    for module in sorted(_TOPICS_PACKAGE_ROOT.rglob("*.py")):
        relative = module.relative_to(_TOPICS_PACKAGE_ROOT)
        if "__pycache__" in relative.parts or module.name.startswith("test_"):
            continue
        tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
        for node in ast.walk(tree):
            offenders.extend(_scan_node_for_cli_surface(node, relative))
    assert offenders == []


def _scan_node_for_cli_surface(node: ast.AST, relative: Path) -> list[str]:
    """Return the per-node CLI-surface offences (empty when the node is clean)."""
    if isinstance(node, ast.Import):
        return _scan_import(node, relative)
    if isinstance(node, ast.ImportFrom):
        return _scan_import_from(node, relative)
    if isinstance(node, ast.Call):
        return _scan_call(node, relative)
    return []


def _scan_import(node: ast.Import, relative: Path) -> list[str]:
    offenders: list[str] = []
    for alias in node.names:
        root = alias.name.split(".", 1)[0]
        if root in _FORBIDDEN_IMPORT_ROOTS or alias.name in _FORBIDDEN_IMPORT_NAMES:
            offenders.append(f"{relative}: import {alias.name}")
    return offenders


def _scan_import_from(node: ast.ImportFrom, relative: Path) -> list[str]:
    offenders: list[str] = []
    imported_module = node.module or ""
    root = imported_module.split(".", 1)[0]
    if root in _FORBIDDEN_IMPORT_ROOTS or imported_module.startswith("aeat.entrypoints"):
        offenders.append(f"{relative}: from {imported_module} import ...")
    for alias in node.names:
        if alias.name in _FORBIDDEN_IMPORT_NAMES:
            offenders.append(f"{relative}: import {alias.name}")
    return offenders


def _scan_call(node: ast.Call, relative: Path) -> list[str]:
    callee = node.func
    if isinstance(callee, ast.Name) and callee.id in _FORBIDDEN_CALL_NAMES:
        return [f"{relative}: call {callee.id}"]
    if isinstance(callee, ast.Attribute) and callee.attr in _FORBIDDEN_CALL_NAMES:
        return [f"{relative}: call {callee.attr}"]
    return []
