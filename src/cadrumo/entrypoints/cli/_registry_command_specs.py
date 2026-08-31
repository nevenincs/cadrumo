"""Import-light command authority for the registry family."""

from __future__ import annotations

from ...core.transport_locus import TransportLocus, TransportRole, TransportShape
from ._command_spec import (
    ArgumentSpec,
    CommandSpec,
    DeferredTarget,
    ExecutionPolicySpec,
    InvocationSpec,
    LazyBinding,
    OptionSpec,
    ParameterConstraint,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
    ValueContract,
)

_METADATA = ExecutionPolicySpec(frozenset({"state-free"}), frozenset({"none"}), "metadata", "none")
_READ = ExecutionPolicySpec(frozenset({"registry"}), frozenset({"none"}), "compute", "none")
_STR = ValueContract(DeferredTarget("builtins", "str"))
_INT = ValueContract(DeferredTarget("builtins", "int"))
_PATH = ValueContract(DeferredTarget("pathlib", "Path"))
_MANUAL = ValueContract(DeferredTarget("cadrumo.application.registry.corpus", "RegistryManualId"))
_PART = ValueContract(DeferredTarget("cadrumo.domain.manuals", "ManualPart"))


def _key(value: str) -> TranslationKey:
    return TranslationKey(value)


def _option(
    name: str,
    declarations: tuple[str, ...],
    value: ValueContract,
    help_key: str,
    *,
    required: bool = False,
    default: str | tuple[str, ...] | None = None,
    multiple: bool = False,
    constraint: ParameterConstraint = ParameterConstraint(),
    transport_locus: TransportLocus = TransportLocus.NONE,
    transport_shape: TransportShape = TransportShape.NOT_APPLICABLE,
    transport_role: TransportRole = TransportRole.NOT_APPLICABLE,
) -> OptionSpec:
    return OptionSpec(
        name,
        declarations,
        value,
        ParameterDefault.required() if required else ParameterDefault.value(default),
        _key(help_key),
        multiple=multiple,
        constraint=constraint,
        transport_locus=transport_locus,
        transport_shape=transport_shape,
        transport_role=transport_role,
    )


_REGISTRY_ROOT = _option(
    "registry_root",
    ("--registry-root",),
    _PATH,
    "cli.registry.inspect_registry_root_help",
    constraint=ParameterConstraint(file_okay=False, readable=True),
    transport_locus=TransportLocus.LOCAL_IN,
    transport_shape=TransportShape.ROOT,
    transport_role=TransportRole.AUXILIARY,
)
_SOURCE_ROOT = _option(
    "source_root",
    ("--source-root",),
    _PATH,
    "cli.registry.verify_source_root_help",
    constraint=ParameterConstraint(exists=True, file_okay=False, readable=True),
    transport_locus=TransportLocus.LOCAL_IN,
    transport_shape=TransportShape.ROOT,
    transport_role=TransportRole.AUXILIARY,
)


def _group(key: str, parent: str, token: str, help_key: str) -> CommandSpec:
    return CommandSpec(
        key,
        parent,
        token,
        "group",
        _key(help_key),
        None,
        InvocationSpec(no_args_is_help=True, add_completion=False),
        (),
        _METADATA,
        None,
        ResultSchemaSpec(SchemaState.NOT_SUPPORTED),
    )


def _leaf(
    key: str,
    parent: str,
    token: str,
    help_key: str,
    module: str,
    handler: str,
    schema_module: str,
    schema: str,
    parameters: tuple[ArgumentSpec | OptionSpec, ...] = (),
) -> CommandSpec:
    return CommandSpec(
        key,
        parent,
        token,
        "leaf",
        _key(help_key),
        None,
        InvocationSpec(context_parameter="ctx"),
        parameters,
        _READ,
        LazyBinding.available(DeferredTarget(module, handler)),
        ResultSchemaSpec(
            SchemaState.TARGET,
            DeferredTarget(schema_module, schema),
            identity=key.removeprefix("app_").replace("_", "."),
        ),
    )


_ROOT_MODULE = "cadrumo.entrypoints.cli.registry"
_CORPUS_MODULE = "cadrumo.entrypoints.cli._registry_corpus"
_ROOT_PAYLOADS = "cadrumo.entrypoints.cli._registry_payloads"
_CORPUS_PAYLOADS = "cadrumo.entrypoints.cli._registry_corpus_payloads"

