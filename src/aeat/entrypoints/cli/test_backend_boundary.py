"""Audit the CLI/backend boundary inventory.

These tests do not bless CLI-owned business logic. They make every tracked
boundary row explicit so each update can remove or downgrade one row at
a time without losing the backend API that owns the behavior.
"""

from __future__ import annotations

import ast
import json
import re
from contextlib import redirect_stdout
from dataclasses import dataclass
from io import StringIO
from pathlib import Path

import click
import pytest
import typer

from aeat.application.review import LedgerReviewFilterKey
from aeat.core.paths import PROJECT_ROOT
from aeat.entrypoints.cli import _ledger
from aeat.tests.cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]

_PLAN_PATH = PROJECT_ROOT / ".vault" / "plan" / "2026-05-08-cli-backend-boundary-plan.md"
_REFERENCE_PATH = PROJECT_ROOT / ".vault" / "reference" / "2026-05-08-cli-backend-boundary-reference.md"
_CLI_ROOT = PROJECT_ROOT / "src" / "aeat" / "entrypoints" / "cli"
_FORBIDDEN_TEST_PROCESS_LANGUAGE = (
    "aspirational",
    "backwards-compat",
    "compatibility shim",
    "deferred",
    "fails by design",
    "migration state",
    "not yet delivered",
    "past-state",
    "phase ",
    "previously in this file",
    "stub",
    "todo",
    "tbd",
    "wave ",
    "xfail",
)

_LIVE_TEST_FILES = frozenset[str]()


@dataclass(frozen=True)
class BoundaryFinding:
    row_id: str
    source: str
    symbols: tuple[str, ...]
    backend_gap: str
    owner: str


_KNOWN_FINDINGS: tuple[BoundaryFinding, ...] = (
    BoundaryFinding(
        row_id="CLI-001",
        source="src/aeat/entrypoints/cli/_common.py",
        symbols=("_canonical_period", "_aggregate_filing_inputs"),
        backend_gap="API-005",
        owner="application.filing",
    ),
    BoundaryFinding(
        row_id="CLI-007",
        source="src/aeat/entrypoints/cli/_overview.py",
        symbols=("overview_status",),
        backend_gap="API-008",
        owner="application.overview",
    ),
)


