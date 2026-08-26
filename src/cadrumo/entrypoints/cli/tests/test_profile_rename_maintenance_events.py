"""CLI conformance pin for the retired ``config profile rename`` verb.

``rename`` is not registered on the live ``aeat config profile`` surface;
the maintenance audit contract it exercised (the two-event
``PROFILE_RENAMED`` + ``BUCKET_RENAMED`` co-emission) died with the verb.
This module pins the retirement: the verb must keep resolving as an
unknown command, and a profile's label must survive the attempt
unchanged.
"""

from __future__ import annotations

import pytest

from cadrumo.application.workflow.profile_bucket_scan import read_profile_bucket

from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage

__all__ = ["isolated_profile_storage"]
from ._profile_lifecycle_support import create_profile_via_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_cli_rename_verb_is_not_registered() -> None:
    """The retired ``rename`` verb stays unregistered: click refuses it.

    The old maintenance-event tests invoked ``config profile rename`` and
    asserted the two-event audit trail; the verb no longer resolves, so
    the boundary worth pinning is the negative conformance itself.
    """

    create_profile_via_cli("alpha")

    result = invoke_cached_cli(("config", "profile", "rename", "alpha", "beta"))
    assert result.exit_code != 0, result.output
    assert "No such command 'rename'" in result.output

    pointer = read_profile_bucket("alpha")
    assert pointer is not None, "the profile label must be unchanged after the refusal"
    assert read_profile_bucket("beta") is None
