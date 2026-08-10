"""Tests for the backend-owned operator surface contract.

The suite pins the command roots, mounted command families, lifecycle tokens,
parser-only source-kind aliases, help documents, and registered refusal error
used by entrypoint adapters. It deliberately exercises the application-owned
contract as data so CLI and MCP surfaces cannot redefine operator vocabulary in
their own layers.

See Also:
    :mod:`~application.operator_surface`
        Public facade for the backend-owned command contract under test.
    :func:`~application.operator_surface.get_operator_surface_contract`
        Cached contract builder exercised by the root, lifecycle, command-family,
        and source-kind assertions.
    :func:`~application.operator_surface.build_help_document`
        Backend help document builder checked against the current mounted
        command families.
    :func:`~application.operator_surface.require_accepted_root`
        Refusal gate that raises the registered operator-surface contract error.
    :func:`~application.operator_surface.build_operator_surface_manifest`
        Agent-facing manifest builder that consumes the same backend contract.
    :mod:`~entrypoints.cli._app_contract`
        CLI adapter that emits the manifest without owning the contract.
"""

from __future__ import annotations

import ast
import inspect
from collections.abc import Iterator, Mapping
from pathlib import Path

import pytest
from dev.locales import LocaleManager
from pydantic import BaseModel, ValidationError
from typer._click.core import Command as ClickCommand
from typer._click.core import Context as ClickContext
from typer.main import get_command as typer_get_command

from ....core import BindingSourceKind
from ....core.aggregation import COUNTERPART_SOURCE_KINDS
from ....core.config import override_settings
from ....core.errors import get_registered_error_code
from ....core.external_constants import OutputLanguage
from ....entrypoints.cli import app as cli_app
from ....entrypoints.cli import command_schema_refs
from ....entrypoints.mcp._input_schema import VerbLeafKind, build_verb_input_schemas
from ....entrypoints.mcp._tools import build_tool_descriptors
from ....entrypoints.schema_surface import (
    CALLBACK_EXCLUSION_REASON_BY_CLI_PATH,
    CALLBACK_RESULT_REUSE_BY_CLI_PATH,
    CALLBACK_SCHEMA_KEY_BY_CLI_PATH,
    GROUP_CALLBACK_SCHEMA_KEYS,
    ROOT_LANDING_SCHEMA_KEYS,
    normalise_cli_path_to_schema_key,
)
from ... import operator_surface
from ...storage_write_policy import is_profile_bound_write_verb_path
from .. import (
    FilingStatus,
    ModeloLifecycleStep,
    MountedCommandDomain,
    OperatorMutability,
    OperatorSurfaceContractError,
    RootSurfaceName,
    build_help_document,
    build_root_landing_report,
    get_operator_surface_contract,
    render_help_text,
    require_accepted_root,
    resolve_source_kind_alias,
)
from .. import _help as _help_module
from .._manifest import (
    ExplicitExclusionInventoryRow,
    InputSchemaInventoryRow,
    LiveLeafInventoryRow,
    McpExposureInventoryRow,
    MountedFamilyInventoryRow,
    ProfilePolicyInventoryRow,
    ReconciliationSurface,
    ResultSchemaInventoryRow,
    reconcile_operator_surface_inventory,
)
from .._models import HelpDocument, HelpEntry, HelpSection, LifecycleContract, RootLandingReport, RootSurface

pytestmark = [pytest.mark.hex_application]


@pytest.fixture(autouse=True)
def pin_english_locale() -> Iterator[None]:
    """Pin the operator-surface contract tests to the English locale.

    The contract surface (help paragraphs, error messages) is rendered
    through the project locale layer. These tests assert against the
    canonical English strings, so we pin the locale here rather than
    coupling the assertions to whatever the default locale happens to be
    in any given environment.
    """
    with override_settings(cadrumo_output_language="en"):
        yield


@pytest.mark.unit
def test_contract_roots_are_exactly_config_and_app() -> None:
    contract = get_operator_surface_contract()

    assert tuple(root.name for root in contract.roots) == (
        RootSurfaceName.CONFIG,
        RootSurfaceName.APP,
    )
    assert contract.roots[0].owns_storage_maintenance is True
    assert contract.roots[1].owns_operational_workflow is True


