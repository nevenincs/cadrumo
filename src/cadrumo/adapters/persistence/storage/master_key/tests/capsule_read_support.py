"""Hold one worker-custody capsule read open while other threads use custody.

The real binding validator still answers every read; this only gates when the
first read finishes, and optionally fails it, so tests can observe what custody
and its callers do meanwhile.
"""

from __future__ import annotations

from pathlib import Path
from threading import Event, Lock
from uuid import UUID

from cadrumo.application.user_profile.access_contracts import ProfileAccessBinding
from cadrumo.core.storage_taxonomy import StorageCategory
from cadrumo_client.contracts.automation_codes import AutomationCustodyCode, AutomationCustodyError

from ...custody.paths import profile_custody_path
from .. import profile_worker_custody

HELD_READ_WAIT_SECONDS = 5
"""How long any wait around a held read lasts before the test fails instead of hanging."""


class HeldCapsuleRead:
    """Hold the first capsule read until released, then let it pass or fail; later reads run unheld.

    Install it over ``profile_worker_custody.validate_automation_profile_binding``.
    """

    def __init__(self, *, fail_held: bool) -> None:
        """Wrap the real validator; ``fail_held`` makes the held read refuse once released."""
        self.entered, self.release = Event(), Event()
        self._fail_held = fail_held
        self._validate = profile_worker_custody.validate_automation_profile_binding
        self._calls = 0
        self._guard = Lock()

    def __call__(self, binding: ProfileAccessBinding, *, root: Path, dek: bytes | None = None) -> None:
        """Validate as custody does, holding and possibly failing only the first read."""
        with self._guard:
            self._calls += 1
            held = self._calls == 1
        if held:
            self.entered.set()
            assert self.release.wait(HELD_READ_WAIT_SECONDS), "the held capsule read was never released"
            if self._fail_held:
                raise AutomationCustodyError(AutomationCustodyCode.INVALID)
        self._validate(binding, root=root, dek=dek)


def republish_capsule_commit(profile_id: UUID, *, root: Path) -> None:
    """Replace the commit record with its own bytes, so the next check reads the capsule rather than a held proof."""
    commit = profile_custody_path(profile_id, StorageCategory.PROFILE_CAPSULE_COMMIT, root=root)
    replaced = commit.with_name(commit.name + ".replaced")
    replaced.write_bytes(commit.read_bytes())
    replaced.replace(commit)
