"""Typer registration for the ``aeat app modelo review-package`` verb group.

Assembles a shareable, checksum-verifiable review package (``build``) and
verifies one already received (``verify``). Both verbs are local-only: they
never contact AEAT. ``build`` internally reuses
:func:`~aeat.application.modelo.export_modelo_revision` to obtain the
fichero-BOE draft bytes it bundles, so it inherits every export-time safety
gate (evidence completeness, cross-period clean state, IVA wallet
reconciliation) and also appends the usual ``MODELO_EXPORTED`` bucket event —
building a review package is, structurally, an export plus a checksum-manifest
wrap.

Cryptographic signing (ed25519 sender/recipient identity) and the
counter-signed accountant feedback-package round trip are a deferred
follow-up slice; ``verify`` here is an INTEGRITY check only.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Annotated

import typer

from ...application.modelo import (
    CalculationRevisionNotFoundError,
    CalculationRevisionStateError,
    ModeloCalculationRevisionSelector,
    ModeloCalculationRevisionSelectorAmbiguousError,
    ModeloCalculationRevisionSelectorNotFoundError,
    ModeloCalculationRevisionSelectorStateError,
    ModeloExportCommand,
    ModeloExportCrossBucketRefusedError,
    ModeloExportNoActiveBucketError,
    ModeloExportOutputPathError,
    ModeloIvaWalletReconciliationBlocked,
    ModeloRefundElectionNotEligibleError,
    ModeloWorkAddressNotFoundError,
    ModeloWorkPeriodTokenError,
    ReviewPackageError,
    ReviewPackageIntegrityError,
    ReviewPackageRevisionStateError,
    WorkUnitNotFoundError,
    build_review_package,
    export_modelo_revision,
    get_work_unit,
    resolve_modelo_revision_for_operator_target,
    verify_review_package,
)
from ...application.workflow import workflow_state_repository
from ...core import Period
from ...core.i18n import tr
from ._common import _emit_envelope, _profile_to_taxpayer
from ._modelo_cli_support import (
    parse_revision_selector,
    resolve_default_actor,
    validate_calculation_revision_id,
    validate_work_unit_id,
)
from ._modelo_review_package_payloads import (
    ModeloReviewPackageBuildResult,
    ModeloReviewPackageVerifyResult,
)

review_package_app = typer.Typer(
    name="review-package",
    help=tr(
        "cli.app.modelo.review_package.group_help",
        default="Build a shareable review package and verify its integrity.",
    ),
    no_args_is_help=True,
)


def register_review_package_commands(app: typer.Typer) -> None:
    """Mount modelo review-package commands on the modelo app."""
    app.add_typer(review_package_app, name="review-package")


@review_package_app.command(
    "build",
    help=tr(
        "cli.app.modelo.review_package.build_help",
        default=(
            "Assemble a shareable, checksum-verifiable review package (fichero-BOE draft, "
            "revision provenance, and bundled ledger evidence) for accountant handoff. "
            "Local-only; never contacts AEAT."
        ),
    ),
)
def review_package_build(
    ctx: typer.Context,
    work_unit_id: Annotated[
        str | None,
        typer.Argument(
            help=tr(
                "cli.app.modelo.review_package.work_unit_id_help",
                default="Work unit id (SHA-256 or unambiguous prefix).",
            ),
        ),
    ] = None,
    modelo: Annotated[
        str | None,
        typer.Option("--modelo", help=tr("cli.app.modelo.work.modelo_help")),
    ] = None,
    year: Annotated[
        int | None,
        typer.Option("--year", help=tr("cli.app.modelo.work.year_help")),
    ] = None,
    period: Annotated[
        str | None,
        typer.Option("--period", help=tr("cli.app.modelo.work.period_help")),
    ] = None,
    registry_revision: Annotated[
        str | None,
        typer.Option("--registry-revision", help=tr("cli.app.modelo.work.revision_help")),
    ] = None,
    bucket_id: Annotated[
        str | None,
        typer.Option("--bucket-id", help=tr("cli.app.modelo.work.bucket_id_help")),
    ] = None,
    select: Annotated[
        str,
        typer.Option(
            "--select",
            help=tr("cli.app.modelo.work.revision_selector_help", default="Revision selector."),
        ),
    ] = ModeloCalculationRevisionSelector.CURRENT.value,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            help=tr(
                "cli.app.modelo.review_package.output_help",
                default="Path to write the review package ZIP to.",
            ),
        ),
    ] = None,
    revision: Annotated[
        str | None,
        typer.Option(
            "--revision",
            help=tr(
                "cli.app.modelo.review_package.revision_help",
                default=(
                    "Calculation revision id to package; defaults to the work unit's "
                    "most recent verified-complete or filed revision."
                ),
            ),
        ),
    ] = None,
    actor: Annotated[
        str | None,
        typer.Option(
            "--by",
            help=tr(
                "cli.app.modelo.review_package.actor_help",
                default="Operator label recorded into the package descriptor and the underlying export event.",
            ),
        ),
    ] = None,
    notes: Annotated[
        str,
        typer.Option(
            "--notes",
            help=tr(
                "cli.app.modelo.review_package.notes_help",
                default="Free-text note embedded in the package descriptor (e.g. why it was shared).",
            ),
        ),
    ] = "",
) -> None:
    """Assemble a shareable review package for the resolved revision."""
    from ._modelo_cli_support import bad_parameter_from_error, selector_bad_parameter

    workflow_state = workflow_state_repository().load()
    workflow_profile = _profile_to_taxpayer(workflow_state)
    if output is None or not str(output).strip() or str(output).strip() == ".":
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.review_package.errors.output_required",
                default="Supply --output PATH for the review package ZIP.",
            ),
        )

    try:
        typed_period = _resolve_optional_cli_period(year=year, period=period)
        selected_revision = resolve_modelo_revision_for_operator_target(
            calculation_revision_id=(validate_calculation_revision_id(revision) if revision is not None else None),
            work_unit_id=validate_work_unit_id(work_unit_id) if work_unit_id is not None else None,
            modelo=modelo,
            year=year,
            period=typed_period,
            registry_revision_id=registry_revision,
            bucket_id=bucket_id,
            selector=parse_revision_selector(select),
            default_for="export",
        )
    except CalculationRevisionNotFoundError as exc:
        if revision is not None:
            raise bad_parameter_from_error(exc) from exc
        raise selector_bad_parameter(exc) from exc
    except (
        ModeloWorkAddressNotFoundError,
        ModeloCalculationRevisionSelectorNotFoundError,
        ModeloCalculationRevisionSelectorStateError,
        ModeloCalculationRevisionSelectorAmbiguousError,
        ModeloWorkPeriodTokenError,
    ) as exc:
        raise selector_bad_parameter(exc) from exc
    target_revision_id = selected_revision.calculation_revision_id

    resolved_actor = actor or resolve_default_actor()
    work_unit = get_work_unit(selected_revision.work_unit_id)

    with tempfile.TemporaryDirectory(prefix="aeat-review-package-draft-") as staging_name:
        draft_path = Path(staging_name) / "draft.fichero-boe"
        try:
            export_result = export_modelo_revision(
                ModeloExportCommand(
                    calculation_revision_id=target_revision_id,
                    output_path=draft_path,
                    actor=resolved_actor,
                ),
                workflow_profile=workflow_profile,
            )
        except (
            CalculationRevisionNotFoundError,
            CalculationRevisionStateError,
            WorkUnitNotFoundError,
            ModeloExportCrossBucketRefusedError,
            ModeloExportNoActiveBucketError,
            ModeloExportOutputPathError,
            ModeloIvaWalletReconciliationBlocked,
            ModeloRefundElectionNotEligibleError,
        ) as exc:
            raise bad_parameter_from_error(exc) from exc

        from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository

        revision_record = CalculationRevisionCatalogueRepository().load().get(target_revision_id)
        if revision_record is None:
            raise bad_parameter_from_error(
                CalculationRevisionNotFoundError(context={"calculation_revision_id": target_revision_id}),
            )

        draft_bytes = draft_path.read_bytes()

        try:
            build_result = build_review_package(
                revision=revision_record,
                work_unit=work_unit,
                draft_bytes=draft_bytes,
                output_path=output,
                built_by=resolved_actor,
                notes=notes,
            )
        except (ReviewPackageRevisionStateError, ReviewPackageError) as exc:
            raise bad_parameter_from_error(exc) from exc

    manifest = build_result.manifest
    result = ModeloReviewPackageBuildResult(
        bucket_id=manifest.bucket_id,
        work_unit_id=manifest.work_unit_id,
        calculation_revision_id=manifest.calculation_revision_id,
        modelo=manifest.modelo,
        filing_year=manifest.filing_year,
        period=manifest.period,
        revision_state=manifest.revision_state,
        has_ledger_evidence=manifest.has_ledger_evidence,
        output_path=str(build_result.output_path),
        member_count=build_result.member_count,
        built_by=manifest.built_by,
        built_at=manifest.built_at.isoformat(),
    )
    lines = [
        "operation\tmodelo.review_package.build",
        f"work_unit_id\t{manifest.work_unit_id}",
        f"calculation_revision_id\t{manifest.calculation_revision_id}",
        f"bucket\t{manifest.bucket_id}",
        f"modelo\t{manifest.modelo}",
        f"filing_year\t{manifest.filing_year}",
        f"period\t{manifest.period}",
        f"output_path\t{build_result.output_path}",
        f"member_count\t{build_result.member_count}",
        f"has_ledger_evidence\t{manifest.has_ledger_evidence}",
        f"export_bucket_event_id\t{export_result.bucket_event_id}",
    ]
    _emit_envelope(ctx, command="modelo.review_package.build", result=result, lines=lines)


@review_package_app.command(
    "verify",
    help=tr(
        "cli.app.modelo.review_package.verify_help",
        default=(
            "Verify a review package's checksum manifest (integrity only; does not "
            "assert who built it). Local-only; never contacts AEAT."
        ),
    ),
)
def review_package_verify(
    ctx: typer.Context,
    package: Annotated[
        Path,
        typer.Argument(
            help=tr(
                "cli.app.modelo.review_package.package_path_help",
                default="Path to the review package ZIP to verify.",
            ),
        ),
    ],
) -> None:
    """Verify a review package's checksum manifest and render its descriptor."""
    from ._modelo_cli_support import bad_parameter_from_error

    try:
        verification = verify_review_package(package)
    except FileNotFoundError as exc:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.review_package.errors.package_not_found",
                package_path=str(package),
                default="Review package not found at {package_path}.",
            ),
        ) from exc
    except ReviewPackageIntegrityError as exc:
        raise bad_parameter_from_error(exc) from exc

    manifest = verification.manifest
    result = ModeloReviewPackageVerifyResult(
        package_path=str(package),
        is_clean=verification.is_clean,
        missing=list(verification.missing),
        unexpected=list(verification.unexpected),
        mismatched=list(verification.mismatched),
        bucket_id=manifest.bucket_id,
        work_unit_id=manifest.work_unit_id,
        calculation_revision_id=manifest.calculation_revision_id,
        modelo=manifest.modelo,
        filing_year=manifest.filing_year,
        period=manifest.period,
        revision_state=manifest.revision_state,
        has_ledger_evidence=manifest.has_ledger_evidence,
        built_by=manifest.built_by,
        built_at=manifest.built_at.isoformat(),
    )
    lines = [
        "operation\tmodelo.review_package.verify",
        f"package_path\t{package}",
        f"is_clean\t{verification.is_clean}",
        f"missing\t{', '.join(verification.missing)}",
        f"unexpected\t{', '.join(verification.unexpected)}",
        f"mismatched\t{', '.join(verification.mismatched)}",
        f"calculation_revision_id\t{manifest.calculation_revision_id}",
        f"modelo\t{manifest.modelo}",
        f"built_by\t{manifest.built_by}",
    ]
    _emit_envelope(ctx, command="modelo.review_package.verify", result=result, lines=lines)


def _resolve_optional_cli_period(*, year: int | None, period: str | None) -> Period | None:
    if period is None:
        return None
    if year is None:
        raise typer.BadParameter(tr("cli.common.errors.period_missing_year", token=period))
    return Period.from_year_and_code(year, period.strip())


__all__ = ["register_review_package_commands", "review_package_app"]
