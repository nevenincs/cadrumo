"""Read-only registry verification CLI commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from ...application.registry import (
    audit_registry_oracles,
    inspect_registry_tree,
    replay_registry_parity,
    run_registry_parity,
    verify_filed_state,
    verify_registry_tree,
    verify_registry_workbooks,
)
from ...core.config import load_settings
from ...core.i18n import tr
from ...core.resources import bundled_path
from ...domain.calculations.registry import OracleEnvironment as _OracleEnvironment
from ._common import _emit_envelope
from ._registry_corpus import citations_app, manuals_app
from ._registry_payloads import (
    RegistryAuditOraclesResult,
    RegistryInspectResult,
    RegistryParityReplayResult,
    RegistryParityRunResult,
    RegistryVerifyFiledStateResult,
    RegistryVerifyResult,
    RegistryWorkbooksVerifyResult,
)

app = typer.Typer(
    name="registry",
    help=tr("cli.registry.app_help"),
    no_args_is_help=True,
    add_completion=False,
)
workbooks_app = typer.Typer(
    name="workbooks",
    help=tr("cli.registry.workbooks_app_help"),
    no_args_is_help=True,
    add_completion=False,
)
parity_app = typer.Typer(
    name="parity",
    help=tr("cli.registry.parity_app_help"),
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(workbooks_app, name="workbooks")
app.add_typer(parity_app, name="parity")
app.add_typer(citations_app, name="citations")
app.add_typer(manuals_app, name="manuals")


def _metric_line(key: str, value: object) -> str:
    line = f"{tr('cli.registry.metrics.' + key)}={value}"
    return line


def _join(values: tuple[object, ...] | list[object] | set[object]) -> str:
    return ",".join(str(value) for value in values)


def _resolve_registry_root(value: Path | None) -> Path:
    return value if value is not None else bundled_path("registry", "aeat")


def _resolve_workbook_root(value: Path | None) -> Path:
    return value if value is not None else bundled_path("corpus", "aeat_official", "disenos_registro")


def _resolve_source_root(value: Path | None) -> Path:
    """Resolve the corpus/source root, defaulting to the bundled data root.

    Source citations carry corpus-root-relative paths (``corpus/...``);
    they only resolve against the bundled data root, never the operator's
    current working directory.
    """
    return value if value is not None else bundled_path()


def _resolve_parity_store_root(value: Path | None) -> Path:
    return value if value is not None else load_settings().aeat_registry_parity_store_dir


@app.command("inspect", help=tr("cli.registry.inspect_help"))
def inspect_registry_cmd(
    ctx: typer.Context,
    registry_root: Annotated[
        Path | None,
        typer.Option(
            "--registry-root",
            file_okay=False,
            dir_okay=True,
            readable=True,
            help=tr("cli.registry.inspect_registry_root_help"),
        ),
    ] = None,
) -> None:
    """Load the read-only registry tree and report inventory counts."""
    registry_root = _resolve_registry_root(registry_root)
    report = inspect_registry_tree(registry_root)
    _emit_envelope(
        ctx,
        command="registry.inspect",
        result=RegistryInspectResult.model_validate(report.model_dump(mode="json")),
        lines=(
            _metric_line("modelo_count", report.modelo_count),
            _metric_line("revision_count", report.revision_count),
            _metric_line("legal_reference_count", report.legal_reference_count),
            _metric_line("source_reference_count", report.source_reference_count),
            _metric_line("casilla_count", report.casilla_count),
            _metric_line("formula_count", report.formula_count),
            _metric_line("extraction_profile_count", report.extraction_profile_count),
            _metric_line("cross_reference_count", report.cross_reference_count),
            _metric_line("workbook_parity_ref_count", report.workbook_parity_ref_count),
            _metric_line("verification_expectation_count", report.verification_expectation_count),
            _metric_line("application_link_count", report.application_link_count),
            _metric_line("application_link_surfaces", _join(list(report.application_link_surfaces))),
            _metric_line("modelos", _join(list(report.modelos))),
        ),
    )


@app.command("verify", help=tr("cli.registry.verify_help"))
def verify_registry_cmd(
    ctx: typer.Context,
    registry_root: Annotated[
        Path | None,
        typer.Option(
            "--registry-root",
            file_okay=False,
            dir_okay=True,
            readable=True,
            help=tr("cli.registry.inspect_registry_root_help"),
        ),
    ] = None,
    source_root: Annotated[
        Path | None,
        typer.Option(
            "--source-root",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            help=tr("cli.registry.verify_source_root_help"),
        ),
    ] = None,
) -> None:
    """Validate every registry modelo against shared legal/source catalogues."""
    registry_root = _resolve_registry_root(registry_root)
    report = verify_registry_tree(registry_root, source_root=_resolve_source_root(source_root))
    _emit_envelope(
        ctx,
        command="registry.verify",
        result=RegistryVerifyResult.model_validate(report.model_dump(mode="json")),
        lines=(
            _metric_line("verified", report.verified),
            _metric_line("modelo_count", report.modelo_count),
            _metric_line("revision_count", report.revision_count),
            _metric_line("legal_reference_count", report.legal_reference_count),
            _metric_line("source_reference_count", report.source_reference_count),
            _metric_line("casilla_count", report.casilla_count),
            _metric_line("formula_count", report.formula_count),
            _metric_line("extraction_profile_count", report.extraction_profile_count),
            _metric_line("cross_reference_count", report.cross_reference_count),
            _metric_line("workbook_parity_ref_count", report.workbook_parity_ref_count),
            _metric_line("verification_expectation_count", report.verification_expectation_count),
            _metric_line("application_link_count", report.application_link_count),
            _metric_line("application_link_surfaces", _join(list(report.application_link_surfaces))),
            _metric_line("modelos", _join(list(report.modelos))),
        ),
    )


@app.command("audit-oracles", help=tr("cli.registry.audit_oracles_help"))
def audit_oracles_cmd(
    ctx: typer.Context,
    registry_root: Annotated[
        Path | None,
        typer.Option(
            "--registry-root",
            file_okay=False,
            dir_okay=True,
            readable=True,
            help=tr("cli.registry.inspect_registry_root_help"),
        ),
    ] = None,
    environment: Annotated[
        str,
        typer.Option(
            "--environment",
            help=tr("cli.registry.audit_oracles_environment_help"),
        ),
    ] = _OracleEnvironment.PRODUCTION,
) -> None:
    """Audit registered live-parity oracles against every modelo's cross-reference bindings.

    Loads the registry, registers every committed oracle adapter into a
    fresh catalogue, then runs ``audit_registry_oracle_bindings``. Each
    failure names the modelo, revision, cross-reference, oracle id, and
    underlying catalogue error. Exit code is non-zero when failures
    exist so CI / pre-deploy pipelines can gate on a clean audit.
    """
    registry_root = _resolve_registry_root(registry_root)
    report = audit_registry_oracles(registry_root, environment=environment)
    lines = [
        _metric_line("environment", report.environment),
        _metric_line("registered_oracle_ids", ",".join(report.registered_oracle_ids)),
        _metric_line("failure_count", report.failure_count),
        _metric_line("applicability_declaration_count", len(report.applicability_declarations)),
        _metric_line("orphan_oracle_ids", ",".join(report.orphan_oracle_ids)),
    ]
    lines.extend(_metric_line(f"failure[{index}]", failure) for index, failure in enumerate(report.failures))
    lines.extend(
        _metric_line(
            f"applicability[{index}]",
            f"{declaration.modelo_id}:{declaration.cross_reference_id} "
            f"mode={declaration.applicability_condition_mode} "
            f"fields={','.join(declaration.predicate_fields)}",
        )
        for index, declaration in enumerate(report.applicability_declarations)
    )
    _emit_envelope(
        ctx,
        command="registry.audit_oracles",
        result=RegistryAuditOraclesResult.model_validate(report.model_dump(mode="json")),
        lines=lines,
    )
    if report.failures:
        raise typer.Exit(code=1)


@app.command("verify-filed-state", help=tr("cli.registry.verify_filed_state_help"))
def verify_filed_state_cmd(
    ctx: typer.Context,
    observation_path: Annotated[
        Path,
        typer.Option(
            "--observation",
            help=tr("cli.registry.observation_help"),
        ),
    ],
    source_observation_paths: Annotated[
        list[Path] | None,
        typer.Option(
            "--source-observation",
            help=tr("cli.registry.source_observation_help"),
        ),
    ] = None,
    registry_root: Annotated[
        Path | None,
        typer.Option(
            "--registry-root",
            file_okay=False,
            dir_okay=True,
            readable=True,
            help=tr("cli.registry.inspect_registry_root_help"),
        ),
    ] = None,
    source_root: Annotated[
        Path | None,
        typer.Option(
            "--source-root",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            help=tr("cli.registry.verify_source_root_help"),
        ),
    ] = None,
    required_casilla_refs: Annotated[
        list[str] | None,
        typer.Option("--casilla", help=tr("cli.registry.casilla_help")),
    ] = None,
) -> None:
    """Verify local registry calculation output against captured filed state."""
    report = verify_filed_state(
        observation_path=observation_path,
        source_observation_paths=tuple(source_observation_paths or ()),
        registry_root=_resolve_registry_root(registry_root),
        source_root=_resolve_source_root(source_root),
        required_casilla_ids=tuple(required_casilla_refs or ()),
    )
    comparison = report.comparison
    lines = [
        _metric_line("status", comparison.status),
        _metric_line("modelo", comparison.modelo),
        _metric_line("revision", comparison.revision),
        _metric_line("compared_casilla_ids", ",".join(comparison.compared_casilla_ids)),
        _metric_line("missing_local_casilla_ids", ",".join(comparison.missing_local_casilla_ids)),
        _metric_line("missing_filed_casilla_ids", ",".join(comparison.missing_filed_casilla_ids)),
        _metric_line("drift_count", len(comparison.drifts)),
    ]
    for drift in comparison.drifts:
        lines.append(
            _metric_line(
                "drift",
                f"{drift.casilla_id}\tlocal={drift.local_value}\tfiled={drift.filed_value}\tdelta={drift.delta}",
            ),
        )
    _emit_envelope(
        ctx,
        command="registry.verify_filed_state",
        result=RegistryVerifyFiledStateResult.model_validate(report.model_dump(mode="json")),
        lines=lines,
    )


@workbooks_app.command("verify", help=tr("cli.registry.workbooks_verify_help"))
def verify_workbooks_cmd(
    ctx: typer.Context,
    root: Annotated[
        Path | None,
        typer.Option(
            "--root",
            file_okay=False,
            dir_okay=True,
            readable=True,
            help=tr("cli.registry.workbooks_root_help"),
        ),
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option("--limit", min=1, help=tr("cli.registry.workbooks_limit_help")),
    ] = None,
    per_file_timeout_seconds: Annotated[
        float,
        typer.Option("--per-file-timeout", min=0.1, help=tr("cli.registry.workbooks_timeout_help")),
    ] = 10.0,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            file_okay=True,
            dir_okay=False,
            writable=True,
            help=tr("cli.registry.workbooks_output_help"),
        ),
    ] = None,
    resume_from: Annotated[
        Path | None,
        typer.Option(
            "--resume-from",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help=tr("cli.registry.workbooks_resume_help"),
        ),
    ] = None,
) -> None:
    """Run the read-only workbook parity backend verification."""
    report = verify_registry_workbooks(
        root=_resolve_workbook_root(root),
        limit=limit,
        per_file_timeout_seconds=per_file_timeout_seconds,
        resume_from=resume_from,
        output=output,
    )
    _emit_envelope(
        ctx,
        command="registry.workbooks.verify",
        result=RegistryWorkbooksVerifyResult.model_validate(report.model_dump(mode="json")),
        lines=(
            _metric_line("backend_exists", report.backend_exists),
            _metric_line("passed", report.passed),
            _metric_line("workbook_count", report.workbook_count),
            _metric_line("scanned_count", report.scanned_count),
            _metric_line("formula_workbook_count", report.formula_workbook_count),
            _metric_line("unsupported_xls_count", report.unsupported_xls_count),
            _metric_line("failed_count", report.failed_count),
            _metric_line("runner_status", report.runner.status),
            _metric_line("runner_detail", report.runner.detail),
        ),
    )


@parity_app.command("run", help=tr("cli.registry.parity_run_help"))
def run_parity_cmd(
    ctx: typer.Context,
    scenario_path: Annotated[
        Path,
        typer.Option(
            "--scenario",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help=tr("cli.registry.parity_scenario_help"),
        ),
    ],
    registry_root: Annotated[
        Path | None,
        typer.Option(
            "--registry-root",
            file_okay=False,
            dir_okay=True,
            readable=True,
            help=tr("cli.registry.inspect_registry_root_help"),
        ),
    ] = None,
    source_root: Annotated[
        Path | None,
        typer.Option(
            "--source-root",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            help=tr("cli.registry.verify_source_root_help"),
        ),
    ] = None,
    store_root: Annotated[
        Path | None,
        typer.Option(
            "--store-root",
            file_okay=False,
            dir_okay=True,
            writable=True,
            help=tr("cli.registry.parity_store_root_help"),
        ),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            file_okay=True,
            dir_okay=False,
            writable=True,
            help=tr("cli.registry.parity_output_help"),
        ),
    ] = None,
) -> None:
    """Run one stored parity scenario and archive the resulting tape."""
    tape, target = run_registry_parity(
        scenario_path=scenario_path,
        registry_root=_resolve_registry_root(registry_root),
        source_root=_resolve_source_root(source_root),
        store_root=_resolve_parity_store_root(store_root),
        output=output,
    )
    _emit_envelope(
        ctx,
        command="registry.parity.run",
        result=RegistryParityRunResult.model_validate(tape.model_dump(mode="json")),
        lines=(
            _metric_line("scenario_id", tape.scenario.id),
            _metric_line("status", tape.report.status),
            _metric_line("tape_path", target.as_posix()),
            _metric_line("workbook_path", tape.scenario.workbook_path.as_posix()),
            _metric_line("comparison_count", len(tape.report.comparisons)),
        ),
    )


@parity_app.command("replay", help=tr("cli.registry.parity_replay_help"))
def replay_parity_cmd(
    ctx: typer.Context,
    tape_path: Annotated[
        Path,
        typer.Option(
            "--tape",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help=tr("cli.registry.parity_tape_help"),
        ),
    ],
    registry_root: Annotated[
        Path | None,
        typer.Option(
            "--registry-root",
            file_okay=False,
            dir_okay=True,
            readable=True,
            help=tr("cli.registry.inspect_registry_root_help"),
        ),
    ] = None,
    source_root: Annotated[
        Path | None,
        typer.Option(
            "--source-root",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            help=tr("cli.registry.verify_source_root_help"),
        ),
    ] = None,
) -> None:
    """Replay one archived parity tape against the current registry runtime."""
    report = replay_registry_parity(
        tape_path=tape_path,
        registry_root=_resolve_registry_root(registry_root),
        source_root=_resolve_source_root(source_root),
    )
    _emit_envelope(
        ctx,
        command="registry.parity.replay",
        result=RegistryParityReplayResult.model_validate(report.model_dump(mode="json")),
        lines=(
            _metric_line("scenario_id", report.scenario_id),
            _metric_line("status", report.status),
            _metric_line("difference_count", len(report.differences)),
            _metric_line("differences", ",".join(report.differences)),
        ),
    )


__all__ = [
    "app",
    "inspect_registry_cmd",
    "parity_app",
    "replay_parity_cmd",
    "run_parity_cmd",
    "verify_filed_state_cmd",
    "verify_registry_cmd",
    "verify_workbooks_cmd",
    "workbooks_app",
]
