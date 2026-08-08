"""What the manager's passphrase action actually rotates.

The operator experience being proved is narrow and load-bearing: pressing
the action and committing a new passphrase must leave the secret store
readable ONLY under the new one, a mismatched confirmation must leave it
untouched, and a wrong current answer must be named rather than folded
into a generic failure. Driven through the shipped
:func:`~cadrumo.entrypoints.cli._config._manager_actions._run_passphrase_change`
with a presenter answering its page — the same seam the running manager
binds through ``presenting_forms_through`` — against the real
:func:`~cadrumo.application.user_profile.change_passphrase` door. No mock,
stub, or reimplementation of what the action should do.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from .....adapters.inbound.tui import presenting_forms_through
from .....adapters.persistence.storage import MasterKeyPassphraseMismatchError
from .....application.user_profile import change_passphrase, register_profile_with_credentials
from .....core.i18n import tr
from .....tests.secure_sql import isolated_profile_storage_root
from .._manager_actions import (
    _PASSPHRASE_CONFIRM_KEY,
    _PASSPHRASE_CURRENT_KEY,
    _PASSPHRASE_NEW_KEY,
    _run_passphrase_change,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .....adapters.inbound.tui import FormPage

_LABEL = "Passphrase Action Subject"
_ORIGINAL_PASSPHRASE = "passphrase-action-original-secret"  # noqa: S105 - synthetic test fixture
_ROTATED_PASSPHRASE = "passphrase-action-rotated-secret"  # noqa: S105 - synthetic test fixture


def _answering(values: Mapping[str, str]):
    """A presenter that commits ``values`` without ever opening a screen."""

    def _present(page: FormPage, _rebuild: object) -> Mapping[str, str]:
        return {field.key: values[field.key] for field in page.fields}

    return _present


def test_a_committed_change_leaves_the_store_open_under_the_new_passphrase(tmp_path) -> None:
    """The rotation this action performs must actually stick.

    A no-op rotation back onto itself, using the NEW passphrase as the
    current answer, only succeeds if the action actually rewrapped the
    store under it.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(label=_LABEL, passphrase=_ORIGINAL_PASSPHRASE)

        answers = {
            _PASSPHRASE_CURRENT_KEY: _ORIGINAL_PASSPHRASE,
            _PASSPHRASE_NEW_KEY: _ROTATED_PASSPHRASE,
            _PASSPHRASE_CONFIRM_KEY: _ROTATED_PASSPHRASE,
        }
        with presenting_forms_through(_answering(answers)):
            outcome = _run_passphrase_change()

        assert outcome.message == tr("flows.manager.action.passphrase_done")

        change_passphrase(current_passphrase=_ROTATED_PASSPHRASE, new_passphrase=_ROTATED_PASSPHRASE)


def test_a_committed_change_leaves_the_store_closed_under_the_old_passphrase(tmp_path) -> None:
    """The superseded passphrase must stop unwrapping the store.

    Kept in its own profile, and asserting nothing further afterwards: the
    failed-attempt backoff this door shares with login (see
    ``change_passphrase``'s own docstring) would throttle a second call in
    the same run, which is a property of the shared budget, not of this
    action, and is out of scope here.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(label=_LABEL, passphrase=_ORIGINAL_PASSPHRASE)

        answers = {
            _PASSPHRASE_CURRENT_KEY: _ORIGINAL_PASSPHRASE,
            _PASSPHRASE_NEW_KEY: _ROTATED_PASSPHRASE,
            _PASSPHRASE_CONFIRM_KEY: _ROTATED_PASSPHRASE,
        }
        with presenting_forms_through(_answering(answers)):
            outcome = _run_passphrase_change()
        assert outcome.message == tr("flows.manager.action.passphrase_done")

        with pytest.raises(MasterKeyPassphraseMismatchError):
            change_passphrase(current_passphrase=_ORIGINAL_PASSPHRASE, new_passphrase="whatever-comes-next")


def test_a_mismatched_confirmation_is_refused_and_the_store_is_untouched(tmp_path) -> None:
    """A typo in the retype must not rotate anything.

    The refusal is judged after collection rather than by a per-field
    validator, so this pins that the judgement actually runs before any
    write — the original passphrase must still open the store afterwards.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(label=_LABEL, passphrase=_ORIGINAL_PASSPHRASE)

        answers = {
            _PASSPHRASE_CURRENT_KEY: _ORIGINAL_PASSPHRASE,
            _PASSPHRASE_NEW_KEY: _ROTATED_PASSPHRASE,
            _PASSPHRASE_CONFIRM_KEY: "typo-" + _ROTATED_PASSPHRASE,
        }
        with presenting_forms_through(_answering(answers)):
            outcome = _run_passphrase_change()

        assert outcome.message == tr("flows.manager.action.passphrase_mismatch")

        # Still opens under the untouched original passphrase.
        change_passphrase(current_passphrase=_ORIGINAL_PASSPHRASE, new_passphrase=_ORIGINAL_PASSPHRASE)


def test_a_wrong_current_passphrase_is_named_rather_than_folded_into_a_generic_failure(tmp_path) -> None:
    """A typo'd current passphrase is the one failure this door can tell apart.

    ``change_passphrase`` unwraps the stored master key under the typed
    current value before it does anything else, so a mismatch there is the
    operator's own typo rather than a defect, and is reported by its own
    message rather than the door's raw exception text.

    Asserts nothing beyond the message: a further call in the same run
    would draw on the failed-attempt backoff this door shares with login,
    which is that budget's property rather than this action's.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(label=_LABEL, passphrase=_ORIGINAL_PASSPHRASE)

        answers = {
            _PASSPHRASE_CURRENT_KEY: "not-the-passphrase",
            _PASSPHRASE_NEW_KEY: _ROTATED_PASSPHRASE,
            _PASSPHRASE_CONFIRM_KEY: _ROTATED_PASSPHRASE,
        }
        with presenting_forms_through(_answering(answers)):
            outcome = _run_passphrase_change()

        assert outcome.message == tr("flows.manager.action.passphrase_wrong_current")
