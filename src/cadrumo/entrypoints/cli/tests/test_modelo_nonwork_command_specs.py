"""Independent parity and absence gates for non-work Modelo command authority."""

from __future__ import annotations

import ast
import importlib
import inspect
from pathlib import Path

import pytest

from .._command_runtime import _behavior_wrapper
from .._modelo_nonwork_bindings_command_specs import (
    _AS_OF_OPTION,
    _BINDINGS_INVOCATION,
    _BINDINGS_SCOPE,
    _MODELO_OPTION,
    _PERIOD_OPTION,
    _YEAR_OPTION,
    MODELO_NONWORK_BINDINGS_COMMAND_SPECS,
)
from .._modelo_nonwork_command_spec_policies import _INTERACTIVE_MODEL_WRITE
from .._modelo_nonwork_command_specs import MODELO_NONWORK_COMMAND_SPECS
from .._modelo_nonwork_discovery_command_specs import (
    _REGISTRY_YEAR_OPTION,
    CASILLA_LOOKUP_SCOPE,
    MODELO_NONWORK_DISCOVERY_COMMAND_SPECS,
)
from .._modelo_nonwork_m036_command_specs import (
    M036_DECLARATION_PARAMETERS,
    MODELO_NONWORK_M036_COMMAND_SPECS,
)
from .._modelo_nonwork_m145_command_specs import (
    M145_ACTOR_PARAMETER,
    M145_COMMUNICATION_RECORD_ID_PARAMETER,
    M145_RECORD_ACTION_PARAMETERS,
    MODELO_NONWORK_M145_COMMAND_SPECS,
)
from .._modelo_nonwork_reconcile_command_specs import (
    MODELO_NONWORK_RECONCILE_COMMAND_SPECS,
    RECONCILE_TARGET_PARAMETERS,
)
from .._modelo_nonwork_review_package_command_specs import (
    _REVIEW_PACKAGE_BUCKET_ID_OPTION,
    _REVIEW_PACKAGE_INPUT,
    _SIGNATURE_INPUT,
    MODELO_NONWORK_REVIEW_PACKAGE_COMMAND_SPECS,
)
from .._modelo_nonwork_work_amend_command_specs import MODELO_NONWORK_WORK_AMEND_COMMAND_SPECS
from .._modelo_work_command_specs import _ADDRESS, _LANGUAGE, _a, _o
from ..command_spec import CommandNodeKind, SchemaState, TranslationKey
from ..command_specs import COMMAND_GRAPH

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


def test_bindings_parameters_keep_exact_order_and_identity() -> None:
    specs = {spec.key: spec for spec in MODELO_NONWORK_BINDINGS_COMMAND_SPECS}
    list_spec = specs["app_modelo_bindings_list"]
    resolve_spec = specs["app_modelo_bindings_resolve"]

    assert type(_BINDINGS_SCOPE) is tuple
    assert tuple(parameter.name for parameter in _BINDINGS_SCOPE) == ("modelo", "year", "period")
    assert _BINDINGS_SCOPE[0] is _MODELO_OPTION
    assert _BINDINGS_SCOPE[1] is _YEAR_OPTION
    assert _BINDINGS_SCOPE[2] is _PERIOD_OPTION
    assert tuple(parameter.name for parameter in list_spec.parameters) == (
        "modelo",
        "year",
        "period",
        "missing",
        "as_of",
    )
    assert tuple(parameter.name for parameter in resolve_spec.parameters) == (
        "modelo",
        "year",
        "period",
        "binding",
        "as_of",
    )

    for parameters in (list_spec.parameters, resolve_spec.parameters):
        assert all(actual is expected for actual, expected in zip(parameters[:3], _BINDINGS_SCOPE, strict=True))
        assert parameters[-1] is _AS_OF_OPTION
    assert list_spec.parameters[3].name == "missing"
    assert resolve_spec.parameters[3].name == "binding"
    assert list_spec.parameters[3] is not resolve_spec.parameters[3]
    assert list_spec.invocation is _BINDINGS_INVOCATION
    assert resolve_spec.invocation is _BINDINGS_INVOCATION

    # The shared options do not collapse the command-specific behavior contract.
    assert list_spec.handler is not resolve_spec.handler
    assert list_spec.policy is resolve_spec.policy
    assert list_spec.result_schema is not resolve_spec.result_schema

    assert COMMAND_GRAPH.resolve_path(("aeat", "app", "modelo", "bindings", "list")) is list_spec
    assert COMMAND_GRAPH.resolve_path(("aeat", "app", "modelo", "bindings", "resolve")) is resolve_spec


