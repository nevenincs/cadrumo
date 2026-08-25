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
from typing import cast

import click
import pytest
import typer

from ....application.review import LedgerReviewFilterKey
from ....core.directory_scan import scan_directory
from ....core.resources import bundled_path
from cadrumo.domain.calculations.registry.loader import discover_modelo_sources
from ....tests import REPO_ROOT
from ....tests.cli_runner import invoke_cached_cli
from ....tests.user_profile import register_cli_profile
from .. import _ledger

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_CLI_ROOT = REPO_ROOT / "src" / "cadrumo" / "entrypoints" / "cli"
_FORBIDDEN_TEST_PROCESS_LANGUAGE = (
    "aspirational",
    "backwards-compat",
    "compatibility shim",
    "deferred",
    "fails by design",
    "migration state",
    "not yet delivered",
    "past-state",
    "pha" + "se ",
    "previously in this file",
    "stub",
    "todo",
    "tbd",
    "wa" + "ve ",
    "xfail",
)


def _modelo_source_paths(modelo_id: str) -> tuple[Path, ...]:
    modelos_dir = bundled_path("registry", "aeat", "modelos")
    for source in discover_modelo_sources(modelos_dir):
        if source.modelo_id != modelo_id:
            continue
        if source.layout == "single_file":
            return (source.path,)
        paths = [source.manifest_path]
        for revision_source in source.revision_sources:
            paths.extend(revision_source.fragment_paths)
        return tuple(dict.fromkeys(paths))
    raise AssertionError(f"modelo {modelo_id} is not present in registry sources")


_LIVE_TEST_FILES = frozenset[str]()


@dataclass(frozen=True)
class BoundaryFinding:
    source: str
    symbols: tuple[str, ...]


_KNOWN_FINDINGS: tuple[BoundaryFinding, ...] = (
    BoundaryFinding(
        source="src/cadrumo/entrypoints/cli/_common.py",
        symbols=("_canonical_period",),
    ),
    BoundaryFinding(
        source="src/cadrumo/entrypoints/cli/_overview.py",
        symbols=("overview_status",),
    ),
)


def _parse_source(relative_path: str) -> ast.Module:
    path = REPO_ROOT / relative_path
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _defined_symbols(tree: ast.Module) -> set[str]:
    return {
        node.name
        for node in ast.iter_child_nodes(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
    }


def _all_cli_modules() -> tuple[Path, ...]:
    """Every CLI source module, floored so a relocated tree cannot silently empty.

    The boundary scans below walk this tree and assert an offender list is empty.
    That green is meaningless if the walk found nothing: a package relocation or a
    rename of ``_CLI_ROOT`` would empty the corpus and pass identically to a clean
    tree. Asserting a floor at the corpus source means every consumer inherits the
    proof that the walk actually reached the CLI surface.
    """
    modules = scan_directory(_CLI_ROOT, pattern="*.py", recursive=True)
    assert len(modules) > 100, (
        f"scanned only {len(modules)} CLI modules under {_CLI_ROOT}; the scan corpus "
        "collapsed (a package relocation or rename), so an empty offender list below would "
        "mean 'nothing was checked' rather than 'nothing is wrong'"
    )
    return modules


def _iter_cli_test_files() -> tuple[Path, ...]:
    files = scan_directory(_CLI_ROOT, pattern="test_*.py", recursive=True)
    assert len(files) > 100, (
        f"scanned only {len(files)} CLI test modules under {_CLI_ROOT}; the scan corpus "
        "collapsed (a package relocation or rename), so an empty offence list would mean "
        "'nothing was checked' rather than 'nothing is wrong'"
    )
    return files


def _invoke_help(*args: str) -> str:
    result = invoke_cached_cli([*args, "--help"])
    assert result.exit_code == 0, result.output
    return result.output


def _registered_ledger_command_names() -> set[str]:
    return {command.name for command in _ledger.app.registered_commands if command.name is not None}


def _ledger_help_by_command() -> dict[str, str]:
    group = typer.main.get_command(_ledger.app)
    # Typer vendors its own Click fork: ``typer.main.get_command`` returns a
    # ``typer.core.TyperGroup`` whose MRO is ``TyperGroup -> typer._click.core
    # .Command -> ABC -> object`` and never descends from the upstream
    # ``click.Group``, so a bare ``isinstance(group, click.Group)`` is False.
    # Derive the vendored ``Command`` base from the TyperGroup MRO so the
    # command-group hierarchy is recognised without a brittle private-module
    # import (mirrors the production fix in ``cli/errors.py``, which derives the
    # vendored ``ClickException`` from ``typer.BadParameter.__mro__``).
    vendored_command = next(base for base in type(group).__mro__ if base.__name__ == "Command")
    assert isinstance(group, vendored_command)
    assert hasattr(group, "commands")
    # The runtime asserts above prove ``group`` is the vendored TyperGroup
    # (command-group shaped). It is structurally identical to upstream
    # click.Group; the casts bridge the static vendored/upstream duality so the
    # help-rendering helpers and ``.commands`` map type-check against click.
    click_group = cast(click.Group, group)
    parent = click_group.make_context("ledger", [], resilient_parsing=True)
    help_by_command = {"ledger": _render_click_help(click_group, parent)}
    for name, command in click_group.commands.items():
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
        path = REPO_ROOT / finding.source
        if not path.exists():
            offences.append(f"source missing: {finding.source}")
            continue
        symbols = _defined_symbols(_parse_source(finding.source))
        missing = sorted(set(finding.symbols) - symbols)
        if missing:
            offences.append(f"missing symbols in {finding.source}: {', '.join(missing)}")
    assert offences == [], "boundary inventory drift:\n  " + "\n  ".join(offences)


def test_manual_ledger_import_and_review_boundaries_stay_backend_owned() -> None:
    """Manual ledger import and review logic must not move back into the CLI."""

    ledger_cli = (REPO_ROOT / "src/cadrumo/entrypoints/cli/_ledger.py").read_text(encoding="utf-8")
    # The monolithic ``_actions.py`` was decomposed into sibling backend modules
    # (``_actions_import.py``, ``_actions_common.py``, ``_actions_manual.py``,
    # ``_models.py``, ...); ``_actions.py`` now re-exports them. Scan the whole
    # ledger backend package so the backend-owned tokens are found wherever the
    # decomposition relocated them.
    ledger_backend = "\n".join(
        path.read_text(encoding="utf-8")
        for path in scan_directory(REPO_ROOT / "src/cadrumo/application/ledger", pattern="*.py")
    )
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
        "query_ledger_review_rows",
        "LedgerReviewQuery",
    ):
        assert token in ledger_backend


