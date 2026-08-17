"""Typer registration for the ``aeat app modelo review-package`` verb group.

Assembles a shareable, checksum-verifiable review package (``build``) and
verifies one already received (``verify``). All verbs are local-only: they
never contact AEAT. ``build`` internally reuses
:func:`~application.modelo.export_modelo_revision` to obtain the
fichero-BOE draft bytes it bundles, so it inherits every export-time safety
gate (evidence completeness, cross-period clean state, IVA wallet
reconciliation) and also appends the usual ``MODELO_EXPORTED`` bucket event —
building a review package is, structurally, an export plus a checksum-manifest
wrap.

``sign`` / ``verify-signature`` / ``counter-sign`` / ``verify-receipt`` wire
the Ed25519 authenticity layer
(:mod:`~application.modelo._review_package_signing`,
:mod:`~application.modelo._review_package_counter_sign`) onto the CLI so
the full operator-shares / accountant-receives / accountant-counter-signs /
operator-verifies workflow is reachable without touching the application
layer directly. Every signing/counter-signing keypair is minted and persisted
through :class:`~adapters.persistence.storage.SecureObjectRepository` at
``SECRET`` sensitivity, scoped to whichever bucket runs the verb (the active
profile by default, or an explicit ``--bucket-id``); only the PUBLIC half of
a keypair is ever surfaced in CLI output. ``verify`` remains an INTEGRITY
check only (did every member arrive byte-for-byte); ``verify-signature`` and
``verify-receipt`` are AUTHENTICITY checks (who signed it).

``encrypt-for-recipient`` / ``decrypt`` wire the X25519 CONFIDENTIALITY layer
(:mod:`~application.modelo._review_package_recipient_encryption`) onto
the CLI: a package sealed with ``encrypt-for-recipient`` can be opened only by
the holder of the matching X25519 private key, unlike ``sign``/``counter-sign``,
which leave the archive itself in plaintext ZIP form.
``encrypt-for-recipient`` looks up the recipient's registered public key via
:class:`~application.modelo.RecipientFingerprintRegistryRepository`
(populated by ``aeat config collab recipient add``); ``decrypt`` mints-or-loads
the running bucket's OWN X25519 keypair (mirroring the signing keypair's
mint-once-persist-as-ciphertext contract exactly, via
:func:`~application.modelo.ensure_recipient_encryption_keypair`) and
composes :class:`~application.modelo.RecipientReplayGuardRepository`
around the pure decrypt primitive to refuse a captured package presented twice.
Both verbs operate entirely on in-memory bytes; the plaintext package bytes are
never written to disk except as the final recovered archive the operator
explicitly requests via ``--output``.

See Also:
    :func:`~application.modelo.build_review_package`
        Application builder for checksum-verifiable review packages.
    :func:`~application.modelo.sign_review_package`
        Ed25519 authenticity primitive wired by ``sign``.
    :func:`~application.modelo.encrypt_review_package_for_recipient`
        X25519 confidentiality primitive wired by ``encrypt-for-recipient``.
    :class:`~application.modelo.RecipientFingerprintRegistryRepository`
        Trusted-recipient public-key registry used before encryption.
    :mod:`~entrypoints.cli._modelo_review_package_payloads`
        Typed JSON payload schemas emitted by this CLI group.
    :mod:`~entrypoints.cli._config._collab`
        Configuration surface that registers recipient fingerprints.
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
    FeedbackCounterSignatureInvalidError,
    ModeloCalculationRevisionSelector,
    ModeloCalculationRevisionSelectorAmbiguousError,
    ModeloCalculationRevisionSelectorNotFoundError,
    ModeloCalculationRevisionSelectorStateError,
    ModeloExportCommand,
    ModeloExportCrossBucketRefusedError,
    ModeloExportNoActiveBucketError,
    ModeloExportOutputPathError,
    ModeloIvaWalletReconciliationBlocked,
    ModeloPaymentElectionCapabilityRefusedError,
    ModeloPaymentElectionIncompatibleError,
    ModeloPriorDomiciliationElectionRefusedError,
    ModeloRefundElectionNotEligibleError,
    ModeloWorkAddressNotFoundError,
    ModeloWorkPeriodTokenError,
    RecipientDecryptionError,
    RecipientEncryptedPackage,
    RecipientEncryptionError,
    RecipientFingerprintRegistryRepository,
    RecipientNotRegisteredError,
    RecipientPackageReplayedError,
    RecipientReplayGuardRepository,
    ReviewPackageCounterSigningError,
    ReviewPackageError,
    ReviewPackageFeedbackError,
    ReviewPackageIntegrityError,
    ReviewPackageRevisionStateError,
    ReviewPackageSigningError,
    SignedReviewPackage,
    WorkUnitNotFoundError,
    build_feedback_package,
    build_review_package,
    counter_sign_review_package,
    decrypt_review_package_for_recipient,
    emit_collab_feedback_countersign_attached_event,
    encrypt_feedback_package_for_originator,
    encrypt_review_package_for_recipient,
    ensure_recipient_encryption_keypair,
    ensure_review_package_signing_keypair,
    export_modelo_revision,
    get_work_unit,
    import_feedback_package,
    resolve_modelo_revision_for_operator_target,
    review_package_signing_public_key,
    sign_review_package,
    verify_counter_signed_receipt,
    verify_review_package,
    verify_review_package_signature,
)
from ...application.workflow import workflow_state_repository
from ...core import PaymentElection, Period, PriorDomiciliationElection, RefundElection
from ...core.external_constants import UTF_8_ENCODING
from ...core.i18n import tr
from ._common import _emit_envelope, _filing_taxpayer_or_refuse
from ._modelo_cli_support import (
    parse_revision_selector,
    resolve_default_actor,
    resolve_explicit_or_active_bucket_id,
    validate_calculation_revision_id,
    validate_work_unit_id,
)
from ._modelo_review_package_rendering import (
    review_package_build_result_lines,
    review_package_build_result_payload,
    review_package_counter_sign_result,
    review_package_decrypt_result,
    review_package_encrypt_feedback_result,
    review_package_encrypt_for_recipient_result,
    review_package_import_feedback_result,
    review_package_sign_result,
    review_package_verify_receipt_result,
    review_package_verify_result,
    review_package_verify_signature_result,
)
from ._modelo_work_options import (
    _BucketIdOpt,
    _ModeloOpt,
    _PaymentElectionOpt,
    _PeriodOpt,
    _PriorDomiciliationElectionOpt,
    _RefundElectionOpt,
    _RegistryRevisionOpt,
    _YearOpt,
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
    modelo: _ModeloOpt = None,
    year: _YearOpt = None,
    period: _PeriodOpt = None,
    registry_revision: _RegistryRevisionOpt = None,
    bucket_id: _BucketIdOpt = None,
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
    refund_election: _RefundElectionOpt = RefundElection.COMPENSAR,
    payment_election: _PaymentElectionOpt = PaymentElection.INGRESO,
    prior_domiciliation_election: _PriorDomiciliationElectionOpt = PriorDomiciliationElection.KEEP,
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
    workflow_profile = _filing_taxpayer_or_refuse(workflow_state)
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

    # Pin staging beside the final destination rather than the OS-shared
    # temp directory: the fichero-BOE draft staged here is plaintext filing
    # data (``sensitive-financial-data-secure-storage-only``). ``mkdir``
    # runs before ``TemporaryDirectory`` because the latter requires ``dir``
    # to already exist; a destination whose parent cannot be created refuses
    # loudly here rather than silently falling back to the OS temp dir.
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cadrumo-review-package-draft-", dir=output.parent) as staging_name:
        draft_path = Path(staging_name) / "draft.fichero-boe"
        try:
            from ...adapters.persistence.profile.justificante import JustificanteRepository

            export_result = export_modelo_revision(
                ModeloExportCommand(
                    calculation_revision_id=target_revision_id,
                    output_path=draft_path,
                    actor=resolved_actor,
                    refund_election=refund_election,
                    payment_election=payment_election,
                    prior_domiciliation_election=prior_domiciliation_election,
                ),
                workflow_profile=workflow_profile,
                justificante_repository=JustificanteRepository(),
            )
        except (
            CalculationRevisionNotFoundError,
            CalculationRevisionStateError,
            WorkUnitNotFoundError,
            ModeloExportCrossBucketRefusedError,
            ModeloExportNoActiveBucketError,
            ModeloExportOutputPathError,
            ModeloIvaWalletReconciliationBlocked,
            ModeloPaymentElectionCapabilityRefusedError,
            ModeloPaymentElectionIncompatibleError,
            ModeloPriorDomiciliationElectionRefusedError,
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

    _emit_envelope(
        ctx,
        command="modelo.review_package.build",
        result=review_package_build_result_payload(build_result),
        lines=review_package_build_result_lines(
            build_result,
            export_bucket_event_id=export_result.bucket_event_id,
        ),
    )


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

    result, lines = review_package_verify_result(package, verification)
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
        typer.Option("--bucket-id", help=tr("cli.app.modelo.review_package.bucket_id_help")),
    ] = None,
) -> None:
    """Sign a review package's manifest digest and write the signature envelope."""
    from ._modelo_cli_support import bad_parameter_from_error

    resolved_bucket_id = resolve_explicit_or_active_bucket_id(bucket_id)

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
    output.write_text(signed.model_dump_json(indent=2), encoding=UTF_8_ENCODING, newline="\n")

    public_key = review_package_signing_public_key(keypair)
    result, lines = review_package_sign_result(
        package,
        output,
        bucket_id=resolved_bucket_id,
        signed=signed,
        signer_public_key_hex=public_key.public_key_hex,
    )
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
        signed = SignedReviewPackage.model_validate_json(signature.read_text(encoding=UTF_8_ENCODING))
    except ValueError as exc:
        raise bad_parameter_from_error(ReviewPackageSigningError(str(exc))) from exc

    signer_public_key_hex = public_key.strip().lower()
    is_valid = verify_review_package_signature(package, signed, public_key_hex=signer_public_key_hex)
    result, lines = review_package_verify_signature_result(
        package,
        signature,
        signer_public_key_hex=signer_public_key_hex,
        is_valid=is_valid,
    )
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
        typer.Option("--bucket-id", help=tr("cli.app.modelo.review_package.bucket_id_help")),
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
        signed = SignedReviewPackage.model_validate_json(signature.read_text(encoding=UTF_8_ENCODING))
    except ValueError as exc:
        raise bad_parameter_from_error(ReviewPackageSigningError(str(exc))) from exc

    resolved_bucket_id = resolve_explicit_or_active_bucket_id(bucket_id)

    from ...adapters.persistence.storage import secure_object_repository_for_bucket

    repository = secure_object_repository_for_bucket(resolved_bucket_id)
    counter_signer_keypair = ensure_review_package_signing_keypair(bucket_id=resolved_bucket_id, repository=repository)

    try:
        receipt = counter_sign_review_package(signed, counter_signer_keypair=counter_signer_keypair, note=note)
    except ReviewPackageCounterSigningError as exc:
        raise bad_parameter_from_error(exc) from exc

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(receipt.model_dump_json(indent=2), encoding=UTF_8_ENCODING, newline="\n")

    counter_public_key = review_package_signing_public_key(counter_signer_keypair)
    result, lines = review_package_counter_sign_result(
        package,
        signature,
        output,
        bucket_id=resolved_bucket_id,
        receipt=receipt,
        counter_signer_public_key_hex=counter_public_key.public_key_hex,
    )
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
        receipt = CounterSignedReceipt.model_validate_json(receipt_path.read_text(encoding=UTF_8_ENCODING))
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

    result, lines = review_package_verify_receipt_result(
        package,
        receipt_path,
        operator_public_key_hex=operator_key,
        counter_signer_public_key_hex=counter_key,
        is_valid=is_valid,
    )
    _emit_envelope(ctx, command="modelo.review_package.verify_receipt", result=result, lines=lines)


