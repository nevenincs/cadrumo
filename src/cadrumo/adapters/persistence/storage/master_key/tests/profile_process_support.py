"""Fresh-process credential and runtime receipt probes for registration tests."""

from __future__ import annotations

from contextlib import ExitStack
from contextvars import Token
from datetime import datetime
from multiprocessing import get_context
from multiprocessing.queues import Queue
from pathlib import Path
from typing import TypedDict
from uuid import UUID

from cadrumo.adapters.persistence.storage.custody.capsule import load_committed_profile_password_material
from cadrumo.adapters.persistence.storage.custody.tests.receipt_runtime_resume import resume_receipt_as_runtime
from cadrumo.adapters.persistence.storage.custody.tests.receipt_sign_in import persist_signed_in_receipt
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.adapters.persistence.storage.profile_persistence_composition import composed_profile_persistence_ports
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    profile_authority_contexts as _profile_contexts_for_test,
)
from cadrumo.application.user_profile.login_session import authenticate_profile_for_invocation
from cadrumo.application.user_profile.profile_record_repository import close_active_profile_record_session
from cadrumo.core import config as config_module
from cadrumo.core.config import Settings
from cadrumo.core.time.clock import now as _now
from cadrumo.tests.process_results import receive_process_result


class _ChildLoginResult(TypedDict):
    bucket_id: str
    closed_previous: str | None
    already_authenticated: bool


class _ResumeProbeResult(TypedDict):
    resumed: bool
    dek_length: int
    refusal: str | None


def _close_live_login() -> None:

    close_active_profile_record_session()
    close_active_bucket_session()


def _child_settings(storage_root: Path) -> tuple[Settings, Token[Settings | None], ExitStack]:
    # Calibration measurement is off for the same reason the session default in
    # `cadrumo/conftest.py` turns it off, and it has to be said again HERE:
    # these children are spawned, so no in-process override reaches them, and
    # `_env_file=None` means no environment default would either. The child
    # rebuilds `Settings` from scratch and would otherwise re-measure the KDF
    # grid -- 16.1s of supervised child processes -- once per spawned
    # registration, for the answer the parent already has.
    #
    # Declining adopts the fixed fallback `calibrate_profile_kdf` also returns
    # on deadline, the floor a measured point never falls below, so the custody
    # envelope these children write is wrapped at a strength production accepts.
    settings = Settings(
        _env_file=None,
        cadrumo_local_storage_root=storage_root,
        cadrumo_active_profile=None,
        cadrumo_profile_kdf_measure_calibration=False,
    )
    composition = ExitStack()
    composition.enter_context(composed_profile_persistence_ports())
    return settings, config_module.settings_override.set(settings), composition


def _close_child_login(
    token: Token[Settings | None],
    composition: ExitStack,
) -> None:
    try:
        _close_live_login()
        config_module.settings_override.reset(token)
    finally:
        composition.__exit__(None, None, None)


def _login_in_separate_process_child(
    storage_root: Path,
    profile: str,
    password: str,
    now: datetime | None,
    persist_receipt: bool,
    result_queue: Queue[_ChildLoginResult],
) -> None:
    """Authenticate one fixture profile with a real password in a fresh process.

    Explicit local proof mints no receipt, so ``persist_receipt`` publishes one
    afterwards through the runtime worker's own step, as a persisted sign-in does.
    """
    _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()
    settings, token, composition = _child_settings(storage_root)
    _ = settings
    try:
        outcome = authenticate_profile_for_invocation(
            name=profile,
            now=now,
            passphrase_callback=lambda: password,
            profile_decode_context=_profile_decode_context_for_test,
        )
        if persist_receipt:
            persist_signed_in_receipt(
                storage_root,
                UUID(outcome.bucket_id),
                password,
                profile_decode_context=_profile_decode_context_for_test,
            )
        result_queue.put(
            {
                "bucket_id": outcome.bucket_id,
                "closed_previous": outcome.closed_previous_bucket_id,
                "already_authenticated": outcome.already_authenticated,
            }
        )
    finally:
        _close_child_login(token, composition)


def _resume_probe_child(
    storage_root: Path,
    profile: str,
    result_queue: Queue[_ResumeProbeResult],
) -> None:
    """Recover one profile's session material with no passphrase, in its own process."""
    settings, token, composition = _child_settings(storage_root)
    _ = settings
    try:
        material = load_committed_profile_password_material(UUID(profile), root=storage_root)
        outcome, dek = resume_receipt_as_runtime(
            storage_root=storage_root,
            profile_id=UUID(profile),
            custody_generation=material.envelope.password_generation,
            dek_epoch=material.envelope.dek_epoch,
            now=_now(),
        )
        result_queue.put(
            {
                "resumed": outcome.resumed,
                "dek_length": 0 if dek is None else len(dek),
                "refusal": None if outcome.refusal is None else outcome.refusal.value,
            }
        )
    finally:
        _close_child_login(token, composition)


def _login_in_separate_process(
    storage_root: Path,
    profile: str,
    password: str,
    *,
    now: datetime | None = None,
    persist_receipt: bool = True,
) -> _ChildLoginResult:
    """Run one login in its own interpreter, which is what every ``aeat`` call is."""
    context = get_context("spawn")
    result_queue: Queue[_ChildLoginResult] = Queue(ctx=context)
    child = context.Process(
        target=_login_in_separate_process_child,
        args=(storage_root, profile, password, now, persist_receipt, result_queue),
    )
    child.start()
    try:
        result = receive_process_result(result_queue, owners=(child,))
        child.join(timeout=None)
        assert child.exitcode == 0
        return result
    finally:
        if child.is_alive():
            child.terminate()
        if child.pid is not None:
            child.join(timeout=30)


def _probe_resumable_session(storage_root: Path, profile: str) -> _ResumeProbeResult:
    """Measure recovered key material from a process that never held the session."""
    context = get_context("spawn")
    result_queue: Queue[_ResumeProbeResult] = Queue(ctx=context)
    child = context.Process(target=_resume_probe_child, args=(storage_root, profile, result_queue))
    child.start()
    try:
        result = receive_process_result(result_queue, owners=(child,))
        child.join(timeout=None)
        assert child.exitcode == 0
        return result
    finally:
        if child.is_alive():
            child.terminate()
        if child.pid is not None:
            child.join(timeout=30)
