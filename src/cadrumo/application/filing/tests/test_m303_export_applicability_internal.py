"""M303 export applicability has no caller-authored override boundary."""

from __future__ import annotations

from inspect import signature

import pytest

from ...modelo import ModeloExportCommand
from .. import export_draft

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_m303_export_applicability_is_internal_to_revision_backed_filing_facts() -> None:
    assert "m303_applicability" not in ModeloExportCommand.model_fields
    assert "m303_applicability" not in signature(export_draft).parameters
