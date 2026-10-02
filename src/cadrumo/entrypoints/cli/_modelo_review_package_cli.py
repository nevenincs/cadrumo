"""Behavior handlers for the ``aeat app modelo review-package`` verb group.

Assembles a shareable, checksum-verifiable review package (``build``) and
verifies one already received (``verify``). The human exchange verbs submit
registered requests to the authenticated profile worker; the public CLI
payloads retain only explicit paths and non-secret receipt metadata. All verbs
are local-only: they never contact AEAT. ``build`` internally reuses
:func:`~application.modelo.export.export_modelo_revision` to obtain the
fichero-BOE draft bytes it bundles, so it inherits every export-time safety
gate (evidence completeness, cross-period clean state, IVA wallet
reconciliation) and also appends the usual ``MODELO_EXPORTED`` bucket event —
building a review package is, structurally, an export plus a checksum-manifest
wrap.

``sign`` / ``counter-sign`` submit package paths and user choices as
``SECURE_REFERENCE`` worker requests. Signing and counter-signing keys, audit
events, replay state, and explicit final artifacts remain in their canonical
worker-owned stores. ``verify-signature`` and ``verify-receipt`` remain local
authenticity checks; only their existing public keys and validity results are
rendered.

``encrypt-for-recipient`` / ``decrypt`` and the two feedback verbs also submit
through the registered worker. The operation result excludes ciphertext,
decrypted bytes, and private keys. Decryption writes plaintext only to the
operator's explicit final ``--output`` path.

See Also:
    :func:`~application.modelo.review_package.build_review_package`
        Application builder for checksum-verifiable review packages.
    :func:`~application.modelo.review_package_signing.sign_review_package`
        Ed25519 authenticity primitive wired by ``sign``.
    :func:`~application.modelo.review_package_recipient_encryption.encrypt_review_package_for_recipient`
        X25519 confidentiality primitive wired by ``encrypt-for-recipient``.
    :class:`~application.modelo.review_package_recipient_registry_ports.RecipientFingerprintRegistryPorts`
        Trusted-recipient public-key capability used before encryption.
    :mod:`~entrypoints.cli._modelo_review_package_payloads`
        Typed JSON payload schemas emitted by this CLI group.
    :mod:`~entrypoints.cli.config.collab`
        Configuration surface that registers recipient fingerprints.
"""

from __future__ import annotations

from pathlib import Path

import typer

from ...application.modelo.operator_inputs import ModeloReviewPackageBuildOperatorInput
from ...application.modelo.review_package import (
    ReviewPackageIntegrityError,
    verify_review_package,
)
from ...application.modelo.review_package_counter_sign import (
    CounterSignedReceipt,
    ReviewPackageCounterSigningError,
    verify_counter_signed_receipt,
)
from ...application.modelo.review_package_operation import (
    ModeloReviewPackageBuildPublicResultV1,
    ModeloReviewPackageBuildRequest,
)
from ...application.modelo.review_package_signing import (
    ReviewPackageSigningError,
    SignedReviewPackage,
    verify_review_package_signature,
)
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...core.external_constants import UTF_8_ENCODING
from ...core.i18n.render import tr
from ._modelo_cli_support import (
    parse_revision_selector,
    resolve_actor_option,
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
from .common import emit_envelope
from .runtime_modelo_review_package import run_modelo_review_package_build
from .runtime_modelo_review_package_exchange import (
    run_review_package_counter_sign,
    run_review_package_decrypt,
    run_review_package_encrypt_feedback,
    run_review_package_encrypt_for_recipient,
    run_review_package_import_feedback,
    run_review_package_sign,
)
from .runtime_modelo_verification import select_modelo_work_revision_for_cli
from .state_projection_support import authority_operation


def review_package_build(
    ctx: typer.Context,
    **input_values: object,
) -> None:
    """Assemble a shareable review package for the resolved revision."""
    operator_input = ModeloReviewPackageBuildOperatorInput.model_validate(input_values)
    if (
        operator_input.output is None
        or not str(operator_input.output).strip()
        or str(operator_input.output).strip() == "."
    ):
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.review_package.errors.output_required",
            )
        )
    client, selected_revision = select_modelo_work_revision_for_cli(
        ctx,
        calculation_revision_id=operator_input.revision,
        work_unit_id=operator_input.work_unit_id,
        modelo=operator_input.modelo,
        year=operator_input.year,
        period=operator_input.period,
        revision=operator_input.registry_revision,
        bucket_id=operator_input.bucket_id,
        selector=parse_revision_selector(operator_input.select),
        default_for="export",
    )
    completed = run_modelo_review_package_build(
        client,
        ModeloReviewPackageBuildRequest(
            profile_id=client.profile_id,
            calculation_revision_id=selected_revision.calculation_revision_id,
            output_path=str(operator_input.output.resolve()),
            actor=resolve_actor_option(operator_input.actor),
            refund_election=operator_input.refund_election,
            payment_election=operator_input.payment_election,
            prior_domiciliation_election=operator_input.prior_domiciliation_election,
            notes=operator_input.notes,
        ),
        work_unit_id=selected_revision.unit.work_unit_id,
    )
    result = completed.projection
    if not isinstance(result, ModeloReviewPackageBuildPublicResultV1):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    build_result = result.to_result()
    emit_envelope(
        ctx,
        command="modelo.review_package.build",
        result=review_package_build_result_payload(build_result),
        lines=review_package_build_result_lines(build_result, export_bucket_event_id=result.export_bucket_event_id),
    )


