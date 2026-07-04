"""Typer registration for the ``aeat app modelo review-package`` verb group.

Assembles a shareable, checksum-verifiable review package (``build``) and
verifies one already received (``verify``). All verbs are local-only: they
never contact AEAT. ``build`` internally reuses
:func:`~aeat.application.modelo.export_modelo_revision` to obtain the
fichero-BOE draft bytes it bundles, so it inherits every export-time safety
gate (evidence completeness, cross-period clean state, IVA wallet
reconciliation) and also appends the usual ``MODELO_EXPORTED`` bucket event —
building a review package is, structurally, an export plus a checksum-manifest
wrap.

``sign`` / ``verify-signature`` / ``counter-sign`` / ``verify-receipt`` wire
the Ed25519 authenticity layer
(:mod:`~aeat.application.modelo._review_package_signing`,
:mod:`~aeat.application.modelo._review_package_counter_sign`) onto the CLI so
the full operator-shares / accountant-receives / accountant-counter-signs /
operator-verifies workflow is reachable without touching the application
layer directly. Every signing/counter-signing keypair is minted and persisted
through :class:`~aeat.adapters.persistence.storage.SecureObjectRepository` at
``SECRET`` sensitivity, scoped to whichever bucket runs the verb (the active
profile by default, or an explicit ``--bucket-id``); only the PUBLIC half of
a keypair is ever surfaced in CLI output. ``verify`` remains an INTEGRITY
check only (did every member arrive byte-for-byte); ``verify-signature`` and
``verify-receipt`` are AUTHENTICITY checks (who signed it).
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Annotated

import typer

from ...application.modelo import (
    CalculationRevisionNotFoundError,
    CalculationRevisionStateError,
    CounterSignedReceipt,
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
    ReviewPackageCounterSigningError,
    ReviewPackageError,
    ReviewPackageIntegrityError,
    ReviewPackageRevisionStateError,
    ReviewPackageSigningError,
    SignedReviewPackage,
    WorkUnitNotFoundError,
    build_review_package,
    counter_sign_review_package,
    ensure_review_package_signing_keypair,
    export_modelo_revision,
    get_work_unit,
    resolve_modelo_revision_for_operator_target,
    review_package_signing_public_key,
    sign_review_package,
    verify_counter_signed_receipt,
    verify_review_package,
    verify_review_package_signature,
)
from ...application.workflow import workflow_state_repository
from ...core import Period
from ...core.i18n import tr
from ._common import _emit_envelope, _profile_to_taxpayer, active_bucket_id_or_refuse
from ._modelo_cli_support import (
    parse_revision_selector,
    resolve_default_actor,
    validate_calculation_revision_id,
    validate_work_unit_id,
)
from ._modelo_review_package_payloads import (
    ModeloReviewPackageBuildResult,
    ModeloReviewPackageCounterSignResult,
    ModeloReviewPackageSignResult,
    ModeloReviewPackageVerifyReceiptResult,
    ModeloReviewPackageVerifyResult,
    ModeloReviewPackageVerifySignatureResult,
)

_BUCKET_ID_HELP = tr("cli.app.modelo.work.bucket_id_help")


def _resolve_signing_bucket_id(bucket_id: str | None) -> str:
    """Return ``bucket_id`` verbatim, or the active profile bucket when unset.

    Mirrors the ``--bucket-id`` fallback already used across the modelo work
    surface: an explicit override lets the accountant scope the command to
    their own profile bucket on a shared machine; omitting it addresses the
    active profile, which is the common single-operator case.
    """
    if bucket_id is not None and bucket_id.strip():
        return bucket_id.strip()
    return active_bucket_id_or_refuse()


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


@review_package_app.command(
    "sign",
    help=tr(
        "cli.app.modelo.review_package.sign_help",
        default=(
            "Sign a review package's checksum manifest with the bucket's Ed25519 "
            "signing keypair (minted on first use) and write the signature envelope "
            "to --output. Local-only; never contacts AEAT."
        ),
    ),
)
def review_package_sign(
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
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            help=tr(
                "cli.app.modelo.review_package.sign_output_help",
                default="Path to write the signature envelope JSON to.",
            ),
        ),
    ],
    bucket_id: Annotated[
        str | None,
        typer.Option("--bucket-id", help=_BUCKET_ID_HELP),
    ] = None,
) -> None:
    """Sign a review package's manifest digest and write the signature envelope."""
    from ._modelo_cli_support import bad_parameter_from_error

    resolved_bucket_id = _resolve_signing_bucket_id(bucket_id)

    from ...adapters.persistence.storage import secure_object_repository_for_bucket

    repository = secure_object_repository_for_bucket(resolved_bucket_id)
    keypair = ensure_review_package_signing_keypair(bucket_id=resolved_bucket_id, repository=repository)

    try:
        signed = sign_review_package(package, keypair=keypair)
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
    except ReviewPackageSigningError as exc:
        raise bad_parameter_from_error(exc) from exc

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(signed.model_dump_json(indent=2), encoding="utf-8")

    public_key = review_package_signing_public_key(keypair)
    result = ModeloReviewPackageSignResult(
        package_path=str(package),
        signature_path=str(output),
        bucket_id=resolved_bucket_id,
        calculation_revision_id=signed.calculation_revision_id,
        manifest_sha256=signed.manifest_sha256,
        signer_public_key_hex=public_key.public_key_hex,
        signed_at=signed.signed_at.isoformat(),
    )
    lines = [
        "operation\tmodelo.review_package.sign",
        f"package_path\t{package}",
        f"signature_path\t{output}",
        f"bucket\t{resolved_bucket_id}",
        f"calculation_revision_id\t{signed.calculation_revision_id}",
        f"signer_public_key_hex\t{public_key.public_key_hex}",
    ]
    _emit_envelope(ctx, command="modelo.review_package.sign", result=result, lines=lines)


