"""Profile bundle import/export command registration for ``aeat config profile``.

Profile import emits a lifecycle event after restoring a portable bundle.
Profile export delegates resolution, serialization, publication, and event
recording to the application-layer export authority.

The bundle passphrase is never an ``argv`` value (the process table and shell
history must not see it): export under ``--encrypt`` collects it via a hidden
confirm-retype prompt or one bounded strict-JSON ``--secrets-stdin`` object,
and import auto-detects an encrypted envelope and collects the passphrase the
same way, through the shared :mod:`._secure_input` channel.

Both verbs carry an interactive mode: when the destination / transport
(export) or the bundle path (import) is omitted on a host that can prompt,
the missing answers are collected through the paged flow substrate (see
:mod:`._profile_bundle_flow`) and acted on by this same canonical path; a
fully-specified invocation never launches a flow, and a non-interactive
host keeps its typed refusal.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from pydantic import BaseModel, ConfigDict, SecretStr

from ....core.errors import CadrumoError as _CadrumoError
from ....core.errors import resolve_error_message as _resolve_error_message
from ....core.external_constants import OutputLanguage
from ....core.i18n import tr
from ....core.json_contract import Notice, NoticeSeverity
from ....core.time import now as _now
from .._common import _emit_envelope
from .._common import activate_subcommand_output_language as _activate_subcommand_output_language
from .._errors import CliRefusedBoundaryError as _CliRefusedBoundaryError
from ._secure_input import prompt_secret_no_echo, read_secrets_stdin

_PROFILE_TAX_ID_PATH = "identity.tax_id"


class _BundleExportSecrets(BaseModel):
    """Strict ``--secrets-stdin`` payload for ``config profile export --encrypt``.

    Export SETS the bundle passphrase, so the payload carries the value and its
    confirmation as :class:`~pydantic.SecretStr`; ``extra="forbid"`` refuses an
    unexpected field.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    passphrase: SecretStr
    passphrase_confirmation: SecretStr