@review_package_app.command(
    "encrypt-for-recipient",
    help=tr(
        "cli.app.modelo.review_package.encrypt_for_recipient_help",
        default=(
            "Seal a review package so only a registered recipient's private key can "
            "open it, and write the encrypted envelope to --output. Local-only; "
            "never contacts AEAT."
        ),
    ),
)
def review_package_encrypt_for_recipient(
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
    recipient_id: Annotated[
        str,
        typer.Option(
            "--recipient",
            help=tr(
                "cli.app.modelo.review_package.recipient_id_help",
                default="Registered recipient id (see `aeat config collab recipient add`).",
            ),
        ),
    ],
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            help=tr(
                "cli.app.modelo.review_package.encrypt_output_help",
                default="Path to write the recipient-encrypted envelope JSON to.",
            ),
        ),
    ],
    review_only: Annotated[
        bool,
        typer.Option(
            "--review-only/--filing-grade",
            help=tr(
                "cli.app.modelo.review_package.review_only_help",
                default=(
                    "Mark the sealed package as carrying no filing authority "
                    "(the recipient may read and verify it, but it is not evidence "
                    "the underlying revision has been or will be filed)."
                ),
            ),
        ),
    ] = False,
    valid_for_days: Annotated[
        int | None,
        typer.Option(
            "--valid-for-days",
            help=tr(
                "cli.app.modelo.review_package.valid_for_days_help",
                default="Optional validity window in days; omit for a package that never expires.",
            ),
        ),
    ] = None,
    bucket_id: Annotated[
        str | None,
        typer.Option("--bucket-id", help=tr("cli.app.modelo.review_package.bucket_id_help")),
    ] = None,
) -> None:
    """Seal a review package for one registered recipient's public key."""
    from ._modelo_cli_support import bad_parameter_from_error

    if not package.exists():
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.review_package.errors.package_not_found",
                package_path=str(package),
                default="Review package not found at {package_path}.",
            ),
        )

    resolved_bucket_id = resolve_explicit_or_active_bucket_id(bucket_id)
    registry = RecipientFingerprintRegistryRepository(bucket_id=resolved_bucket_id)
    try:
        recipient = registry.get(recipient_id)
    except RecipientNotRegisteredError as exc:
        raise bad_parameter_from_error(exc) from exc

    if valid_for_days is not None and valid_for_days <= 0:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.review_package.errors.invalid_valid_for_days",
                default="--valid-for-days must be a strictly positive integer.",
            ),
        )

    from datetime import timedelta

    try:
        envelope = encrypt_review_package_for_recipient(
            package.read_bytes(),
            recipient_public_key_hex=recipient.public_key_hex,
            review_only=review_only,
            valid_for=timedelta(days=valid_for_days) if valid_for_days is not None else None,
        )
    except RecipientEncryptionError as exc:
        raise bad_parameter_from_error(exc) from exc

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(envelope.model_dump_json(indent=2), encoding=UTF_8_ENCODING, newline="\n")

    result, lines = review_package_encrypt_for_recipient_result(
        package,
        output,
        recipient_id=recipient_id,
        recipient_public_key_hex=recipient.public_key_hex,
        envelope=envelope,
    )
    _emit_envelope(ctx, command="modelo.review_package.encrypt_for_recipient", result=result, lines=lines)


