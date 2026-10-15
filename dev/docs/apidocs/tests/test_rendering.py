"""Tests for API annotation rendering in Sphinx."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Annotated, get_args, get_type_hints

import pytest
from mcp.server import Server
from pydantic import AllowInfNan, Field
from sphinx.application import Sphinx

from cadrumo.application.user_profile.access_contracts import AccessSession
from cadrumo_harness.mcp.server import build_server
from dev._paths import REPO_ROOT

from ..manager import _public_type_aliases
from ..rendering import format_type_hint

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]
_FORMATTER_INPUTS: list[object] = []


def _recording_formatter(annotation: object, config: object = None) -> str | None:
    _FORMATTER_INPUTS.append(annotation)
    return format_type_hint(annotation, config)


_ALLOW_INF_NAN_ANNOTATION = get_type_hints(AccessSession, include_extras=True)["issued_monotonic"]
_ALLOW_INF_NAN_INSTANCE = next(
    item
    for field_info in get_args(_ALLOW_INF_NAN_ANNOTATION)[1:]
    for item in field_info.metadata
    if isinstance(item, AllowInfNan)
)


def test_regex_metadata_is_rendered_as_source_literal() -> None:
    annotation = "Annotated[str, Field(min_length=32, pattern=r'^[A-Za-z0-9_-]+$')]"

    assert format_type_hint(annotation) == "str ``Field(min_length=32, pattern=r'^[A-Za-z0-9_-]+$')``"


def test_evaluated_regex_metadata_is_rendered_as_source_literal() -> None:
    annotation = Annotated[str, Field(min_length=32, pattern=r"^[A-Za-z0-9_-]+$")]

    rendered = format_type_hint(annotation)

    assert rendered is not None and rendered.startswith("str ``") and rendered.endswith("``")
    assert "pattern='^[A-Za-z0-9_-]+$'" in rendered


def test_allow_inf_nan_metadata_keeps_the_actual_field_constraint() -> None:
    metadata = get_args(_ALLOW_INF_NAN_ANNOTATION)[1:]
    allow_inf_nan = next(
        item for field_info in metadata for item in field_info.metadata if isinstance(item, AllowInfNan)
    )

    rendered = format_type_hint(_ALLOW_INF_NAN_ANNOTATION)

    assert rendered is not None and "AllowInfNan(allow_inf_nan=False)" in rendered
    assert format_type_hint(allow_inf_nan) == (
        "`AllowInfNan <https://pydantic.dev/docs/validation/latest/api/pydantic/types/#pydantic.types.AllowInfNan>`_"
    )


def test_annotated_unknown_base_remains_a_cross_reference() -> None:
    rendered = format_type_hint("Annotated[MissingFirstParty, Field(pattern='^[A-Z]+$')]")

    assert rendered == ":py:class:`MissingFirstParty` ``Field(pattern='^[A-Z]+$')``"


def test_external_api_types_link_to_their_defining_documentation() -> None:
    assert format_type_hint("pydantic.types.AllowInfNan") == (
        "`AllowInfNan <https://pydantic.dev/docs/validation/latest/api/pydantic/types/#pydantic.types.AllowInfNan>`_"
    )
    assert format_type_hint("mcp.server.lowlevel.server.Server") == (
        "`Server <https://py.sdk.modelcontextprotocol.io/api/mcp/server/lowlevel/server/>`_"
    )
    assert format_type_hint("AllowInfNan") is None
    assert format_type_hint("Server") is None
    assert format_type_hint(AllowInfNan) == (
        "`AllowInfNan <https://pydantic.dev/docs/validation/latest/api/pydantic/types/#pydantic.types.AllowInfNan>`_"
    )
    assert format_type_hint(Server) == (
        "`Server <https://py.sdk.modelcontextprotocol.io/api/mcp/server/lowlevel/server/>`_"
    )


def test_unaffected_annotations_use_the_default_formatter() -> None:
    assert format_type_hint("str") is None
    assert format_type_hint("Annotated[str, Field(min_length=1)]") is None


def test_type_alias_class_references_and_regex_fields_render_in_sphinx(tmp_path: Path) -> None:
    """The generated alias target and formatter resolve under nitpicky Sphinx."""
    assert build_server.__annotations__["return"] == "Server"
    docs = tmp_path / "docs"
    docs.mkdir()
    alias_module = "cadrumo_client.transport.automation_decision"
    alias_source = REPO_ROOT / "src" / "cadrumo_client" / "transport" / "automation_decision.py"
    alias_target = "\n".join(_public_type_aliases(alias_module, alias_source))
    assert ".. py:type:: AutomationDecision" in alias_target
    unresolved_reference = format_type_hint("Annotated[MissingFirstParty, Field(pattern='^[A-Z]+$')]")
    assert unresolved_reference is not None

    conf_path = REPO_ROOT / "docs" / "conf.py"
    conf = f"""\
import importlib.util
import os
import sys
from pathlib import Path
from dev.docs.apidocs.tests.test_rendering import _recording_formatter