class _BundleImportSecrets(BaseModel):
    """Strict ``--secrets-stdin`` payload for ``config profile import``.

    Import USES an existing bundle passphrase, so one field suffices.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    passphrase: SecretStr


def _resolve_export_passphrase(secrets_stdin: bool) -> str:
    """Return the confirmed bundle passphrase from stdin JSON or no-echo prompts.

    A value/confirmation mismatch refuses before any bundle is serialized;
    nothing is ever read from ``argv``.
    """
    if secrets_stdin:
        secrets = read_secrets_stdin(_BundleExportSecrets)
        value = secrets.passphrase.get_secret_value()
        confirmation = secrets.passphrase_confirmation.get_secret_value()
    else:
        value = prompt_secret_no_echo(tr("cli.config.profile.export_passphrase_prompt"))
        confirmation = prompt_secret_no_echo(tr("cli.config.profile.export_confirm_passphrase_prompt"))
    if value != confirmation:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.export_passphrase_mismatch",
        )
    return value


def _resolve_import_passphrase(secrets_stdin: bool) -> str:
    """Return the bundle passphrase for an encrypted import, never from ``argv``."""
    if secrets_stdin:
        return read_secrets_stdin(_BundleImportSecrets).passphrase.get_secret_value()
    return prompt_secret_no_echo(tr("cli.config.profile.import_passphrase_prompt"))


if TYPE_CHECKING:
    from ....domain.buckets import BucketEventType
    from ....domain.user_profile import UserProfilePortableExport, UserProfileRecord


def register_profile_bundle_commands(
    profile_app: typer.Typer,
    *,
    atomic_create_profile: Callable[..., str],
) -> None:
    """Register profile bundle import/export commands."""
    _register_profile_export_command(profile_app)
    _register_profile_sar_command(profile_app)
    _register_profile_import_command(profile_app, atomic_create_profile=atomic_create_profile)


def _register_profile_sar_command(profile_app: typer.Typer) -> None:
    @profile_app.command(
        "subject-access-request",
        help=tr(
            "cli.config.profile.sar_help",
            default=(
                "Export all personal data held for a profile as a GDPR "
                "right-of-access archive (the portable profile bundle)."
            ),
        ),
    )
    def config_profile_subject_access_request(
        ctx: typer.Context,
        name: str | None = typer.Argument(
            None,
            help=tr("cli.config.profile.export_name_help", default="Profile to export; defaults to active."),
        ),
        out: Path = typer.Option(
            ...,
            "--to",
            help=tr("cli.config.profile.export_out_help", default="Destination path for the JSON bundle."),
        ),
        output_language: OutputLanguage | None = typer.Option(
            None,
            "--output-language",
            "--language",
            help=tr("cli.config.auth.output_language_help"),
        ),
    ) -> None:
        """Produce the operator's own personal-data archive (GDPR right of access)."""
        from ....application.user_profile import (
            ProfileBundleExportPurpose,
            ProfileBundleExportRequest,
            ProfileBundleExportTransport,
            export_profile_bundle,
        )
        from ....application.workflow import ProfileLabelAmbiguousError
        from ....domain.user_profile import ProfileNotFoundError
        from .._config_payloads import ConfigProfileSubjectAccessRequestResult

        _activate_subcommand_output_language(ctx, output_language)
        try:
            export = export_profile_bundle(
                ProfileBundleExportRequest(
                    profile_name=name,
                    destination=out,
                    purpose=ProfileBundleExportPurpose.SUBJECT_ACCESS,
                    transport=ProfileBundleExportTransport.CLEARTEXT_LOCAL,
                ),
            )
        except ProfileLabelAmbiguousError as exc:
            raise _CliRefusedBoundaryError(
                translated_message="errors.refused.refused_profile_label_ambiguous",
            ) from exc
        except ProfileNotFoundError as exc:
            if name is None:
                raise _CliRefusedBoundaryError(
                    translated_message="cli.config.errors.no_active_profile",
                ) from exc
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.profile.unknown_profile",
                context={"name": name},
            ) from exc

        result = ConfigProfileSubjectAccessRequestResult(
            profile_id=export.profile_id,
            display_name=export.display_name,
            out=str(export.destination),
            schema_version=export.bundle_schema_version,
            data_categories=list(export.data_categories),
        )
        sensitivity_notice = _build_export_sensitivity_notice(out)
        catalogue_notice = _build_sar_catalogue_notice(export.data_categories)
        _emit_envelope(
            ctx,
            command="config.profile.subject_access_request",
            result=result,
            lines=(
                f"profile_id\t{export.profile_id}",
                f"display_name\t{export.display_name}",
                f"out\t{out}",
                f"schema_version\t{export.bundle_schema_version}",
                f"data_categories\t{','.join(export.data_categories)}",
                f"INFO\t{catalogue_notice.message}",
                f"WARNING\t{sensitivity_notice.message}",
            ),
            notices=(catalogue_notice, sensitivity_notice),
        )


def _build_sar_catalogue_notice(data_categories: tuple[str, ...]) -> Notice:
    """Build the data-catalogue notice for the personal-data categories held.

    A GDPR right-of-access response must tell the subject what categories of
    their personal data are held, not only hand over a blob. The authoritative
    category set is the one the export service derives from the bundle schema
    and its carried registry namespaces; this info :class:`Notice` points the
    subject at that derived ``data_categories`` set (carried on the response and
    machine-readably in ``context``) rather than re-enumerating a static list
    the CLI would own and let drift, per
    ``cli-notices-are-the-only-diagnostic-channel``.
    """
    return Notice(
        severity=NoticeSeverity.INFO,
        code="config.profile.subject_access_request.data_catalogue",
        message=tr(
            "cli.config.profile.sar_catalogue_info",
            default=(
                "This archive holds every personal-data category kept for the "
                "profile. The exact categories are listed in the data_categories "
                "field of this response and its machine-readable context. "
                "Attachment evidence bytes and AEAT captures stay in encrypted "
                "storage; use the encrypted recovery archive to include them."
            ),
        ),
        context={"data_categories": ",".join(data_categories)},
    )


