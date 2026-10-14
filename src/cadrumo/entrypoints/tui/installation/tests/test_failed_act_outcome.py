"""A failed act that may have changed records offers the read of its outcome, where its act has one."""

from __future__ import annotations

from uuid import uuid4

import pytest

from cadrumo_client.contracts.installation_requests import (
    INSTALLATION_ACT_CONTRACTS,
    InstallationAct,
    InstallationFailed,
)

from .....core.i18n.render import tr
from ..door import ActFailed
from ..rendering import ActPresentation, present_outcome

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _failed(act: InstallationAct, *, may_have_changed_records: bool) -> ActPresentation:
    reply = InstallationFailed(request_id=uuid4(), runtime_boot_id=uuid4(), connection_id=uuid4(), act=act)
    return present_outcome(
        ActFailed(reply, may_have_changed_records=may_have_changed_records), INSTALLATION_ACT_CONTRACTS[act]
    )


@pytest.mark.parametrize("act", [InstallationAct.RESET_START, InstallationAct.RESET_RESUME])
def test_a_failed_reset_whose_effect_is_unknown_offers_the_status_act_that_reads_it(act: InstallationAct) -> None:
    shown = _failed(act, may_have_changed_records=True)

    assert shown.tone == "error"
    assert shown.status == tr("tui.installation.status.failed_unknown", act=act.value)
    assert shown.outcome_read_by is InstallationAct.RESET_STATUS


def test_a_failed_act_with_no_reader_or_no_possible_change_offers_none() -> None:
    no_reader = _failed(InstallationAct.STORAGE_INIT, may_have_changed_records=True)
    unconfirmed = _failed(InstallationAct.RESET_START, may_have_changed_records=False)

    assert no_reader.status == tr("tui.installation.status.failed_unknown", act="storage_init")
    assert no_reader.outcome_read_by is None
    assert unconfirmed.status == tr("tui.installation.status.failed", act="reset_start")
    assert unconfirmed.outcome_read_by is None