@pytest.mark.unit
def test_contract_lifecycle_forbids_live_submission() -> None:
    contract = get_operator_surface_contract()

    assert contract.lifecycle.steps == (
        ModeloLifecycleStep.CALCULATE,
        ModeloLifecycleStep.VERIFY,
        ModeloLifecycleStep.FILE,
    )
    assert contract.lifecycle.internal_filed_term == "internal filed"
    assert contract.lifecycle.live_submission_enabled is False

    with pytest.raises(ValidationError, match=r"steps|VERIFY|lifecycle"):
        LifecycleContract(
            steps=(
                ModeloLifecycleStep.CALCULATE,
                ModeloLifecycleStep.FILE,
            ),
        )
    with pytest.raises(ValidationError, match=r"live_submission_enabled|forbidden|False"):
        LifecycleContract(
            steps=(
                ModeloLifecycleStep.CALCULATE,
                ModeloLifecycleStep.VERIFY,
                ModeloLifecycleStep.FILE,
            ),
            live_submission_enabled=True,
        )


@pytest.mark.unit
def test_contract_source_kind_aliases_are_parser_only() -> None:
    assert resolve_source_kind_alias("ledger_transaction") is BindingSourceKind.LEDGER_TRANSACTION
    assert resolve_source_kind_alias("lt") is BindingSourceKind.LEDGER_TRANSACTION
    assert resolve_source_kind_alias("pie") is BindingSourceKind.PURCHASE_INVOICE_EVIDENCE
    assert resolve_source_kind_alias("pi") is BindingSourceKind.PAYABLE_INVOICE
    assert resolve_source_kind_alias("ci") is BindingSourceKind.COLLECTIBLE_INVOICE


@pytest.mark.unit
def test_require_accepted_root_uses_registered_application_error() -> None:
    assert require_accepted_root("config").name is RootSurfaceName.CONFIG

    with pytest.raises(OperatorSurfaceContractError, match=r"operator|surface|contract") as exc_info:
        require_accepted_root("setup")

    error = exc_info.value
    assert error.reason == "The CLI accepts only the config and app roots."
    assert error.suggestion == "aeat --help"
    assert get_registered_error_code(error).code == "REFUSED_OPERATOR_SURFACE_CONTRACT"


@pytest.mark.unit
def test_contract_models_are_strict_and_immutable() -> None:
    root = get_operator_surface_contract().roots[0]

    with pytest.raises(ValidationError, match=r"required_children|duplicate|unique"):
        RootSurface(
            name=RootSurfaceName.CONFIG,
            purpose="duplicate children",
            owns_storage_maintenance=True,
            owns_operational_workflow=False,
            required_children=("profile", "profile"),
        )
    with pytest.raises(ValidationError, match=r"Extra inputs are not permitted"):
        extra_kwargs: dict[str, object] = {"unexpected": True}
        RootSurface.model_validate(
            {
                "name": RootSurfaceName.CONFIG,
                "purpose": "extra field",
                "owns_storage_maintenance": True,
                "owns_operational_workflow": False,
                **extra_kwargs,
            },
        )
    with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
        setattr(root, "purpose", "mutated")  # noqa: B010 - frozen-model refusal is the assertion


