"""Tests for API annotation rendering in Sphinx."""

from __future__ import annotations

import inspect
import io
import pickle
from pathlib import Path
from typing import Annotated, get_args, get_type_hints
from uuid import UUID

import pytest
from mcp.server import Server
from pydantic import AllowInfNan, Field
from sphinx.application import Sphinx

from cadrumo.application.operations.models import CredentialFreeOperationRequest
from cadrumo.application.user_profile.access_administration import FreshPasswordAuthorization
from cadrumo.application.user_profile.access_contracts import AccessEvaluationContext, AccessSession
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_harness.mcp.runtime_adapter import RuntimeMcpAdapter
from cadrumo_harness.mcp.server import build_server
from cadrumo_harness.mcp.surfaces import McpSurface
from cadrumo_runtime.contracts.profile_worker import ProfileWorkerSettlementRequest
from cadrumo_runtime.host.frontend.tui.secret.runtime_login_contracts import (
    RuntimeClientOpener as ContractRuntimeClientOpener,
)
from cadrumo_runtime.host.frontend.tui.secret.runtime_login_session import (
    RuntimeClientOpener as SessionRuntimeClientOpener,
)
from dev._paths import REPO_ROOT

from ..manager import _public_type_aliases
from ..rendering import TypeHintsFormatter, format_type_hint
from ._sphinx_probe import run_sphinx_probe

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


_FRESH_PASSWORD_ANNOTATION = inspect.signature(FreshPasswordAuthorization).parameters["verified_monotonic"].annotation


def _fresh_password_signature_probe(value: object) -> None:
    """Exercise the exact generated constructor annotation through autodoc."""


def _access_session_signature_probe(value: object) -> None:
    """Exercise another actual generated constructor annotation through autodoc."""


def _access_context_signature_probe(value: object) -> None:
    """Exercise a context constructor annotation through autodoc."""


def _worker_signature_probe(value: object) -> None:
    """Exercise a worker constructor annotation through autodoc."""


_SIGNATURE_PROBES = (
    (_fresh_password_signature_probe, FreshPasswordAuthorization, "verified_monotonic"),
    (_access_session_signature_probe, AccessSession, "issued_monotonic"),
    (_access_context_signature_probe, AccessEvaluationContext, "monotonic_now"),
    (_worker_signature_probe, ProfileWorkerSettlementRequest, "wait_seconds"),
)
for _probe, _model, _parameter in _SIGNATURE_PROBES:
    _probe.__annotations__["value"] = inspect.signature(_model).parameters[_parameter].annotation


_ALLOW_INF_NAN_ANNOTATION = get_type_hints(AccessSession, include_extras=True)["issued_monotonic"]
_ALLOW_INF_NAN_INSTANCE = next(
    item
    for field_info in get_args(_ALLOW_INF_NAN_ANNOTATION)[1:]
    for item in field_info.metadata
    if isinstance(item, AllowInfNan)
)


def _canonical_class_target(value: type[object]) -> str:
    """Use an actual imported class's owner for a minimal Sphinx target."""
    return f".. py:class:: {value.__module__}.{value.__qualname__}"


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


def test_generated_constructor_signatures_preserve_finite_float_metadata() -> None:
    constructors = (
        (FreshPasswordAuthorization, "verified_monotonic"),
        (AccessSession, "issued_monotonic"),
        (AccessEvaluationContext, "monotonic_now"),
        (ProfileWorkerSettlementRequest, "wait_seconds"),
    )

    for model, parameter in constructors:
        annotation = inspect.signature(model).parameters[parameter].annotation
        rendered = format_type_hint(annotation)
        assert rendered is not None, f"{model.__name__}.{parameter} bypassed constrained metadata formatting"
        assert "AllowInfNan(allow_inf_nan=False)" in rendered
        assert "AllowInfNan`" not in rendered