def _parse_source(relative_path: str) -> ast.Module:
    path = PROJECT_ROOT / relative_path
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _defined_symbols(tree: ast.Module) -> set[str]:
    return {
        node.name
        for node in ast.iter_child_nodes(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
    }


def _iter_cli_test_files() -> tuple[Path, ...]:
    return tuple(sorted(_CLI_ROOT.rglob("test_*.py")))


def _invoke_help(*args: str) -> str:
    result = invoke_cached_cli([*args, "--help"])
    assert result.exit_code == 0, result.output
    return result.output


def _registered_ledger_command_names() -> set[str]:
    return {command.name for command in _ledger.app.registered_commands if command.name is not None}


def _ledger_help_by_command() -> dict[str, str]:
    group = typer.main.get_command(_ledger.app)
    assert isinstance(group, click.Group)
    parent = group.make_context("ledger", [], resilient_parsing=True)
    help_by_command = {"ledger": _render_click_help(group, parent)}
    for name, command in group.commands.items():
        ctx = command.make_context(name, ["--help"], parent=parent, resilient_parsing=True)
        help_by_command[name] = _render_click_help(command, ctx)
    return help_by_command


def _render_click_help(command: click.Command, ctx: click.Context) -> str:
    buffer = StringIO()
    with redirect_stdout(buffer):
        rendered = command.get_help(ctx)
    return rendered or buffer.getvalue()


def test_boundary_inventory_rows_have_live_source_anchors() -> None:
    """Every tracked CLI violation row must point at source that still exists."""

    offences: list[str] = []
    for finding in _KNOWN_FINDINGS:
        path = PROJECT_ROOT / finding.source
        if not path.exists():
            offences.append(f"{finding.row_id}: source missing: {finding.source}")
            continue
        symbols = _defined_symbols(_parse_source(finding.source))
        missing = sorted(set(finding.symbols) - symbols)
        if missing:
            offences.append(f"{finding.row_id}: missing symbols in {finding.source}: {', '.join(missing)}")
    assert offences == [], "boundary inventory drift:\n  " + "\n  ".join(offences)


def test_boundary_plan_tracks_every_known_cli_finding_and_backend_gap() -> None:
    """The rollout docs must track every static audit row and backend owner."""

    plan_text = _PLAN_PATH.read_text(encoding="utf-8")
    reference_text = _REFERENCE_PATH.read_text(encoding="utf-8")
    combined = f"{plan_text}\n{reference_text}"
    offences: list[str] = []
    for finding in _KNOWN_FINDINGS:
        for token in (finding.row_id, finding.backend_gap, finding.owner):
            if token not in combined:
                offences.append(f"{finding.row_id}: docs do not track {token!r}")
    assert offences == [], "boundary docs missing tracked rows:\n  " + "\n  ".join(offences)


def test_manual_ledger_import_and_review_boundaries_stay_backend_owned() -> None:
    """Manual ledger import and review logic must not move back into the CLI."""

    ledger_cli = (PROJECT_ROOT / "src/aeat/entrypoints/cli/_ledger.py").read_text(encoding="utf-8")
    ledger_backend = (PROJECT_ROOT / "src/aeat/application/ledger/_actions.py").read_text(encoding="utf-8")
    forbidden_cli_tokens = (
        "CsvProvider",
        "OfxProvider",
        "XlsxProvider",
        "PdfN26Provider",
        "FinancialProvider",
        "detect_provider",
        "sha256_file",
        "_direction_resolver",
        "_ledger_row_status",
    )

    assert [token for token in forbidden_cli_tokens if token in ledger_cli] == []
    for token in (
        "import_ledger_source",
        "_direction_from_amount",
        "query_ledger_review_rows",
        "LedgerReviewQuery",
    ):
        assert token in ledger_backend


def test_manual_ledger_registry_uses_accepted_command_vocabulary() -> None:
    """The retained ledger Typer registry must expose current lifecycle names only."""

    accepted_commands = {
        "create",
        "edit",
        "classify",
        "allocate",
        "attach",
        "archive",
        "stash",
        "remove",
        "reset",
        "export",
        "list",
        "read",
        "status",
        "track",
        "import",
        "review",
    }
    rejected_commands = {"set-ratio", "unset-ratio", "split", "sanitize", "financial"}

    command_names = _registered_ledger_command_names()
    assert accepted_commands <= command_names
    assert command_names & rejected_commands == set()


def test_manual_ledger_help_rejects_legacy_vocabulary_across_subcommands() -> None:
    """Legacy command names and retired domain words must not leak into ledger help."""

    rejected_terms = ("set-ratio", "unset-ratio", "split", "sanitize", "financial")
    offences: list[str] = []
    for command_name, help_text in _ledger_help_by_command().items():
        lowered = help_text.lower()
        offences.extend(
            f"{command_name}: {term}"
            for term in rejected_terms
            if re.search(rf"(?<![a-z0-9_-]){re.escape(term)}(?![a-z0-9_-])", lowered)
        )
    assert offences == []


def test_manual_ledger_export_help_keeps_serialization_format_named_as_export_format() -> None:
    """Ledger export serialization must not reintroduce command-local output format."""

    export_help = _ledger_help_by_command()["export"]
    assert "--export-format" in export_help
    assert "--format" not in export_help


def test_manual_ledger_root_format_still_controls_emitted_payload_shape(tmp_path: Path) -> None:
    """The root ``--format`` flag must remain the rendering switch used by ``_emit``."""

    statement = tmp_path / "statement.csv"
    statement.write_text(
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID\n"
        "2026-04-15,Client SL,Invoice 1,121.00,EUR,n26-001\n",
        encoding="utf-8",
    )

    result = invoke_cached_cli(
        ["--format", "json", "app", "ledger", "import", str(statement), "--provider", "csv", "--dry-run"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["dry_run"] is True
    assert payload["rows"] == 1


def test_manual_ledger_review_help_exposes_backend_filter_vocabulary() -> None:
    """Review filter help must name every backend-owned filter key."""

    review_help = _ledger_help_by_command()["review"]
    for key in LedgerReviewFilterKey:
        assert key.value in review_help


def test_removed_workflow_shim_modules_stay_absent() -> None:
    """Rejected operator surfaces must not keep importable Typer shims."""

    removed = (
        "src/aeat/entrypoints/cli/_declaration.py",
        "src/aeat/entrypoints/cli/_invoice.py",
        "src/aeat/entrypoints/cli/auth/__init__.py",
        "src/aeat/entrypoints/cli/auth/_registry.py",
        "src/aeat/entrypoints/cli/browser/__init__.py",
        "src/aeat/entrypoints/cli/browser/health.py",
        "src/aeat/entrypoints/cli/browser/test_health.py",
        "src/aeat/entrypoints/cli/financial/__init__.py",
        "src/aeat/entrypoints/cli/financial/_catalogue.py",
        "src/aeat/entrypoints/cli/financial/_profile_aliases.py",
        "src/aeat/entrypoints/cli/financial/ingest.py",
        "src/aeat/entrypoints/cli/financial/invoices.py",
        "src/aeat/entrypoints/cli/financial/profile.py",
        "src/aeat/entrypoints/cli/financial/test_cli.py",
        "src/aeat/entrypoints/cli/financial/test_profile.py",
        "src/aeat/entrypoints/cli/financial/test_profile_aliases.py",
        "src/aeat/entrypoints/cli/financial/txs.py",
        "src/aeat/entrypoints/cli/filing/__init__.py",
        "src/aeat/entrypoints/cli/filing/conftest.py",
        "src/aeat/entrypoints/cli/filing/test_filing_cli.py",
    )
    assert [path for path in removed if (PROJECT_ROOT / path).exists()] == []


def test_aeat_workflow_root_command_is_unknown() -> None:
    """`aeat workflow ...` is not a registered root: workflow orchestration is
    folded under `aeat app modelo` per apex §4.3 + §8."""
    result = invoke_cached_cli(["workflow", "--help"])
    assert result.exit_code != 0


def test_aeat_run_root_command_is_unknown() -> None:
    """`aeat run ...` is not a registered root: the redesigned CLI exposes
    exactly two roots — `aeat config` and `aeat app`."""
    result = invoke_cached_cli(["run", "--help"])
    assert result.exit_code != 0


def test_app_modelo_preflight_verb_is_unknown() -> None:
    """No standalone `aeat app modelo preflight` verb exists. Preflight runs
    inside `verify` / `file` actions per apex §8 backend exit-cap mandate."""
    result = invoke_cached_cli(["app", "modelo", "preflight", "--help"])
    assert result.exit_code != 0


def test_app_modelo_work_resume_help_exposes_documented_argument() -> None:
    """The resume verb advertises WORKFLOW_RUN_ID as its sole positional."""
    result = invoke_cached_cli(["app", "modelo", "work", "resume", "--help"])
    assert result.exit_code == 0
    assert "WORKFLOW_RUN_ID" in result.output


def test_profile_backend_schema_duplicate_branch_stays_removed() -> None:
    """Retired application-profile branch files must stay absent."""

    removed = (
        "src/aeat/application/profile/__init__.py",
        "src/aeat/application/profile/_actions.py",
        "src/aeat/application/profile/_models.py",
        "src/aeat/application/profile/_repository.py",
        "src/aeat/application/profile/test_actions.py",
        "src/aeat/application/profile/test_validate.py",
    )
    assert [path for path in removed if (PROJECT_ROOT / path).exists()] == []


def test_profile_backend_schema_deleted_package_has_no_surviving_imports() -> None:
    """Callers must use canonical user-profile services only."""

    forbidden_tokens = (
        "aeat.application.profile",
        "from .profile",
        "profile_bucket_repository",
        "set_active_profile",
        "set_profile_values",
    )
    search_roots = (
        PROJECT_ROOT / "src" / "aeat" / "application",
        PROJECT_ROOT / "src" / "aeat" / "entrypoints",
    )
    offenders: list[str] = []
    for root in search_roots:
        for path in sorted(root.rglob("*.py")):
            if path == Path(__file__):
                continue
            text = path.read_text(encoding="utf-8")
            for token in forbidden_tokens:
                if token in text:
                    offenders.append(f"{path.relative_to(PROJECT_ROOT).as_posix()}: {token}")
    assert offenders == [], "retired application-profile references survive:\n  " + "\n  ".join(offenders)


def test_per_modelo_aggregation_placeholder_paths_stay_removed() -> None:
    """Per-modelo aggregation must fail through registered backend errors."""

    scoped_files = (
        "src/aeat/application/aggregation/_retenciones.py",
        "src/aeat/application/aggregation/_counterpart.py",
        "src/aeat/application/aggregation/test_retenciones.py",
        "src/aeat/application/aggregation/test_counterpart.py",
    )
    forbidden_tokens = ("NotImplementedError", "not implemented")
    offenders: list[str] = []
    for relative_path in scoped_files:
        text = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
        for token in forbidden_tokens:
            if token in text:
                offenders.append(f"{relative_path}: {token}")
    assert offenders == [], "per-modelo aggregation placeholder paths survive:\n  " + "\n  ".join(offenders)


def test_per_modelo_aggregation_duplicate_cli_surfaces_stay_absent() -> None:
    """The CLI may expose aggregation only through the central service command."""

    canonical_cli = _CLI_ROOT / "_modelo.py"
    forbidden_family_calls = (
        "aggregate_retenciones_",
        "aggregate_counterpart_",
        "aggregate_foreign_assets_720",
    )
    offenders: list[str] = []
    for path in sorted(_CLI_ROOT.rglob("*.py")):
        if path.name.startswith("test_"):
            continue
        text = path.read_text(encoding="utf-8")
        if path != canonical_cli and "aggregate_per_modelo" in text:
            offenders.append(f"{path.relative_to(PROJECT_ROOT).as_posix()}: aggregate_per_modelo")
        for token in forbidden_family_calls:
            if token in text:
                offenders.append(f"{path.relative_to(PROJECT_ROOT).as_posix()}: {token}")
    assert offenders == [], "parallel per-modelo aggregation CLI surfaces survive:\n  " + "\n  ".join(offenders)


def test_census_modelo_foundation_stays_backend_owned() -> None:
    """CLI must not reimplement Modelo 036/037 census foundation routing."""

    forbidden_cli_tokens = (
        "CensusModeloFoundationCommand",
        "resolve_census_modelo_foundation",
        "resolve_census_modelo_work_unit_foundation",
        "is_active_census_modelo",
        "CensusModeloRole",
        "active_work_unit_allowed",
        "historical_metadata_only",
    )
    offenders: list[str] = []
    for path in sorted(_CLI_ROOT.rglob("*.py")):
        if path.name.startswith("test_"):
            continue
        text = path.read_text(encoding="utf-8")
        for token in forbidden_cli_tokens:
            if token in text:
                offenders.append(f"{path.relative_to(PROJECT_ROOT).as_posix()}: {token}")
    assert offenders == [], "census modelo foundation logic leaked into CLI:\n  " + "\n  ".join(offenders)


def test_census_modelo_scope_arguments_stay_raw_until_backend_calls() -> None:
    """Modelo and period scope parsing must stay separate from backend policy."""

    source_path = _CLI_ROOT / "_modelo.py"
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(source_path))
    functions = {
        node.name: node
        for node in ast.iter_child_nodes(tree)
        if isinstance(node, ast.FunctionDef)
    }
    work_create = functions["work_create"]
    bindings_list = functions["bindings_list"]
    bindings_preview = functions["bindings_preview"]

    work_create_call = next(
        call
        for call in ast.walk(work_create)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id == "create_work_unit"
    )
    work_create_keywords = {keyword.arg: keyword.value for keyword in work_create_call.keywords}
    assert isinstance(work_create_keywords["modelo"], ast.Name)
    assert work_create_keywords["modelo"].id == "modelo"
    assert isinstance(work_create_keywords["period"], ast.Name)
    assert work_create_keywords["period"].id == "period"

    targets_assignment = next(
        node
        for node in ast.walk(bindings_list)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "targets" for target in node.targets)
    )
    assert isinstance(targets_assignment.value, ast.IfExp)
    assert isinstance(targets_assignment.value.orelse, ast.Tuple)
    assert [ast.dump(element) for element in targets_assignment.value.orelse.elts] == [
        ast.dump(ast.Name(id="modelo", ctx=ast.Load())),
    ]

    preview_scope_call = next(
        call
        for call in ast.walk(bindings_preview)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Attribute)
        and call.func.attr == "bindings_for_scope"
    )
    assert preview_scope_call.args
    assert isinstance(preview_scope_call.args[0], ast.Name)
    assert preview_scope_call.args[0].id == "modelo"
    preview_scope_keywords = {keyword.arg: keyword.value for keyword in preview_scope_call.keywords}
    assert isinstance(preview_scope_keywords["period"], ast.Name)
    assert preview_scope_keywords["period"].id == "period"

    forbidden_methods = {
        "strip",
        "lstrip",
        "rstrip",
        "removeprefix",
        "removesuffix",
        "replace",
        "zfill",
    }
    scope_functions = (work_create, bindings_list, bindings_preview)
    offenders: list[str] = []
    for function in scope_functions:
        for node in ast.walk(function):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in forbidden_methods:
                continue
            segment = ast.get_source_segment(source, node) or ""
            if "modelo" in segment or "period" in segment:
                offenders.append(f"{function.name}: {segment}")
    assert offenders == [], "CLI-local census scope normalization survived:\n  " + "\n  ".join(offenders)