def _raw_live_click_surface() -> tuple[
    dict[tuple[str, ...], ClickCommand],
    frozenset[tuple[str, ...]],
    dict[tuple[str, ...], tuple[str, ...]],
]:
    """Walk the materialised production CLI without consulting any schema projection.

    Terminal commands and ``invoke_without_command`` callbacks are intentionally
    recorded separately.  The latter are real dispatch surfaces but do not appear
    as child leaves in Click's tree, which is exactly the blind spot this S07
    reconciliation is meant to close.
    """
    root = typer_get_command(cli_app)
    terminals: dict[tuple[str, ...], ClickCommand] = {}
    callbacks: set[tuple[str, ...]] = set()
    children_by_group: dict[tuple[str, ...], tuple[str, ...]] = {}

    def walk(command: ClickCommand, context: ClickContext, path: tuple[str, ...]) -> None:
        lister = getattr(command, "list_commands", None)
        getter = getattr(command, "get_command", None)
        if not callable(lister) or not callable(getter):
            terminals[path] = command
            return
        if bool(getattr(command, "invoke_without_command", False)):
            callbacks.add(path)
        child_names = tuple(str(name) for name in lister(context))
        children_by_group[path] = child_names
        for child_name in child_names:
            child = getter(context, child_name)
            if child is not None:
                walk(
                    child,
                    ClickContext(child, parent=context, info_name=child_name),
                    (*path, child_name),
                )

    walk(root, ClickContext(root, info_name=str(root.name)), ())
    return terminals, frozenset(callbacks), children_by_group