def test_typehints_formatter_config_value_is_pickleable() -> None:
    formatter = TypeHintsFormatter()

    serialized = pickle.dumps(formatter)

    assert serialized
    assert formatter("str") is None


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
    assert format_type_hint(ContractRuntimeClientOpener) == (
        ":py:class:`cadrumo_runtime.host.frontend.tui.secret.runtime_login_contracts.RuntimeClientOpener`"
    )
    assert format_type_hint(SessionRuntimeClientOpener) == (
        ":py:class:`cadrumo_runtime.host.frontend.tui.secret.runtime_login_session.RuntimeClientOpener`"
    )


def test_unaffected_annotations_use_the_default_formatter() -> None:
    assert format_type_hint("str") is None
    assert format_type_hint("Annotated[str, Field(min_length=1)]") is None


def test_type_alias_class_references_and_regex_fields_render_in_sphinx(tmp_path: Path) -> None:
    run_sphinx_probe(__name__, "_build_type_alias_and_regex_probe", tmp_path)


def _build_type_alias_and_regex_probe(tmp_path: Path) -> None:
    """The generated alias target and formatter resolve under nitpicky Sphinx."""
    request_annotations = dict(CredentialFreeOperationRequest.__annotations__)
    assert build_server.__annotations__["return"] == "Server"
    dependency_types = (UUID, FrontendClient, McpSurface)
    assert tuple((value.__module__, value.__qualname__) for value in dependency_types) == (
        ("uuid", "UUID"),
        ("cadrumo_client.transport.frontend_client", "FrontendClient"),
        ("cadrumo_harness.mcp.surfaces", "McpSurface"),
    )
    dependency_targets = "\n\n".join(_canonical_class_target(value) for value in dependency_types)
    assert (RuntimeMcpAdapter.__module__, RuntimeMcpAdapter.__qualname__) == (
        "cadrumo_harness.mcp.runtime_adapter",
        "RuntimeMcpAdapter",
    )
    runtime_adapter_target = (
        f".. autoclass:: {RuntimeMcpAdapter.__module__}.{RuntimeMcpAdapter.__qualname__}\n   :no-members:\n\n"
    )
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
from dev.docs.apidocs.rendering import TypeHintsFormatter

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
typehints_formatter = TypeHintsFormatter()
exclude_patterns = []

def setup(app):
    app.connect("missing-reference", docs_conf._resolve_short_reference, priority=700)