def test_census_modelo_execution_stays_delegated_to_backend_services() -> None:
    """Accepted census-facing CLI paths must call central services for execution."""

    source_path = _CLI_ROOT / "_modelo.py"
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(source_path))
    functions = {
        node.name: node
        for node in ast.iter_child_nodes(tree)
        if isinstance(node, ast.FunctionDef)
    }

    imports_by_module: dict[tuple[int, str | None], set[str]] = {}
    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        imports_by_module[(node.level, node.module)] = {alias.name for alias in node.names}

    assert "RegistryQueryService" in imports_by_module[(3, "domain.calculations.registry")]
    assert "create_work_unit" in imports_by_module[(3, "application.modelo")]

    def called_names(function_name: str) -> set[str]:
        names: set[str] = set()
        for node in ast.walk(functions[function_name]):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                names.add(node.func.attr)
        return names

    assert {"bindings", "bindings_for_scope"} <= called_names("bindings_list")
    assert "bindings_for_scope" in called_names("bindings_preview")
    assert "create_work_unit" in called_names("work_create")
    assert "assemble_work_unit_history" in called_names("work_history")

    service_function = functions["_service"]
    service_calls = called_names("_service")
    assert "RegistryQueryService" in service_calls
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "load"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "ValidatedRegistryAuthority"
        for node in ast.walk(service_function)
    )
    assert all(
        not isinstance(node, ast.Constant) or node.value != "036"
        for node in ast.walk(service_function)
    )