@pytest.mark.integration
def test_live_operator_surface_reconciles_raw_click_paths_callbacks_and_mcp_policy_by_identity() -> None:
    """Reconcile independently walked Click identities with every projection.

    The expected MCP set is assembled from raw terminal paths and callback
    authorities.  It deliberately never calls the MCP adapter's exposure filter:
    a mistaken filter must make descriptor output disagree with this proof.
    """
    raw_terminals, raw_callback_paths, children_by_group = _raw_live_click_surface()
    raw_terminal_path_by_key: dict[str, tuple[str, ...]] = {}
    for path in raw_terminals:
        key = normalise_cli_path_to_schema_key(path)
        prior = raw_terminal_path_by_key.setdefault(key, path)
        assert prior == path, f"two raw terminal Click paths normalised to {key!r}: {prior!r}, {path!r}"

    callback_schema_paths = frozenset(CALLBACK_SCHEMA_KEY_BY_CLI_PATH)
    callback_reuse_paths = frozenset(CALLBACK_RESULT_REUSE_BY_CLI_PATH)
    help_only_callback_paths = frozenset(CALLBACK_EXCLUSION_REASON_BY_CLI_PATH)
    assert raw_callback_paths == callback_schema_paths | callback_reuse_paths | help_only_callback_paths
    assert frozenset(CALLBACK_SCHEMA_KEY_BY_CLI_PATH.values()) == GROUP_CALLBACK_SCHEMA_KEYS
    assert frozenset(
        key for key in CALLBACK_SCHEMA_KEY_BY_CLI_PATH.values() if key.startswith("root.")
    ) == ROOT_LANDING_SCHEMA_KEYS

    primary_path_by_key = dict(raw_terminal_path_by_key)
    for callback_path, key in CALLBACK_SCHEMA_KEY_BY_CLI_PATH.items():
        assert key not in primary_path_by_key, f"schema key {key!r} has both raw terminal and callback paths"
        primary_path_by_key[key] = callback_path
    callback_reuse_paths_by_key: dict[str, set[tuple[str, ...]]] = {}
    for callback_path, key in CALLBACK_RESULT_REUSE_BY_CLI_PATH.items():
        assert key in raw_terminal_path_by_key, f"callback reuse key {key!r} has no raw terminal command"
        callback_reuse_paths_by_key.setdefault(key, set()).add(callback_path)

    schema_refs = command_schema_refs()
    registered_keys = frozenset(ref.command for ref in schema_refs)
    assert len(registered_keys) == len(schema_refs), "result-schema registry published a duplicate command identity"
    assert frozenset(primary_path_by_key) == registered_keys, (
        "raw Click surfaces and result-schema registration diverged: "
        f"raw-only={sorted(set(primary_path_by_key) - registered_keys)!r}; "
        f"registry-only={sorted(registered_keys - set(primary_path_by_key))!r}"
    )

    input_schemas = build_verb_input_schemas(tuple(sorted(registered_keys)))
    assert frozenset(input_schemas) == registered_keys
    for key, schema in input_schemas.items():
        assert schema.resolved_leaf.cli_path == primary_path_by_key[key]
        expected_kind = VerbLeafKind.CALLBACK if key in GROUP_CALLBACK_SCHEMA_KEYS else VerbLeafKind.COMMAND
        assert schema.resolved_leaf.kind is expected_kind

    descriptors = build_tool_descriptors()
    descriptor_by_key = {descriptor.command_key: descriptor for descriptor in descriptors}
    assert len(descriptor_by_key) == len(descriptors), "MCP exposed one command identity more than once"
    expected_mcp_keys = (
        frozenset(raw_terminal_path_by_key)
        | frozenset(CALLBACK_SCHEMA_KEY_BY_CLI_PATH.values())
    ) - ROOT_LANDING_SCHEMA_KEYS
    assert frozenset(descriptor_by_key) == expected_mcp_keys, (
        "MCP descriptors did not equal raw terminal commands plus declared callback schema surfaces: "
        f"missing={sorted(expected_mcp_keys - set(descriptor_by_key))!r}; "
        f"unexpected={sorted(set(descriptor_by_key) - expected_mcp_keys)!r}"
    )

    live_leaves = tuple(
        LiveLeafInventoryRow(
            subject_leaf_key=key,
            canonical_cli_path=primary_path_by_key[key],
            alias_cli_paths=tuple(sorted(callback_reuse_paths_by_key.get(key, set()))),
            provenance="raw materialised Click traversal with declared callback reuse",
        )
        for key in sorted(primary_path_by_key)
    )
    result_schemas = tuple(
        ResultSchemaInventoryRow(
            subject_leaf_key=ref.command,
            schema_name=ref.schema_name,
            provenance="SCHEMA_REGISTRY through command_schema_refs",
        )
        for ref in schema_refs
    )
    input_rows = tuple(
        InputSchemaInventoryRow(
            subject_leaf_key=key,
            required_input_names=tuple(parameter.name for parameter in schema.required_inputs),
            provenance="S05 VerbInputSchema.required_inputs",
        )
        for key, schema in sorted(input_schemas.items())
    )
    mounted_families = tuple(
        MountedFamilyInventoryRow(
            root=family.root.value,
            child=family.child,
            provenance="OperatorSurfaceContract.command_families",
        )
        for family in get_operator_surface_contract().command_families
    )
    profile_policies = tuple(
        ProfilePolicyInventoryRow(
            subject_leaf_key=key,
            classification=(
                "profile_bound_write"
                if is_profile_bound_write_verb_path(" ".join(primary_path_by_key[key]))
                else "non_profile_bound"
            ),
            should_expose_via_mcp=key not in ROOT_LANDING_SCHEMA_KEYS,
            provenance="application storage policy plus root landing exposure contract",
        )
        for key, schema in sorted(input_schemas.items())
    )
    mcp_exposures = tuple(
        McpExposureInventoryRow(
            subject_leaf_key=key,
            exposed=key in descriptor_by_key,
            provenance="build_tool_descriptors",
        )
        for key in sorted(input_schemas)
    )
    exclusions = tuple(
        exclusion
        for key in sorted(ROOT_LANDING_SCHEMA_KEYS)
        for exclusion in (
            ExplicitExclusionInventoryRow(
                subject_leaf_key=key,
                surface=ReconciliationSurface.MOUNTED_FAMILY,
                reason="root landing callback has no mounted command family",
                authority="ROOT_LANDING_SCHEMA_KEYS",
                provenance="entrypoints.schema_surface",
            ),
            ExplicitExclusionInventoryRow(
                subject_leaf_key=key,
                surface=ReconciliationSurface.MCP_EXPOSURE,
                reason="root landing callback is excluded from MCP tools",
                authority="ROOT_LANDING_SCHEMA_KEYS",
                provenance="entrypoints.schema_surface",
            ),
        )
    )

    report = reconcile_operator_surface_inventory(
        live_leaves=live_leaves,
        result_schemas=result_schemas,
        input_schemas=input_rows,
        mounted_families=mounted_families,
        profile_policies=profile_policies,
        mcp_exposures=mcp_exposures,
        exclusions=exclusions,
    )
    reconciled_by_key = {leaf.live_leaf.subject_leaf_key: leaf for leaf in report.leaves}

    assert frozenset(reconciled_by_key) == registered_keys
    assert frozenset(row.subject_leaf_key for row in profile_policies) == registered_keys
    assert {row.classification for row in profile_policies}.issuperset({"profile_bound_write", "non_profile_bound"})
    reconciled_raw_paths = {
        path
        for row in reconciled_by_key.values()
        for path in (row.live_leaf.canonical_cli_path, *row.live_leaf.alias_cli_paths)
    }
    assert reconciled_raw_paths == (
        frozenset(raw_terminals) | callback_schema_paths | callback_reuse_paths
    ), "the reconciliation omitted or invented a raw envelope-emitting Click path"

    excluded_from_mcp = frozenset(key for key, row in reconciled_by_key.items() if not row.mcp_exposure.exposed)
    assert excluded_from_mcp == ROOT_LANDING_SCHEMA_KEYS
    for key in excluded_from_mcp:
        row = reconciled_by_key[key]
        assert {exclusion.surface for exclusion in row.exclusions} == {
            ReconciliationSurface.MOUNTED_FAMILY,
            ReconciliationSurface.MCP_EXPOSURE,
        }
        assert row.mounted_family is None
        assert row.profile_policy is not None
        assert row.profile_policy.should_expose_via_mcp is False

    for key, descriptor in descriptor_by_key.items():
        assert descriptor.verb_schema == input_schemas[key]
        assert descriptor.input_schema == input_schemas[key].json_schema()
        assert reconciled_by_key[key].result_schema is not None
        assert reconciled_by_key[key].input_schema is not None

    provisioning = next(
        family
        for family in get_operator_surface_contract().command_families
        if family.domain is MountedCommandDomain.PROVISIONING
    )
    assert provisioning.root is RootSurfaceName.CONFIG
    assert provisioning.child == "provision"
    assert provisioning.service_owner == "cadrumo.application.provisioning"
    assert provisioning.mutability is OperatorMutability.LOCAL_STATE_MUTATING
    assert "provision" in provisioning.operator_question.lower()
    assert "readiness" in provisioning.operator_question.lower()
    assert provisioning.commands == ("report", "pull", "verify")
    assert provisioning.commands == children_by_group[("config", "provision")]