@review_package_app.command(
    "decrypt",
    help=tr(
        "cli.app.modelo.review_package.decrypt_help",
        default=(
            "Open a recipient-encrypted review package with this bucket's X25519 "
            "encryption keypair (minted on first use) and write the recovered "
            "package ZIP to --output. Local-only; never contacts AEAT."
        ),
    ),
)
def review_package_decrypt(
    ctx: typer.Context,
    envelope_path: Annotated[
        Path,
        typer.Argument(
            help=tr(
                "cli.app.modelo.review_package.envelope_path_help",
                default="Path to the recipient-encrypted envelope JSON produced by `encrypt-for-recipient`.",
            ),
        ),
    ],
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            help=tr(
                "cli.app.modelo.review_package.decrypt_output_help",
                default="Path to write the recovered review package ZIP to.",
            ),
        ),
    ],
    bucket_id: Annotated[
        str | None,
        typer.Option("--bucket-id", help=tr("cli.app.modelo.review_package.bucket_id_help")),
    ] = None,
) -> None:
    """Decrypt a recipient-encrypted review package with this bucket's own keypair."""
    from ._modelo_cli_support import bad_parameter_from_error

    if not envelope_path.exists():
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.review_package.errors.envelope_not_found",
                envelope_path=str(envelope_path),
                default="Recipient-encrypted envelope not found at {envelope_path}.",
            ),
        )

    try:
        envelope = RecipientEncryptedPackage.model_validate_json(envelope_path.read_text(encoding=UTF_8_ENCODING))
    except ValueError as exc:
        raise bad_parameter_from_error(RecipientEncryptionError(str(exc))) from exc

    resolved_bucket_id = resolve_explicit_or_active_bucket_id(bucket_id)

    from ...adapters.persistence.storage import secure_object_repository_for_bucket

    repository = secure_object_repository_for_bucket(resolved_bucket_id)
    keypair = ensure_recipient_encryption_keypair(bucket_id=resolved_bucket_id, repository=repository)

    try:
        decrypted = decrypt_review_package_for_recipient(envelope, recipient_private_key=keypair.private_key())
    except RecipientDecryptionError as exc:
        raise bad_parameter_from_error(exc) from exc

    replay_guard = RecipientReplayGuardRepository(bucket_id=resolved_bucket_id)
    try:
        replay_guard.mark_consumed(envelope.envelope_nonce_hex)
    except RecipientPackageReplayedError as exc:
        raise bad_parameter_from_error(exc) from exc

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(decrypted.package_bytes)

    result, lines = review_package_decrypt_result(
        envelope_path,
        output,
        bucket_id=resolved_bucket_id,
        decrypted=decrypted,
    )
    _emit_envelope(ctx, command="modelo.review_package.decrypt", result=result, lines=lines)