def test_census_modelo_results_render_through_emitters() -> None:
    """Accepted census-facing CLI paths must render only through central emitters."""

    source_path = _CLI_ROOT / "_modelo.py"
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(source_path))
    functions = {
        node.name: node
        for node in ast.iter_child_nodes(tree)
        if isinstance(node, ast.FunctionDef)
    }
    census_facing_functions = (
        "bindings_list",
        "bindings_preview",
        "work_create",
        "work_list",
        "work_history",
    )
    forbidden_call_names = {
        "echo",
        "print",
        "Console",
        "render",
        "emit_json_success",
        "emit_json_document",
    }
    forbidden_attribute_calls = {
        ("typer", "echo"),
        ("json", "dump"),
        ("json", "dumps"),
    }
    offenders: list[str] = []
    for function_name in census_facing_functions:
        function = functions[function_name]
        calls_emit = any(
            isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_emit"
            for node in ast.walk(function)
        )
        if not calls_emit:
            offenders.append(f"{function_name}: missing _emit")
        for node in ast.walk(function):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name) and node.func.id in forbidden_call_names:
                offenders.append(f"{function_name}: {node.func.id}")
            if (
                isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and (node.func.value.id, node.func.attr) in forbidden_attribute_calls
            ):
                offenders.append(f"{function_name}: {node.func.value.id}.{node.func.attr}")
    assert offenders == [], "census modelo CLI rendering bypasses central emitters:\n  " + "\n  ".join(offenders)


