"""A real profile the harness owns, created once and reused.

Three of the seven surfaces — login, manager, status — render nothing
meaningful without a real profile behind them, and registration needs a
storage root it is allowed to write into. So the harness keeps its own
root and creates a real profile in it through the real registration door:
real Argon2id derivation, real AEAD, real manifest. Nothing here is a
stand-in, because a stand-in would make every reading about the stand-in.

The root is the harness's own, never the operator's. Sensitive financial
data stays where it always does — inside the encrypted store this root
provides — and the root is gitignored, so nothing it holds is committable.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from cadrumo.application.user_profile import logout_active_profile
from cadrumo.entrypoints.cli._config._manager_frontend import attempt_registration
from cadrumo.tests.secure_sql import isolated_profile_storage_root

WORKSPACE_ENV_VAR = "CADRUMO_TUI_WORKSPACE"

_STATE_ROOT = Path(__file__).resolve().parent / ".state"


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
"""Where this caller keeps its root, session and screenshots. Gitignored."""

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
def harness_storage(*, fresh: bool = False) -> Iterator[Path]:
    """Enter the harness's own storage root for the duration of a block.

    Reuses the project's canonical isolation helper rather than
    re-deriving the override set: the helper simply takes a path, and
    nothing about it requires that path be throwaway. Pointing it at a
    persistent directory is the whole of "reuse my profile".
    """
    root = workspace() / ("fresh" if fresh else "profile")
    root.mkdir(parents=True, exist_ok=True)
    with isolated_profile_storage_root(tmp_path=root) as storage_root:
        yield storage_root


def ensure_profile() -> str:
    """Return the harness profile's bucket id, creating it if absent.

    Registration leaves the new profile unlocked; the session is closed
    again before returning so the login surface meets the locked machine
    it exists for. Caller must already be inside :func:`harness_storage`.
    """
    from cadrumo.application.workflow import list_profile_buckets

    existing = list_profile_buckets()
    if existing:
        return next(iter(existing))

    attempt = attempt_registration(PROFILE_LABEL, passphrase(), "es")
    if attempt.outcome is None:
        message = f"the harness profile could not be created: {attempt.refusal}"
        raise RuntimeError(message)
    logout_active_profile()
    return attempt.outcome.bucket_id


def ensure_session() -> str:
    """Unlock the harness profile and return its bucket id.

    The manager surface reads through the active-profile pointer, so an
    existing-but-locked profile is not enough for it. Unlocking goes
    through the real login door — real derivation, real unwrap — because
    a surface rendered over a stand-in session would be a reading about
    the stand-in.
    """
    from cadrumo.application.user_profile import login_profile

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
    "workspace",
]
