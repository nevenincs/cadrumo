"""Runtime-owned supplied receipt admission over public profile custody ports."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import ExitStack, contextmanager
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from cadrumo.application.user_profile.capsule_record import ProfileRecordSession
from cadrumo.application.user_profile.custody_ports import (
    load_profile_custody_password_material,
    verify_profile_custody_dek_against_sentinel,
)
from cadrumo.application.user_profile.login_session import (
    ProfileLoginCandidate,
    ProfileLoginOutcome,
    ProfileReceiptRefusedError,
    resolve_login_target,
)
from cadrumo.application.user_profile.login_session_port import profile_login_session_port
from cadrumo.core.config import load_settings
from cadrumo.core.errors.hierarchy import CadrumoError
from cadrumo.core.paths import effective_storage_root
from cadrumo.core.profile_session import ProfileSessionRefusalReason
from cadrumo.core.time.clock import now as current_time

if TYPE_CHECKING:
    from cadrumo.application.user_profile.access_contracts import ProfileAccessBinding
    from cadrumo.domain.calculations.registry.authority_artifact import ProfileDecodeContext


@contextmanager
def resume_profile_candidate(
    *,
    bucket_id: UUID,
    receipt_key: bytearray,
    profile_decode_context: ProfileDecodeContext,
    login_id: str,
    sign_in_binding: ProfileAccessBinding,
    now: datetime | None = None,
) -> Generator[ProfileLoginCandidate]:
    """Prove a supplied human receipt without binding or selecting a profile.

    The runtime composes this with ``login_id``, the originating OS login of
    the connection presenting the proof, and ``sign_in_binding``, its worker's
    custody binding. The receipt must name that login and the current sign-in
    generation; a receipt refused for its binding or its own metadata is
    deleted by the reader, never by the presenting frontend, except that a
    login mismatch deletes only when the supplied proof unwraps the receipt.
    A valid proof inherits the receipt's original deadlines. It never reads
    the OS keyring for a key, renews human life, or changes the active
    frontend context.
    """
    instant = current_time() if now is None else now
    storage_root = effective_storage_root()
    material = load_profile_custody_password_material(bucket_id, root=storage_root)
    outcome, dek = profile_login_session_port().resume_acceleration_receipt_with_key(
        storage_root=storage_root,
        profile_id=bucket_id,
        custody_generation=material.envelope.password_generation,
        dek_epoch=material.envelope.dek_epoch,
        now=instant,
        receipt_key=receipt_key,
        login_id=login_id,
        sign_in_binding=sign_in_binding,
    )
    if not outcome.resumed or outcome.record is None or dek is None:
        if dek is not None:
            profile_login_session_port().zeroise_owned_buffer(dek)
        raise ProfileReceiptRefusedError(outcome.refusal or ProfileSessionRefusalReason.ABSENT, binding=outcome.binding)
    record = outcome.record
    with ExitStack() as cleanup:
        cleanup.callback(profile_login_session_port().zeroise_owned_buffer, dek)
        try:
            verify_profile_custody_dek_against_sentinel(
                dek=bytes(dek),
                profile_id=bucket_id,
                dek_epoch=material.envelope.dek_epoch,
                sentinel=material.sentinel,
            )
        except CadrumoError as error:
            raise ProfileReceiptRefusedError(ProfileSessionRefusalReason.TAMPERED) from error
        idle_minutes = load_settings().cadrumo_bucket_default_idle_lock_minutes
        session = profile_login_session_port().open_resumed_session(
            bucket_id=str(bucket_id),
            dek=bytes(dek),
            idle_minutes=idle_minutes,
            opened_at=record.issued_at,
            idle_deadline=record.idle_deadline,
            absolute_deadline=record.absolute_deadline,
            storage_root=storage_root,
        )
        cleanup.callback(session.close)
        # Match password candidates' local record authority construction;
        # actual record reads retain their own later authenticated boundary.
        record_session = ProfileRecordSession.from_envelope(
            envelope=material.envelope,
            dek=bytes(dek),
            profile_decode_context=profile_decode_context,
        )
        record_session.close()
        target = resolve_login_target(str(bucket_id))
        yield ProfileLoginCandidate(
            outcome=ProfileLoginOutcome(
                bucket_id=str(bucket_id),
                label=target.label,
                authenticated_at=record.issued_at,
                idle_deadline=record.idle_deadline,
                absolute_deadline=record.absolute_deadline,
                session_persisted=True,
                already_authenticated=True,
                closed_previous_bucket_id=None,
            ),
            session=session,
        )