def test_census_modelo_failures_use_central_error_boundary() -> None:
    """Census foundation failures must emit registered stderr errors, not prose fallbacks."""

    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "create",
            "--modelo",
            "037",
            "--year",
            "2025",
            "--period",
            "alta",
            "--revision",
            "historical",
            "--bucket-id",
            "census-boundary-error",
        ]
    )

    assert result.exit_code != 0
    assert result.stdout == ""
    payload = json.loads(result.stderr)
    assert payload["error"]["code"] == "ERROR_MODELO_WORK_UNIT_MUTATION_REFUSED"
    assert payload["error"]["message"] == (
        "census modelo 037 is historical census metadata only and cannot create active work units"
    )
    assert "Traceback" not in result.output


def test_census_modelo_help_uses_accepted_foundation_vocabulary_only() -> None:
    """Help for census-facing modelo commands must describe only the accepted 036 workflow."""

    help_outputs = [
        _invoke_help("app", "modelo", "work", "create"),
        _invoke_help("app", "modelo", "bindings", "list"),
        _invoke_help("app", "modelo", "bindings", "preview"),
    ]
    forbidden_tokens = (
        "037",
        "setup wizard",
        "portal-only",
        "integer modelo",
        "live submission",
        "compatibility",
        "shim",
        "stub",
        "fake",
        "alias",
        "not implemented",
    )

    for help_text in help_outputs:
        assert "Modelo 036" in help_text
        assert "alta" in help_text
        assert "modificacion" in help_text
        assert "baja" in help_text
        lowered = help_text.lower()
        for token in forbidden_tokens:
            assert token not in lowered


