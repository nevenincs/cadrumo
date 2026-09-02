"""Behavior handlers for the ``aeat app modelo review-package`` verb group.

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
composes :class:`~adapters.persistence.profile.recipient_replay_guard.RecipientReplayGuardRepository`
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
    :mod:`~entrypoints.cli.config._collab`
        Configuration surface that registers recipient fingerprints.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import typer

from ...adapters.persistence.profile.recipient_replay_guard import (
    RecipientPackageReplayedError,
    RecipientReplayGuardRepository,
)
from ...application.modelo.action_errors import (
    CalculationRevisionNotFoundError,
    CalculationRevisionStateError,
    ModeloPaymentElectionCapabilityRefusedError,
    ModeloPaymentElectionIncompatibleError,
    ModeloPriorDomiciliationElectionRefusedError,
    ModeloRefundElectionNotEligibleError,
    WorkUnitNotFoundError,
)
from ...application.modelo.export import (
    ModeloExportCommand,
    ModeloExportCrossBucketRefusedError,
    ModeloExportNoActiveBucketError,
    ModeloExportOutputPathError,
    export_modelo_revision,
)
from ...application.modelo.iva_wallet_gate import ModeloIvaWalletReconciliationBlocked
from ...application.modelo.review_package import (
    ReviewPackageError,
    ReviewPackageIntegrityError,
    ReviewPackageRevisionStateError,
    build_review_package,
    verify_review_package,
)
from ...application.modelo.review_package_collab_audit import emit_collab_feedback_countersign_attached_event
from ...application.modelo.review_package_counter_sign import (
    CounterSignedReceipt,
    ReviewPackageCounterSigningError,
    counter_sign_review_package,
    verify_counter_signed_receipt,
)
from ...application.modelo.review_package_feedback import (
    FeedbackCounterSignatureInvalidError,
    ReviewPackageFeedbackError,
    build_feedback_package,
    encrypt_feedback_package_for_originator,
    import_feedback_package,
)
from ...application.modelo.review_package_recipient_encryption import (
    RecipientDecryptionError,
    RecipientEncryptedPackage,
    RecipientEncryptionError,
    decrypt_review_package_for_recipient,
    encrypt_review_package_for_recipient,
    ensure_recipient_encryption_keypair,
)
from ...application.modelo.review_package_recipient_registry import (
    RecipientFingerprintRegistryRepository,
    RecipientNotRegisteredError,
)
from ...application.modelo.review_package_signing import (
    ReviewPackageSigningError,
    SignedReviewPackage,
    ensure_review_package_signing_keypair,
    review_package_signing_public_key,
    sign_review_package,
    verify_review_package_signature,
)
from ...application.modelo.selectors import (
    ModeloCalculationRevisionSelector,
    ModeloCalculationRevisionSelectorAmbiguousError,
    ModeloCalculationRevisionSelectorNotFoundError,
    ModeloCalculationRevisionSelectorStateError,
)
from ...application.modelo.work_addressing import (
    ModeloWorkAddressNotFoundError,
    ModeloWorkPeriodTokenError,
)
from ...application.modelo.work_lifecycle import get_work_unit
from ...application.workflow.persistence import workflow_state_repository
from ...core.external_constants import UTF_8_ENCODING
from ...core.i18n.render import tr
from ...core.payment_election import PaymentElection
from ...core.period import Period
from ...core.prior_domiciliation_election import PriorDomiciliationElection
from ...core.refund_election import RefundElection
from ._common import emit_envelope, filing_taxpayer_or_refuse
from ._modelo_behavior_support import resolve_revision_for_cli
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


def review_package_build(
    ctx: typer.Context,
    work_unit_id: str | None = None,
    modelo: str | None = None,
    year: int | None = None,
    period: str | None = None,
    registry_revision: str | None = None,
    bucket_id: str | None = None,
    select: str = ModeloCalculationRevisionSelector.CURRENT.value,
    output: Path | None = None,
    revision: str | None = None,
    actor: str | None = None,
    refund_election: RefundElection = RefundElection.COMPENSAR,
    payment_election: PaymentElection = PaymentElection.INGRESO,
    prior_domiciliation_election: PriorDomiciliationElection = PriorDomiciliationElection.KEEP,
    notes: str = "",
) -> None:
    """Assemble a shareable review package for the resolved revision."""
    from ._modelo_cli_support import bad_parameter_from_error, selector_bad_parameter

    workflow_state = workflow_state_repository().load()
    workflow_profile = filing_taxpayer_or_refuse(workflow_state)
    if output is None or not str(output).strip() or str(output).strip() == ".":
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.review_package.errors.output_required",
                default="Supply --output PATH for the review package ZIP.",
            )
        )
    try:
        typed_period = _resolve_optional_cli_period(year=year, period=period)
        selected_revision = resolve_revision_for_cli(
            calculation_revision_id=validate_calculation_revision_id(revision) if revision is not None else None,
            work_unit_id=validate_work_unit_id(work_unit_id) if work_unit_id is not None else None,
            modelo=modelo,
            year=year,
            period=typed_period,
            registry_revision=registry_revision,
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
                CalculationRevisionNotFoundError(context={"calculation_revision_id": target_revision_id})
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
    emit_envelope(
        ctx,
        command="modelo.review_package.build",
        result=review_package_build_result_payload(build_result),
        lines=review_package_build_result_lines(build_result, export_bucket_event_id=export_result.bucket_event_id),
    )


def review_package_verify(ctx: typer.Context, package: Path) -> None:
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
            )
        ) from exc
    except ReviewPackageIntegrityError as exc:
        raise bad_parameter_from_error(exc) from exc
    result, lines = review_package_verify_result(package, verification)
    emit_envelope(ctx, command="modelo.review_package.verify", result=result, lines=lines)


def review_package_sign(ctx: typer.Context, package: Path, output: Path, bucket_id: str | None = None) -> None:
    """Sign a review package's manifest digest and write the signature envelope."""
    from ._modelo_cli_support import bad_parameter_from_error

    resolved_bucket_id = resolve_explicit_or_active_bucket_id(bucket_id)
    from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket

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
            )
        ) from exc
    except ReviewPackageIntegrityError as exc:
        raise bad_parameter_from_error(exc) from exc
    except ReviewPackageSigningError as exc:
        raise bad_parameter_from_error(exc) from exc
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(signed.model_dump_json(indent=2), encoding=UTF_8_ENCODING, newline="\n")
    public_key = review_package_signing_public_key(keypair)
    result, lines = review_package_sign_result(
        package, output, bucket_id=resolved_bucket_id, signed=signed, signer_public_key_hex=public_key.public_key_hex
    )
    emit_envelope(ctx, command="modelo.review_package.sign", result=result, lines=lines)


