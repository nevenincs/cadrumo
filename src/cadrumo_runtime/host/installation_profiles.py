"""Installation acts over profiles nobody has opened: listing, creation, archives and recovery.

Each handler calls the application function the matching ``config profile``
command calls, over the storage root this runtime owns, and answers with that
command's result: the same members and the real values. A frontend shows the
reply as it arrives. Hiding an identifier is what the command does when it
prints, and a caller names a profile by the identifier it reads here.

A passphrase arrives in the act's one secret frame and never in a request. A
profile is created here, in the runtime, so its key is generated and wrapped in
no frontend process, and the created profile is left selected and signed out. A
recovery code leaves in the act's one outbound secret frame and is read back
before the wrapper is installed, so nothing is enrolled under a code nobody
holds. Neither enters a reply, a refusal or a log record.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager, suppress
from hmac import compare_digest
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from cadrumo.adapters.persistence.storage.errors import StorageValidationError
from cadrumo.adapters.persistence.storage.profile_persistence_composition import composed_profile_persistence_ports
from cadrumo.adapters.persistence.storage.recovery_key import canonical_recovery_code
from cadrumo.application.user_profile.custody_ports import ProfileCustodyRecordIntegrityError
from cadrumo.application.user_profile.profile_summary import profile_listing, selected_profile_id
from cadrumo.core.errors.hierarchy import NoActiveProfileError
from cadrumo_client.contracts.automation_codes import AutomationCustodyCode, AutomationCustodyError
from cadrumo_client.contracts.installation_requests import (
    ArchiveImportPrepareReply,
    ArchiveImportPrepareRequest,
    ArchiveImportReply,
    ArchiveImportRequest,
    ArchiveInspectReply,
    ArchiveInspectRequest,
    InstallationCompleted,
    InstallationNewPassphrase,
    InstallationPassphrase,
    ProfileCreateReply,
    ProfileCreateRequest,
    ProfileListReply,
    ProfileListRequest,
    RecoveryDisableReply,
    RecoveryDisableRequest,
    RecoveryEnrollReply,
    RecoveryEnrollRequest,
)

if TYPE_CHECKING:
    from cadrumo.application.user_profile.recovery_custody import ProfileRecoveryEnrollment

    from .installation_composition import InstallationActRegistry
    from .installation_door import InstallationActExchange

__all__ = ["register_profile_acts"]


@contextmanager
def _installation_scope(exchange: InstallationActExchange, *, changes_custody: bool = False) -> Generator[None]:
    """Bind this runtime's storage root and the profile persistence for the length of one act.

    An act runs on a connection thread that inherits no settings scope. The
    runtime's protected credential store is composed only for an act that
    changes custody, so a read never opens it.
    """
    with (
        exchange.served_settings(),
        composed_profile_persistence_ports(
            automation_secrets_store=exchange.secret_store() if changes_custody else None
        ),
    ):
        yield


def _result_reply[ReplyT: InstallationCompleted](
    exchange: InstallationActExchange, reply_type: type[ReplyT], result: BaseModel
) -> ReplyT:
    """Answer with the application's result, member for member and value for value.

    The reply declares the members the command's result has, so a result the
    command would print differently cannot be built into it. Nothing is hidden
    here: hiding an identifier is what a command does when it prints.
    """
    return exchange.reply(reply_type, **result.model_dump())


def _serve_profile_list(request: ProfileListRequest, exchange: InstallationActExchange) -> ProfileListReply:
    del request
    with _installation_scope(exchange):
        listing = profile_listing(root=exchange.storage_root)
        if not listing.inventory.recognized:
            # A reply has no channel for the advisory the command prints beside
            # an untrusted listing, and an empty listing alone would say the
            # profiles are gone. The observation is refused as what it is.
            raise ProfileCustodyRecordIntegrityError(listing.inventory.detail or str(listing.inventory.outcome))
        return _result_reply(exchange, ProfileListReply, listing.result())


def _serve_profile_create(request: ProfileCreateRequest, exchange: InstallationActExchange) -> ProfileCreateReply:
    """Create the profile under the passphrase the person chose and confirmed, without signing it in.

    The two copies are compared before anything is derived or written, as
    every frontend that asks for a new passphrase compares them.
    """
    from cadrumo.application.user_profile.registration import ProfileRegistrationError, create_profile_signed_out
    from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority

    with _installation_scope(exchange, changes_custody=True):
        secrets = exchange.receive_secret(InstallationNewPassphrase)
        try:
            passphrase = secrets.passphrase.get_secret_value()
            if not compare_digest(
                passphrase.encode("utf-8"), secrets.passphrase_confirmation.get_secret_value().encode("utf-8")
            ):
                raise ProfileRegistrationError(
                    translated_message="application.user_profile.errors.passphrase_confirmation_mismatch"
                )
            with bundled_indexed_authority().operation() as operation:
                exchange.changes_begin()
                outcome = create_profile_signed_out(
                    label=request.label,
                    passphrase=passphrase,
                    profile_create_context=operation.profile_create_context(),
                    profile_decode_context=operation.profile_decode_context(),
                )
        finally:
            del secrets
        # Creation selects the new profile: a frontend watching the selection asks again.
        exchange.selection_changed()
        return exchange.reply(
            ProfileCreateReply,
            profile_id=outcome.profile_id,
            label=outcome.label,
            setup_state=outcome.setup_state.value,
            selected=selected_profile_id(root=exchange.storage_root) == outcome.profile_id,
        )


def _serve_archive_inspect(request: ArchiveInspectRequest, exchange: InstallationActExchange) -> ArchiveInspectReply:
    from cadrumo.application.user_profile.capsule_archive import inspect_profile_capsule_archive

    with _installation_scope(exchange):
        return _result_reply(exchange, ArchiveInspectReply, inspect_profile_capsule_archive(Path(request.path)))


def _serve_archive_import_prepare(
    request: ArchiveImportPrepareRequest, exchange: InstallationActExchange
) -> ArchiveImportPrepareReply:
    """Read the source before any credential is asked for, as the command reads it before prompting."""
    from cadrumo.application.user_profile.capsule_archive import read_restorable_profile_capsule

    with _installation_scope(exchange):
        capsule = read_restorable_profile_capsule(Path(request.path))
    return exchange.reply(ArchiveImportPrepareReply, source_digest=capsule.digest)


def _serve_archive_import(request: ArchiveImportRequest, exchange: InstallationActExchange) -> ArchiveImportReply:
    """Republish the prepared source from the members read here, never from a second read.

    The source is read once. Its digest is compared with the prepared one
    before the passphrase is asked for, and the members that were digested are
    the ones published, so replacing the path afterwards changes nothing.
    """
    from cadrumo.application.user_profile.capsule_archive import read_restorable_profile_capsule
    from cadrumo.application.user_profile.capsule_restore import restore_profile_capsule_with_password
    from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority

    with _installation_scope(exchange, changes_custody=True):
        capsule = read_restorable_profile_capsule(Path(request.path))
        if not compare_digest(capsule.digest, request.source_digest):
            raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
        with exchange.reserve_profiles((capsule.source.password_envelope.profile_id,)):
            secrets = exchange.receive_secret(InstallationPassphrase)
            try:
                with bundled_indexed_authority().operation() as operation:
                    exchange.changes_begin()
                    outcome = restore_profile_capsule_with_password(
                        label=request.label,
                        capsule=capsule.source,
                        password=secrets.passphrase.get_secret_value(),
                        root=exchange.storage_root,
                        profile_decode_context=operation.profile_decode_context(),
                    )
            finally:
                del secrets
        return _result_reply(exchange, ArchiveImportReply, outcome)


def _read_back_code(read_back: bytes) -> str:
    """Return the code the client read back in the form the minted code is compared in.

    A person may type the code back with different spacing or case, which the
    command accepts, so the same canonical form is taken here. Bytes that are
    no recovery code at all are the possession mismatch a wrong code is, and
    that refusal is raised outside the decoder's scope so nothing that could
    retain the rejected bytes is chained to it.
    """
    from cadrumo.application.user_profile.recovery_custody import ProfileRecoveryError

    canonical: str | None = None
    with suppress(UnicodeError, StorageValidationError):
        canonical = canonical_recovery_code(read_back.decode("utf-8"))
    if canonical is None:
        raise ProfileRecoveryError(translated_message="application.user_profile.errors.recovery_possession_mismatch")
    return canonical


def _profile_to_enrol(
    request: RecoveryEnrollRequest | RecoveryDisableRequest, exchange: InstallationActExchange
) -> UUID:
    """Return the profile the request names, or the selected one when it names none."""
    if request.profile_id is not None:
        return request.profile_id
    selected = selected_profile_id(root=exchange.storage_root)
    if selected is None:
        raise NoActiveProfileError(translated_message="application.workflow.errors.no_active_profile_bucket")
    return UUID(selected)


def _serve_recovery_enroll(request: RecoveryEnrollRequest, exchange: InstallationActExchange) -> RecoveryEnrollReply:
    """Enrol through the custody service, taking the passphrase in and handing the code out and back.

    The profile is settled before the passphrase is asked for, as the command
    settles it before it reads its secret channel.
    """
    from cadrumo.application.user_profile.recovery_custody import enroll_profile_recovery

    def handover(enrollment: ProfileRecoveryEnrollment) -> str:
        read_back = exchange.deliver_secret(bytearray(enrollment.recovery_key.code, "utf-8"))
        code = _read_back_code(read_back.get_secret_value())
        # The service writes nothing before the handover and installs the wrapper once the code read back matches.
        exchange.changes_begin()
        return code

    with _installation_scope(exchange, changes_custody=True):
        profile_id = _profile_to_enrol(request, exchange)
        secrets = exchange.receive_secret(InstallationPassphrase)
        try:
            with exchange.reserve_profiles((profile_id,)):
                outcome = enroll_profile_recovery(
                    profile_id=profile_id,
                    current_passphrase=secrets.passphrase.get_secret_value(),
                    root=exchange.storage_root,
                    recovery_handover=handover,
                )
        finally:
            del secrets
        return _result_reply(exchange, RecoveryEnrollReply, outcome)


def _serve_recovery_disable(request: RecoveryDisableRequest, exchange: InstallationActExchange) -> RecoveryDisableReply:
    """Remove the code after the custody service proves the passphrase taken in.

    The profile is settled before the passphrase is asked for, as it is for
    enrolment. The passphrase is proved before anything is removed, so a
    refused proof changes nothing.
    """
    from cadrumo.application.user_profile.recovery_custody import revoke_profile_recovery

    with _installation_scope(exchange, changes_custody=True):
        profile_id = _profile_to_enrol(request, exchange)
        secrets = exchange.receive_secret(InstallationPassphrase)
        try:
            with exchange.reserve_profiles((profile_id,)):
                exchange.changes_begin()
                outcome = revoke_profile_recovery(
                    profile_id=profile_id,
                    current_passphrase=secrets.passphrase.get_secret_value(),
                    root=exchange.storage_root,
                )
        finally:
            del secrets
        return exchange.reply(RecoveryDisableReply, profile_id=outcome.profile_id, changed=outcome.changed)


def register_profile_acts(registry: InstallationActRegistry) -> None:
    """Serve the profile listing, creation, the archive acts and recovery enrolment and removal on ``registry``."""
    registry.register(ProfileListRequest, _serve_profile_list)
    registry.register(ProfileCreateRequest, _serve_profile_create)
    registry.register(ArchiveInspectRequest, _serve_archive_inspect)
    registry.register(ArchiveImportPrepareRequest, _serve_archive_import_prepare)
    registry.register(ArchiveImportRequest, _serve_archive_import)
    registry.register(RecoveryEnrollRequest, _serve_recovery_enroll)
    registry.register(RecoveryDisableRequest, _serve_recovery_disable)