def test_census_modelo_removed_shims_and_stubs_stay_removed() -> None:
    """Removed census-foundation aliases and placeholder support must not return."""

    scanned_files = (
        _CLI_ROOT / "_modelo.py",
        _CLI_ROOT / "test_modelo.py",
        PROJECT_ROOT / "src" / "aeat" / "locales" / "en.yml",
        PROJECT_ROOT / "src" / "aeat" / "locales" / "es.yml",
        PROJECT_ROOT / "src" / "aeat" / "locales" / "ca.yml",
        PROJECT_ROOT / "src" / "aeat" / "locales" / "hu.yml",
        PROJECT_ROOT / "src" / "aeat" / "domain" / "calculations" / "registry" / "_census_modelos.py",
        PROJECT_ROOT / "src" / "aeat" / "domain" / "calculations" / "registry" / "_queries.py",
        PROJECT_ROOT / "src" / "aeat" / "domain" / "calculations" / "registry" / "test_census_modelo_foundation.py",
        PROJECT_ROOT / "src" / "aeat" / "domain" / "calculations" / "registry" / "test_census_modelo_registry_data.py",
        PROJECT_ROOT / "src" / "aeat" / "domain" / "calculations" / "registry" / "test_queries.py",
        PROJECT_ROOT / "registry" / "aeat" / "modelos" / "036.toml",
        PROJECT_ROOT / "registry" / "aeat" / "apoderamientos" / "scopes.toml",
    )
    forbidden_tokens = (
        "036, 037",
        "modelo 037)",
        "modelos 036/037",
        "2025-alta",
        "2025-modificacion",
        "2025-baja",
        "aeat-justificante-pdf",
        "aeat-csv-register",
        "aliases also accepted",
        'replace("-", "_")',
        ".zfill(",
        ".lstrip(",
        'strip("0")',
        "_CENSUS_MODELO_OWNERSHIP",
        "NotImplementedError",
        "not implemented",
        "fake active",
        "synthetic 037",
        'source_modelo = "037"',
        'modelo_codes = ["036", "037"]',
    )
    offenders: list[str] = []
    for path in scanned_files:
        text = path.read_text(encoding="utf-8")
        for token in forbidden_tokens:
            if token in text:
                offenders.append(f"{path.relative_to(PROJECT_ROOT).as_posix()}: {token}")
    assert offenders == [], "removed census modelo shim/stub surfaces returned:\n  " + "\n  ".join(offenders)