review_package_build.__dict__["__input_model__"] = ModeloReviewPackageBuildOperatorInput


def review_package_verify(ctx: typer.Context, package: Path) -> None:
    """Verify a review package's checksum manifest and render its descriptor."""
    from ._modelo_cli_support import bad_parameter_from_error

    try:
        verification = verify_review_package(package, operation=authority_operation(ctx))
    except FileNotFoundError as exc:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.review_package.errors.package_not_found",
                package_path=str(package),
            )
        ) from exc
    except ReviewPackageIntegrityError as exc:
        raise bad_parameter_from_error(exc) from exc
    result, lines = review_package_verify_result(package, verification)
    emit_envelope(ctx, command="modelo.review_package.verify", result=result, lines=lines)


def review_package_sign(ctx: typer.Context, package: Path, output: Path, bucket_id: str | None = None) -> None:
    """Sign a review package's manifest digest and write the signature envelope."""
    if not package.exists():
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.review_package.errors.package_not_found",
                package_path=str(package),
            )
        )
    projection = run_review_package_sign(ctx, package=package, output=output, bucket_id=bucket_id)
    result, lines = review_package_sign_result(projection)
    emit_envelope(ctx, command="modelo.review_package.sign", result=result, lines=lines)


def review_package_verify_signature(ctx: typer.Context, package: Path, signature: Path, public_key: str) -> None:
    """Verify a review package's Ed25519 signature against the signer's public key."""
    from ._modelo_cli_support import bad_parameter_from_error

    if not signature.exists():
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.review_package.errors.signature_not_found",
                signature_path=str(signature),
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
    if not signature.exists():
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.review_package.errors.signature_not_found",
                signature_path=str(signature),
            )
        )
    projection = run_review_package_counter_sign(
        ctx,
        package=package,
        signature=signature,
        output=output,
        note=note,
        bucket_id=bucket_id,
    )
    result, lines = review_package_counter_sign_result(projection)
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
    if not package.exists():
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.review_package.errors.package_not_found",
                package_path=str(package),
            )
        )
    if valid_for_days is not None and valid_for_days <= 0:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.review_package.errors.invalid_valid_for_days",
            )
        )
    projection = run_review_package_encrypt_for_recipient(
        ctx,
        package=package,
        recipient_id=recipient_id,
        output=output,
        review_only=review_only,
        valid_for_days=valid_for_days,
        bucket_id=bucket_id,
    )
    result, lines = review_package_encrypt_for_recipient_result(projection)
    emit_envelope(ctx, command="modelo.review_package.encrypt_for_recipient", result=result, lines=lines)


def review_package_decrypt(ctx: typer.Context, envelope_path: Path, output: Path, bucket_id: str | None = None) -> None:
    """Decrypt a recipient-encrypted review package with this bucket's own keypair."""
    if not envelope_path.exists():
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.review_package.errors.envelope_not_found",
                envelope_path=str(envelope_path),
            )
        )
    projection = run_review_package_decrypt(ctx, envelope_path=envelope_path, output=output, bucket_id=bucket_id)
    result, lines = review_package_decrypt_result(projection)
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
    if receipt is not None and not receipt.exists():
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.review_package.errors.receipt_not_found",
                receipt_path=str(receipt),
            )
        )
    projection = run_review_package_encrypt_feedback(
        ctx,
        originator_id=originator_id,
        work_unit_id=work_unit_id,
        calculation_revision_id=calculation_revision_id,
        submitted_by=submitted_by,
        output=output,
        note=note,
        receipt=receipt,
        bucket_id=bucket_id,
    )
    result, lines = review_package_encrypt_feedback_result(projection)
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
    if not envelope_path.exists():
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.review_package.errors.feedback_envelope_not_found",
                envelope_path=str(envelope_path),
            )
        )
    if not package.exists():
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.review_package.errors.package_not_found",
                package_path=str(package),
            )
        )
    projection = run_review_package_import_feedback(
        ctx,
        envelope_path=envelope_path,
        package=package,
        operator_public_key_hex=operator_public_key_hex,
        counter_signer_public_key_hex=counter_signer_public_key_hex,
        bucket_id=bucket_id,
    )
    result, lines = review_package_import_feedback_result(projection)
    emit_envelope(ctx, command="modelo.review_package.import_feedback", result=result, lines=lines)


__all__ = []