def _register_profile_export_command(profile_app: typer.Typer) -> None:
    @profile_app.command(
        "export",
        help=tr(
            "cli.config.profile.export_help",
            default=(
                "Write a passphrase-encrypted portable profile bundle to PATH; "
                "cleartext JSON requires --cleartext-local for local/SAR use only."
            ),
        ),
    )
    def config_profile_export(
        ctx: typer.Context,
        name: str | None = typer.Argument(
            None,
            help=tr("cli.config.profile.export_name_help", default="Profile to export; defaults to active."),
        ),
        out: Path | None = typer.Option(
            None,
            "--to",
            help=tr("cli.config.profile.export_out_help", default="Destination path for the profile bundle."),
        ),
        encrypt: bool = typer.Option(
            False,
            "--encrypt",
            help=tr(
                "cli.config.profile.export_encrypt_help",
                default=(
                    "AEAD-encrypt the bundle for transfer; the passphrase is "
                    "prompted (hidden) or read via --secrets-stdin, never argv."
                ),
            ),
        ),
        secrets_stdin: bool = typer.Option(
            False,
            "--secrets-stdin",
            help=tr("cli.config.custody.secrets_stdin_help"),
        ),
        cleartext_local: bool = typer.Option(
            False,
            "--cleartext-local",
            help=tr(
                "cli.config.profile.export_cleartext_local_help",
                default="Write cleartext JSON for local/SAR handling only; not safe for email, sync, or transfer.",
            ),
        ),
        output_language: OutputLanguage | None = typer.Option(
            None,
            "--output-language",
            "--language",
            help=tr("cli.config.auth.output_language_help"),
        ),
    ) -> None:
        """Serialize a profile bundle to a JSON file."""
        from ....application.user_profile import (
            ProfileBundleExportPurpose,
            ProfileBundleExportRequest,
            ProfileBundleExportTransport,
            export_profile_bundle,
        )
        from ....application.workflow import ProfileLabelAmbiguousError
        from ....domain.user_profile import ProfileNotFoundError
        from .._config_payloads import ConfigProfileExportResult

        _activate_subcommand_output_language(ctx, output_language)
        # ``--secrets-stdin`` only carries the encryption passphrase, so it
        # implies the encrypted transport.
        encrypted_mode = encrypt or secrets_stdin
        if not secrets_stdin and (out is None or (not encrypted_mode and not cleartext_local)):
            from ._profile_bundle_flow import collect_export_request_interactively, interactive_capability

            capability = interactive_capability()
            if capability is not None:
                collected = collect_export_request_interactively(
                    name=name,
                    destination=out,
                    encrypt=encrypt,
                    cleartext_local=cleartext_local,
                    capability=capability,
                )
                name = collected.profile_name
                out = collected.destination
                if not encrypt and not cleartext_local:
                    encrypt = collected.encrypt
                    cleartext_local = not collected.encrypt
                encrypted_mode = encrypt or secrets_stdin
        if out is None:
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.profile.export_requires_destination",
                suggestion="aeat config profile export NAME --to bundle.json --encrypt",
            )
        _validate_export_transport_options(encrypt=encrypted_mode, cleartext_local=cleartext_local)
        passphrase: str | None = None
        if encrypted_mode:
            passphrase = _resolve_export_passphrase(secrets_stdin)
            if len(passphrase) < 8:
                raise _CliRefusedBoundaryError(
                    translated_message="cli.config.profile.export_passphrase_too_short",
                )
        try:
            export = export_profile_bundle(
                ProfileBundleExportRequest(
                    profile_name=name,
                    destination=out,
                    purpose=ProfileBundleExportPurpose.PORTABLE_TRANSFER,
                    transport=(
                        ProfileBundleExportTransport.CLEARTEXT_LOCAL
                        if passphrase is None
                        else ProfileBundleExportTransport.PASSPHRASE_ENCRYPTED
                    ),
                    passphrase=SecretStr(passphrase) if passphrase is not None else None,
                ),
            )
        except ProfileLabelAmbiguousError as exc:
            raise _CliRefusedBoundaryError(
                translated_message="errors.refused.refused_profile_label_ambiguous",
            ) from exc
        except ProfileNotFoundError as exc:
            if name is None:
                raise _CliRefusedBoundaryError(
                    translated_message="cli.config.errors.no_active_profile",
                ) from exc
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.profile.unknown_profile",
                context={"name": name},
            ) from exc
        if passphrase is None:
            notices = (_build_export_sensitivity_notice(out),)
            transport = "cleartext-local"
        else:
            notices = (_build_encrypted_export_notice(out),)
            transport = "passphrase-encrypted"

        export_result = ConfigProfileExportResult(
            profile_id=export.profile_id,
            display_name=export.display_name,
            out=str(export.destination),
            schema_version=export.bundle_schema_version,
        )
        _emit_envelope(
            ctx,
            command="config.profile.export",
            result=export_result,
            lines=(
                f"profile_id\t{export.profile_id}",
                f"display_name\t{export.display_name}",
                f"out\t{out}",
                f"transport\t{transport}",
                f"schema_version\t{export.bundle_schema_version}",
                *(f"{notice.severity.value.upper()}\t{notice.message}" for notice in notices),
            ),
            notices=notices,
        )