def review_package_verify_signature(ctx: typer.Context, package: Path, signature: Path, public_key: str) -> None:
    """Verify a review package's Ed25519 signature against the signer's public key."""
    from ._modelo_cli_support import bad_parameter_from_error

    if not signature.exists():
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.review_package.errors.signature_not_found",
                signature_path=str(signature),
                default="Signature envelope not found at {signature_path}.",
            )
        )
    try:
        signed = SignedReviewPackage.model_validate_json(signature.read_text(encoding=UTF_8_ENCODING))
    except ValueError as exc:
        raise bad_parameter_from_error(ReviewPackageSigningError(str(exc))) from exc
    signer_public_key_hex = public_key.strip().lower()
    is_valid = verify_review_package_signature(package, signed, public_key_hex=signer_public_key_hex)
    result, lines = review_package_verify_signature_result(
        package, signature, signer_public_key_hex=signer_public_key_hex, is_valid=is_valid
    )
    emit_envelope(ctx, command="modelo.review_package.verify_signature", result=result, lines=lines)


def review_package_counter_sign(
    ctx: typer.Context, package: Path, signature: Path, output: Path, note: str = "", bucket_id: str | None = None
) -> None:
    """Counter-sign an operator's signature envelope and write the receipt."""
    from ._modelo_cli_support import bad_parameter_from_error

    if not signature.exists():
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.review_package.errors.signature_not_found",
                signature_path=str(signature),
                default="Signature envelope not found at {signature_path}.",
            )
        )
    try:
        signed = SignedReviewPackage.model_validate_json(signature.read_text(encoding=UTF_8_ENCODING))
    except ValueError as exc:
        raise bad_parameter_from_error(ReviewPackageSigningError(str(exc))) from exc
    resolved_bucket_id = resolve_explicit_or_active_bucket_id(bucket_id)
    from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket

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
    emit_envelope(ctx, command="modelo.review_package.counter_sign", result=result, lines=lines)


def review_package_verify_receipt(
    ctx: typer.Context, package: Path, receipt_path: Path, operator_public_key: str, counter_signer_public_key: str
) -> None:
    """Verify both signature layers of a counter-signed review-package receipt."""
    from ._modelo_cli_support import bad_parameter_from_error

    if not receipt_path.exists():
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.review_package.errors.receipt_not_found",
                receipt_path=str(receipt_path),
                default="Receipt envelope not found at {receipt_path}.",
            )
        )
    try:
        receipt = CounterSignedReceipt.model_validate_json(receipt_path.read_text(encoding=UTF_8_ENCODING))
    except ValueError as exc:
        raise bad_parameter_from_error(ReviewPackageCounterSigningError(str(exc))) from exc
    operator_key = operator_public_key.strip().lower()
    counter_key = counter_signer_public_key.strip().lower()
    is_valid = verify_counter_signed_receipt(
        package, receipt, operator_public_key_hex=operator_key, counter_signer_public_key_hex=counter_key
    )
    result, lines = review_package_verify_receipt_result(
        package,
        receipt_path,
        operator_public_key_hex=operator_key,
        counter_signer_public_key_hex=counter_key,
        is_valid=is_valid,
    )
    emit_envelope(ctx, command="modelo.review_package.verify_receipt", result=result, lines=lines)


