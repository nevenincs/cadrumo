"""Roundtrip: InitializeWorkspaceCommand output_language field type migration.

Every output_language field referencing the language axis must consume OutputLanguage
 enum per the dual-keying contract pattern (output-language typed-constant
migration). This test pins the roundtrip contract: InitializeWorkspaceCommand must accept
OutputLanguage members and None, validate enum membership, and reject invalid strings.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ....core.external_constants import OutputLanguage
from ....domain.deadlines import IVARegime
from .._contracts import InitializeWorkspaceCommand

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_initialize_workspace_command_output_language_accepts_enum_members() -> None:
    """InitializeWorkspaceCommand.output_language accepts OutputLanguage enum members."""
    for lang in OutputLanguage:
        cmd = InitializeWorkspaceCommand(
            tax_id="12345678Z",
            activity="design",
            iva_regime=IVARegime.GENERAL,
            output_language=lang,
        )
        assert cmd.output_language == lang


def test_initialize_workspace_command_output_language_accepts_none() -> None:
    """InitializeWorkspaceCommand.output_language accepts None (default)."""
    cmd = InitializeWorkspaceCommand(
        tax_id="12345678Z",
        activity="design",
        iva_regime=IVARegime.GENERAL,
        output_language=None,
    )
    assert cmd.output_language is None


def test_initialize_workspace_command_output_language_defaults_to_none() -> None:
    """InitializeWorkspaceCommand.output_language defaults to None when omitted."""
    cmd = InitializeWorkspaceCommand(
        tax_id="12345678Z",
        activity="design",
        iva_regime=IVARegime.GENERAL,
    )
    assert cmd.output_language is None


def test_initialize_workspace_command_output_language_rejects_invalid_string() -> None:
    """InitializeWorkspaceCommand.output_language rejects bare strings not in OutputLanguage."""
    with pytest.raises(ValidationError) as exc_info:
        InitializeWorkspaceCommand(
            tax_id="12345678Z",
            activity="design",
            iva_regime=IVARegime.GENERAL,
            output_language="invalid_language",  # type: ignore
        )
    assert "output_language" in str(exc_info.value)