def _build_export_sensitivity_notice(out: Path) -> Notice:
    """Build the loud sensitivity warning for a written cleartext profile bundle.

    The portable bundle is a deliberate :class:`UserProfilePortableExport`
    portability surface, so unlike every other persistence path it lands
    cleartext on operator disk. The bundle carries the raw tax id (verbatim,
    not the ``sha256:`` redaction ``config profile show`` applies) plus the
    full ledger, calculation revisions, and filing records. This warning is
    the operator's only signal that the file is sensitive financial data: it
    names the contents, the exact path written, and instructs deletion after
    transfer. Routed through the typed :class:`Notice` channel per
    ``cli-notices-are-the-only-diagnostic-channel``; the ``sensitive-financial
    -data-secure-storage-only`` rule's portability carve-out is what makes the
    cleartext write permissible, and this warning is its floor.
    """
    return Notice(
        severity=NoticeSeverity.WARNING,
        code="config.profile.export.cleartext_sensitive_bundle",
        message=tr(
            "cli.config.profile.export_sensitivity_warning",
            default=(
                "This bundle is UNENCRYPTED and contains sensitive financial data: "
                "the raw tax id (not redacted), names/surnames, the full ledger, "
                "calculation revisions, and filing records. It was written to {out}. "
                "Use it only for local/SAR handling; do not email, sync, or transfer it. "
                "Delete it after that local/SAR handling is complete. "
                "Use 'aeat config profile export --encrypt' for an AEAD-encrypted "
                "structured transfer bundle. It is NOT a full backup: "
                "attachment evidence bytes, AEAT captures, and the audit trail are "
                "excluded. Use the encrypted recovery archive for a complete backup."
            ),
            out=str(out),
        ),
        context={"out": str(out)},
    )


def _build_encrypted_export_notice(out: Path) -> Notice:
    """Build the info notice for the passphrase-encrypted bundle transport."""
    return Notice(
        severity=NoticeSeverity.INFO,
        code="config.profile.export.encrypted_bundle",
        message=tr(
            "cli.config.profile.export_encrypted_info",
            default=(
                "This profile bundle was written to {out} with AEAD passphrase encryption. "
                "Import it with 'aeat config profile import PATH'; the passphrase is "
                "prompted (hidden) or read via --secrets-stdin. "
                "It carries the structured profile bundle only; use the encrypted recovery "
                "archive for a complete backup with attachment evidence bytes and audit trail."
            ),
            out=str(out),
        ),
        suggestion="aeat config profile import PATH",
        context={"out": str(out), "transport": "passphrase-encrypted"},
    )