"""
    (docs / "conf.py").write_text(conf, encoding="utf-8")
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
        parallel=2,
    )
    assert app.config.typehints_formatter == TypeHintsFormatter()
    attribute_extension = app.extensions["dev.docs.apidocs.attribute_types"]
    assert attribute_extension.parallel_read_safe
    assert attribute_extension.parallel_write_safe
    from sphinx_autodoc_typehints import format_annotation

    regex_annotation = Annotated[str, Field(min_length=32, max_length=4096, pattern=r"^[A-Za-z0-9_-]+$")]
    rendered_regex = format_annotation(regex_annotation, app.config)
    rendered_allow_inf_nan = format_annotation(_ALLOW_INF_NAN_ANNOTATION, app.config)
    rendered_allow_inf_nan_type = format_annotation(_ALLOW_INF_NAN_INSTANCE, app.config)
    rendered_server_type = format_annotation(Server, app.config)
    constructor_annotations = tuple(
        inspect.signature(model).parameters[parameter].annotation
        for model, parameter in (
            (FreshPasswordAuthorization, "verified_monotonic"),
            (AccessSession, "issued_monotonic"),
            (AccessEvaluationContext, "monotonic_now"),
            (ProfileWorkerSettlementRequest, "wait_seconds"),
        )
    )
    rendered_constructor_annotations = tuple(
        format_annotation(annotation, app.config) for annotation in constructor_annotations
    )
    assert all("AllowInfNan(allow_inf_nan=False)" in rendered for rendered in rendered_constructor_annotations)
    (docs / "index.rst").write_text(
        "API rendering probe\n====================\n\n"
        f"{alias_target}\n"
        ".. py:currentmodule:: cadrumo_client.transport.frame_io\n\n"
        "The decision type is :class:`AutomationDecision`.\n\n"
        ".. py:type:: RuntimeClientOpener\n"
        "   :module: cadrumo_runtime.host.frontend.tui.secret.runtime_login_contracts\n\n"
        ".. py:type:: RuntimeClientOpener\n"
        "   :module: cadrumo_runtime.host.frontend.tui.secret.runtime_login_session\n\n"
        ".. py:currentmodule:: cadrumo_runtime.host.frontend.tui.runtime_admission\n\n"
        "The imported runtime opener is :class:`RuntimeClientOpener`.\n\n"
        f"The production regex-bearing annotation is {rendered_regex}.\n\n"
        f"The production profile field annotation is {rendered_allow_inf_nan}.\n\n"
        f"The constructor field annotation is {rendered_constructor_annotations[0]}.\n\n"
        f"Its Pydantic metadata type is {rendered_allow_inf_nan_type}.\n\n"
        f"The MCP SDK type is {rendered_server_type}.\n\n"
        "The fully qualified MCP target is :class:`mcp.server.lowlevel.server.Server`.\n\n"
        f"{runtime_adapter_target}"
        f"{dependency_targets}\n\n"
        ".. autoattribute:: cadrumo.application.operations.models.CredentialFreeOperationRequest.model_config\n"
        "   :annotation:\n"
        "   :no-value:\n\n"
        ".. autofunction:: cadrumo_harness.mcp.server.build_server\n\n"
        ".. autofunction:: dev.docs.apidocs.tests.test_rendering._fresh_password_signature_probe\n\n"
        ".. autofunction:: dev.docs.apidocs.tests.test_rendering._access_session_signature_probe\n\n"
        ".. autofunction:: dev.docs.apidocs.tests.test_rendering._access_context_signature_probe\n\n"
        ".. autofunction:: dev.docs.apidocs.tests.test_rendering._worker_signature_probe\n\n"
        ".. autoattribute:: cadrumo_agent_service.contracts.ServiceStartupFrame.bearer\n\n"
        ".. autoattribute:: cadrumo_agent_service.contracts.ServiceStartupFrame.gateway_bearer\n\n"
        ".. autoattribute:: cadrumo_client.contracts.extension_records.ExtensionRecordCapability.capability\n\n"
        ".. autoattribute:: cadrumo_client.contracts.extension_records.ExtensionRecordCapability.namespace\n\n"
        f"The unresolved constrained type is {unresolved_reference}.\n",
        encoding="utf-8",
    )
    app.build(force_all=True)

    assert CredentialFreeOperationRequest.__annotations__ == request_annotations
    assert "__pydantic_extra__" not in CredentialFreeOperationRequest.__annotations__
    from cadrumo.application.user_profile import operations
    from cadrumo.application.user_profile.view_operation import ProfileViewOperationRequest

    request_schema = ProfileViewOperationRequest.model_json_schema()
    assert request_schema["title"] == "ProfileViewOperationRequest"
    assert "profile_id" in request_schema["properties"]
    assert any(
        definition.request_type is ProfileViewOperationRequest
        for definition in operations.build_user_profile_operation_definitions()
    )

    diagnostics = [
        line.partition(marker)[2].rsplit(" [", maxsplit=1)[0]
        for line in warnings.getvalue().splitlines()
        for marker in ("ERROR: ", "WARNING: ")
        if marker in line
    ]
    assert diagnostics == ["py:class reference target not found: MissingFirstParty"], warnings.getvalue()
    rendered_html = (tmp_path / "html" / "index.html").read_text(encoding="utf-8")
    assert "AllowInfNan(allow_inf_nan=False)" in rendered_html
    assert rendered_html.count("Constraint for") >= 4
    assert "https://py.sdk.modelcontextprotocol.io/api/mcp/server/lowlevel/server/" in rendered_html
    assert "cadrumo_runtime.host.frontend.tui.secret.runtime_login_contracts.RuntimeClientOpener" in rendered_html
    assert "bearer" in rendered_html and "gateway_bearer" in rendered_html
    assert "capability" in rendered_html and "namespace" in rendered_html
    assert "pattern='^[a-z][a-z0-9_-]{0,63}$'" in rendered_html