def test_discovery_lookup_parameters_keep_exact_order_and_identity() -> None:
    specs = {spec.key: spec for spec in MODELO_NONWORK_DISCOVERY_COMMAND_SPECS}
    expected_orders = {
        "app_modelo_list": ("year", "domain"),
        "app_modelo_describe": ("modelo", "year", "period", "as_of"),
        "app_modelo_casillas": (
            "modelo",
            "year",
            "period",
            "as_of",
            "input_kind",
            "required",
            "form_number",
            "casilla_number",
            "explain",
        ),
        "app_modelo_casilla": ("modelo", "casilla_id", "year", "period", "as_of"),
    }

    assert type(CASILLA_LOOKUP_SCOPE) is tuple
    assert tuple(parameter.name for parameter in CASILLA_LOOKUP_SCOPE) == (
        "modelo",
        "year",
        "period",
        "as_of",
    )
    assert _REGISTRY_YEAR_OPTION.name == "year"
    assert _REGISTRY_YEAR_OPTION.declarations == ("--year",)
    assert {
        key: tuple(parameter.name for parameter in specs[key].parameters) for key in expected_orders
    } == expected_orders
    assert specs["app_modelo_list"].parameters[0] is _REGISTRY_YEAR_OPTION
    assert specs["app_modelo_describe"].parameters[1] is _REGISTRY_YEAR_OPTION
    assert all(
        actual is expected
        for actual, expected in zip(specs["app_modelo_casillas"].parameters[:4], CASILLA_LOOKUP_SCOPE, strict=True)
    )
    casilla_parameters = specs["app_modelo_casilla"].parameters
    assert casilla_parameters[0] is CASILLA_LOOKUP_SCOPE[0]
    assert casilla_parameters[1] is not CASILLA_LOOKUP_SCOPE[0]
    assert all(
        actual is expected for actual, expected in zip(casilla_parameters[2:], CASILLA_LOOKUP_SCOPE[1:], strict=True)
    )
    for token, key in (
        ("list", "app_modelo_list"),
        ("describe", "app_modelo_describe"),
        ("casillas", "app_modelo_casillas"),
        ("casilla", "app_modelo_casilla"),
    ):
        assert COMMAND_GRAPH.resolve_path(("aeat", "app", "modelo", token)) is specs[key]


def test_reconcile_target_parameters_keep_order_and_import_extras_local() -> None:
    specs = {spec.key: spec for spec in MODELO_NONWORK_RECONCILE_COMMAND_SPECS}
    pull = specs["app_modelo_reconcile_pull"]
    imported = specs["app_modelo_reconcile_import"]

    assert type(RECONCILE_TARGET_PARAMETERS) is tuple
    assert tuple(parameter.name for parameter in RECONCILE_TARGET_PARAMETERS) == (
        "work_unit_id",
        "modelo",
        "year",
        "period",
        "revision",
        "bucket_id",
        "actor",
    )
    assert pull.parameters is RECONCILE_TARGET_PARAMETERS
    assert tuple(parameter.name for parameter in imported.parameters) == (
        "work_unit_id",
        "file",
        "modelo",
        "year",
        "period",
        "revision",
        "bucket_id",
        "actor",
        "kind",
    )
    assert imported.parameters[0] is RECONCILE_TARGET_PARAMETERS[0]
    assert all(
        actual is expected
        for actual, expected in zip(imported.parameters[2:8], RECONCILE_TARGET_PARAMETERS[1:], strict=True)
    )
    assert pull.policy is not imported.policy
    assert pull.handler is not imported.handler
    assert pull.result_schema is not imported.result_schema
    assert COMMAND_GRAPH.resolve_path(("aeat", "app", "modelo", "reconcile", "pull")) is pull
    assert COMMAND_GRAPH.resolve_path(("aeat", "app", "modelo", "reconcile", "import")) is imported


