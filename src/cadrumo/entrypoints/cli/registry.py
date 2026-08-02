"""Read-only registry verification CLI commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, cast

import click
import typer
import typer._click.types as typer_click_types

from ...application.registry import (
    RegistryRevisionDiffReport,
    RegistryTreeReport,
    audit_registry_oracles,
    diff_registry_revisions,
    inspect_registry_tree,
    replay_registry_parity,
    run_registry_parity,
    verify_filed_state,
    verify_registry_tree,
    verify_registry_workbooks,
)
from ...core import NON_REGISTRY_MODELOS, Modelo
from ...core.config import load_settings
from ...core.i18n import tr
from ...core.resources import bundled_path
from ...domain.calculations.registry import OracleEnvironment as _OracleEnvironment
from ._common import _emit_envelope
from ._registry_corpus import citations_app, manuals_app
from ._registry_diff_payloads import RegistryDiffRevisionsResult
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

# The accepted-code set for the ``modelo`` argument is derived from the closed
# core identifier taxonomy, mirroring ``_MODELO_CHOICE`` in
# ``_modelo_discovery_cli.py``. Help and parse-time refusals must render even
# while a peer registry authoring slice is fail-hard invalid; the year-to-year
# resolution refusal itself still comes from the registry-backed service.
#
# typer vendors its own copy of click, so ``click.Choice`` is a
# ``click.types.ParamType`` while ``typer.Argument``'s ``click_type`` expects
# ``typer._click.types.ParamType``. They are the same object at runtime (the
# vendored click), so the cast only bridges the static type duality.
# CAST-RATIONALE-TYPER-CLICK-PARAMTYPE-DUALITY: typer vendors its own click, so
# click.Choice's click.types.ParamType and typer's typer._click.types.ParamType
# are the same runtime object behind two static names; the cast bridges only that
# static duality, with no Any escape.
_DIFF_MODELO_CHOICE: typer_click_types.ParamType = cast(
    typer_click_types.ParamType,
    click.Choice([modelo.value for modelo in Modelo if modelo not in NON_REGISTRY_MODELOS]),
)


def _metric_line(key: str, value: object) -> str:
    line = f"{tr('cli.registry.metrics.' + key)}={value}"
    return line


def _join(values: tuple[object, ...] | list[object] | set[object]) -> str:
    return ",".join(str(value) for value in values)


_RegistryRootOpt = Annotated[
    Path | None,
    typer.Option(
        "--registry-root",
        file_okay=False,
        dir_okay=True,
        readable=True,
        help=tr("cli.registry.inspect_registry_root_help"),
    ),
]
_SourceRootOpt = Annotated[
    Path | None,
    typer.Option(
        "--source-root",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        help=tr("cli.registry.verify_source_root_help"),
    ),
]


def _registry_tree_metric_lines(report: RegistryTreeReport) -> tuple[str, ...]:
    """Render the shared registry-tree inventory metrics common to inspect and verify.

    ``verify`` prepends its own ``verified`` row; every other count row is
    identical across both commands, so it is one shared projection.
    """
    return (
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
    )


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
    return value if value is not None else load_settings().cadrumo_registry_parity_store_dir


@app.command("inspect", help=tr("cli.registry.inspect_help"))
def inspect_registry_cmd(
    ctx: typer.Context,
    registry_root: _RegistryRootOpt = None,
) -> None:
    """Load the read-only registry tree and report inventory counts."""
    registry_root = _resolve_registry_root(registry_root)
    report = inspect_registry_tree(registry_root)
    _emit_envelope(
        ctx,
        command="registry.inspect",
        result=RegistryInspectResult.model_validate(report.model_dump(mode="json")),
        lines=_registry_tree_metric_lines(report),
    )


@app.command("verify", help=tr("cli.registry.verify_help"))
def verify_registry_cmd(
    ctx: typer.Context,
    registry_root: _RegistryRootOpt = None,
    source_root: _SourceRootOpt = None,
) -> None:
    """Validate every registry modelo against shared legal/source catalogues."""
    registry_root = _resolve_registry_root(registry_root)
    resolved_source_root = _resolve_source_root(source_root)
    report = verify_registry_tree(registry_root, source_root=resolved_source_root)
    _emit_envelope(
        ctx,
        command="registry.verify",
        result=RegistryVerifyResult.model_validate(report.model_dump(mode="json")),
        lines=(
            _metric_line("verified", report.verified),
            *_registry_tree_metric_lines(report),
        ),
    )


@app.command("audit-oracles", help=tr("cli.registry.audit_oracles_help"))
def audit_oracles_cmd(
    ctx: typer.Context,
    registry_root: _RegistryRootOpt = None,
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
        result=RegistryAuditOraclesResult(
            environment=report.environment,
            registered_oracle_ids=list(report.registered_oracle_ids),
            failure_count=report.failure_count,
            failures=list(report.failures),
            applicability_declarations=list(report.applicability_declarations),
            orphan_oracle_ids=list(report.orphan_oracle_ids),
        ),
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
    registry_root: _RegistryRootOpt = None,
    source_root: _SourceRootOpt = None,
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
        result=RegistryVerifyFiledStateResult(
            observation_path=report.observation_path,
            source_observation_paths=list(report.source_observation_paths),
            comparison=report.comparison,
        ),
        lines=lines,
    )


@app.command("diff-revisions", help=tr("cli.registry.diff_revisions_help"))
def diff_revisions_cmd(
    ctx: typer.Context,
    modelo: Annotated[
        str,
        typer.Argument(click_type=_DIFF_MODELO_CHOICE, help=tr("cli.registry.diff_revisions_modelo_help")),
    ],
    from_year: Annotated[
        int,
        typer.Option("--from-year", help=tr("cli.registry.diff_revisions_from_year_help")),
    ],
    to_year: Annotated[
        int,
        typer.Option("--to-year", help=tr("cli.registry.diff_revisions_to_year_help")),
    ],
    registry_root: _RegistryRootOpt = None,
    source_root: _SourceRootOpt = None,
) -> None:
    """Diff the two registry revisions of one modelo that cover ``--from-year`` and ``--to-year``.

    Surfaces what changed in the AEAT filing rulebook year-to-year: added,
    removed, and renumbered casillas; changed formulas, parameters
    (rates/thresholds), and bindings; and revision-level legal reference
    deltas. Each bare filing year resolves to exactly one covering revision;
    an ambiguous or uncovered year is refused naming the modelo's declared
    revisions.
    """
    report = diff_registry_revisions(
        modelo,
        from_year=from_year,
        to_year=to_year,
        registry_root=_resolve_registry_root(registry_root),
        source_root=_resolve_source_root(source_root),
    )
    _emit_envelope(
        ctx,
        command="registry.diff_revisions",
        result=RegistryDiffRevisionsResult.model_validate(report.model_dump(mode="json")),
        lines=_diff_revisions_lines(report),
    )


def _diff_revisions_lines(report: RegistryRevisionDiffReport) -> list[str]:
    lines = [
        _metric_line("modelo", report.modelo),
        _metric_line("from_revision_id", report.from_revision_id),
        _metric_line("to_revision_id", report.to_revision_id),
        _metric_line("same_revision", report.same_revision),
        _metric_line("added_casilla_count", len(report.added_casillas)),
        _metric_line("removed_casilla_count", len(report.removed_casillas)),
        _metric_line("renumbered_casilla_count", len(report.renumbered_casillas)),
        _metric_line("changed_casilla_legal_ref_count", len(report.changed_casilla_legal_refs)),
        _metric_line("added_formula_count", len(report.added_formulas)),
        _metric_line("removed_formula_count", len(report.removed_formulas)),
        _metric_line("changed_formula_count", len(report.changed_formulas)),
        _metric_line("added_parameter_count", len(report.added_parameters)),
        _metric_line("removed_parameter_count", len(report.removed_parameters)),
        _metric_line("changed_parameter_count", len(report.changed_parameters)),
        _metric_line("added_binding_count", len(report.added_bindings)),
        _metric_line("removed_binding_count", len(report.removed_bindings)),
        _metric_line("revision_legal_refs_added", ",".join(report.revision_legal_refs_added)),
        _metric_line("revision_legal_refs_removed", ",".join(report.revision_legal_refs_removed)),
    ]
    for casilla in report.added_casillas:
        lines.append("\t".join(("added_casilla", casilla.id, casilla.number, casilla.label)))
    for casilla in report.removed_casillas:
        lines.append("\t".join(("removed_casilla", casilla.id, casilla.number, casilla.label)))
    for renumbered in report.renumbered_casillas:
        lines.append(
            "\t".join(
                (
                    "renumbered_casilla",
                    renumbered.continuidad_id,
                    f"{renumbered.from_id}({renumbered.from_number})",
                    f"{renumbered.to_id}({renumbered.to_number})",
                ),
            ),
        )
    lines.extend(f"changed_casilla_legal_refs\t{casilla_id}" for casilla_id in report.changed_casilla_legal_refs)
    lines.extend(f"added_formula\t{formula_id}" for formula_id in report.added_formulas)
    lines.extend(f"removed_formula\t{formula_id}" for formula_id in report.removed_formulas)
    for formula in report.changed_formulas:
        lines.append("\t".join(("changed_formula", formula.id, formula.target_casilla_id)))
    lines.extend(f"added_parameter\t{parameter_id}" for parameter_id in report.added_parameters)
    lines.extend(f"removed_parameter\t{parameter_id}" for parameter_id in report.removed_parameters)
    for parameter in report.changed_parameters:
        lines.append("\t".join(("changed_parameter", parameter.id, parameter.data_type)))
    for binding in report.added_bindings:
        lines.append("\t".join(("added_binding", binding.id, binding.source)))
    for binding in report.removed_bindings:
        lines.append("\t".join(("removed_binding", binding.id, binding.source)))
    return lines


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
        result=RegistryWorkbooksVerifyResult(
            root=report.root,
            workbook_count=report.workbook_count,
            scanned_count=report.scanned_count,
            formula_workbook_count=report.formula_workbook_count,
            unsupported_xls_count=report.unsupported_xls_count,
            failed_count=report.failed_count,
            runner=report.runner,
            reports=list(report.reports),
            modelo_coverage=list(report.modelo_coverage),
        ),
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
    registry_root: _RegistryRootOpt = None,
    source_root: _SourceRootOpt = None,
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
    resolved_registry_root = _resolve_registry_root(registry_root)
    resolved_source_root = _resolve_source_root(source_root)
    tape, target = run_registry_parity(
        scenario_path=scenario_path,
        registry_root=resolved_registry_root,
        source_root=resolved_source_root,
        store_root=_resolve_parity_store_root(store_root),
        output=output,
    )
    _emit_envelope(
        ctx,
        command="registry.parity.run",
        result=RegistryParityRunResult(
            created_at=tape.created_at,
            scenario_path=tape.scenario_path,
            scenario=tape.scenario,
            workbook=tape.workbook,
            runner=tape.runner,
            report=tape.report,
            path=tape.path,
        ),
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
    registry_root: _RegistryRootOpt = None,
    source_root: _SourceRootOpt = None,
) -> None:
    """Replay one archived parity tape against the current registry runtime."""
    resolved_registry_root = _resolve_registry_root(registry_root)
    resolved_source_root = _resolve_source_root(source_root)
    report = replay_registry_parity(
        tape_path=tape_path,
        registry_root=resolved_registry_root,
        source_root=resolved_source_root,
    )
    _emit_envelope(
        ctx,
        command="registry.parity.replay",
        result=RegistryParityReplayResult(
            tape_path=report.tape_path,
            scenario_id=report.scenario_id,
            status=report.status,
            differences=list(report.differences),
            stored=report.stored,
            current=report.current,
        ),
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
