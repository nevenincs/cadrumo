"""The registration screen shows an operator words, not a message key.

``attempt_registration`` is the seam between the application layer, which
CLASSIFIES a refusal, and the screen, which DISPLAYS one. Its own docstring
says translating between the two is this seam's job. It returned
``str(refusal)`` instead, and ``str()`` on a translated error yields the message
KEY -- the constructor hands ``translated_message`` to ``Exception.__init__``
as a fallback rather than as prose.

So an operator who reused a profile name read
``application.user_profile.errors.profile_already_exists`` on the screen, where
the rendered message would have named the profile and told them to run
``aeat config login`` or ``config profile delete``. The words existed in all
four catalogues the whole time; nothing asked for them.

The existing screen tests assert a refusal is SHOWN and never what it says, so
a key satisfied them exactly as prose would. This asserts the content.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

from .....tests.secure_sql import isolated_profile_storage_root

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_LABEL = "Reused Profile Name"

#: A dotted lowercase path with no spaces -- what an untranslated key looks like.
_MESSAGE_KEY_SHAPE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*){2,}$")


def _passphrase() -> str:
    """The passphrase the isolated CLI backend registers profiles under."""
    from .....core.config import load_settings

    return load_settings().cadrumo_dev_test_database_password.get_secret_value()


def test_a_reused_name_is_refused_in_words_the_operator_can_act_on(tmp_path: Path) -> None:
    """DISCRIMINATING: the screen displays this string verbatim.

    A message key is not a refusal an operator can act on, and it reaches the
    screen unchanged because the screen deliberately treats the text as opaque.
    """
    from .._manager_frontend import attempt_registration

    with isolated_profile_storage_root(tmp_path=tmp_path):
        first = attempt_registration(label=_LABEL, passphrase=_passphrase(), output_language="en")
        assert first.outcome is not None, first.refusal

        second = attempt_registration(label=_LABEL, passphrase=_passphrase(), output_language="en")

    assert second.outcome is None
    assert second.refusal is not None
    assert not _MESSAGE_KEY_SHAPE.match(second.refusal), (
        f"the operator is shown an untranslated message key: {second.refusal!r}"
    )
    assert _LABEL in second.refusal, (
        "the rendered refusal must carry its context -- naming the profile is what "
        f"makes it actionable, but got {second.refusal!r}"
    )


def test_a_successful_registration_reports_no_refusal(tmp_path: Path) -> None:
    """ANTI-TAUTOLOGY: the refusal channel must stay empty when nothing refused.

    Without this, a seam that always produced some readable string would
    satisfy the assertions above while reporting a failure for every success.
    """
    from .._manager_frontend import attempt_registration

    with isolated_profile_storage_root(tmp_path=tmp_path):
        attempt = attempt_registration(
            label="Fresh Profile Name",
            passphrase=_passphrase(),
            output_language="en",
        )

    assert attempt.outcome is not None
    assert attempt.refusal is None


def test_the_key_shape_recogniser_matches_a_key_and_not_a_sentence() -> None:
    """ANTI-TAUTOLOGY: the recogniser must be able to say yes.

    If it matched nothing, the assertion above would pass against a screen
    showing keys, which is the state this test exists to prevent.
    """
    assert _MESSAGE_KEY_SHAPE.match("application.user_profile.errors.profile_already_exists")
    assert not _MESSAGE_KEY_SHAPE.match("Profile 'Reused Profile Name' already exists; run aeat config login NAME")