def _validate_export_transport_options(*, encrypt: bool, cleartext_local: bool) -> None:
    """Require an explicit encrypted or local-cleartext export mode."""
    if encrypt and cleartext_local:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.export_transport_conflict",
        )
    if not encrypt and not cleartext_local:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.export_requires_transport",
            suggestion="aeat config profile export NAME --to bundle.json --encrypt",
        )


def _register_profile_import_command(
    profile_app: typer.Typer,
    *,
    atomic_create_profile: Callable[..., str],
) -> None:
    @profile_app.command(
        "import",
        help=tr(
            "cli.config.profile.import_help",
            default="Register a portable profile bundle from PATH into the active profile.",
        ),
    )
    def config_profile_import(
        ctx: typer.Context,
        path: Path | None = typer.Argument(
            None,
            help=tr("cli.config.profile.import_path_help", default="Path to the profile bundle."),
        ),
        secrets_stdin: bool = typer.Option(
            False,
            "--secrets-stdin",
            help=tr("cli.config.custody.secrets_stdin_help"),
        ),
        label: str | None = typer.Option(
            None,
            "--label",
            help=tr("cli.config.profile.import_label_help"),
        ),
        output_language: OutputLanguage | None = typer.Option(
            None,
            "--output-language",
            "--language",
            help=tr("cli.config.auth.output_language_help"),
        ),
    ) -> None:
        """Read a portable profile bundle from a JSON file and register it."""
        _activate_subcommand_output_language(ctx, output_language)
        if path is None:
            from ._profile_bundle_flow import collect_import_request_interactively, interactive_capability

            capability = interactive_capability()
            if capability is None:
                raise _CliRefusedBoundaryError(
                    translated_message="cli.config.profile.import_requires_path",
                    suggestion="aeat config profile import bundle.json",
                )
            collected = collect_import_request_interactively(label=label, capability=capability)
            path = collected.path
            label = collected.label
        from ....application.user_profile import (
            deserialize_profile_bundle,
            missing_filing_baseline_flags,
            profile_storage_session,
            record_to_path_values,
        )
        from ....domain.buckets import BucketEventType
        from .._config_payloads import ConfigProfileImportResult

        raw_bundle_text = _load_import_bundle_text(path)
        bundle = _decode_import_bundle(raw_bundle_text, path, secrets_stdin=secrets_stdin)
        record = bundle.profile
        _validate_imported_profile_tax_id(record)
        _validate_imported_profile_filing_baseline(
            missing_filing_baseline_flags(record_to_path_values(record)),
        )
        target_label = _resolve_import_target_label(record, label)
        target_id = _create_imported_profile(
            record,
            target_label,
            atomic_create_profile=atomic_create_profile,
        )

        with profile_storage_session(target_id):
            deserialize_profile_bundle(bundle, target_bucket_id=target_id)
            _emit_profile_lifecycle_event(
                event_type=BucketEventType.PROFILE_IMPORTED,
                bucket_id=target_id,
                object_id=target_id,
                payload={
                    "display_name": target_label,
                    "source_path": str(path),
                    "schema_version": str(bundle.bundle_schema_version),
                },
            )

        import_result = ConfigProfileImportResult(
            profile_id=target_id,
            display_name=target_label,
            schema_version=bundle.bundle_schema_version,
        )
        switch_notice = _build_import_active_switch_notice(target_label)
        _emit_envelope(
            ctx,
            command="config.profile.import",
            result=import_result,
            lines=(
                f"profile_id\t{target_id}",
                f"display_name\t{target_label}",
                f"schema_version\t{bundle.bundle_schema_version}",
                f"INFO\t{switch_notice.message}",
            ),
            notices=(switch_notice,),
        )