def test_work_amend_wizard_parameters_reuse_the_canonical_work_kernel() -> None:
    wizard = MODELO_NONWORK_WORK_AMEND_COMMAND_SPECS[0]
    expected = (
        _a("work_unit_id"),
        *_ADDRESS,
        _o("actor", "--by"),
        _o("output_language_opt", "--output-language", _LANGUAGE, help_name="output_language"),
    )

    assert wizard.key == "app_modelo_work_amend_wizard"
    assert wizard.parent_key == "app_modelo_work"
    assert wizard.kind is CommandNodeKind.LEAF
    assert wizard.help_key.value == "cli.app.modelo.work.amend_wizard_help"
    assert wizard.short_help_key is None
    assert wizard.invocation.context_parameter == "ctx"
    assert wizard.invocation.no_args_is_help is False
    assert tuple(parameter.name for parameter in wizard.parameters) == (
        "work_unit_id",
        "modelo",
        "year",
        "period",
        "revision",
        "bucket_id",
        "actor",
        "output_language_opt",
    )
    assert tuple(parameter.help_key for parameter in wizard.parameters) == (
        TranslationKey("cli.app.modelo.work.work_unit_id_help"),
        TranslationKey("cli.app.modelo.work.modelo_help"),
        TranslationKey("cli.app.modelo.work.year_help"),
        TranslationKey("cli.app.modelo.work.period_help"),
        TranslationKey("cli.app.modelo.work.revision_help"),
        TranslationKey("cli.app.modelo.work.bucket_id_help"),
        TranslationKey("cli.app.modelo.work.actor_help"),
        TranslationKey("cli.app.modelo.work.output_language_help"),
    )
    assert wizard.parameters == expected
    assert all(actual is expected for actual, expected in zip(wizard.parameters[1:6], _ADDRESS, strict=True))
    assert wizard.policy is _INTERACTIVE_MODEL_WRITE
    assert wizard.handler is not None and wizard.handler.target is not None
    assert wizard.handler.target.module == "cadrumo.entrypoints.cli._modelo_amend_wizard_cli"
    assert wizard.handler.target.qualname == "work_amend_wizard"
    assert wizard.result_schema.state is SchemaState.TARGET
    assert wizard.result_schema.target is not None
    assert wizard.result_schema.target.module == "cadrumo.entrypoints.cli._modelo_amend_wizard_payloads"
    assert wizard.result_schema.target.qualname == "WorkAmendWizardResult"
    assert wizard.result_schema.identity == "modelo.work.amend_wizard"
    assert COMMAND_GRAPH.resolve_path(("aeat", "app", "modelo", "work", "amend-wizard")) is wizard


def test_m036_declaration_parameters_keep_exact_order_and_identity() -> None:
    specs = {spec.key: spec for spec in MODELO_NONWORK_M036_COMMAND_SPECS}
    declaration_keys = (
        "app_modelo_m036_alta",
        "app_modelo_m036_modificacion",
        "app_modelo_m036_baja",
    )

    assert type(M036_DECLARATION_PARAMETERS) is tuple
    assert tuple(parameter.name for parameter in M036_DECLARATION_PARAMETERS) == (
        "declared_on",
        "sede_justificante",
        "note",
    )
    assert tuple(parameter.declarations for parameter in M036_DECLARATION_PARAMETERS) == (
        ("--declared-on",),
        ("--sede-justificante",),
        ("--note",),
    )
    assert all(specs[key].parameters is M036_DECLARATION_PARAMETERS for key in declaration_keys)