REGISTRY_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    _group("app_registry", "app", "registry", "cli.registry.app_help"),
    _group("app_registry_citations", "app_registry", "citations", "cli.registry.citations.app_help"),
    _group("app_registry_manuals", "app_registry", "manuals", "cli.registry.manuals.app_help"),
    _leaf(
        "app_registry_inspect",
        "app_registry",
        "inspect",
        "cli.registry.inspect_help",
        _ROOT_MODULE,
        "inspect_registry_cmd",
        _ROOT_PAYLOADS,
        "RegistryInspectResult",
        (_REGISTRY_ROOT,),
    ),
    _leaf(
        "app_registry_verify",
        "app_registry",
        "verify",
        "cli.registry.verify_help",
        _ROOT_MODULE,
        "verify_registry_cmd",
        _ROOT_PAYLOADS,
        "RegistryInspectResult",
        (_REGISTRY_ROOT, _SOURCE_ROOT),
    ),
    _leaf(
        "app_registry_verify_filed_state",
        "app_registry",
        "verify-filed-state",
        "cli.registry.verify_filed_state_help",
        _ROOT_MODULE,
        "verify_filed_state_cmd",
        _ROOT_PAYLOADS,
        "RegistryVerifyFiledStateResult",
        (
            _option(
                "observation_path",
                ("--observation",),
                _PATH,
                "cli.registry.observation_help",
                required=True,
                transport_locus=TransportLocus.LOCAL_IN,
                transport_shape=TransportShape.FILE,
                transport_role=TransportRole.AUXILIARY,
            ),
            _option(
                "source_observation_paths",
                ("--source-observation",),
                _PATH,
                "cli.registry.source_observation_help",
                multiple=True,
                transport_locus=TransportLocus.LOCAL_IN,
                transport_shape=TransportShape.FILE,
                transport_role=TransportRole.AUXILIARY,
            ),
            _REGISTRY_ROOT,
            _SOURCE_ROOT,
            _option("required_casilla_refs", ("--casilla",), _STR, "cli.registry.casilla_help", multiple=True),
        ),
    ),
    _leaf(
        "app_registry_diff_revisions",
        "app_registry",
        "diff-revisions",
        "cli.registry.diff_revisions_help",
        _ROOT_MODULE,
        "diff_revisions_cmd",
        "cadrumo.entrypoints.cli._registry_diff_payloads",
        "RegistryDiffRevisionsResult",
        (
            ArgumentSpec("modelo", _STR, ParameterDefault.required(), _key("cli.registry.diff_revisions_modelo_help")),
            _option("from_year", ("--from-year",), _INT, "cli.registry.diff_revisions_from_year_help", required=True),
            _option("to_year", ("--to-year",), _INT, "cli.registry.diff_revisions_to_year_help", required=True),
            _REGISTRY_ROOT,
            _SOURCE_ROOT,
        ),
    ),
    _leaf(
        "app_registry_citations_list",
        "app_registry_citations",
        "list",
        "cli.registry.citations.list_help",
        _CORPUS_MODULE,
        "list_citations_cmd",
        _CORPUS_PAYLOADS,
        "CitationListResult",
        (_option("tag", ("--tag",), _STR, "cli.registry.citations.tag_help"),),
    ),
    _leaf(
        "app_registry_citations_view",
        "app_registry_citations",
        "view",
        "cli.registry.citations.view_help",
        _CORPUS_MODULE,
        "show_citation_cmd",
        _CORPUS_PAYLOADS,
        "CitationShowResult",
        (
            ArgumentSpec("legal_id", _STR, ParameterDefault.required(), _key("cli.registry.citations.legal_id_help")),
            _option("articulo", ("--articulo",), _STR, "cli.registry.citations.articulo_help"),
        ),
    ),
    _leaf(
        "app_registry_citations_verify",
        "app_registry_citations",
        "verify",
        "cli.registry.citations.verify_help",
        _CORPUS_MODULE,
        "verify_citations_cmd",
        _CORPUS_PAYLOADS,
        "CitationVerifyResult",
    ),
    _leaf(
        "app_registry_manuals_list",
        "app_registry_manuals",
        "list",
        "cli.registry.manuals.list_help",
        _CORPUS_MODULE,
        "list_manuals_cmd",
        _CORPUS_PAYLOADS,
        "ManualListResult",
        (
            _option("manual", ("--manual",), _MANUAL, "cli.registry.manuals.manual_help"),
            _option("year", ("--year",), _INT, "cli.registry.manuals.year_help"),
        ),
    ),
    _leaf(
        "app_registry_manuals_view",
        "app_registry_manuals",
        "view",
        "cli.registry.manuals.view_help",
        _CORPUS_MODULE,
        "show_manual_cmd",
        _CORPUS_PAYLOADS,
        "ManualShowResult",
        (
            _option("manual", ("--manual",), _MANUAL, "cli.registry.manuals.manual_help", required=True),
            _option("year", ("--year",), _INT, "cli.registry.manuals.year_help", required=True),
            _option("part", ("--part",), _PART, "cli.registry.manuals.part_help", default="single"),
            _option("section", ("--section",), _STR, "cli.registry.manuals.section_help"),
        ),
    ),
    _leaf(
        "app_registry_manuals_rules",
        "app_registry_manuals",
        "rules",
        "cli.registry.manuals.rules_help",
        _CORPUS_MODULE,
        "list_manual_rules_cmd",
        _CORPUS_PAYLOADS,
        "ManualRulesListResult",
        (
            _option("manual", ("--manual",), _MANUAL, "cli.registry.manuals.manual_help", required=True),
            _option("year", ("--year",), _INT, "cli.registry.manuals.year_help", required=True),
            _option("part", ("--part",), _PART, "cli.registry.manuals.part_help", default="single"),
            _option("kind", ("--kind",), _STR, "cli.registry.manuals.kind_help"),
        ),
    ),
    _leaf(
        "app_registry_manuals_verify",
        "app_registry_manuals",
        "verify",
        "cli.registry.manuals.verify_help",
        _CORPUS_MODULE,
        "verify_manual_cmd",
        _CORPUS_PAYLOADS,
        "ManualVerifyResult",
        (
            _option("manual", ("--manual",), _MANUAL, "cli.registry.manuals.manual_help", required=True),
            _option("year", ("--year",), _INT, "cli.registry.manuals.year_help", required=True),
            _option("part", ("--part",), _PART, "cli.registry.manuals.part_help", default="single"),
        ),
    ),
)

__all__ = ["REGISTRY_COMMAND_SPECS"]