def review_package_encrypt_for_recipient(
    ctx: typer.Context,
    package: Path,
    recipient_id: str,
    output: Path,
    review_only: bool = False,
    valid_for_days: int | None = None,
    bucket_id: str | None = None,
) -> None:
    """Seal a review package for one registered recipient's public key."""
    from ._modelo_cli_support import bad_parameter_from_error

    if not package.exists():
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.review_package.errors.package_not_found",
                package_path=str(package),
                default="Review package not found at {package_path}.",
            )
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
            )
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
        package, output, recipient_id=recipient_id, recipient_public_key_hex=recipient.public_key_hex, envelope=envelope
    )
    emit_envelope(ctx, command="modelo.review_package.encrypt_for_recipient", result=result, lines=lines)


def review_package_decrypt(ctx: typer.Context, envelope_path: Path, output: Path, bucket_id: str | None = None) -> None:
    """Decrypt a recipient-encrypted review package with this bucket's own keypair."""
    from ._modelo_cli_support import bad_parameter_from_error

    if not envelope_path.exists():
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.review_package.errors.envelope_not_found",
                envelope_path=str(envelope_path),
                default="Recipient-encrypted envelope not found at {envelope_path}.",
            )
        )
    try:
        envelope = RecipientEncryptedPackage.model_validate_json(envelope_path.read_text(encoding=UTF_8_ENCODING))
    except ValueError as exc:
        raise bad_parameter_from_error(RecipientEncryptionError(str(exc))) from exc
    resolved_bucket_id = resolve_explicit_or_active_bucket_id(bucket_id)
    from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket

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
        envelope_path, output, bucket_id=resolved_bucket_id, decrypted=decrypted
    )
    emit_envelope(ctx, command="modelo.review_package.decrypt", result=result, lines=lines)


def review_package_encrypt_feedback(
    ctx: typer.Context,
    originator_id: str,
    work_unit_id: str,
    calculation_revision_id: str,
    submitted_by: str,
    output: Path,
    note: str = "",
    receipt: Path | None = None,
    bucket_id: str | None = None,
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
                )
            )
        try:
            counter_signed_receipt = CounterSignedReceipt.model_validate_json(
                receipt.read_text(encoding=UTF_8_ENCODING)
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
            feedback, originator_public_key_hex=originator.public_key_hex
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
    emit_envelope(ctx, command="modelo.review_package.encrypt_feedback", result=result, lines=lines)


def review_package_import_feedback(
    ctx: typer.Context,
    envelope_path: Path,
    package: Path,
    operator_public_key_hex: str,
    counter_signer_public_key_hex: str | None = None,
    bucket_id: str | None = None,
) -> None:
    """Import, verify, and journal a recipient's feedback package."""
    from ._modelo_cli_support import bad_parameter_from_error

    if not envelope_path.exists():
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.review_package.errors.feedback_envelope_not_found",
                envelope_path=str(envelope_path),
                default="Feedback envelope not found at {envelope_path}.",
            )
        )
    if not package.exists():
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.review_package.errors.package_not_found",
                package_path=str(package),
                default="Review package not found at {package_path}.",
            )
        )
    try:
        envelope = RecipientEncryptedPackage.model_validate_json(envelope_path.read_text(encoding=UTF_8_ENCODING))
    except ValueError as exc:
        raise bad_parameter_from_error(RecipientEncryptionError(str(exc))) from exc
    resolved_bucket_id = resolve_explicit_or_active_bucket_id(bucket_id)
    from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket

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
            imported, bucket_id=resolved_bucket_id, repository=BucketEventHistoryRepository(objects=repository)
        )
        attached = True
    result, lines = review_package_import_feedback_result(
        envelope_path, bucket_id=resolved_bucket_id, imported=imported, attached=attached
    )
    emit_envelope(ctx, command="modelo.review_package.import_feedback", result=result, lines=lines)


def _resolve_optional_cli_period(*, year: int | None, period: str | None) -> Period | None:
    if period is None:
        return None
    if year is None:
        raise typer.BadParameter(tr("cli.common.errors.period_missing_year", token=period))
    return Period.from_year_and_code(year, period.strip())


__all__ = []