def test_manual_ledger_registry_uses_accepted_command_vocabulary() -> None:
    """The retained ledger Typer registry must expose current lifecycle names only."""

    accepted_commands = {
        "add",
        "update",
        "view",
        "classify",
        "allocate",
        "attach",
        "archive",
        "stash",
        "remove",
        "reset",
        "split",
        "merge",
        "history",
        "export",
        "list",
        "status",
        "track",
        "import",
        "review",
    }
    rejected_commands = {"set-ratio", "unset-ratio", "sanitize", "financial", "create", "edit", "read"}

    command_names = _registered_ledger_command_names()
    assert accepted_commands <= command_names
    assert command_names & rejected_commands == set()


def test_manual_ledger_help_rejects_legacy_vocabulary_across_subcommands() -> None:
    """Legacy command names and retired domain words must not leak into ledger help."""

    rejected_terms = ("set-ratio", "unset-ratio", "sanitize", "financial")
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
    """The root ``--format`` flag remains the switch used by the envelope emitter."""

    env = {"CADRUMO_SECRET_PASSPHRASE": "backend-boundary-passphrase"}
    register_cli_profile(
        label="operator",
        facts={
            "taxpayer_type.entity_type": "natural_person",
            "identity.tax_id": "12345678Z",
            "identity.name": "Operator",
            "identity.surnames": "Operator",
            "activities.description": "design",
        },
    )

    statement = tmp_path / "statement.csv"
    statement.write_text(
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID\n"
        "2026-04-15,Client SL,Invoice 1,121.00,EUR,n26-001\n",
        encoding="utf-8",
    )

    result = invoke_cached_cli(
        ["--format", "json", "app", "ledger", "import", "--file", str(statement), "--provider", "csv", "--dry-run"],
        env=env,
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    body = payload.get("result", payload)
    assert body["dry_run"] is True
    assert body["rows"] == 1


def test_manual_ledger_review_help_exposes_backend_filter_vocabulary() -> None:
    """Review filter help must name every backend-owned filter key."""

    review_help = _ledger_help_by_command()["review"]
    for key in LedgerReviewFilterKey:
        assert key.value in review_help


def test_removed_workflow_shim_modules_stay_absent() -> None:
    """Rejected operator surfaces must not keep importable Typer shims."""

    removed = (
        "src/cadrumo/entrypoints/cli/_declaration.py",
        "src/cadrumo/entrypoints/cli/_invoice.py",
        "src/cadrumo/entrypoints/cli/auth/__init__.py",
        "src/cadrumo/entrypoints/cli/auth/_registry.py",
        "src/cadrumo/entrypoints/cli/browser/__init__.py",
        "src/cadrumo/entrypoints/cli/browser/health.py",
        "src/cadrumo/entrypoints/cli/browser/test_health.py",
        "src/cadrumo/entrypoints/cli/financial/__init__.py",
        "src/cadrumo/entrypoints/cli/financial/_catalogue.py",
        "src/cadrumo/entrypoints/cli/financial/_profile_aliases.py",
        "src/cadrumo/entrypoints/cli/financial/ingest.py",
        "src/cadrumo/entrypoints/cli/financial/invoices.py",
        "src/cadrumo/entrypoints/cli/financial/profile.py",
        "src/cadrumo/entrypoints/cli/financial/test_cli.py",
        "src/cadrumo/entrypoints/cli/financial/test_profile.py",
        "src/cadrumo/entrypoints/cli/financial/test_profile_aliases.py",
        "src/cadrumo/entrypoints/cli/financial/txs.py",
        "src/cadrumo/entrypoints/cli/filing/__init__.py",
        "src/cadrumo/entrypoints/cli/filing/conftest.py",
        "src/cadrumo/entrypoints/cli/filing/test_filing_cli.py",
    )
    assert [path for path in removed if (REPO_ROOT / path).exists()] == []


def test_cadrumo_workflow_root_command_is_unknown() -> None:
    """`aeat workflow ...` is not a registered root: workflow orchestration is
    folded under `aeat app modelo`."""
    result = invoke_cached_cli(["workflow", "--help"])
    assert result.exit_code != 0


def test_cadrumo_run_root_command_is_unknown() -> None:
    """`aeat run ...` is not a registered root: the redesigned CLI exposes
    exactly two roots — `aeat config` and `aeat app`."""
    result = invoke_cached_cli(["run", "--help"])
    assert result.exit_code != 0


def test_app_modelo_preflight_verb_is_unknown() -> None:
    """No standalone `aeat app modelo preflight` verb exists. Preflight runs
    inside `verify` / `file` actions per the backend exit-cap mandate."""
    result = invoke_cached_cli(["app", "modelo", "preflight", "--help"])
    assert result.exit_code != 0


def test_app_modelo_work_resume_help_exposes_documented_argument() -> None:
    """The resume verb advertises TARGET as its sole positional.

    ``TARGET`` accepts either a 16-character workflow run id or the
    64-character work-unit id, so an operator can resume without
    holding the run-id hash by hand.
    """
    result = invoke_cached_cli(["app", "modelo", "work", "resume", "--help"])
    assert result.exit_code == 0
    # Typer renders the optional positional metavar as `[target]` in the
    # usage line (older Typer emitted bare-uppercase `TARGET`). The optional
    # TARGET positional is still advertised — only the metavar spelling moved.
    assert "[target]" in result.output


def test_profile_backend_schema_duplicate_branch_stays_removed() -> None:
    """Retired application-profile branch files must stay absent."""

    removed = (
        "src/cadrumo/application/profile/__init__.py",
        "src/cadrumo/application/profile/_actions.py",
        "src/cadrumo/application/profile/_models.py",
        "src/cadrumo/application/profile/_repository.py",
        "src/cadrumo/application/profile/test_actions.py",
        "src/cadrumo/application/profile/test_validate.py",
    )
    assert [path for path in removed if (REPO_ROOT / path).exists()] == []


def test_profile_backend_schema_deleted_package_has_no_surviving_imports() -> None:
    """Callers must use canonical user-profile services only."""

    forbidden_tokens = (
        "cadrumo.application.profile",
        "from .profile",
        "profile_bucket_repository",
        "set_active_profile",
        "set_profile_values",
    )
    search_roots = (
        REPO_ROOT / "src" / "cadrumo" / "application",
        REPO_ROOT / "src" / "cadrumo" / "entrypoints",
    )
    scanned_files = [
        path
        for root in search_roots
        for path in scan_directory(root, pattern="*.py", recursive=True)
        if path != Path(__file__)
    ]
    assert len(scanned_files) > 500, (
        f"scanned only {len(scanned_files)} modules under application/ and entrypoints/; the "
        "scan corpus collapsed (a package relocation or rename), so an empty offender list "
        "below would mean 'nothing was checked' rather than 'nothing is wrong'"
    )
    offenders: list[str] = []
    for path in scanned_files:
        text = path.read_text(encoding="utf-8")
        for token in forbidden_tokens:
            if token in text:
                offenders.append(f"{path.relative_to(REPO_ROOT).as_posix()}: {token}")
    assert offenders == [], "retired application-profile references survive:\n  " + "\n  ".join(offenders)


def test_per_modelo_aggregation_placeholder_paths_stay_removed() -> None:
    """Per-modelo aggregation must fail through registered backend errors."""

    scoped_files = (
        "src/cadrumo/application/aggregation/_retenciones.py",
        "src/cadrumo/application/aggregation/_counterpart.py",
        "src/cadrumo/application/aggregation/tests/test_retenciones.py",
        "src/cadrumo/application/aggregation/tests/test_counterpart.py",
    )
    forbidden_tokens = ("NotImplementedError", "not implemented")
    offenders: list[str] = []
    for relative_path in scoped_files:
        text = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
        for token in forbidden_tokens:
            if token in text:
                offenders.append(f"{relative_path}: {token}")
    assert offenders == [], "per-modelo aggregation placeholder paths survive:\n  " + "\n  ".join(offenders)


def test_per_modelo_aggregation_duplicate_cli_surfaces_stay_absent() -> None:
    """The CLI may expose aggregation only through the central service command."""

    canonical_cli = _CLI_ROOT / "_modelo_aggregate_cli.py"
    forbidden_family_calls = (
        "aggregate_retenciones_",
        "aggregate_counterpart_",
        "aggregate_foreign_assets_720",
    )
    offenders: list[str] = []
    for path in _all_cli_modules():
        if path.name.startswith("test_"):
            continue
        text = path.read_text(encoding="utf-8")
        if path != canonical_cli and "aggregate_per_modelo" in text:
            offenders.append(f"{path.relative_to(REPO_ROOT).as_posix()}: aggregate_per_modelo")
        for token in forbidden_family_calls:
            if token in text:
                offenders.append(f"{path.relative_to(REPO_ROOT).as_posix()}: {token}")
    assert offenders == [], "parallel per-modelo aggregation CLI surfaces survive:\n  " + "\n  ".join(offenders)


def test_censo_modelo_foundation_stays_backend_owned() -> None:
    """CLI must not reimplement Modelo 036/037 censo foundation routing."""

    forbidden_cli_tokens = (
        "CensoModeloFoundationCommand",
        "resolve_censo_modelo_foundation",
        "resolve_censo_modelo_work_unit_foundation",
        "is_active_censo_modelo",
        "CensoModeloRole",
        "active_work_unit_allowed",
        "historical_metadata_only",
    )
    offenders: list[str] = []
    for path in _all_cli_modules():
        if path.name.startswith("test_"):
            continue
        text = path.read_text(encoding="utf-8")
        for token in forbidden_cli_tokens:
            if token in text:
                offenders.append(f"{path.relative_to(REPO_ROOT).as_posix()}: {token}")
    assert offenders == [], "censo modelo foundation logic leaked into CLI:\n  " + "\n  ".join(offenders)


def test_censo_modelo_removed_shims_and_stubs_stay_removed() -> None:
    """Removed censo-foundation aliases and placeholder support must not return."""

    # test_modelo.py is excluded: its evidence-kind normalization tests legitimately
    # use aeat-justificante-pdf / aeat-csv-register / replace("-", "_") as real
    # input aliases under test — not censo shim language.
    # scopes.toml is excluded: the CENSO apoderamiento scope legitimately carries
    # "036, 037" and modelo_codes = ["036", "037"] as live AEAT catalogue data.
    registry_dir = REPO_ROOT / "src" / "cadrumo" / "domain" / "calculations" / "registry"
    registry_tests = registry_dir / "tests"
    scanned_files = (
        _CLI_ROOT / "_modelo.py",
        REPO_ROOT / "src" / "cadrumo" / "locales" / "en.yml",
        REPO_ROOT / "src" / "cadrumo" / "locales" / "es.yml",
        REPO_ROOT / "src" / "cadrumo" / "locales" / "ca.yml",
        REPO_ROOT / "src" / "cadrumo" / "locales" / "hu.yml",
        registry_dir / "_censo_modelos.py",
        registry_dir / "_queries.py",
        registry_tests / "test_censo_modelo_foundation.py",
        registry_tests / "test_censo_modelo_registry_data.py",
        registry_tests / "test_queries.py",
        *_modelo_source_paths("036"),
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
        "_CENSO_MODELO_OWNERSHIP",
        "NotImplementedError",
        "not implemented",
        "fake active",
        "synthetic 037",
        'source_modelo = "037"',
        'modelo_codes = ["036", "037"]',
    )
    # The 036 extraction profile references the synthetic fixture filename
    # ``2025-alta.pdf`` in a grounding comment; that fixture name is a legitimate
    # test-data artefact, not a stub-language leak.
    extraction_profile_exempt_tokens = {"2025-alta"}
    offenders: list[str] = []
    for path in scanned_files:
        text = path.read_text(encoding="utf-8")
        is_extraction_profile = "extraction_profiles" in path.parts
        for token in forbidden_tokens:
            if is_extraction_profile and token in extraction_profile_exempt_tokens:
                continue
            if token in text:
                offenders.append(f"{path.relative_to(REPO_ROOT).as_posix()}: {token}")
    assert offenders == [], "removed censo modelo shim/stub surfaces returned:\n  " + "\n  ".join(offenders)


def test_modelo_145_shims_stubs_and_compatibility_aliases_stay_absent() -> None:
    """Modelo 145 must stay a real local communication surface, not a compatibility shell."""

    application_dir = REPO_ROOT / "src" / "cadrumo" / "application" / "modelo"
    scanned_files = (
        _CLI_ROOT / "_modelo_m145_cli.py",
        _CLI_ROOT / "_modelo_m145_parsing.py",
        _CLI_ROOT / "_modelo_m145_rendering.py",
        _CLI_ROOT / "_modelo_payloads_m145.py",
        application_dir / "_m145_communication.py",
        application_dir / "_m145_communication_records.py",
        *_modelo_source_paths("145"),
    )
    forbidden_tokens = (
        "NotImplementedError",
        "_Fake",
        "_Stub",
        "aliases also accepted",
        "backwards compatibility",
        "compatibility alias",
        "deprecated",
        "deprecated spelling",
        "deprecation",
        "fake support",
        "not implemented",
        "shim",
        "stub",
    )
    offenders: list[str] = []
    for path in scanned_files:
        text = path.read_text(encoding="utf-8")
        for token in forbidden_tokens:
            if token in text:
                offenders.append(f"{path.relative_to(REPO_ROOT).as_posix()}: {token}")
    assert offenders == [], "modelo 145 shim/stub/compatibility surfaces returned:\n  " + "\n  ".join(offenders)


def test_legacy_application_aggregation_test_tree_stays_absent() -> None:
    """Retired top-level aggregation tests must not shadow package-owned tests."""

    legacy_tree = REPO_ROOT / "tests" / "application" / "aggregation"
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
    for path in _all_cli_modules():
        if path == canonical or path.name.startswith("test_"):
            continue
        text = path.read_text(encoding="utf-8")
        if any(pattern in text for pattern in forbidden_patterns):
            offenders.append(path.relative_to(REPO_ROOT).as_posix())
    assert offenders == []


def test_cli_observability_wrapper_module_is_absent_from_command_tree() -> None:
    """Generic run tracing is not part of the accepted CLI surface."""

    wrapper_path = REPO_ROOT / "src" / "cadrumo" / "entrypoints" / "cli" / "_observability.py"
    assert not wrapper_path.exists()

    offences: list[str] = []
    for path in _all_cli_modules():
        if path.name.startswith("test_"):
            continue
        text = path.read_text(encoding="utf-8")
        if "cli_run_context" in text or "build_arguments" in text or "._observability" in text:
            offences.append(path.relative_to(REPO_ROOT).as_posix())
    assert offences == []


def test_cli_unit_tests_do_not_contain_process_state_or_xfail_language() -> None:
    """CLI unit tests must describe executable behavior, not rollout meta-state."""

    offences: list[str] = []
    for path in _iter_cli_test_files():
        if path == Path(__file__):
            continue
        rel = path.relative_to(REPO_ROOT).as_posix()
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