def test_m145_record_action_parameters_keep_adjudicated_order_and_identity() -> None:
    specs = {spec.key: spec for spec in MODELO_NONWORK_M145_COMMAND_SPECS}
    record_action_keys = (
        "app_modelo_m145_export",
        "app_modelo_m145_mark_delivered_to_payer",
        "app_modelo_m145_mark_locally_completed",
    )

    assert type(M145_RECORD_ACTION_PARAMETERS) is tuple
    assert tuple(parameter.name for parameter in M145_RECORD_ACTION_PARAMETERS) == (
        "communication_record_id",
        "actor",
    )
    assert M145_RECORD_ACTION_PARAMETERS[0] is M145_COMMUNICATION_RECORD_ID_PARAMETER
    assert M145_RECORD_ACTION_PARAMETERS[1] is M145_ACTOR_PARAMETER
    validate_parameters = specs["app_modelo_m145_validate"].parameters
    assert validate_parameters == (M145_COMMUNICATION_RECORD_ID_PARAMETER,)
    assert validate_parameters[0] is M145_COMMUNICATION_RECORD_ID_PARAMETER
    assert validate_parameters is not M145_RECORD_ACTION_PARAMETERS
    assert all(specs[key].parameters is M145_RECORD_ACTION_PARAMETERS for key in record_action_keys)
    create_parameters = specs["app_modelo_m145_create"].parameters
    assert create_parameters[-1] is M145_ACTOR_PARAMETER
    assert tuple(parameter.name for parameter in create_parameters) == (
        "year",
        "period",
        "casilla",
        "note",
        "actor",
    )
    assert all(parameter is not M145_COMMUNICATION_RECORD_ID_PARAMETER for parameter in create_parameters)


def test_review_package_shared_inputs_keep_exact_order_and_identity() -> None:
    specs = {spec.key: spec for spec in MODELO_NONWORK_REVIEW_PACKAGE_COMMAND_SPECS}
    expected_orders = {
        "app_modelo_review_package_build": (
            "work_unit_id",
            "modelo",
            "year",
            "period",
            "registry_revision",
            "bucket_id",
            "select",
            "output",
            "revision",
            "actor",
            "refund_election",
            "payment_election",
            "prior_domiciliation_election",
            "notes",
        ),
        "app_modelo_review_package_verify": ("package",),
        "app_modelo_review_package_sign": ("package", "output", "bucket_id"),
        "app_modelo_review_package_verify_signature": ("package", "signature", "public_key"),
        "app_modelo_review_package_counter_sign": ("package", "signature", "output", "note", "bucket_id"),
        "app_modelo_review_package_verify_receipt": (
            "package",
            "receipt_path",
            "operator_public_key",
            "counter_signer_public_key",
        ),
        "app_modelo_review_package_encrypt_for_recipient": (
            "package",
            "recipient_id",
            "output",
            "review_only",
            "valid_for_days",
            "bucket_id",
        ),
        "app_modelo_review_package_decrypt": ("envelope_path", "output", "bucket_id"),
        "app_modelo_review_package_encrypt_feedback": (
            "originator_id",
            "work_unit_id",
            "calculation_revision_id",
            "submitted_by",
            "output",
            "note",
            "receipt",
            "bucket_id",
        ),
        "app_modelo_review_package_import_feedback": (
            "envelope_path",
            "package",
            "operator_public_key_hex",
            "counter_signer_public_key_hex",
            "bucket_id",
        ),
    }
    assert {
        key: tuple(parameter.name for parameter in spec.parameters) for key, spec in specs.items()
    } == expected_orders

    for key in (
        "app_modelo_review_package_verify",
        "app_modelo_review_package_sign",
        "app_modelo_review_package_verify_signature",
        "app_modelo_review_package_counter_sign",
        "app_modelo_review_package_verify_receipt",
        "app_modelo_review_package_encrypt_for_recipient",
    ):
        assert specs[key].parameters[0] is _REVIEW_PACKAGE_INPUT
    for key in (
        "app_modelo_review_package_verify_signature",
        "app_modelo_review_package_counter_sign",
    ):
        assert specs[key].parameters[1] is _SIGNATURE_INPUT
    for key in (
        "app_modelo_review_package_sign",
        "app_modelo_review_package_counter_sign",
        "app_modelo_review_package_encrypt_for_recipient",
        "app_modelo_review_package_decrypt",
        "app_modelo_review_package_encrypt_feedback",
        "app_modelo_review_package_import_feedback",
    ):
        assert specs[key].parameters[-1] is _REVIEW_PACKAGE_BUCKET_ID_OPTION

    build = specs["app_modelo_review_package_build"]
    assert build.parameters[5].name == "bucket_id"
    assert build.parameters[5] is not _REVIEW_PACKAGE_BUCKET_ID_OPTION
    imported = specs["app_modelo_review_package_import_feedback"]
    assert imported.parameters[1].name == "package"
    assert imported.parameters[1] is not _REVIEW_PACKAGE_INPUT


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
        _behavior_wrapper(COMMAND_GRAPH, spec)


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