@review_package_app.command(
    "encrypt-feedback",
    help=tr(
        "cli.app.modelo.review_package.encrypt_feedback_help",
        default=(
            "Seal a recipient's review feedback (a note, optionally a counter-signed "
            "receipt) back to the originator so only the originator's private key can "
            "open it, and write the envelope to --output. Local-only; never contacts AEAT."
        ),
    ),
)
def review_package_encrypt_feedback(
    ctx: typer.Context,
    originator_id: Annotated[
        str,
        typer.Option(
            "--originator",
            help=tr(
                "cli.app.modelo.review_package.originator_id_help",
                default=(
                    "Registered originator id whose public key seals the feedback "
                    "(see `aeat config collab recipient add`)."
                ),
            ),
        ),
    ],
    work_unit_id: Annotated[
        str,
        typer.Option(
            "--work-unit-id",
            help=tr(
                "cli.app.modelo.review_package.feedback_work_unit_id_help",
                default="Work unit id the feedback concerns (from the reviewed package descriptor).",
            ),
        ),
    ],
    calculation_revision_id: Annotated[
        str,
        typer.Option(
            "--calculation-revision-id",
            help=tr(
                "cli.app.modelo.review_package.feedback_revision_id_help",
                default="Calculation revision id the feedback concerns (from the reviewed package descriptor).",
            ),
        ),
    ],
    submitted_by: Annotated[
        str,
        typer.Option(
            "--by",
            help=tr(
                "cli.app.modelo.review_package.feedback_submitted_by_help",
                default="The reviewer's actor label (e.g. the accountant's display name).",
            ),
        ),
    ],
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            help=tr(
                "cli.app.modelo.review_package.feedback_output_help",
                default="Path to write the originator-encrypted feedback envelope JSON to.",
            ),
        ),
    ],
    note: Annotated[
        str,
        typer.Option(
            "--note",
            help=tr(
                "cli.app.modelo.review_package.feedback_note_help",
                default="Free-text verdict or note (e.g. `reviewed, no changes`).",
            ),
        ),
    ] = "",
    receipt: Annotated[
        Path | None,
        typer.Option(
            "--receipt",
            help=tr(
                "cli.app.modelo.review_package.feedback_receipt_help",
                default="Optional counter-signed receipt JSON (from `counter-sign`) to bundle as a formal sign-off.",
            ),
        ),
    ] = None,
    bucket_id: Annotated[
        str | None,
        typer.Option("--bucket-id", help=tr("cli.app.modelo.review_package.bucket_id_help")),
    ] = None,
) -> None:
    """Seal review feedback back to the originator's registered public key."""
    from ._modelo_cli_support import bad_parameter_from_error

    resolved_bucket_id = resolve_explicit_or_active_bucket_id(bucket_id)
    registry = RecipientFingerprintRegistryRepository(bucket_id=resolved_bucket_id)
    try:
        originator = registry.get(originator_id)
    except RecipientNotRegisteredError as exc:
        raise bad_parameter_from_error(exc) from exc

    counter_signed_receipt: CounterSignedReceipt | None = None
    if receipt is not None:
        if not receipt.exists():
            raise typer.BadParameter(
                tr(
                    "cli.app.modelo.review_package.errors.receipt_not_found",
                    receipt_path=str(receipt),
                    default="Counter-signed receipt not found at {receipt_path}.",
                ),
            )
        try:
            counter_signed_receipt = CounterSignedReceipt.model_validate_json(
                receipt.read_text(encoding=UTF_8_ENCODING),
            )
        except ValueError as exc:
            raise bad_parameter_from_error(ReviewPackageCounterSigningError(str(exc))) from exc

    try:
        feedback = build_feedback_package(
            bucket_id=originator.recipient_id,
            work_unit_id=work_unit_id,
            calculation_revision_id=calculation_revision_id,
            note=note,
            counter_signed_receipt=counter_signed_receipt,
            submitted_by=submitted_by,
        )
        envelope = encrypt_feedback_package_for_originator(
            feedback,
            originator_public_key_hex=originator.public_key_hex,
        )
    except (ReviewPackageFeedbackError, RecipientEncryptionError) as exc:
        raise bad_parameter_from_error(exc) from exc

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(envelope.model_dump_json(indent=2), encoding=UTF_8_ENCODING, newline="\n")

    result, lines = review_package_encrypt_feedback_result(
        output,
        originator_id=originator_id,
        originator_public_key_hex=originator.public_key_hex,
        work_unit_id=work_unit_id,
        calculation_revision_id=calculation_revision_id,
        has_counter_sign=counter_signed_receipt is not None,
        envelope=envelope,
    )
    _emit_envelope(ctx, command="modelo.review_package.encrypt_feedback", result=result, lines=lines)


