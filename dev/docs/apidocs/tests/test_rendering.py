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
from dev._paths import REPO_ROOT
from cadrumo_harness.mcp.server import build_server

from ..manager import _public_type_aliases
from ..rendering import format_type_hint

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]
_FORMATTER_INPUTS: list[object] = []


def _recording_formatter(annotation: object, config: object = None) -> str | None:
    _FORMATTER_INPUTS.append(annotation)
    return format_type_hint(annotation, config)


def _regex_annotation_probe(
    value: Annotated[str, Field(min_length=32, max_length=4096, pattern=r"^[A-Za-z0-9_-]+$")],
) -> Annotated[str, Field(min_length=32, max_length=4096, pattern=r"^[A-Za-z0-9_-]+$")]:
    """Carry an evaluated regex-bearing annotation through autodoc.

    :param value: The constrained test value.
    :returns: The same value.
    """
    return value


def _allow_inf_nan_annotation_probe(value: float) -> float:
    """Render the exact evaluated annotation of a production Pydantic field.

    :param value: The production non-finite-number field contract.
    :returns: The unchanged value.
    """
    return value


_ALLOW_INF_NAN_ANNOTATION = get_type_hints(AccessSession, include_extras=True)["issued_monotonic"]
_allow_inf_nan_annotation_probe.__annotations__["value"] = _ALLOW_INF_NAN_ANNOTATION
_allow_inf_nan_annotation_probe.__annotations__["return"] = _ALLOW_INF_NAN_ANNOTATION


def _mcp_server_annotation_probe(server: Server) -> Server:
    """Carry the installed MCP SDK Server object through autodoc.

    :param server: An SDK server instance.
    :returns: The same server instance.
    """
    return server


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
    allow_inf_nan = next(item for item in metadata if isinstance(item, AllowInfNan))

    rendered = format_type_hint(_ALLOW_INF_NAN_ANNOTATION)

    assert rendered is not None and "AllowInfNan(allow_inf_nan=False)" in rendered
    assert format_type_hint(allow_inf_nan) == (
        "`AllowInfNan <https://pydantic.dev/docs/validation/latest/api/pydantic/types/#pydantic.types.AllowInfNan>`_"
    )


def test_annotated_unknown_base_remains_a_cross_reference() -> None:
    rendered = format_type_hint("Annotated[MissingFirstParty, Field(pattern='^[A-Z]+$')]")

    assert rendered == ":py:class:`MissingFirstParty` ``Field(pattern='^[A-Z]+$')``"


def test_external_api_types_link_to_their_defining_documentation() -> None:
    assert format_type_hint("AllowInfNan") == (
        "`AllowInfNan <https://pydantic.dev/docs/validation/latest/api/pydantic/types/#pydantic.types.AllowInfNan>`_"
    )
    assert format_type_hint("mcp.server.lowlevel.server.Server") == (
        "`Server <https://py.sdk.modelcontextprotocol.io/api/mcp/server/lowlevel/server/>`_"
    )
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
extensions = ["sphinx.ext.autodoc", "sphinx_autodoc_typehints"]
master_doc = "index"
nitpicky = True
autodoc_typehints = "description"
autodoc_typehints_format = "short"
typehints_formatter = None
exclude_patterns = []

def setup(app):
    app.connect("missing-reference", docs_conf._resolve_short_reference, priority=700)
"""
    (docs / "conf.py").write_text(conf, encoding="utf-8")
    (docs / "index.rst").write_text(
        "API rendering probe\n====================\n\n"
        f"{alias_target}\n"
        ".. py:currentmodule:: cadrumo_client.transport.frame_io\n\n"
        "The decision type is :class:`AutomationDecision`.\n\n"
        ".. autofunction:: dev.docs.apidocs.tests.test_rendering._regex_annotation_probe\n\n"
        ".. autofunction:: dev.docs.apidocs.tests.test_rendering._allow_inf_nan_annotation_probe\n\n"
        ".. autofunction:: dev.docs.apidocs.tests.test_rendering._mcp_server_annotation_probe\n\n"
        ".. autofunction:: cadrumo_harness.mcp.server.build_server\n\n"
        f"The unresolved constrained type is {unresolved_reference}.\n",
        encoding="utf-8",
    )
    warnings = io.StringIO()
    app = Sphinx(
        str(docs),
        str(docs),
        str(tmp_path / "html"),
        str(tmp_path / "doctrees"),
        "html",
        status=io.StringIO(),
        warning=warnings,
        freshenv=True,
    )
    _FORMATTER_INPUTS.clear()
    app.config.typehints_formatter = _recording_formatter

    app.build(force_all=True)

    assert any("pattern=" in repr(annotation) for annotation in _FORMATTER_INPUTS)
    assert any("AllowInfNan(allow_inf_nan=False)" in repr(annotation) for annotation in _FORMATTER_INPUTS)
    assert any(annotation is Server for annotation in _FORMATTER_INPUTS)
    assert "py:class reference target not found: MissingFirstParty" in warnings.getvalue()
    assert "reference target not found: AllowInfNan" not in warnings.getvalue()
    assert "reference target not found: mcp.server.lowlevel.server.Server" not in warnings.getvalue()
    assert "FieldInfo" not in warnings.getvalue(), warnings.getvalue()
    assert "pattern=" not in warnings.getvalue()
    rendered_html = (tmp_path / "html" / "index.html").read_text(encoding="utf-8")
    assert "AllowInfNan(allow_inf_nan=False)" in rendered_html
    assert "https://py.sdk.modelcontextprotocol.io/api/mcp/server/lowlevel/server/" in rendered_html