def _load_import_bundle_text(path: Path) -> str:
    """Read the portable bundle file as UTF-8 text, refusing a missing/unreadable path."""
    if not path.is_file():
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.import_missing_bundle",
            context={"path": str(path)},
        )
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.import_invalid_bundle",
            context={"error": str(exc)},
        ) from exc


def _decode_import_bundle(
    raw_bundle_text: str,
    path: Path,
    *,
    secrets_stdin: bool,
) -> UserProfilePortableExport:
    """Auto-detect the transport and decode the portable bundle.

    The strict encrypted envelope (``extra="forbid"``, required KDF fields)
    cannot validate a cleartext bundle, so a successful parse means an encrypted
    export. Only then is the passphrase collected — via the secure-input channel,
    never argv.
    """
    from pydantic import ValidationError

    from ....application.user_profile import (
        EncryptedProfileBundleError,
        EncryptedProfileBundleExport,
        UnsupportedBundleSchemaVersionError,
        decrypt_profile_bundle_with_passphrase,
        validate_bundle_payload,
    )

    encrypted: EncryptedProfileBundleExport | None
    try:
        encrypted = EncryptedProfileBundleExport.model_validate_json(raw_bundle_text)
    except (ValueError, ValidationError):
        encrypted = None
    try:
        if encrypted is None:
            return validate_bundle_payload(raw_bundle_text)
        passphrase = _resolve_import_passphrase(secrets_stdin)
        return decrypt_profile_bundle_with_passphrase(encrypted, passphrase=passphrase)
    except UnsupportedBundleSchemaVersionError as exc:
        raise _CliRefusedBoundaryError(str(exc)) from exc
    except EncryptedProfileBundleError as exc:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.import_encrypted_bundle_invalid",
            context={"path": str(path)},
        ) from exc
    except _CadrumoError:
        raise
    except Exception as exc:
        from ....core.logging import get_logger

        get_logger(__name__).debug("config profile import rejected invalid portable bundle", exc_info=True)
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.import_invalid_bundle",
            context={"error": str(exc)},
        ) from exc


def _resolve_import_target_label(record: UserProfileRecord, label: str | None) -> str:
    """Resolve the target profile label, refusing UUID collisions and taken labels.

    The label defaults to the bundled :class:`UserProfileRecord` display name,
    and the record's ``profile_id`` is what the collision check looks up.
    """
    from ....application.workflow import read_profile_bucket as _read_profile_bucket
    from ....application.workflow import read_profile_bucket_by_id

    bundle_profile_id = record.profile_id
    explicit_label = label.strip() if label is not None and label.strip() else None
    if read_profile_bucket_by_id(bundle_profile_id) is not None:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.import_uuid_collision",
            context={"profile_id": bundle_profile_id},
        )
    target_label = explicit_label if explicit_label is not None else record.display_name
    existing = _read_profile_bucket(target_label)
    if existing is not None:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.import_label_taken_different_id",
            context={"name": target_label},
        )
    return target_label


def _create_imported_profile(
    record: UserProfileRecord,
    target_label: str,
    *,
    atomic_create_profile: Callable[..., str],
) -> str:
    """Create the imported profile under ``target_label``, keeping the bundle UUID."""
    from ....application.user_profile import ProfileAlreadyRegisteredError

    try:
        return atomic_create_profile(
            display_name=target_label,
            facts=record.facts,
            profile_id=record.profile_id,
        )
    except ProfileAlreadyRegisteredError as exc:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.profile.already_exists",
            context={"name": target_label},
        ) from exc