@review_package_app.command(
    "import-feedback",
    help=tr(
        "cli.app.modelo.review_package.import_feedback_help",
        default=(
            "Open a feedback envelope with this bucket's X25519 keypair, verify any "
            "counter-signed receipt against your locally-held review package, and attach "
            "the verified countersignature to your approval journal. Local-only; never contacts AEAT."
        ),
    ),
)
def review_package_import_feedback(
    ctx: typer.Context,
    envelope_path: Annotated[
        Path,
        typer.Argument(
            help=tr(
                "cli.app.modelo.review_package.feedback_envelope_path_help",
                default="Path to the originator-encrypted feedback envelope JSON produced by `encrypt-feedback`.",
            ),
        ),
    ],
    package: Annotated[
        Path,
        typer.Option(
            "--package",
            help=tr(
                "cli.app.modelo.review_package.feedback_package_help",
                default=(
                    "Path to your locally-held original review package ZIP a "
                    "counter-signed receipt is verified against."
                ),
            ),
        ),
    ],
    operator_public_key_hex: Annotated[
        str,
        typer.Option(
            "--operator-public-key",
            help=tr(
                "cli.app.modelo.review_package.feedback_operator_public_key_help",
                default="Your own Ed25519 signing public key the original signature must verify against.",
            ),
        ),
    ],
    counter_signer_public_key_hex: Annotated[
        str | None,
        typer.Option(
            "--counter-signer-public-key",
            help=tr(
                "cli.app.modelo.review_package.feedback_counter_signer_public_key_help",
                default=(
                    "The reviewer's Ed25519 signing public key the counter-signature "
                    "must verify against (required when the feedback carries a receipt)."
                ),
            ),
        ),
    ] = None,
    bucket_id: Annotated[
        str | None,
        typer.Option("--bucket-id", help=tr("cli.app.modelo.review_package.bucket_id_help")),
    ] = None,
) -> None:
    """Import, verify, and journal a recipient's feedback package."""
    from ._modelo_cli_support import bad_parameter_from_error

    if not envelope_path.exists():
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.review_package.errors.feedback_envelope_not_found",
                envelope_path=str(envelope_path),
                default="Feedback envelope not found at {envelope_path}.",
            ),
        )
    if not package.exists():
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.review_package.errors.package_not_found",
                package_path=str(package),
                default="Review package not found at {package_path}.",
            ),
        )

    try:
        envelope = RecipientEncryptedPackage.model_validate_json(envelope_path.read_text(encoding=UTF_8_ENCODING))
    except ValueError as exc:
        raise bad_parameter_from_error(RecipientEncryptionError(str(exc))) from exc

    resolved_bucket_id = resolve_explicit_or_active_bucket_id(bucket_id)

    from ...adapters.persistence.storage import secure_object_repository_for_bucket

    repository = secure_object_repository_for_bucket(resolved_bucket_id)
    keypair = ensure_recipient_encryption_keypair(bucket_id=resolved_bucket_id, repository=repository)

    try:
        imported = import_feedback_package(
            envelope,
            originator_private_key=keypair.private_key(),
            reviewed_package_path=package,
            operator_public_key_hex=operator_public_key_hex,
            counter_signer_public_key_hex=counter_signer_public_key_hex,
        )
    except (RecipientDecryptionError, ReviewPackageFeedbackError, FeedbackCounterSignatureInvalidError) as exc:
        raise bad_parameter_from_error(exc) from exc

    attached = False
    if imported.counter_signature_verified:
        from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository

        emit_collab_feedback_countersign_attached_event(
            imported,
            bucket_id=resolved_bucket_id,
            repository=BucketEventHistoryRepository(objects=repository),
        )
        attached = True

    result, lines = review_package_import_feedback_result(
        envelope_path,
        bucket_id=resolved_bucket_id,
        imported=imported,
        attached=attached,
    )
    _emit_envelope(ctx, command="modelo.review_package.import_feedback", result=result, lines=lines)


def _resolve_optional_cli_period(*, year: int | None, period: str | None) -> Period | None:
    if period is None:
        return None
    if year is None:
        raise typer.BadParameter(tr("cli.common.errors.period_missing_year", token=period))
    return Period.from_year_and_code(year, period.strip())


__all__ = ["register_review_package_commands", "review_package_app"]
