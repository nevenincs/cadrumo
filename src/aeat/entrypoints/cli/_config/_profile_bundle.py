"""Profile bundle import/export command registration for ``aeat config profile``.

Profile import/export emits
:class:`~aeat.domain.buckets.BucketEventHistoryRepository` lifecycle events
around portable bundle writes and reads.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import typer

from ....core.errors import AeatError as _AeatError
from ....core.external_constants import OutputLanguage
from ....core.i18n import tr
from ....core.json_contract import Notice, NoticeSeverity
from ....core.time import now as _now
from .._common import _emit_envelope
from .._common import activate_subcommand_output_language as _activate_subcommand_output_language
from .._errors import CliRefusedBoundaryError as _CliRefusedBoundaryError

_PROFILE_TAX_ID_PATH = "identity.tax_id"

if TYPE_CHECKING:
    from ....application.workflow import ProfileBucketPointer, WorkflowStateRepository
    from ....domain.buckets import BucketEventType


def register_profile_bundle_commands(
    profile_app: typer.Typer,
    *,
    profile_state: Callable[[], WorkflowStateRepository],
    resolve_profile_by_label: Callable[[str], ProfileBucketPointer],
    resolve_active_profile_pointer: Callable[[], ProfileBucketPointer | None],
    atomic_create_profile: Callable[..., str],
) -> None:
    """Register profile bundle import/export commands."""
    _register_profile_export_command(
        profile_app,
        profile_state=profile_state,
        resolve_profile_by_label=resolve_profile_by_label,
        resolve_active_profile_pointer=resolve_active_profile_pointer,
    )
    _register_profile_import_command(profile_app, atomic_create_profile=atomic_create_profile)


def _register_profile_export_command(
    profile_app: typer.Typer,
    *,
    profile_state: Callable[[], WorkflowStateRepository],
    resolve_profile_by_label: Callable[[str], ProfileBucketPointer],
    resolve_active_profile_pointer: Callable[[], ProfileBucketPointer | None],
) -> None:
    @profile_app.command(
        "export",
        help=tr(
            "cli.config.profile.export_help",
            default="Write a portable profile bundle to PATH.",
        ),
    )
    def config_profile_export(
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
        """Serialize a profile bundle to a JSON file."""
        from ....application.user_profile import profile_storage_session, serialize_profile_bundle
        from ....domain.buckets import BucketEventType
        from ....domain.user_profile import ProfileNotFoundError
        from ....domain.user_profile._portable_export import UserProfilePortableExport
        from .._config_payloads import ConfigProfileExportResult

        _activate_subcommand_output_language(ctx, output_language)
        profile_state().load()
        if name is not None:
            pointer = resolve_profile_by_label(name)
        else:
            pointer = resolve_active_profile_pointer()
            if pointer is None:
                raise _CliRefusedBoundaryError(
                    translated_message="cli.config.errors.no_active_profile",
                )

        def _serialize_and_record() -> UserProfilePortableExport:
            serialized = serialize_profile_bundle(bucket_id=pointer.bucket_id)
            _emit_profile_lifecycle_event(
                event_type=BucketEventType.PROFILE_EXPORTED,
                bucket_id=pointer.bucket_id,
                object_id=pointer.bucket_id,
                payload={
                    "display_name": pointer.label or "",
                    "out": str(out),
                    "schema_version": str(serialized.bundle_schema_version),
                },
            )
            return serialized

        try:
            from ....adapters.persistence.storage import has_active_bucket_session
            from ....core import resolve_active_bucket_id as _resolve_active_bucket_id

            if pointer.bucket_id == _resolve_active_bucket_id() and has_active_bucket_session():
                bundle = _serialize_and_record()
            else:
                with profile_storage_session(pointer.bucket_id):
                    bundle = _serialize_and_record()
        except ProfileNotFoundError as exc:
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.profile.unknown_profile",
                context={"name": pointer.label},
            ) from exc
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(bundle.model_dump_json(indent=2), encoding="utf-8")

        export_result = ConfigProfileExportResult(
            profile_id=pointer.bucket_id,
            display_name=pointer.label,
            out=str(out),
            schema_version=bundle.bundle_schema_version,
        )
        sensitivity_notice = _build_export_sensitivity_notice(out)
        _emit_envelope(
            ctx,
            command="config.profile.export",
            result=export_result,
            lines=(
                f"profile_id\t{pointer.bucket_id}",
                f"display_name\t{pointer.label}",
                f"out\t{out}",
                f"schema_version\t{bundle.bundle_schema_version}",
                f"WARNING\t{sensitivity_notice.message}",
            ),
            notices=(sensitivity_notice,),
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
                "the raw tax id (not redacted), the full ledger, calculation revisions, "
                "and filing records. It was written to {out}. Delete it after transfer; "
                "do not email, sync, or leave it on disk."
            ),
            out=str(out),
        ),
        context={"out": str(out)},
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
        path: Path = typer.Argument(
            ...,
            help=tr("cli.config.profile.import_path_help", default="Path to the JSON bundle."),
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
        from ....application.user_profile import (
            ProfileAlreadyRegisteredError,
            UnsupportedBundleSchemaVersionError,
            deserialize_profile_bundle,
            profile_storage_session,
        )
        from ....application.workflow import read_profile_bucket as _read_profile_bucket
        from ....application.workflow import read_profile_bucket_by_id
        from ....domain.buckets import BucketEventType
        from ....domain.user_profile._portable_export import UserProfilePortableExport
        from .._config_payloads import ConfigProfileImportResult

        if not path.is_file():
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.profile.import_missing_bundle",
                context={"path": str(path)},
            )
        try:
            bundle = UserProfilePortableExport.model_validate_json(path.read_text(encoding="utf-8"))
        except _AeatError:
            raise
        except Exception as exc:
            from ....core.logging import get_logger

            get_logger(__name__).debug("config profile import rejected invalid portable bundle", exc_info=True)
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.profile.import_invalid_bundle",
                context={"error": str(exc)},
            ) from exc
        try:
            _validate_bundle_schema_version(bundle)
        except UnsupportedBundleSchemaVersionError as exc:
            raise _CliRefusedBoundaryError(str(exc)) from exc
        record = bundle.profile
        _validate_imported_profile_tax_id(record)
        bundle_profile_id = record.profile_id

        explicit_label = label.strip() if label is not None and label.strip() else None
        fresh_uuid_mode = explicit_label is not None

        if not fresh_uuid_mode and read_profile_bucket_by_id(bundle_profile_id) is not None:
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
        try:
            target_id = atomic_create_profile(
                display_name=target_label,
                facts=record.facts,
                profile_id=None if fresh_uuid_mode else bundle_profile_id,
            )
        except ProfileAlreadyRegisteredError as exc:
            raise _CliRefusedBoundaryError(
                translated_message="cli.config.profile.already_exists",
                context={"name": target_label},
            ) from exc

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
                    "fresh_uuid_mode": str(fresh_uuid_mode).lower(),
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
                "commands operate on it. Run 'aeat config switch <name>' to change "
                "the active profile."
            ),
            name=target_label,
        ),
        suggestion=f"aeat config switch {target_label}",
        context={"active_profile": target_label},
    )


def _validate_bundle_schema_version(bundle: object) -> None:
    """Raise UnsupportedBundleSchemaVersionError if bundle version is not supported."""
    from ....application.user_profile import (
        SUPPORTED_BUNDLE_SCHEMA_VERSIONS,
        UnsupportedBundleSchemaVersionError,
    )

    version = getattr(bundle, "bundle_schema_version", None)
    if version not in SUPPORTED_BUNDLE_SCHEMA_VERSIONS:
        raise UnsupportedBundleSchemaVersionError(
            f"bundle_schema_version {version!r} is not supported; "
            f"supported versions: {sorted(SUPPORTED_BUNDLE_SCHEMA_VERSIONS)}",
            translated_message="application.user_profile.errors.unsupported_bundle_schema_version",
        )


def _validate_imported_profile_tax_id(record: object) -> None:
    """Refuse portable bundles whose filing identity tax id is absent or invalid."""
    # The bundle is plaintext and may be tampered. `config profile create`
    # validates the NIF/CIF/NIE checksum via SubjectTaxId; the import path must
    # enforce the same gate so an invalid identifier cannot become an active,
    # filing-grade profile (a tampered or garbage tax id otherwise imports clean).
    from ....core.identity import IdentityError, validate_spanish_tax_id

    tax_id_values = [
        fact.value
        for fact in getattr(record, "facts", ())
        if getattr(fact, "path", None) == _PROFILE_TAX_ID_PATH
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
        raise _invalid_import_tax_id(str(exc)) from exc


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
    from ....domain.buckets import (
        BucketEvent,
        BucketEventHistoryCatalogue,
        BucketEventHistoryRepository,
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