def _build_import_active_switch_notice(target_label: str) -> Notice:
    """Build the info notice that names the active-profile switch on import.

    Importing a bundle provisions the new profile through
    ``register_active_profile``, which atomically makes the imported profile
    the ACTIVE one — every subsequent command in the session operates on it.
    A gestor importing a client mid-session would otherwise be silently
    switched onto that client. This non-blocking ``info`` :class:`Notice`
    makes the switch explicit and tells the operator how to switch back,
    per ``cli-notices-are-the-only-diagnostic-channel``.
    """
    return Notice(
        severity=NoticeSeverity.INFO,
        code="config.profile.import.active_profile_switched",
        message=tr(
            "cli.config.profile.import_active_switch_info",
            default=(
                "The imported profile {name} is now the ACTIVE profile; subsequent "
                "commands operate on it. Run 'aeat config login <name>' to change "
                "the active profile."
            ),
            name=target_label,
        ),
        suggestion=f"aeat config login {target_label}",
        context={"active_profile": target_label},
    )


def _validate_imported_profile_tax_id(record: object) -> None:
    """Refuse portable bundles whose filing identity tax id is absent or invalid."""
    # The bundle is plaintext and may be tampered. `config profile create`
    # validates the NIF/CIF/NIE checksum via SubjectTaxId; the import path must
    # enforce the same gate so an invalid identifier cannot become an active,
    # filing-grade profile (a tampered or garbage tax id otherwise imports clean).
    from ....core.identity import IdentityError, validate_spanish_tax_id

    tax_id_values = [
        fact.value for fact in getattr(record, "facts", ()) if getattr(fact, "path", None) == _PROFILE_TAX_ID_PATH
    ]
    if len(tax_id_values) != 1:
        raise _invalid_import_tax_id(
            f"{_PROFILE_TAX_ID_PATH} must appear exactly once in the profile bundle",
        )
    tax_id = tax_id_values[0]
    if not isinstance(tax_id, str) or not tax_id.strip():
        raise _invalid_import_tax_id(f"{_PROFILE_TAX_ID_PATH} must be a non-empty string")
    try:
        validate_spanish_tax_id(tax_id.strip())
    except IdentityError as exc:
        raise _invalid_import_tax_id(_resolve_error_message(exc)) from exc


def _validate_imported_profile_filing_baseline(missing_flags: tuple[str, ...]) -> None:
    """Refuse portable bundles that would register filing-incomplete profiles."""
    if not missing_flags:
        return
    raise _CliRefusedBoundaryError(
        translated_message="cli.config.profile.import_missing_filing_baseline",
        context={"missing_flags": _format_missing_flags(missing_flags)},
    )


def _format_missing_flags(missing_flags: tuple[str, ...]) -> str:
    return " ".join(f"--{flag}" for flag in missing_flags)


def _invalid_import_tax_id(error: str) -> _CliRefusedBoundaryError:
    return _CliRefusedBoundaryError(
        translated_message="cli.config.profile.import_invalid_tax_id",
        context={"error": error},
    )


def _emit_profile_lifecycle_event(
    *,
    event_type: BucketEventType,
    bucket_id: str,
    object_id: str,
    payload: dict[str, str],
) -> None:
    """Append a profile-lifecycle event to the bucket-event-history catalogue."""
    from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
    from ....domain.buckets import (
        BucketEvent,
        BucketEventHistoryCatalogue,
        BucketEventObjectType,
        derive_bucket_event_id,
    )

    occurred_at = _now().replace(microsecond=0)
    actor = "operator"
    event_id = derive_bucket_event_id(
        bucket_id=bucket_id,
        event_type=event_type,
        occurred_at=occurred_at,
        actor=actor,
        object_type=BucketEventObjectType.PROFILE,
        object_id=object_id,
        payload=payload,
    )
    event = BucketEvent(
        event_id=event_id,
        bucket_id=bucket_id,
        event_type=event_type,
        occurred_at=occurred_at,
        actor=actor,
        object_type=BucketEventObjectType.PROFILE,
        object_id=object_id,
        payload_version=1,
        payload=payload,
    )
    repo = BucketEventHistoryRepository()
    catalogue = repo.load()
    repo.save(BucketEventHistoryCatalogue(events={**catalogue.events, event_id: event}))


__all__ = ["register_profile_bundle_commands"]
