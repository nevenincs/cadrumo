"""Canonical ownership and exact seed vocabulary of operator action classes."""

from __future__ import annotations

from pathlib import Path

import pytest

from ... import core
from ...tests import modules_declaring_class
from .. import operator_action_enums as owner
from ..operator_action_enums import OperatorActionAxis

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_operator_action_axis_is_the_single_public_core_identity() -> None:
    assert core.OperatorActionAxis is owner.OperatorActionAxis
    assert tuple(OperatorActionAxis.__members__) == (
        "SUPPLY_MANUAL_INPUT",
        "IMPORT_LEDGER_DATA",
        "SET_PROFILE_FACT",
        "FILE_PRIOR_PERIOD",
        "CAPTURE_EXTERNAL_EVIDENCE",
        "RESOLVE_VALUE_DIVERGENCE",
        "RE_VERIFY",
        "RESOLVE_REVISION_MISMATCH",
        "CONFIRM_GROUP_MEMBERSHIP",
        "RESOLVE_IDENTITY",
        "COMPLETE_DOCUMENT_EVIDENCE",
        "REVIEW_ADVISORY",
    )
    assert tuple(member.value for member in OperatorActionAxis) == (
        "supply_manual_input",
        "import_ledger_data",
        "set_profile_fact",
        "file_prior_period",
        "capture_external_evidence",
        "resolve_value_divergence",
        "re_verify",
        "resolve_revision_mismatch",
        "confirm_group_membership",
        "resolve_identity",
        "complete_document_evidence",
        "review_advisory",
    )

    declarations = list(modules_declaring_class("OperatorActionAxis"))
    assert declarations == [Path(owner.__file__).resolve()]
