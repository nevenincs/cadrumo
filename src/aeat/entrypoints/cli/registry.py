"""Read-only registry verification CLI commands."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, NamedTuple

import typer
from pydantic import BaseModel, ConfigDict

from ...adapters.outbound.aeat.auth import AeatSession
from ...adapters.outbound.aeat.auth._providers import ClaveMovilSessionDetail
from ...adapters.outbound.aeat.sede import (
    Declaration,
    FiledDeclarationObservationStore,
    capture_filed_declaration_observation,
    shared_playwright,
    walk_declarations_register,
)
from ...application.auth import AuthProviderKind
from ...core.config import Settings, load_settings
from ...domain.calculations.registry import RegistryValidator, load_registry_tree, verify_workbook_backend
from ...domain.calculations.registry._workbook_parity import WorkbookBackendVerificationReport
from ._i18n import tr
from .auth import _session
from .auth._paths import storage_state_paths

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
app.add_typer(workbooks_app, name="workbooks")


class RegistryTreeReport(BaseModel):
    """Read-only registry tree load or verification result."""

    model_config = ConfigDict(frozen=True)

    registry_root: str
    source_root: str | None = None
    modelo_count: int
    revision_count: int
    legal_reference_count: int
    source_reference_count: int
    casilla_count: int
    formula_count: int
    extraction_profile_count: int
    cross_reference_count: int
    workbook_parity_ref_count: int
    verification_expectation_count: int
    application_link_count: int
    application_link_surfaces: tuple[str, ...]
    relation_count: int
    relation_dependency_roles: tuple[str, ...]
    filing_schedule_count: int
    modelos: tuple[str, ...]
    revision_details: tuple[RegistryRevisionDetailReport, ...]
    verified: bool


class RegistryWorkbookParityDetailReport(BaseModel):
    """Workbook parity coverage declared by one registry revision."""

    model_config = ConfigDict(frozen=True)

    id: str
    workbook_source: str
    formula_coverage: str
    runner_required: bool
    output_cell_count: int


class RegistryRevisionDetailReport(BaseModel):
    """Read-only details for one modelo revision from the central registry."""

    model_config = ConfigDict(frozen=True)

    modelo: str
    revision: str
    legal_refs: tuple[str, ...]
    source_refs: tuple[str, ...]
    export_layout_ids: tuple[str, ...]
    export_layout_count: int
    export_record_count: int
    export_field_count: int
    deadline_window_count: int
    deadline_periods: tuple[str, ...]
    relation_ids: tuple[str, ...]
    relation_count: int
    relation_dependency_roles: tuple[str, ...]
    filing_schedule_ids: tuple[str, ...]
    filing_schedule_count: int
    portal_guard_policy_ids: tuple[str, ...]
    workbook_parity: tuple[RegistryWorkbookParityDetailReport, ...]
    support_removal_decision_count: int


class FiledDataCaptureReport(BaseModel):
    """Read-only filed-declaration capture report."""

    model_config = ConfigDict(frozen=True)

    output_root: str
    modelo: str
    year: int
    captured_count: int
    observation_paths: tuple[str, ...]
    artefact_refs: tuple[str, ...]
    casilla_count: int


class FiledDataListingRow(BaseModel):
    """One filed declaration row listed from AEAT without downloading artefacts."""

    model_config = ConfigDict(frozen=True)

    modelo: str
    year: int
    period: str
    expediente_id: str
    status: str
    presented_at: datetime
    has_submitted_file: bool
    has_declaration_copy: bool
    has_justificante: bool


class FiledDataListingReport(BaseModel):
    """Read-only filed-declaration listing report."""

    model_config = ConfigDict(frozen=True)

    modelo: str
    year_from: int
    year_to: int
    row_count: int
    rows: tuple[FiledDataListingRow, ...]


class RegistryRevisionInventory(NamedTuple):
    casilla_count: int
    formula_count: int
    extraction_profile_count: int
    cross_reference_count: int
    workbook_parity_ref_count: int
    verification_expectation_count: int
    application_link_count: int
    application_link_surfaces: tuple[str, ...]
    relation_count: int
    relation_dependency_roles: tuple[str, ...]
    filing_schedule_count: int


def _revision_inventory(modelos) -> RegistryRevisionInventory:
    revisions = tuple(revision for modelo in modelos for revision in modelo.revisions.values())
    application_surfaces = {link.surface for revision in revisions for link in revision.application_links}
    relation_roles = {relation.dependency_role for revision in revisions for relation in revision.relations}
    return RegistryRevisionInventory(
        casilla_count=sum(len(revision.casillas) for revision in revisions),
        formula_count=sum(len(revision.formulas) for revision in revisions),
        extraction_profile_count=sum(len(revision.extraction_profiles) for revision in revisions),
        cross_reference_count=sum(len(revision.live_cross_references) for revision in revisions),
        workbook_parity_ref_count=sum(len(revision.workbook_parity_refs) for revision in revisions),
        verification_expectation_count=sum(len(revision.verification_expectations) for revision in revisions),
        application_link_count=sum(len(revision.application_links) for revision in revisions),
        application_link_surfaces=tuple(sorted(application_surfaces)),
        relation_count=sum(len(revision.relations) for revision in revisions),
        relation_dependency_roles=tuple(sorted(relation_roles)),
        filing_schedule_count=sum(len(revision.filing_schedules) for revision in revisions),
    )


def _revision_details(modelos) -> tuple[RegistryRevisionDetailReport, ...]:
    reports: list[RegistryRevisionDetailReport] = []
    for modelo in sorted(modelos, key=lambda item: item.id):
        for revision_id, revision in sorted(modelo.revisions.items()):
            export_records = tuple(record for layout in revision.export_layouts for record in layout.records)
            export_fields = tuple(field for record in export_records for field in record.fields)
            workbook_parity = tuple(
                RegistryWorkbookParityDetailReport(
                    id=str(reference.id),
                    workbook_source=str(reference.workbook_source),
                    formula_coverage=reference.formula_coverage,
                    runner_required=reference.runner_required,
                    output_cell_count=len(reference.output_cells),
                )
                for reference in sorted(revision.workbook_parity_refs, key=lambda item: item.id)
            )
            reports.append(
                RegistryRevisionDetailReport(
                    modelo=str(modelo.id),
                    revision=str(revision_id),
                    legal_refs=tuple(str(ref) for ref in revision.legal_refs),
                    source_refs=tuple(str(ref) for ref in revision.source_refs),
                    export_layout_ids=tuple(str(layout.id) for layout in revision.export_layouts),
                    export_layout_count=len(revision.export_layouts),
                    export_record_count=len(export_records),
                    export_field_count=len(export_fields),
                    deadline_window_count=len(revision.deadline_windows),
                    deadline_periods=tuple(sorted(window.period for window in revision.deadline_windows)),
                    relation_ids=tuple(str(relation.id) for relation in revision.relations),
                    relation_count=len(revision.relations),
                    relation_dependency_roles=tuple(
                        sorted({relation.dependency_role for relation in revision.relations})
                    ),
                    filing_schedule_ids=tuple(str(schedule.id) for schedule in revision.filing_schedules),
                    filing_schedule_count=len(revision.filing_schedules),
                    portal_guard_policy_ids=tuple(
                        sorted({decision.guard_policy_id for decision in revision.live_cross_references})
                    ),
                    workbook_parity=workbook_parity,
                    support_removal_decision_count=len(revision.support_removal_decisions),
                )
            )
    return tuple(reports)


def _emit_metric(key: str, value: object) -> None:
    line = f"{tr('cli.registry.metrics.' + key)}={value}"
    typer.echo(line)


def inspect_registry_tree(registry_root: Path) -> RegistryTreeReport:
    """Load the registry tree and return stable read-only inventory counts."""

    modelos, catalogues = load_registry_tree(registry_root)
    inventory = _revision_inventory(modelos)
    return RegistryTreeReport(
        registry_root=str(registry_root),
        modelo_count=len(modelos),
        revision_count=sum(len(modelo.revisions) for modelo in modelos),
        legal_reference_count=len(catalogues.legal),
        source_reference_count=len(catalogues.sources),
        casilla_count=inventory.casilla_count,
        formula_count=inventory.formula_count,
        extraction_profile_count=inventory.extraction_profile_count,
        cross_reference_count=inventory.cross_reference_count,
        workbook_parity_ref_count=inventory.workbook_parity_ref_count,
        verification_expectation_count=inventory.verification_expectation_count,
        application_link_count=inventory.application_link_count,
        application_link_surfaces=inventory.application_link_surfaces,
        relation_count=inventory.relation_count,
        relation_dependency_roles=inventory.relation_dependency_roles,
        filing_schedule_count=inventory.filing_schedule_count,
        modelos=tuple(sorted(modelo.id for modelo in modelos)),
        revision_details=_revision_details(modelos),
        verified=False,
    )


def verify_registry_tree(registry_root: Path, *, source_root: Path) -> RegistryTreeReport:
    """Load and fail-fast validate every registry modelo against shared catalogues."""

    modelos, catalogues = load_registry_tree(registry_root)
    validator = RegistryValidator(catalogues, source_root=source_root)
    validator.validate_registry(modelos)
    inventory = _revision_inventory(modelos)
    return RegistryTreeReport(
        registry_root=str(registry_root),
        source_root=str(source_root),
        modelo_count=len(modelos),
        revision_count=sum(len(modelo.revisions) for modelo in modelos),
        legal_reference_count=len(catalogues.legal),
        source_reference_count=len(catalogues.sources),
        casilla_count=inventory.casilla_count,
        formula_count=inventory.formula_count,
        extraction_profile_count=inventory.extraction_profile_count,
        cross_reference_count=inventory.cross_reference_count,
        workbook_parity_ref_count=inventory.workbook_parity_ref_count,
        verification_expectation_count=inventory.verification_expectation_count,
        application_link_count=inventory.application_link_count,
        application_link_surfaces=inventory.application_link_surfaces,
        relation_count=inventory.relation_count,
        relation_dependency_roles=inventory.relation_dependency_roles,
        filing_schedule_count=inventory.filing_schedule_count,
        modelos=tuple(sorted(modelo.id for modelo in modelos)),
        revision_details=_revision_details(modelos),
        verified=True,
    )


def select_declarations_for_capture(
    declarations: tuple[Declaration, ...],
    *,
    period: str | None = None,
    expediente_id: str | None = None,
    limit: int | None = None,
) -> tuple[Declaration, ...]:
    """Select filed-declaration rows for capture from one register query."""

    selected = declarations
    if period is not None:
        selected = tuple(row for row in selected if row.period.upper() == period.upper())
    if expediente_id is not None:
        selected = tuple(row for row in selected if row.expediente_id == expediente_id)
    if expediente_id is not None and not selected:
        raise typer.BadParameter(f"AEAT declaration register did not return expediente {expediente_id!r}")
    if limit is not None:
        selected = selected[:limit]
    return selected


def _filed_data_listing_row(declaration: Declaration) -> FiledDataListingRow:
    return FiledDataListingRow(
        modelo=declaration.modelo,
        year=declaration.ejercicio,
        period=declaration.period,
        expediente_id=declaration.expediente_id,
        status=declaration.estado,
        presented_at=declaration.presented_at,
        has_submitted_file=bool(declaration.archive_link_text and declaration.archive_cell_index is not None),
        has_declaration_copy=bool(
            declaration.declaration_copy_link_text and declaration.declaration_copy_cell_index is not None
        ),
        has_justificante=bool(declaration.justificante_link_text and declaration.justificante_cell_index is not None),
    )


def _active_clave_movil_session() -> tuple[AeatSession, Settings]:
    settings = load_settings()
    persisted_session = _session.load(settings, AuthProviderKind.CLAVE_MOVIL)
    if persisted_session is None:
        raise typer.BadParameter(
            "No active Cl@ve Movil AEAT session; run `aeat auth login --provider clave_movil` before reading filed data"
        )
    if persisted_session.is_expired(datetime.now(UTC)):
        raise typer.BadParameter(
            "Cl@ve Movil AEAT session is expired; "
            "run `aeat auth login --provider clave_movil` before reading filed data"
        )
    if persisted_session.provider_kind is not AuthProviderKind.CLAVE_MOVIL:
        raise typer.BadParameter("Filed-data reads currently require an active Cl@ve Movil AEAT session")
    return (
        AeatSession(
            provider_kind=persisted_session.provider_kind,
            authenticated_at=persisted_session.authenticated_at,
            idle_deadline=persisted_session.idle_deadline,
            storage_state_path=storage_state_paths(settings, persisted_session.provider_kind).storage_state,
            identity_nif=persisted_session.identity_nif,
            provider_detail=ClaveMovilSessionDetail(
                dni_nie=persisted_session.identity_nif,
                used_non_qr_fallback=True,
                verification_code=None,
            ),
        ),
        settings,
    )


async def list_filed_data(
    *,
    modelo: str,
    year_from: int,
    year_to: int,
) -> FiledDataListingReport:
    """List filed declaration rows through the active AEAT session without downloading artefacts."""

    if year_from > year_to:
        raise typer.BadParameter(tr("cli.registry.errors.invalid_year_range"))
    session, settings = _active_clave_movil_session()
    rows: list[FiledDataListingRow] = []
    async with shared_playwright(session) as playwright:
        for year in range(year_to, year_from - 1, -1):
            declarations = await walk_declarations_register(
                session,
                modelo=modelo,
                ejercicio=year,
                settings=settings,
                playwright=playwright,
            )
            rows.extend(_filed_data_listing_row(declaration) for declaration in declarations)
    return FiledDataListingReport(
        modelo=modelo,
        year_from=year_from,
        year_to=year_to,
        row_count=len(rows),
        rows=tuple(rows),
    )


async def capture_filed_data(
    *,
    modelo: str,
    year: int,
    output_root: Path,
    period: str | None = None,
    expediente_id: str | None = None,
    limit: int | None = None,
) -> FiledDataCaptureReport:
    """Capture filed-declaration artefacts through the active AEAT session."""

    session, _settings = _active_clave_movil_session()
    store = FiledDeclarationObservationStore(output_root)
    observation_paths: list[str] = []
    artefact_refs: list[str] = []
    casilla_count = 0

    async with shared_playwright(session) as playwright:
        declarations = await walk_declarations_register(
            session,
            modelo=modelo,
            ejercicio=year,
            playwright=playwright,
        )
        selected = select_declarations_for_capture(
            declarations,
            period=period,
            expediente_id=expediente_id,
            limit=limit,
        )
        for declaration in selected:
            observation = await capture_filed_declaration_observation(
                session,
                declaration,
                playwright=playwright,
                artefact_sink=store.persist_artefact,
            )
            manifest_path = store.persist_observation(observation)
            observation_paths.append(manifest_path.relative_to(output_root).as_posix())
            artefact_refs.extend(
                storage_ref
                for artefact in observation.artefacts
                for storage_ref in (artefact.storage_ref,)
                if storage_ref is not None
            )
            casilla_count += len(observation.casillas)

    return FiledDataCaptureReport(
        output_root=str(output_root),
        modelo=modelo,
        year=year,
        captured_count=len(observation_paths),
        observation_paths=tuple(observation_paths),
        artefact_refs=tuple(artefact_refs),
        casilla_count=casilla_count,
    )


@app.command("inspect", help=tr("cli.registry.inspect_help"))
def inspect_registry_cmd(
    registry_root: Annotated[
        Path,
        typer.Option(
            "--registry-root",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            help=tr("cli.registry.inspect_registry_root_help"),
        ),
    ] = Path("registry/aeat"),
    json_output: Annotated[
        bool,
        typer.Option("--json", help=tr("cli.registry.json_help")),
    ] = False,
) -> None:
    """Load the read-only registry tree and report inventory counts."""

    report = inspect_registry_tree(registry_root)
    if json_output:
        typer.echo(report.model_dump_json(indent=2))
        return
    _emit_metric("modelo_count", report.modelo_count)
    _emit_metric("revision_count", report.revision_count)
    _emit_metric("legal_reference_count", report.legal_reference_count)
    _emit_metric("source_reference_count", report.source_reference_count)
    _emit_metric("casilla_count", report.casilla_count)
    _emit_metric("formula_count", report.formula_count)
    _emit_metric("extraction_profile_count", report.extraction_profile_count)
    _emit_metric("cross_reference_count", report.cross_reference_count)
    _emit_metric("workbook_parity_ref_count", report.workbook_parity_ref_count)
    _emit_metric("verification_expectation_count", report.verification_expectation_count)
    _emit_metric("application_link_count", report.application_link_count)
    _emit_metric("application_link_surfaces", ",".join(report.application_link_surfaces))
    _emit_metric("modelos", ",".join(report.modelos))


@app.command("verify", help=tr("cli.registry.verify_help"))
def verify_registry_cmd(
    registry_root: Annotated[
        Path,
        typer.Option(
            "--registry-root",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            help=tr("cli.registry.inspect_registry_root_help"),
        ),
    ] = Path("registry/aeat"),
    source_root: Annotated[
        Path,
        typer.Option(
            "--source-root",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            help=tr("cli.registry.verify_source_root_help"),
        ),
    ] = Path("."),
    json_output: Annotated[
        bool,
        typer.Option("--json", help=tr("cli.registry.json_help")),
    ] = False,
) -> None:
    """Validate every registry modelo against shared legal/source catalogues."""

    report = verify_registry_tree(registry_root, source_root=source_root)
    if json_output:
        typer.echo(report.model_dump_json(indent=2))
        return
    _emit_metric("verified", report.verified)
    _emit_metric("modelo_count", report.modelo_count)
    _emit_metric("revision_count", report.revision_count)
    _emit_metric("legal_reference_count", report.legal_reference_count)
    _emit_metric("source_reference_count", report.source_reference_count)
    _emit_metric("casilla_count", report.casilla_count)
    _emit_metric("formula_count", report.formula_count)
    _emit_metric("extraction_profile_count", report.extraction_profile_count)
    _emit_metric("cross_reference_count", report.cross_reference_count)
    _emit_metric("workbook_parity_ref_count", report.workbook_parity_ref_count)
    _emit_metric("verification_expectation_count", report.verification_expectation_count)
    _emit_metric("application_link_count", report.application_link_count)
    _emit_metric("application_link_surfaces", ",".join(report.application_link_surfaces))
    _emit_metric("modelos", ",".join(report.modelos))


@app.command("list-filed-data", help=tr("cli.registry.list_filed_data_help"))
def list_filed_data_cmd(
    modelo: Annotated[
        str,
        typer.Option("--modelo", help=tr("cli.registry.modelo_help")),
    ],
    year_from: Annotated[
        int,
        typer.Option("--from-year", min=2000, max=2099, help=tr("cli.registry.from_year_help")),
    ],
    year_to: Annotated[
        int,
        typer.Option("--to-year", min=2000, max=2099, help=tr("cli.registry.to_year_help")),
    ],
    json_output: Annotated[
        bool,
        typer.Option("--json", help=tr("cli.registry.list_filed_data_json_help")),
    ] = False,
) -> None:
    """List filed-declaration rows without downloading justificantes or submitted files."""

    report = asyncio.run(
        list_filed_data(
            modelo=modelo,
            year_from=year_from,
            year_to=year_to,
        )
    )
    if json_output:
        typer.echo(report.model_dump_json(indent=2))
        return
    _emit_metric("row_count", report.row_count)
    for row in report.rows:
        _emit_metric(
            "row",
            "\t".join(
                (
                    row.modelo,
                    str(row.year),
                    row.period,
                    row.expediente_id,
                    row.status,
                    row.presented_at.isoformat(),
                    f"submitted_file={row.has_submitted_file}",
                    f"declaration_copy={row.has_declaration_copy}",
                    f"justificante={row.has_justificante}",
                )
            ),
        )


@app.command("capture-filed-data", help=tr("cli.registry.capture_filed_data_help"))
def capture_filed_data_cmd(
    modelo: Annotated[
        str,
        typer.Option("--modelo", help=tr("cli.registry.modelo_help")),
    ],
    year: Annotated[
        int,
        typer.Option("--year", min=2000, max=2099, help=tr("cli.registry.year_help")),
    ],
    output_root: Annotated[
        Path,
        typer.Option(
            "--output-root",
            file_okay=False,
            dir_okay=True,
            writable=True,
            help=tr("cli.registry.output_root_help"),
        ),
    ] = Path("var/aeat/filed-declarations"),
    period: Annotated[
        str | None,
        typer.Option("--period", help=tr("cli.registry.period_help")),
    ] = None,
    expediente_id: Annotated[
        str | None,
        typer.Option("--expediente", help=tr("cli.registry.expediente_help")),
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option("--limit", min=1, help=tr("cli.registry.capture_limit_help")),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help=tr("cli.registry.capture_filed_data_json_help")),
    ] = False,
) -> None:
    """Capture filed-declaration data from the authenticated AEAT register."""

    report = asyncio.run(
        capture_filed_data(
            modelo=modelo,
            year=year,
            output_root=output_root,
            period=period,
            expediente_id=expediente_id,
            limit=limit,
        )
    )
    if json_output:
        typer.echo(report.model_dump_json(indent=2))
        return
    _emit_metric("captured_count", report.captured_count)
    _emit_metric("casilla_count", report.casilla_count)
    _emit_metric("observation_paths", ",".join(report.observation_paths))
    _emit_metric("artefact_refs", ",".join(report.artefact_refs))


@workbooks_app.command("verify", help=tr("cli.registry.workbooks_verify_help"))
def verify_workbooks_cmd(
    root: Annotated[
        Path,
        typer.Option(
            "--root",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            help=tr("cli.registry.workbooks_root_help"),
        ),
    ] = Path("corpus/aeat_official/disenos_registro"),
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
    json_output: Annotated[
        bool,
        typer.Option("--json", help=tr("cli.registry.json_help")),
    ] = False,
) -> None:
    """Run the read-only workbook parity backend verification."""

    previous_report = None
    if resume_from is not None:
        previous_report = WorkbookBackendVerificationReport.model_validate_json(resume_from.read_text(encoding="utf-8"))
    report = verify_workbook_backend(
        root,
        scan_limit=limit,
        per_file_timeout_seconds=per_file_timeout_seconds,
        previous_report=previous_report,
    )
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    if json_output:
        typer.echo(report.model_dump_json(indent=2))
        return
    _emit_metric("backend_exists", report.backend_exists)
    _emit_metric("passed", report.passed)
    _emit_metric("workbook_count", report.workbook_count)
    _emit_metric("scanned_count", report.scanned_count)
    _emit_metric("formula_workbook_count", report.formula_workbook_count)
    _emit_metric("unsupported_xls_count", report.unsupported_xls_count)
    _emit_metric("failed_count", report.failed_count)
    _emit_metric("runner_status", report.runner.status)
    _emit_metric("runner_detail", report.runner.detail)


def _json_default(value: object) -> str:
    return str(value)


def render_report_json(report: object) -> str:
    """Render a pydantic report object as stable JSON for tests and scripts."""

    model_dump = getattr(report, "model_dump", None)
    if model_dump is None:
        return json.dumps(report, default=_json_default, sort_keys=True)
    return json.dumps(model_dump(mode="json"), sort_keys=True)


__all__ = [
    "FiledDataCaptureReport",
    "RegistryTreeReport",
    "app",
    "capture_filed_data",
    "capture_filed_data_cmd",
    "inspect_registry_cmd",
    "inspect_registry_tree",
    "render_report_json",
    "select_declarations_for_capture",
    "verify_registry_cmd",
    "verify_registry_tree",
    "verify_workbooks_cmd",
    "workbooks_app",
]