@review_package_app.command(
    "verify-signature",
    help=tr(
        "cli.app.modelo.review_package.verify_signature_help",
        default=(
            "Verify a review package's Ed25519 signature envelope against a signer's "
            "public key (authenticity check; re-runs the checksum-manifest integrity "
            "check first). Local-only; never contacts AEAT."
        ),
    ),
)
def review_package_verify_signature(
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
    signature: Annotated[
        Path,
        typer.Argument(
            help=tr(
                "cli.app.modelo.review_package.signature_path_help",
                default="Path to the signature envelope JSON produced by `sign`.",
            ),
        ),
    ],
    public_key: Annotated[
        str,
        typer.Option(
            "--public-key",
            help=tr(
                "cli.app.modelo.review_package.public_key_help",
                default="Signer's public key, as 64 lowercase hex characters.",
            ),
        ),
    ],
) -> None:
    """Verify a review package's Ed25519 signature against the signer's public key."""
    from ._modelo_cli_support import bad_parameter_from_error

    if not signature.exists():
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.review_package.errors.signature_not_found",
                signature_path=str(signature),
                default="Signature envelope not found at {signature_path}.",
            ),
        )

    try:
        signed = SignedReviewPackage.model_validate_json(signature.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise bad_parameter_from_error(ReviewPackageSigningError(str(exc))) from exc

    is_valid = verify_review_package_signature(package, signed, public_key_hex=public_key.strip().lower())

    result = ModeloReviewPackageVerifySignatureResult(
        package_path=str(package),
        signature_path=str(signature),
        signer_public_key_hex=public_key.strip().lower(),
        is_valid=is_valid,
    )
    lines = [
        "operation\tmodelo.review_package.verify_signature",
        f"package_path\t{package}",
        f"signature_path\t{signature}",
        f"is_valid\t{is_valid}",
    ]
    _emit_envelope(ctx, command="modelo.review_package.verify_signature", result=result, lines=lines)


@review_package_app.command(
    "counter-sign",
    help=tr(
        "cli.app.modelo.review_package.counter_sign_help",
        default=(
            "Counter-sign an operator-signed review package on behalf of the "
            "receiving accountant and write the receipt envelope to --output. "
            "Local-only; never contacts AEAT."
        ),
    ),
)
def review_package_counter_sign(
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
    signature: Annotated[
        Path,
        typer.Argument(
            help=tr(
                "cli.app.modelo.review_package.signature_path_help",
                default="Path to the signature envelope JSON produced by `sign`.",
            ),
        ),
    ],
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            help=tr(
                "cli.app.modelo.review_package.counter_sign_output_help",
                default="Path to write the counter-signed receipt JSON to.",
            ),
        ),
    ],
    note: Annotated[
        str,
        typer.Option(
            "--note",
            help=tr(
                "cli.app.modelo.review_package.counter_sign_note_help",
                default="Free-text counter-signer note or verdict (e.g. 'reviewed, no changes').",
            ),
        ),
    ] = "",
    bucket_id: Annotated[
        str | None,
        typer.Option("--bucket-id", help=_BUCKET_ID_HELP),
    ] = None,
) -> None:
    """Counter-sign an operator's signature envelope and write the receipt."""
    from ._modelo_cli_support import bad_parameter_from_error

    if not signature.exists():
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.review_package.errors.signature_not_found",
                signature_path=str(signature),
                default="Signature envelope not found at {signature_path}.",
            ),
        )

    try:
        signed = SignedReviewPackage.model_validate_json(signature.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise bad_parameter_from_error(ReviewPackageSigningError(str(exc))) from exc

    resolved_bucket_id = _resolve_signing_bucket_id(bucket_id)

    from ...adapters.persistence.storage import secure_object_repository_for_bucket

    repository = secure_object_repository_for_bucket(resolved_bucket_id)
    counter_signer_keypair = ensure_review_package_signing_keypair(bucket_id=resolved_bucket_id, repository=repository)

    try:
        receipt = counter_sign_review_package(signed, counter_signer_keypair=counter_signer_keypair, note=note)
    except ReviewPackageCounterSigningError as exc:
        raise bad_parameter_from_error(exc) from exc

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(receipt.model_dump_json(indent=2), encoding="utf-8")

    counter_public_key = review_package_signing_public_key(counter_signer_keypair)
    result = ModeloReviewPackageCounterSignResult(
        package_path=str(package),
        signature_path=str(signature),
        receipt_path=str(output),
        bucket_id=resolved_bucket_id,
        note=receipt.note,
        counter_signer_public_key_hex=counter_public_key.public_key_hex,
        counter_signed_at=receipt.counter_signed_at.isoformat(),
    )
    lines = [
        "operation\tmodelo.review_package.counter_sign",
        f"package_path\t{package}",
        f"receipt_path\t{output}",
        f"bucket\t{resolved_bucket_id}",
        f"counter_signer_public_key_hex\t{counter_public_key.public_key_hex}",
    ]
    _emit_envelope(ctx, command="modelo.review_package.counter_sign", result=result, lines=lines)


@review_package_app.command(
    "verify-receipt",
    help=tr(
        "cli.app.modelo.review_package.verify_receipt_help",
        default=(
            "Verify both signature layers of a counter-signed review-package receipt: "
            "the operator's original signature and the accountant's counter-signature. "
            "Local-only; never contacts AEAT."
        ),
    ),
)
def review_package_verify_receipt(
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
    receipt_path: Annotated[
        Path,
        typer.Argument(
            help=tr(
                "cli.app.modelo.review_package.receipt_path_help",
                default="Path to the counter-signed receipt JSON produced by `counter-sign`.",
            ),
        ),
    ],
    operator_public_key: Annotated[
        str,
        typer.Option(
            "--operator-public-key",
            help=tr(
                "cli.app.modelo.review_package.operator_public_key_help",
                default="The operator's (original signer's) public key, as 64 lowercase hex characters.",
            ),
        ),
    ],
    counter_signer_public_key: Annotated[
        str,
        typer.Option(
            "--counter-signer-public-key",
            help=tr(
                "cli.app.modelo.review_package.counter_signer_public_key_help",
                default="The accountant's (counter-signer's) public key, as 64 lowercase hex characters.",
            ),
        ),
    ],
) -> None:
    """Verify both signature layers of a counter-signed review-package receipt."""
    from ._modelo_cli_support import bad_parameter_from_error

    if not receipt_path.exists():
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.review_package.errors.receipt_not_found",
                receipt_path=str(receipt_path),
                default="Receipt envelope not found at {receipt_path}.",
            ),
        )

    try:
        receipt = CounterSignedReceipt.model_validate_json(receipt_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise bad_parameter_from_error(ReviewPackageCounterSigningError(str(exc))) from exc

    operator_key = operator_public_key.strip().lower()
    counter_key = counter_signer_public_key.strip().lower()
    is_valid = verify_counter_signed_receipt(
        package,
        receipt,
        operator_public_key_hex=operator_key,
        counter_signer_public_key_hex=counter_key,
    )

    result = ModeloReviewPackageVerifyReceiptResult(
        package_path=str(package),
        receipt_path=str(receipt_path),
        operator_public_key_hex=operator_key,
        counter_signer_public_key_hex=counter_key,
        is_valid=is_valid,
    )
    lines = [
        "operation\tmodelo.review_package.verify_receipt",
        f"package_path\t{package}",
        f"receipt_path\t{receipt_path}",
        f"is_valid\t{is_valid}",
    ]
    _emit_envelope(ctx, command="modelo.review_package.verify_receipt", result=result, lines=lines)


def _resolve_optional_cli_period(*, year: int | None, period: str | None) -> Period | None:
    if period is None:
        return None
    if year is None:
        raise typer.BadParameter(tr("cli.common.errors.period_missing_year", token=period))
    return Period.from_year_and_code(year, period.strip())


__all__ = ["register_review_package_commands", "review_package_app"]
