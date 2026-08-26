"""Independent parity and absence gates for non-work Modelo command authority."""

from __future__ import annotations

import ast
import importlib
import inspect
from pathlib import Path

import pytest

from .._command_runtime import _behavior_wrapper
from .._modelo_nonwork_command_specs import MODELO_NONWORK_COMMAND_SPECS

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_EXPECTED_KEYS = {
    "app_modelo_aggregate",
    "app_modelo_bindings",
    "app_modelo_bindings_list",
    "app_modelo_bindings_resolve",
    "app_modelo_casilla",
    "app_modelo_casillas",
    "app_modelo_describe",
    "app_modelo_export",
    "app_modelo_filing_record",
    "app_modelo_filing_record_import",
    "app_modelo_filing_record_list",
    "app_modelo_filing_record_observe_local",
    "app_modelo_filing_record_view",
    "app_modelo_formulas",
    "app_modelo_iva_wallet",
    "app_modelo_iva_wallet_balance",
    "app_modelo_iva_wallet_correct",
    "app_modelo_iva_wallet_override",
    "app_modelo_iva_wallet_seed",
    "app_modelo_list",
    "app_modelo_m036",
    "app_modelo_m036_alta",
    "app_modelo_m036_baja",
    "app_modelo_m036_list",
    "app_modelo_m036_modificacion",
    "app_modelo_m036_view",
    "app_modelo_m145",
    "app_modelo_m145_create",
    "app_modelo_m145_export",
    "app_modelo_m145_mark_delivered_to_payer",
    "app_modelo_m145_mark_locally_completed",
    "app_modelo_m145_validate",
    "app_modelo_reconcile",
    "app_modelo_reconcile_import",
    "app_modelo_reconcile_list",
    "app_modelo_reconcile_pull",
    "app_modelo_requires",
    "app_modelo_review_package",
    "app_modelo_review_package_build",
    "app_modelo_review_package_counter_sign",
    "app_modelo_review_package_decrypt",
    "app_modelo_review_package_encrypt_feedback",
    "app_modelo_review_package_encrypt_for_recipient",
    "app_modelo_review_package_import_feedback",
    "app_modelo_review_package_sign",
    "app_modelo_review_package_verify",
    "app_modelo_review_package_verify_receipt",
    "app_modelo_review_package_verify_signature",
    "app_modelo_support_matrix",
    "app_modelo_verification_report",
    "app_modelo_verification_report_list",
    "app_modelo_verification_report_view",
    "app_modelo_work_amend_wizard",
    "app_modelo_work_preview_maritime_exemption",
}

_HANDLER_MODULES = {
    spec.handler.target.module
    for spec in MODELO_NONWORK_COMMAND_SPECS
    if spec.handler is not None and spec.handler.target is not None
}


def test_nonwork_modelo_specs_are_the_exact_54_node_set() -> None:
    assert len(MODELO_NONWORK_COMMAND_SPECS) == 54
    assert {spec.key for spec in MODELO_NONWORK_COMMAND_SPECS} == _EXPECTED_KEYS
    assert sum(spec.kind == "group" for spec in MODELO_NONWORK_COMMAND_SPECS) == 8
    assert sum(spec.kind == "leaf" for spec in MODELO_NONWORK_COMMAND_SPECS) == 46
    assert sum(len(spec.parameters) for spec in MODELO_NONWORK_COMMAND_SPECS) == 197


def test_every_nonwork_target_is_public_resolvable_and_runtime_materializable() -> None:
    executable = tuple(spec for spec in MODELO_NONWORK_COMMAND_SPECS if spec.handler is not None)
    assert len(executable) == 46
    for spec in executable:
        assert spec.handler is not None and spec.handler.target is not None
        target = spec.handler.target
        assert "<locals>" not in target.qualname
        assert not target.qualname.startswith("_")
        behavior = getattr(importlib.import_module(target.module), target.qualname)
        assert callable(behavior)
        behavior_parameters = {name for name in inspect.signature(behavior).parameters if name != "ctx"}
        assert behavior_parameters == {parameter.name for parameter in spec.parameters}
        _behavior_wrapper(spec)


def test_nonwork_handlers_and_schemas_have_no_legacy_authority() -> None:
    root = Path(__file__).parents[1]
    forbidden_calls = {"Typer", "Option", "Argument", "command_execution_policy", "declare_metadata_group"}
    for module_name in _HANDLER_MODULES:
        source = root / f"{module_name.rsplit('.', 1)[-1]}.py"
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                assert "register" not in node.name
                assert not node.decorator_list
            if isinstance(node, ast.Call):
                name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
                assert name not in forbidden_calls
                assert name != "add_typer"

    identities = {
        spec.result_schema.identity for spec in MODELO_NONWORK_COMMAND_SPECS if spec.result_schema.identity is not None
    }
    for source in root.glob("*payload*.py"):
        text = source.read_text(encoding="utf-8")
        for identity in identities:
            assert f'@register_schema("{identity}")' not in text
