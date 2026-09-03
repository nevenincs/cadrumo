"""Exact-set and contract gates for the import-light app live authority."""

from __future__ import annotations

import ast
from importlib import import_module
from pathlib import Path

import pytest
from typer.main import get_command

from ....core.transport_locus import TransportLocus, TransportRole, TransportShape
from .._app_live_command_spec_support import (
    _ENCRYPTED_LOCAL_READ_POLICY,
    _LEAF_INVOCATION,
    _METADATA_GROUP_INVOCATION,
    _METADATA_POLICY,
    _OPTIONAL_MODELOS_OPTION,
    _OPTIONAL_TAXPAYER_NIF_OPTION,
    _OPTIONAL_YEAR_FROM_OPTION,
    _OPTIONAL_YEAR_TO_OPTION,
    _OPTIONAL_YEAR_OPTION,
    _OUTPUT_ROOT_OPTION,
    _PROFILE_BOUND_NETWORK_CAPTURE_POLICY,
    _REQUIRED_FILING_YEAR_OPTION,
    _REQUIRED_MODELO_OPTION,
    _REQUIRED_PERIOD_OPTION,
    _REQUIRED_YEAR_FROM_OPTION,
    _REQUIRED_YEAR_OPTION,
    _REQUIRED_YEAR_TO_OPTION,
    NO_RESULT_SCHEMA,
)
from .._app_live_command_specs import LIVE_COMMAND_SPECS
from .._app_live_borrador_command_specs import LIVE_BORRADOR_COMMAND_SPECS
from .._app_live_deudas_command_specs import LIVE_DEUDAS_COMMAND_SPECS
from .._app_live_expedientes_command_specs import LIVE_EXPEDIENTES_COMMAND_SPECS
from .._app_live_foundation_command_specs import LIVE_FOUNDATION_COMMAND_SPECS
from .._app_live_iva_wallet_command_specs import LIVE_IVA_WALLET_COMMAND_SPECS
from .._app_live_justificante_command_specs import LIVE_JUSTIFICANTE_COMMAND_SPECS
from .._app_live_notifications_command_specs import (
    _NOTIFICATION_CERTIFICADO_ID_ARGUMENT,
    LIVE_NOTIFICATIONS_COMMAND_SPECS,
)
from .._app_live_portals_command_specs import LIVE_PORTALS_COMMAND_SPECS
from .._app_live_verify_command_specs import _VERIFY_EXPECTED_OPTION, LIVE_VERIFY_COMMAND_SPECS
from .._command_runtime import build_command_subtree
from .._root_command_specs import ROOT_COMMAND_SPECS
from ..command_spec import (
    BindingState,
    CommandSpecGraph,
    CommandWriteRoute,
    DeferredTarget,
    ExecutionPolicySpec,
    InvocationSpec,
    LazyBinding,
    OptionSpec,
    ParameterConstraint,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    ValueContract,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


EXPECTED_LIVE_PATHS = {
    "app live",
    "app live borrador",
    "app live borrador 100",
    "app live borrador 100 import",
    "app live borrador 100 latest",
    "app live borrador 100 list",
    "app live borrador 100 view",
    "app live deudas",
    "app live deudas latest",
    "app live deudas list",
    "app live deudas view",
    "app live expedientes",
    "app live expedientes latest",
    "app live expedientes list",
    "app live expedientes pull",
    "app live expedientes view",
    "app live filed",
    "app live filed discover",
    "app live filed list",
    "app live filed pull",
    "app live filed pull-all",
    "app live filed pull-sources",
    "app live iva-wallet",
    "app live iva-wallet history",
    "app live iva-wallet pull",
    "app live iva-wallet pull-evidence",
    "app live iva-wallet pull-history",
    "app live justificante",
    "app live justificante list",
    "app live justificante pull",
    "app live justificante view",
    "app live notifications",
    "app live notifications document",
    "app live notifications document history",
    "app live notifications document pull",
    "app live notifications document view",
    "app live notifications latest",
    "app live notifications list",
    "app live notifications pull",
    "app live notifications view",
    "app live portals",
    "app live portals list",
    "app live portals view",
    "app live verify",
    "app live verify latest",
    "app live verify list",
    "app live verify nif-iva",
    "app live verify tgvi",
    "app live verify view",
}


def _resolve(binding: LazyBinding) -> object:
    assert binding.state is BindingState.TARGET
    assert binding.target is not None
    value: object = import_module(binding.target.module)
    for part in binding.target.qualname.split("."):
        value = getattr(value, part)
    return value


def _assert_shared_option_contract(
    option: OptionSpec,
    *,
    name: str,
    declarations: tuple[str, ...],
    value: DeferredTarget,
    default: ParameterDefault,
    help_key: str,
    constraint: ParameterConstraint,
    multiple: bool = False,
    transport_locus: TransportLocus = TransportLocus.NONE,
    transport_shape: TransportShape = TransportShape.NOT_APPLICABLE,
    transport_role: TransportRole = TransportRole.NOT_APPLICABLE,
) -> None:
    assert option.name == name
    assert option.declarations == declarations
    assert option.value == ValueContract(value)
    assert option.default == default
    assert option.help_key is not None
    assert option.help_key.value == help_key
    assert option.multiple is multiple
    assert option.is_flag is False
    assert option.flag_value is None
    assert option.constraint == constraint
    assert option.transport_locus is transport_locus
    assert option.transport_shape is transport_shape
    assert option.transport_role is transport_role


def test_live_shared_support_contracts_are_independently_pinned() -> None:
    assert _METADATA_GROUP_INVOCATION == InvocationSpec(no_args_is_help=True, context_parameter=None)
    assert _LEAF_INVOCATION == InvocationSpec(no_args_is_help=False, context_parameter="ctx")
    assert _METADATA_POLICY == ExecutionPolicySpec(
        capabilities=frozenset(["state-free"]),
        side_effects=frozenset(["none"]),
        performance="metadata",
        write_route=CommandWriteRoute.NONE,
        destructive=False,
        handoff=False,
        live_write=False,
    )
    assert _ENCRYPTED_LOCAL_READ_POLICY == ExecutionPolicySpec(
        capabilities=frozenset(["encrypted-facts"]),
        side_effects=frozenset(["none"]),
        performance="local-io",
        write_route=CommandWriteRoute.NONE,
        destructive=False,
        handoff=False,
        live_write=False,
    )
    assert _PROFILE_BOUND_NETWORK_CAPTURE_POLICY == ExecutionPolicySpec(
        capabilities=frozenset(["encrypted-facts", "network"]),
        side_effects=frozenset(["local-state", "network"]),
        performance="external-io",
        write_route=CommandWriteRoute.PROFILE_BOUND,
        destructive=False,
        handoff=False,
        live_write=False,
    )
    assert NO_RESULT_SCHEMA == ResultSchemaSpec(SchemaState.NOT_SUPPORTED)

    _assert_shared_option_contract(
        _OPTIONAL_MODELOS_OPTION,
        name="modelos",
        declarations=("--modelo",),
        value=DeferredTarget("builtins", "str"),
        default=ParameterDefault.value(()),
        help_key="cli.app.live.filed.pull_modelo_help",
        constraint=ParameterConstraint(minimum=None, maximum=None),
        multiple=True,
    )
    _assert_shared_option_contract(
        _OPTIONAL_TAXPAYER_NIF_OPTION,
        name="taxpayer_nif",
        declarations=("--taxpayer-nif",),
        value=DeferredTarget("builtins", "str"),
        default=ParameterDefault.value(None),
        help_key="cli.app.live.iva_wallet.taxpayer_nif_help",
        constraint=ParameterConstraint(minimum=None, maximum=None),
    )
    _assert_shared_option_contract(
        _OPTIONAL_YEAR_FROM_OPTION,
        name="year_from",
        declarations=("--from-year",),
        value=DeferredTarget("builtins", "int"),
        default=ParameterDefault.value(None),
        help_key="cli.app.live.from_year_help",
        constraint=ParameterConstraint(minimum=2000, maximum=2099),
    )
    _assert_shared_option_contract(
        _OPTIONAL_YEAR_TO_OPTION,
        name="year_to",
        declarations=("--to-year",),
        value=DeferredTarget("builtins", "int"),
        default=ParameterDefault.value(None),
        help_key="cli.app.live.to_year_help",
        constraint=ParameterConstraint(minimum=2000, maximum=2099),
    )
    _assert_shared_option_contract(
        _OPTIONAL_YEAR_OPTION,
        name="year",
        declarations=("--year",),
        value=DeferredTarget("builtins", "int"),
        default=ParameterDefault.value(None),
        help_key="cli.app.live.year_help",
        constraint=ParameterConstraint(minimum=2000, maximum=2099),
    )
    _assert_shared_option_contract(
        _OUTPUT_ROOT_OPTION,
        name="output_root",
        declarations=("--output-root",),
        value=DeferredTarget("pathlib", "Path"),
        default=ParameterDefault.value(None),
        help_key="cli.app.live.output_root_help",
        constraint=ParameterConstraint(minimum=None, maximum=None),
        transport_locus=TransportLocus.LOCAL_OUT,
        transport_shape=TransportShape.DIRECTORY,
        transport_role=TransportRole.PRIMARY,
    )
    _assert_shared_option_contract(
        _REQUIRED_FILING_YEAR_OPTION,
        name="filing_year",
        declarations=("--filing-year",),
        value=DeferredTarget("builtins", "int"),
        default=ParameterDefault.required(),
        help_key="cli.app.live.borrador.filing_year_help",
        constraint=ParameterConstraint(minimum=2000, maximum=2099),
    )
    _assert_shared_option_contract(
        _REQUIRED_MODELO_OPTION,
        name="modelo",
        declarations=("--modelo",),
        value=DeferredTarget("builtins", "str"),
        default=ParameterDefault.required(),
        help_key="cli.app.live.modelo_help",
        constraint=ParameterConstraint(minimum=None, maximum=None),
    )
    _assert_shared_option_contract(
        _REQUIRED_PERIOD_OPTION,
        name="period",
        declarations=("--period",),
        value=DeferredTarget("builtins", "str"),
        default=ParameterDefault.required(),
        help_key="cli.app.live.period_help",
        constraint=ParameterConstraint(minimum=None, maximum=None),
    )
    _assert_shared_option_contract(
        _REQUIRED_YEAR_FROM_OPTION,
        name="year_from",
        declarations=("--from-year",),
        value=DeferredTarget("builtins", "int"),
        default=ParameterDefault.required(),
        help_key="cli.app.live.from_year_help",
        constraint=ParameterConstraint(minimum=2000, maximum=2099),
    )
    _assert_shared_option_contract(
        _REQUIRED_YEAR_OPTION,
        name="year",
        declarations=("--year",),
        value=DeferredTarget("builtins", "int"),
        default=ParameterDefault.required(),
        help_key="cli.app.live.year_help",
        constraint=ParameterConstraint(minimum=2000, maximum=2099),
    )
    _assert_shared_option_contract(
        _REQUIRED_YEAR_TO_OPTION,
        name="year_to",
        declarations=("--to-year",),
        value=DeferredTarget("builtins", "int"),
        default=ParameterDefault.required(),
        help_key="cli.app.live.to_year_help",
        constraint=ParameterConstraint(minimum=2000, maximum=2099),
    )


def test_live_specs_are_the_exact_complete_current_surface() -> None:
    graph = CommandSpecGraph((*ROOT_COMMAND_SPECS, *LIVE_COMMAND_SPECS))
    live_keys = {spec.key for spec in LIVE_COMMAND_SPECS}
    actual = {" ".join(node.path[1:]) for node in graph.nodes() if node.spec.key in live_keys}
    assert len(LIVE_COMMAND_SPECS) == 49
    assert sum(spec.kind == "leaf" for spec in LIVE_COMMAND_SPECS) == 37
    assert actual == EXPECTED_LIVE_PATHS


def test_live_shared_specs_keep_exact_identity_order_and_routes() -> None:
    foundation = {spec.key: spec for spec in LIVE_FOUNDATION_COMMAND_SPECS}
    borrador = {spec.key: spec for spec in LIVE_BORRADOR_COMMAND_SPECS}
    deudas = {spec.key: spec for spec in LIVE_DEUDAS_COMMAND_SPECS}
    expedientes = {spec.key: spec for spec in LIVE_EXPEDIENTES_COMMAND_SPECS}
    iva_wallet = {spec.key: spec for spec in LIVE_IVA_WALLET_COMMAND_SPECS}
    justificante = {spec.key: spec for spec in LIVE_JUSTIFICANTE_COMMAND_SPECS}
    verify = {spec.key: spec for spec in LIVE_VERIFY_COMMAND_SPECS}
    portals = {spec.key: spec for spec in LIVE_PORTALS_COMMAND_SPECS}
    notifications = {spec.key: spec for spec in LIVE_NOTIFICATIONS_COMMAND_SPECS}

    for spec in (
        foundation["app_live"],
        foundation["app_live_filed"],
        iva_wallet["app_live_iva_wallet"],
        justificante["app_live_justificante"],
        verify["app_live_verify"],
        portals["app_live_portals"],
        notifications["app_live_notifications"],
        notifications["app_live_notifications_document"],
        borrador["app_live_borrador"],
        borrador["app_live_borrador_100"],
        deudas["app_live_deudas"],
        expedientes["app_live_expedientes"],
    ):
        assert spec.invocation is _METADATA_GROUP_INVOCATION
        assert spec.policy is _METADATA_POLICY
        assert spec.result_schema is NO_RESULT_SCHEMA

    for spec in (
        *LIVE_FOUNDATION_COMMAND_SPECS[2:],
        *LIVE_IVA_WALLET_COMMAND_SPECS[1:],
        *LIVE_JUSTIFICANTE_COMMAND_SPECS[1:],
        *LIVE_VERIFY_COMMAND_SPECS[1:],
        *LIVE_PORTALS_COMMAND_SPECS[1:],
        *(spec for spec in LIVE_NOTIFICATIONS_COMMAND_SPECS[1:] if spec.kind == "leaf"),
        *LIVE_BORRADOR_COMMAND_SPECS[2:],
        *LIVE_DEUDAS_COMMAND_SPECS[1:],
        *LIVE_EXPEDIENTES_COMMAND_SPECS[1:],
    ):
        assert spec.invocation is _LEAF_INVOCATION

    for key in ("app_live_filed_list",):
        assert foundation[key].policy is _ENCRYPTED_LOCAL_READ_POLICY
    for key in (
        "app_live_borrador_100_list",
        "app_live_borrador_100_view",
        "app_live_borrador_100_latest",
    ):
        assert borrador[key].policy is _ENCRYPTED_LOCAL_READ_POLICY
    for key in ("app_live_deudas_list", "app_live_deudas_view", "app_live_deudas_latest"):
        assert deudas[key].policy is _ENCRYPTED_LOCAL_READ_POLICY
    for key in (
        "app_live_expedientes_list",
        "app_live_expedientes_view",
        "app_live_expedientes_latest",
    ):
        assert expedientes[key].policy is _ENCRYPTED_LOCAL_READ_POLICY
    for key in ("app_live_iva_wallet_history",):
        assert iva_wallet[key].policy is _ENCRYPTED_LOCAL_READ_POLICY
    for key in (
        "app_live_justificante_list",
        "app_live_justificante_view",
    ):
        assert justificante[key].policy is _ENCRYPTED_LOCAL_READ_POLICY
    for key in (
        "app_live_filed_pull_all",
        "app_live_filed_pull",
        "app_live_filed_pull_sources",
    ):
        assert foundation[key].policy is _PROFILE_BOUND_NETWORK_CAPTURE_POLICY
    assert expedientes["app_live_expedientes_pull"].policy is _PROFILE_BOUND_NETWORK_CAPTURE_POLICY
    for key in (
        "app_live_iva_wallet_pull",
        "app_live_iva_wallet_pull_history",
    ):
        assert iva_wallet[key].policy is _PROFILE_BOUND_NETWORK_CAPTURE_POLICY
    assert justificante["app_live_justificante_pull"].policy is _PROFILE_BOUND_NETWORK_CAPTURE_POLICY
    assert foundation["app_live_filed_discover"].policy is not _PROFILE_BOUND_NETWORK_CAPTURE_POLICY
    assert iva_wallet["app_live_iva_wallet_pull_evidence"].policy is not _PROFILE_BOUND_NETWORK_CAPTURE_POLICY

    assert foundation["app_live_filed_list"].parameters[1] is _OPTIONAL_YEAR_FROM_OPTION
    assert foundation["app_live_filed_list"].parameters[2] is _OPTIONAL_YEAR_TO_OPTION
    assert foundation["app_live_filed_pull"].parameters[2] is _OPTIONAL_YEAR_FROM_OPTION
    assert foundation["app_live_filed_pull"].parameters[3] is _OPTIONAL_YEAR_TO_OPTION
    assert foundation["app_live_filed_pull"].parameters[0] is _OPTIONAL_MODELOS_OPTION
    assert foundation["app_live_filed_pull"].parameters[1] is _OPTIONAL_YEAR_OPTION
    assert expedientes["app_live_expedientes_pull"].parameters == (
        _OPTIONAL_MODELOS_OPTION,
        _OPTIONAL_YEAR_OPTION,
        _OPTIONAL_YEAR_FROM_OPTION,
        _OPTIONAL_YEAR_TO_OPTION,
    )
    assert borrador["app_live_borrador_100_import"].parameters[1] is _REQUIRED_FILING_YEAR_OPTION
    assert borrador["app_live_borrador_100_latest"].parameters[0] is _REQUIRED_FILING_YEAR_OPTION
    for spec, position in (
        (foundation["app_live_filed_pull_all"], 0),
        (foundation["app_live_filed_pull"], 4),
        (foundation["app_live_filed_pull_sources"], 3),
        (iva_wallet["app_live_iva_wallet_pull_history"], 2),
        (iva_wallet["app_live_iva_wallet_pull_evidence"], 5),
    ):
        assert spec.parameters[position] is _OUTPUT_ROOT_OPTION
    for spec in (
        foundation["app_live_filed_pull_sources"],
        justificante["app_live_justificante_pull"],
    ):
        assert spec.parameters[0] is _REQUIRED_MODELO_OPTION
    for spec, year_position, period_position in (
        (foundation["app_live_filed_pull_sources"], 1, 2),
        (iva_wallet["app_live_iva_wallet_pull"], 0, 1),
        (justificante["app_live_justificante_pull"], 1, 2),
    ):
        assert spec.parameters[year_position] is _REQUIRED_YEAR_OPTION
        assert spec.parameters[period_position] is _REQUIRED_PERIOD_OPTION
    for spec, position in (
        (iva_wallet["app_live_iva_wallet_pull"], 2),
        (iva_wallet["app_live_iva_wallet_pull_evidence"], 4),
    ):
        assert spec.parameters[position] is _OPTIONAL_TAXPAYER_NIF_OPTION
    for spec in (
        iva_wallet["app_live_iva_wallet_pull_history"],
        iva_wallet["app_live_iva_wallet_pull_evidence"],
    ):
        assert spec.parameters[0] is _REQUIRED_YEAR_FROM_OPTION
        assert spec.parameters[1] is _REQUIRED_YEAR_TO_OPTION

    for key in (
        "app_live_verify_list",
        "app_live_verify_view",
        "app_live_verify_latest",
    ):
        assert verify[key].policy is _ENCRYPTED_LOCAL_READ_POLICY
    for key in ("app_live_portals_list", "app_live_portals_view"):
        assert portals[key].policy is _METADATA_POLICY
    for key in (
        "app_live_notifications_list",
        "app_live_notifications_view",
        "app_live_notifications_latest",
        "app_live_notifications_document_view",
        "app_live_notifications_document_history",
    ):
        assert notifications[key].policy is _ENCRYPTED_LOCAL_READ_POLICY

    for key in ("app_live_verify_nif_iva", "app_live_verify_tgvi"):
        assert verify[key].policy is _PROFILE_BOUND_NETWORK_CAPTURE_POLICY
        assert tuple(parameter.name for parameter in verify[key].parameters) == ("nif", "expected")
        assert verify[key].parameters[1] is _VERIFY_EXPECTED_OPTION
    assert verify["app_live_verify_nif_iva"].parameters is not verify["app_live_verify_tgvi"].parameters
    assert verify["app_live_verify_nif_iva"].parameters[0] is not verify["app_live_verify_tgvi"].parameters[0]
    assert verify["app_live_verify_nif_iva"].handler is not verify["app_live_verify_tgvi"].handler
    assert verify["app_live_verify_nif_iva"].result_schema is not verify["app_live_verify_tgvi"].result_schema

    for key in ("app_live_notifications_pull", "app_live_notifications_document_pull"):
        assert notifications[key].policy is _PROFILE_BOUND_NETWORK_CAPTURE_POLICY
    for key in ("app_live_notifications_document_pull", "app_live_notifications_document_view"):
        assert tuple(parameter.name for parameter in notifications[key].parameters) == ("certificado_id",)
        assert notifications[key].parameters[0] is _NOTIFICATION_CERTIFICADO_ID_ARGUMENT
    assert (
        notifications["app_live_notifications_document_pull"].parameters
        is not notifications["app_live_notifications_document_view"].parameters
    )
    assert (
        notifications["app_live_notifications_document_pull"].handler
        is not notifications["app_live_notifications_document_view"].handler
    )
    assert (
        notifications["app_live_notifications_document_pull"].result_schema
        is not notifications["app_live_notifications_document_view"].result_schema
    )

    graph = CommandSpecGraph((*ROOT_COMMAND_SPECS, *LIVE_COMMAND_SPECS))
    for path, spec in (
        (("aeat", "app", "live"), foundation["app_live"]),
        (("aeat", "app", "live", "borrador", "100", "latest"), borrador["app_live_borrador_100_latest"]),
        (("aeat", "app", "live", "deudas", "view"), deudas["app_live_deudas_view"]),
        (("aeat", "app", "live", "expedientes", "pull"), expedientes["app_live_expedientes_pull"]),
        (("aeat", "app", "live", "filed", "pull-sources"), foundation["app_live_filed_pull_sources"]),
        (("aeat", "app", "live", "iva-wallet", "pull-evidence"), iva_wallet["app_live_iva_wallet_pull_evidence"]),
        (("aeat", "app", "live", "justificante", "pull"), justificante["app_live_justificante_pull"]),
        (("aeat", "app", "live", "verify"), verify["app_live_verify"]),
        (("aeat", "app", "live", "verify", "nif-iva"), verify["app_live_verify_nif_iva"]),
        (("aeat", "app", "live", "verify", "tgvi"), verify["app_live_verify_tgvi"]),
        (("aeat", "app", "live", "portals", "list"), portals["app_live_portals_list"]),
        (
            ("aeat", "app", "live", "notifications", "document", "pull"),
            notifications["app_live_notifications_document_pull"],
        ),
        (
            ("aeat", "app", "live", "notifications", "document", "view"),
            notifications["app_live_notifications_document_view"],
        ),
    ):
        assert graph.resolve_path(path) is spec


def test_every_live_leaf_has_public_resolvable_behavior_and_schema_targets() -> None:
    leaves = [spec for spec in LIVE_COMMAND_SPECS if spec.kind == "leaf"]
    assert len(leaves) == 37
    for spec in leaves:
        assert spec.handler is not None
        assert spec.handler.target is not None
        assert "<locals>" not in spec.handler.target.qualname
        assert not spec.handler.target.qualname.startswith("_")
        assert callable(_resolve(spec.handler))
        assert spec.result_schema.target is not None
        assert _resolve(LazyBinding.available(spec.result_schema.target)) is not None


def test_live_specs_own_policy_schema_and_localised_parameter_contracts() -> None:
    for spec in LIVE_COMMAND_SPECS:
        assert spec.help_key.value.startswith("cli.app.live.")
        assert spec.policy.capabilities
        if spec.kind == "leaf":
            assert spec.result_schema.identity is not None
            assert spec.result_schema.identity.startswith("app.live.")
        for parameter in spec.parameters:
            assert parameter.help_key is None or parameter.help_key.value.startswith("cli.app.live.")


def test_every_live_subtree_compiles_from_specs_without_legacy_structure() -> None:
    graph = CommandSpecGraph((*ROOT_COMMAND_SPECS, *LIVE_COMMAND_SPECS))
    for spec in LIVE_COMMAND_SPECS:
        app = build_command_subtree(graph, spec.key)
        assert get_command(app) is not None


def test_live_behavior_and_payload_modules_contain_no_structural_authority() -> None:
    cli_root = Path(__file__).parents[1]
    assert not (cli_root / "_app_live_payloads.py").exists()
    paths = [cli_root / "_app_live.py", cli_root / "_app_live_payloads_support.py"]
    paths.extend(sorted(cli_root.glob("_app_live_*_payloads.py")))
    paths.extend(sorted(cli_root.glob("_app_live_*_cli.py")))
    forbidden_names = {"command_execution_policy", "declare_metadata_group", "register_schema"}
    for path in paths:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        assert "Typer(" not in source
        assert not any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("register_")
            for node in ast.walk(tree)
        )
        assert not any(isinstance(node, ast.Name) and node.id in forbidden_names for node in ast.walk(tree))
        assert not any(
            isinstance(node, ast.Attribute) and node.attr in {"command", "callback", "add_typer"}
            for node in ast.walk(tree)
        )