@pytest.mark.unit
def test_operator_surface_application_package_has_no_typer_dependency() -> None:
    import subprocess
    import sys
    import textwrap

    script = textwrap.dedent("""\
        import importlib
        import sys

        for module_name in (
            "cadrumo.application.operator_surface",
            "cadrumo.application.operator_surface._contract",
            "cadrumo.application.operator_surface._help",
            "cadrumo.application.operator_surface._models",
        ):
            importlib.import_module(module_name)

        leaked = sorted(
            name
            for name in sys.modules
            if name == "typer" or name.startswith("typer.") or name.startswith("cadrumo.entrypoints.cli")
        )
        assert leaked == [], leaked
    """)
    result = subprocess.run(  # noqa: S603 - fixed interpreter argv with in-test script.
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, (
        f"operator surface imported a CLI-only dependency.\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


@pytest.mark.unit
def test_log_fields_and_error_codes_are_backend_owned() -> None:
    contract = get_operator_surface_contract()

    assert contract.log_fields.as_extra().for_logging() == {
        "contract_name": "operator_surface",
        "root_count": 2,
        "lifecycle": "calculate -> verify -> file",
        "source_kind_count": 4,
    }
    assert contract.error_codes == ("REFUSED_OPERATOR_SURFACE_CONTRACT",)


@pytest.mark.unit
def test_mounted_command_families_are_backend_owned_and_service_backed() -> None:
    contract = get_operator_surface_contract()

    by_domain = {family.domain: family for family in contract.command_families}

    assert MountedCommandDomain.FIRST_RUN not in by_domain
    assert by_domain[MountedCommandDomain.PROFILE].root is RootSurfaceName.CONFIG
    assert by_domain[MountedCommandDomain.PROFILE].child == "profile"
    assert by_domain[MountedCommandDomain.PROFILE].service_owner == "cadrumo.application.user_profile"
    assert {"create", "edit", "show", "delete", "status"}.issubset(by_domain[MountedCommandDomain.PROFILE].commands)
    custody_commands = {
        command
        for family in contract.command_families
        if family.domain is MountedCommandDomain.CUSTODY
        for command in family.commands
    }
    assert {"login", "logout", "change", "recover", "status", "create", "rotate", "verify"} == custody_commands
    # The append-only event-history verb merged into the `config profile` group
    # as `config profile history` (D1 family rename); the standalone
    # `config bucket` group was retired, so there is no BUCKET family.
    assert MountedCommandDomain.BUCKET not in by_domain
    assert "history" in by_domain[MountedCommandDomain.PROFILE].commands
    assert by_domain[MountedCommandDomain.OVERVIEW].mutability is OperatorMutability.READ_ONLY
    assert by_domain[MountedCommandDomain.LEDGER].service_owner == "cadrumo.application.transactions"
    assert by_domain[MountedCommandDomain.REVIEW].service_owner == "cadrumo.application.review"

    mounted_pairs = {(family.root.value, family.child) for family in contract.command_families}
    assert ("config", "auth") in mounted_pairs
    assert ("config", "bucket") not in mounted_pairs
    assert ("config", "profile") in mounted_pairs
    assert ("app", "modelo") in mounted_pairs
    assert all("invoice" not in family.child for family in contract.command_families)


@pytest.mark.unit
def test_required_children_match_mounted_command_families() -> None:
    contract = get_operator_surface_contract()

    for root in contract.roots:
        mounted_children = tuple(family.child for family in contract.command_families if family.root is root.name)
        assert root.required_children == mounted_children


@pytest.mark.unit
def test_help_documents_are_backend_owned_and_current_surface_only() -> None:
    root = build_help_document("root")
    config = build_help_document("config")
    app = build_help_document("app")

    root_text = render_help_text(root)
    config_text = render_help_text(config)
    app_text = render_help_text(app)

    assert "The CLI has exactly two roots: config and app." in root.paragraphs
    assert "aeat config profile create NAME" in root_text
    assert "CADRUMO_LOCAL_STORAGE_ROOT" in root_text
    assert "CADRUMO_SECRET_STORE_DIR" in root_text
    assert "CADRUMO_SECRET_PASSPHRASE" in config_text
    assert ("aeat config " + "init") not in root_text
    assert "aeat app ledger import" in root_text
    assert "aeat app live filed list" in root_text
    assert "aeat app live filed pull" in app_text
    assert "aeat config bucket" not in root_text
    assert "aeat config bucket" not in config_text
    assert "aeat config profile history" in config_text
    assert "aeat app invoice" not in app_text
    assert "aeat app declaration" not in app_text
    assert "cadrumo app" not in root_text + config_text + app_text
    assert "cadrumo config" not in root_text + config_text + app_text


@pytest.mark.unit
@pytest.mark.parametrize("locale", list(OutputLanguage))
def test_help_documents_build_in_every_shipped_locale(locale: OutputLanguage) -> None:
    """Building the help documents must succeed in every locale, not only English.

    Every ``HelpEntry.description``, ``HelpSection.title``,
    ``HelpDocument.heading``, and ``HelpDocument.footer`` is a translated
    string feeding an 80- or 120-character pydantic cap. English is
    comfortably short by construction, so a suite pinned to English cannot
    observe a translation that exceeds its cap -- exactly what shipped when
    three Spanish and Hungarian ``config storage`` descriptions blew the
    80-character limit and ``aeat config --help`` exited 2 for every operator
    in those locales, invisible to every English-pinned test in this file.

    Command invocations (``entry.command``) are literal Python strings in
    ``_help.py``, never translated, so the structural assertions below hold
    in every locale exactly as they do in English -- this is not a weaker
    check for non-English locales, it is the same property, proven where a
    translation can actually break it.
    """
    with override_settings(cadrumo_output_language=locale.value):
        root = build_help_document("root")
        config = build_help_document("config")
        app = build_help_document("app")

    root_text = render_help_text(root)
    config_text = render_help_text(config)
    app_text = render_help_text(app)

    assert "aeat config profile create NAME" in root_text
    assert ("aeat config " + "init") not in root_text
    assert "aeat app ledger import" in root_text
    assert "aeat app live filed list" in root_text
    assert "aeat app live filed pull" in app_text
    assert "aeat config bucket" not in root_text
    assert "aeat config bucket" not in config_text
    assert "aeat config profile history" in config_text
    assert "aeat app invoice" not in app_text
    assert "aeat app declaration" not in app_text
    # Product-name hygiene must hold in translated prose too: "cadrumo" must
    # never leak into a command verb in place of "aeat", in any locale.
    assert "cadrumo app" not in root_text + config_text + app_text
    assert "cadrumo config" not in root_text + config_text + app_text


@pytest.mark.unit
@pytest.mark.parametrize("locale", list(OutputLanguage))
def test_help_command_rows_are_backed_by_mounted_command_families(locale: OutputLanguage) -> None:
    contract = get_operator_surface_contract()
    mounted = {(family.root.value, family.child) for family in contract.command_families}

    with override_settings(cadrumo_output_language=locale.value):
        for surface in ("root", "config", "app"):
            document = build_help_document(surface)
            for section in document.sections:
                for entry in section.entries:
                    if " -> " in entry.command or "rejected" in entry.command:
                        continue
                    tokens = entry.command.split()
                    assert tokens[0] == "aeat"
                    assert (tokens[1], tokens[2]) in mounted


_LENGTH_CAPPED_MODELS: dict[str, type[BaseModel]] = {
    "HelpEntry": HelpEntry,
    "HelpSection": HelpSection,
    "HelpDocument": HelpDocument,
    "RootLandingReport": RootLandingReport,
}
"""Models :mod:`.._help` constructs whose fields carry a pydantic ``max_length``."""


def _field_max_length(model: type[BaseModel], field: str) -> int | None:
    """Return the ``max_length`` constraint ``model.field`` carries, if any.

    Introspects the live pydantic field metadata rather than hand-copying the
    80/120/160 caps from ``_models.py``, so a future constraint change is
    picked up automatically instead of silently drifting from the check.
    """
    info = model.model_fields.get(field)
    if info is None:
        return None
    for constraint in info.metadata:
        candidate = getattr(constraint, "max_length", None)
        if isinstance(candidate, int):
            return candidate
    return None


def _tr_key_from_call(node: ast.expr) -> str | None:
    """Return the literal locale key a ``tr(...)``/``t(...)`` call passes, if any."""
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
        return None
    if node.func.id not in {"tr", "t"} or not node.args:
        return None
    first = node.args[0]
    return first.value if isinstance(first, ast.Constant) and isinstance(first.value, str) else None


def _capped_translation_keys() -> tuple[tuple[str, int], ...]:
    """AST-scan ``_help.py`` for every translated string feeding a length-capped field.

    Walks every ``HelpEntry``/``HelpSection``/``HelpDocument``/``RootLandingReport``
    construction call in the module and returns ``(locale_key, max_length)`` for
    each keyword argument whose value is a ``tr(...)`` call and whose target field
    carries a pydantic ``max_length``. ``entry.command`` and ``report.command`` are
    always literal Python strings in ``_help.py`` (never translated), so they never
    match a ``tr(...)`` value and are correctly absent from the returned set.
    """
    tree = ast.parse(inspect.getsource(_help_module))
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        model = _LENGTH_CAPPED_MODELS.get(node.func.id)
        if model is None:
            continue
        for kw in node.keywords:
            if kw.arg is None:
                continue
            key = _tr_key_from_call(kw.value)
            if key is None:
                continue
            cap = _field_max_length(model, kw.arg)
            if cap is not None:
                found.append((key, cap))
    return tuple(found)


def _lookup_dotted(catalogue: Mapping[str, object], dotted_key: str) -> str | None:
    """Resolve a dot-notated locale key against a nested locale mapping."""
    node: object = catalogue
    for part in dotted_key.split("."):
        if not isinstance(node, dict):
            return None
        level: dict[str, object] = {str(key): value for key, value in node.items()}
        if part not in level:
            return None
        node = level[part]
    return node if isinstance(node, str) else None


@pytest.mark.unit
def test_help_and_landing_locale_strings_stay_within_field_caps() -> None:
    """Every translated help/landing string must fit its pydantic length cap, in every locale.

    Sharper companion to :func:`test_help_documents_build_in_every_shipped_locale`:
    that test proves the DOCUMENT still builds per locale, but pydantic raises on
    the FIRST over-length field it hits, so a multi-violation regression is only
    partially visible through it and the failure names a raw string, not the
    offending (locale, key). This test checks every capped ``tr(...)`` call site
    against every locale catalogue directly and reports every violation at once,
    naming the exact locale key, its length, and its cap -- the actionable form of
    the same guarantee. It is independent of :func:`.._help.build_help_document`
    successfully constructing anything, so it also covers a key whose value would
    fail for an unrelated reason (a missing interpolation placeholder, say) before
    ever reaching the model boundary.
    """
    capped_keys = _capped_translation_keys()
    assert capped_keys, "AST scan found no capped tr() call sites in _help.py -- the scanner has regressed"

    cadrumo_root = Path(operator_surface.__file__).parent.parent.parent
    manager = LocaleManager(src_dir=cadrumo_root, locales_dir=cadrumo_root / "locales")

    violations: list[str] = []
    for locale in OutputLanguage:
        catalogue = manager.load_locale(manager.locales_dir / f"{locale.value}.yml")
        for key, cap in capped_keys:
            value = _lookup_dotted(catalogue, key)
            if value is None:
                # Missing-key coverage/parity is owned by the locales audit gate,
                # not this length check.
                continue
            if len(value) > cap:
                violations.append(f"{locale.value}: {key!r} is {len(value)} chars, cap is {cap}: {value!r}")

    assert violations == [], "locale strings exceed their pydantic max_length:\n  " + "\n  ".join(violations)


@pytest.mark.unit
def test_root_landing_report_reads_profile_state_input_only() -> None:
    missing = build_root_landing_report(None)
    active = build_root_landing_report("operator")

    assert missing.command == "aeat config profile create NAME"
    assert missing.active_profile is None
    assert active.command == "aeat app overview status"
    assert active.active_profile == "operator"


@pytest.mark.unit
def test_filing_status_filed_is_sole_source_for_filed_token() -> None:
    """FilingStatus.FILED is the token exposed by the LIVE command family."""
    assert FilingStatus.FILED == "filed"
    assert str(FilingStatus.FILED) == "filed"

    contract = get_operator_surface_contract()
    live_family = next(f for f in contract.command_families if f.domain is MountedCommandDomain.LIVE)
    assert FilingStatus.FILED in live_family.commands


@pytest.mark.unit
def test_filing_status_has_no_token_shim_module() -> None:
    assert not (Path(operator_surface.__path__[0]) / "_filing_status_token.py").exists()


@pytest.mark.unit
def test_operator_source_kinds_mirror_the_counterpart_subset_of_binding_source_kind() -> None:
    """The operator-surface source kinds are exactly the counterpart subset of the core enum.

    taxonomy unification: the duplicate ``operator_surface.SourceKind``
    enum was deleted and the operator surface now declares its source kinds
    directly as :class:`BindingSourceKind` members. They must equal the canonical
    counterpart subset (:data:`COUNTERPART_SOURCE_KINDS`) — the four
    transaction/invoice settlement kinds — so the operator surface and the core
    taxonomy can never drift.
    """
    contract = get_operator_surface_contract()
    operator_kinds = set(contract.source_kinds)

    assert all(isinstance(kind, BindingSourceKind) for kind in operator_kinds), (
        "operator surface source kinds must be BindingSourceKind members"
    )
    assert operator_kinds == set(COUNTERPART_SOURCE_KINDS), (
        "operator surface source kinds must exactly mirror the counterpart subset of "
        f"BindingSourceKind; unexpected operator-only={sorted(operator_kinds - set(COUNTERPART_SOURCE_KINDS))} "
        f"subset-only={sorted(set(COUNTERPART_SOURCE_KINDS) - operator_kinds)}"
    )
