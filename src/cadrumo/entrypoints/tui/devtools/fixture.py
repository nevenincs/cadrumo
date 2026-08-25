"""A real profile the canonical TUI devtool owns, created once and reused.

Three of the seven surfaces — login, manager, status — render nothing
meaningful without a real profile behind them, and registration needs a
storage root it is allowed to write into. So the harness keeps its own
root and creates a real profile in it through the real registration door:
real Argon2id derivation, real AEAD, real manifest. Nothing here is a
stand-in, because a stand-in would make every reading about the stand-in.

The root is the harness's own, never the operator's. Sensitive financial
data stays where it always does — inside the encrypted store this root
provides — outside the source tree under the configured local-storage root.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from ....application.user_profile.login_session import logout_active_profile
from ....core.config import load_settings
from ....core.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH

WORKSPACE_ENV_VAR = "CADRUMO_TUI_WORKSPACE"

_STATE_ROOT = load_settings().cadrumo_local_storage_root / "devtools" / "tui"


def workspace() -> Path:
    """This caller's private corner of the harness state.

    Concurrent reviewers each need their own session journal AND their own
    storage root: one shared journal means every ``open`` clobbers someone
    else's walk, and one shared root means two agents contend on the same
    SQLite bucket and active-profile pointer. Set
    ``CADRUMO_TUI_WORKSPACE`` to a name per reviewer and neither can
    happen.
    """
    name = os.environ.get(WORKSPACE_ENV_VAR, "").strip() or "default"
    return _STATE_ROOT / name


STATE_DIR = workspace()
"""Where this caller keeps its root, session and screenshots outside source."""

PASSPHRASE_ENV_VAR = "CADRUMO_TUI_HARNESS_PASSPHRASE"  # noqa: S105 - the variable NAME, not a secret

_DEFAULT_PASSPHRASE = "tui-harness-operator-secret"  # noqa: S105 - synthetic harness fixture

PROFILE_LABEL = "Harness Subject"


def passphrase() -> str:
    """The harness profile's passphrase.

    One passphrase for the whole root, because the master key is
    root-wide: profiles in one root are unwrapped by one passphrase, so a
    per-profile secret is not a state this application can be in.
    """
    return os.environ.get(PASSPHRASE_ENV_VAR) or _DEFAULT_PASSPHRASE


@contextmanager
def harness_storage(*, fresh: bool = False, namespace: str = "profile") -> Iterator[Path]:
    """Enter the harness's own storage root for the duration of a block.

    The devtool owns this isolated configuration seam rather than importing a
    test helper. Its persistent root is still caller-private and encrypted;
    the context simply makes that root the active application configuration.
    """
    if not namespace.strip():
        raise ValueError("devtool storage namespace must not be blank")
    root = workspace() / ("fresh" if fresh else namespace)
    root.mkdir(parents=True, exist_ok=True)
    from ..launcher import profile_storage_scope

    with profile_storage_scope(root) as storage_root:
        yield storage_root


def ensure_profile() -> str:
    """Return the harness profile's bucket id, creating it if absent.

    Registration leaves the new profile unlocked; the session is closed
    again before returning so the login surface meets the locked machine
    it exists for. Caller must already be inside :func:`harness_storage`.
    """
    from cadrumo.application.workflow.profile_bucket_scan import list_profile_buckets

    existing = list_profile_buckets()
    if existing:
        return next(iter(existing))

    from ....application.user_profile.registration import register_profile_with_credentials
    from ....domain.user_profile.values import UserProfileFact

    outcome = register_profile_with_credentials(
        label=PROFILE_LABEL,
        passphrase=passphrase(),
        facts=(UserProfileFact(path=PROFILE_OUTPUT_LANGUAGE_PATH, value="es"),),
        recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
    )
    logout_active_profile()
    return outcome.bucket_id


def registration_attempt(
    label: str,
    candidate_passphrase: str,
    output_language: str,
    recovery_handover,
):
    """Adapt public profile registration into the TUI screen's result contract."""
    from ....application.user_profile.registration import ProfileRegistrationError, register_profile_with_credentials
    from ....domain.user_profile.values import UserProfileFact
    from ....entrypoints.tui.secret.app import (
        RecoveryHandoverCancelledError,
        RegistrationAttempt,
        RegistrationRefusal,
    )

    try:
        outcome = register_profile_with_credentials(
            label=label,
            passphrase=candidate_passphrase,
            facts=(UserProfileFact(path=PROFILE_OUTPUT_LANGUAGE_PATH, value=output_language),),
            recovery_handover=recovery_handover,
        )
    except RecoveryHandoverCancelledError:
        return RegistrationAttempt(
            expected_refusal=RegistrationRefusal(
                message_key="cli.config.profile.create_recovery_verification_cancelled",
            )
        )
    except ProfileRegistrationError as refusal:
        if refusal.translated_message is None:
            raise
        return RegistrationAttempt(
            expected_refusal=RegistrationRefusal(
                message_key=refusal.translated_message,
                context=tuple((refusal.context or {}).items()),
            )
        )
    return RegistrationAttempt(outcome=outcome)


def ensure_session() -> str:
    """Unlock the harness profile and return its bucket id.

    The manager surface reads through the active-profile pointer, so an
    existing-but-locked profile is not enough for it. Unlocking goes
    through the real login door — real derivation, real unwrap — because
    a surface rendered over a stand-in session would be a reading about
    the stand-in.
    """
    from ....application.user_profile.login_session import login_profile

    bucket_id = ensure_profile()
    login_profile(name=bucket_id, passphrase_callback=lambda *_args, **_kwargs: passphrase())
    return bucket_id


__all__ = [
    "PASSPHRASE_ENV_VAR",
    "PROFILE_LABEL",
    "STATE_DIR",
    "WORKSPACE_ENV_VAR",
    "ensure_profile",
    "ensure_session",
    "harness_storage",
    "passphrase",
    "registration_attempt",
    "workspace",
]
