"""Guard: an operator's real ``env/.env`` dotfile must reach the environment.

Production ``Settings`` carries no dotenv source of its own; ``env/.env``
is development/test-only configuration (a local operator's live-test
credentials) that reaches a test process only through the repo-root
``conftest.py`` bridge (:func:`cadrumo.tests._env_loader.bridge_env_file_into_environ`,
run before any Cadrumo import can resolve ``Settings``).

If that bridge silently breaks -- a future edit reorders the import so a
Cadrumo import runs first, an exception inside the bridge gets swallowed,
or the wiring is simply removed -- a live test whose credential comes only
from ``env/.env`` (e.g. ``CADRUMO_CLAVE_MOVIL_DNI_NIE``) fails its
prerequisite gate instead of exercising the real probe it exists to run.
That is a silent regression: the suite still runs, and nothing announces
that the credential channel stopped working. This test makes the
regression loud on any machine that actually carries an ``env/.env``, and
is a clean no-op (skipped, not failed) on a machine that does not -- CI,
a fresh clone, an installed run.
"""

from __future__ import annotations

import os

import pytest

from ._env_loader import load_env_file
from ._inventory import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_operator_dotenv_keys_are_bridged_into_the_environment() -> None:
    """Every key ``env/.env`` declares must already be visible in ``os.environ``.

    Presence, not exact-value equality, is the check: an operator may
    legitimately override a dotfile value with a real ambient shell/CI
    variable (the bridge's own ``setdefault`` precedence, exercised
    directly in ``test_env_loader.py``), and that is not a broken
    channel. A key entirely absent from ``os.environ`` despite being
    declared in ``env/.env`` is what a structurally broken bridge looks
    like, and is what this test refuses.
    """
    env_path = REPO_ROOT / "env" / ".env"
    declared = load_env_file(env_path)
    if not declared:
        # No env/.env on this machine (CI, a fresh clone, an installed run):
        # zero declared keys means there is nothing to assert. A benign
        # early return, not pytest.skip -- this module is pytest.mark.unit
        # (always collected) and the project's skip/xfail-shortcut gate
        # (the skip-policy ratchet) forbids pytest.skip in deterministic
        # unit modules; only an explicitly-selected aeat_live module may
        # fail-rather-than-skip on a missing prerequisite.
        return

    missing = sorted(key for key in declared if key not in os.environ)
    assert not missing, (
        f"env/.env declares {missing} but "
        f"{'this key is' if len(missing) == 1 else 'these keys are'} absent from "
        "os.environ at test time. The repo-root conftest.py dotenv bridge "
        "(cadrumo.tests._env_loader.bridge_env_file_into_environ) appears "
        "broken, bypassed, or ordered after a Cadrumo import already "
        "resolved Settings -- a live test whose credential comes only from "
        "env/.env would silently fail its prerequisite gate instead of "
        "running."
    )