repo = Path({str(REPO_ROOT)!r})
os.environ["CADRUMO_DOCS_PROJECT_ROOT"] = str(repo)
os.environ["CADRUMO_LOCAL_STORAGE_ROOT"] = {str(tmp_path / "storage")!r}
os.environ["CADRUMO_STORAGE_ROOT"] = {str(tmp_path / "storage")!r}
sys.path.insert(0, str(repo))
sys.path.insert(0, str(repo / "src"))
spec = importlib.util.spec_from_file_location("cadrumo_docs_conf_probe", {str(conf_path)!r})
docs_conf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(docs_conf)

project = "API rendering probe"
extensions = ["sphinx.ext.autodoc", "dev.docs.apidocs.attribute_types", "sphinx_autodoc_typehints"]
master_doc = "index"
nitpicky = True
autodoc_typehints = "description"
autodoc_typehints_format = "short"
typehints_formatter = _recording_formatter
exclude_patterns = []

def setup(app):
    app.connect("missing-reference", docs_conf._resolve_short_reference, priority=700)
"""
    (docs / "conf.py").write_text(conf, encoding="utf-8")
    warnings = io.StringIO()
    _FORMATTER_INPUTS.clear()
    app = Sphinx(
        str(docs),
        str(docs),
        str(tmp_path / "html"),
        str(tmp_path / "doctrees"),
        "html",
        status=io.StringIO(),
        warning=warnings,
        freshenv=True,
        parallel=2,
    )
    assert app.config.typehints_formatter is _recording_formatter
    attribute_extension = app.extensions["dev.docs.apidocs.attribute_types"]
    assert attribute_extension.parallel_read_safe
    assert attribute_extension.parallel_write_safe
    from sphinx_autodoc_typehints import format_annotation

    regex_annotation = Annotated[str, Field(min_length=32, max_length=4096, pattern=r"^[A-Za-z0-9_-]+$")]
    rendered_regex = format_annotation(regex_annotation, app.config)
    rendered_allow_inf_nan = format_annotation(_ALLOW_INF_NAN_ANNOTATION, app.config)
    rendered_allow_inf_nan_type = format_annotation(_ALLOW_INF_NAN_INSTANCE, app.config)
    rendered_server_type = format_annotation(Server, app.config)
    (docs / "index.rst").write_text(
        "API rendering probe\n====================\n\n"
        f"{alias_target}\n"
        ".. py:currentmodule:: cadrumo_client.transport.frame_io\n\n"
        "The decision type is :class:`AutomationDecision`.\n\n"
        f"The production regex-bearing annotation is {rendered_regex}.\n\n"
        f"The production profile field annotation is {rendered_allow_inf_nan}.\n\n"
        f"Its Pydantic metadata type is {rendered_allow_inf_nan_type}.\n\n"
        f"The MCP SDK type is {rendered_server_type}.\n\n"
        "The fully qualified MCP target is :class:`mcp.server.lowlevel.server.Server`.\n\n"
        ".. autoclass:: cadrumo_harness.mcp.runtime_adapter.RuntimeMcpAdapter\n"
        "   :no-members:\n"
        "   :no-signature:\n\n"
        ".. autofunction:: cadrumo_harness.mcp.server.build_server\n\n"
        ".. autoattribute:: cadrumo_agent_service.contracts.ServiceStartupFrame.bearer\n\n"
        ".. autoattribute:: cadrumo_agent_service.contracts.ServiceStartupFrame.gateway_bearer\n\n"
        ".. autoattribute:: cadrumo_client.contracts.extension_records.ExtensionRecordCapability.capability\n\n"
        ".. autoattribute:: cadrumo_client.contracts.extension_records.ExtensionRecordCapability.namespace\n\n"
        f"The unresolved constrained type is {unresolved_reference}.\n",
        encoding="utf-8",
    )
    app.build(force_all=True)

    assert any("pattern=" in repr(annotation) for annotation in _FORMATTER_INPUTS)
    assert any("AllowInfNan(allow_inf_nan=False)" in repr(annotation) for annotation in _FORMATTER_INPUTS)
    assert any(annotation is Server for annotation in _FORMATTER_INPUTS)
    assert "py:class reference target not found: MissingFirstParty" in warnings.getvalue()
    assert "reference target not found: AllowInfNan" not in warnings.getvalue()
    assert "reference target not found: mcp.server.lowlevel.server.Server" not in warnings.getvalue()
    assert "Unknown target name:" not in warnings.getvalue(), warnings.getvalue()
    assert "FieldInfo" not in warnings.getvalue(), warnings.getvalue()
    assert "pattern=" not in warnings.getvalue(), warnings.getvalue()
    rendered_html = (tmp_path / "html" / "index.html").read_text(encoding="utf-8")
    assert "AllowInfNan(allow_inf_nan=False)" in rendered_html
    assert "https://py.sdk.modelcontextprotocol.io/api/mcp/server/lowlevel/server/" in rendered_html
    assert "bearer" in rendered_html and "gateway_bearer" in rendered_html
    assert "capability" in rendered_html and "namespace" in rendered_html
    assert "pattern='^[a-z][a-z0-9_-]{0,63}$'" in rendered_html