def test_legacy_application_aggregation_test_tree_stays_absent() -> None:
    """Retired top-level aggregation tests must not shadow package-owned tests."""

    legacy_tree = PROJECT_ROOT / "tests" / "application" / "aggregation"
    assert not legacy_tree.exists()


def test_registry_corpus_cli_ownership_is_registry_only() -> None:
    """Citation and manual corpus commands must live only under the registry app."""

    canonical = _CLI_ROOT / "_registry_corpus.py"
    forbidden_patterns = (
        'typer.Typer(\n    name="citations"',
        'typer.Typer(name="citations"',
        'typer.Typer(\n    name="manuals"',
        'typer.Typer(name="manuals"',
    )
    offenders: list[str] = []
    for path in sorted(_CLI_ROOT.rglob("*.py")):
        if path == canonical or path.name.startswith("test_"):
            continue
        text = path.read_text(encoding="utf-8")
        if any(pattern in text for pattern in forbidden_patterns):
            offenders.append(path.relative_to(PROJECT_ROOT).as_posix())
    assert offenders == []


def test_cli_observability_wrapper_module_is_absent_from_command_tree() -> None:
    """Generic run tracing is not part of the accepted CLI surface."""

    wrapper_path = PROJECT_ROOT / "src" / "aeat" / "entrypoints" / "cli" / "_observability.py"
    assert not wrapper_path.exists()

    offences: list[str] = []
    for path in sorted(_CLI_ROOT.rglob("*.py")):
        if path.name.startswith("test_"):
            continue
        text = path.read_text(encoding="utf-8")
        if "cli_run_context" in text or "build_arguments" in text or "._observability" in text:
            offences.append(path.relative_to(PROJECT_ROOT).as_posix())
    assert offences == []


def test_cli_unit_tests_do_not_contain_process_state_or_xfail_language() -> None:
    """CLI unit tests must describe executable behavior, not rollout meta-state."""

    offences: list[str] = []
    for path in _iter_cli_test_files():
        if path == Path(__file__):
            continue
        rel = path.relative_to(PROJECT_ROOT).as_posix()
        if rel in _LIVE_TEST_FILES:
            continue
        text = path.read_text(encoding="utf-8").lower()
        for phrase in _FORBIDDEN_TEST_PROCESS_LANGUAGE:
            pattern = re.compile(rf"(?<![a-z0-9_]){re.escape(phrase)}(?![a-z0-9_])")
            if pattern.search(text):
                offences.append(f"{rel} contains {phrase!r}")
        if re.search(r"(?<![a-z0-9_])pytest\.skip(?![a-z0-9_])", text):
            offences.append(f"{rel} contains pytest.skip")
    assert offences == [], "CLI tests contain process-state or skip language:\n  " + "\n  ".join(offences)
