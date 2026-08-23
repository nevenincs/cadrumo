"""Tests for the manifest-derived domain toolsets.

Exercised against the live operator-surface manifest and command keys - no mocks
- so the toolset membership is verified to derive from the real CLI surface.
"""

from __future__ import annotations

import pytest

from cadrumo.entrypoints.cli import command_schema_refs, is_exposable_command

from .._toolsets import (
    Toolset,
    ToolsetGroup,
    _family_domain_map,
    build_toolsets,
    toolset_for_command,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_build_toolsets_emits_one_group_per_toolset_in_order() -> None:
    groups = build_toolsets()
    assert tuple(group.toolset for group in groups) == tuple(Toolset)
    assert all(isinstance(group, ToolsetGroup) for group in groups)


def _members() -> dict[Toolset, tuple[str, ...]]:
    return {group.toolset: group.command_keys for group in build_toolsets()}


def test_ledger_toolset_is_the_ledger_domain() -> None:
    members = _members()
    assert members[Toolset.LEDGER]
    assert all(key.startswith("ledger.") for key in members[Toolset.LEDGER])


def test_modelo_lifecycle_excludes_the_tax_concept_carve_outs() -> None:
    members = _members()
    lifecycle = members[Toolset.MODELO_LIFECYCLE]
    assert "modelo.work.calculate" in lifecycle
    assert all(key.startswith("modelo.") for key in lifecycle)
    # The IVA-wallet and M036 verbs are carved out to their own toolsets.
    assert all("iva_wallet" not in key.split(".") for key in lifecycle)
    assert all("m036" not in key.split(".") for key in lifecycle)


def test_censo_covers_the_m036_surface() -> None:
    members = _members()
    censo = members[Toolset.CENSO]
    assert "modelo.m036.alta" in censo


def test_iva_spans_live_and_modelo_wallet_surfaces() -> None:
    members = _members()
    iva = members[Toolset.IVA]
    assert "app.live.iva_wallet.pull" in iva
    assert "modelo.iva_wallet.balance" in iva


def test_renta_is_the_borrador_draft_surface() -> None:
    members = _members()
    assert members[Toolset.RENTA]
    assert all(key.startswith("app.live.borrador.100") for key in members[Toolset.RENTA])


def test_membership_is_derived_completely_from_the_live_surface() -> None:
    # Every live iva-wallet verb joins the IVA toolset by derivation - proving the
    # membership is not a hand-listed subset that could drift from the CLI.
    family_map = _family_domain_map()
    wallet_keys = {
        ref.command
        for ref in command_schema_refs()
        if is_exposable_command(ref.command) and "iva_wallet" in ref.command.split(".")
    }
    iva = set(_members()[Toolset.IVA])
    assert wallet_keys
    assert wallet_keys <= iva
    # A read-only overview verb is long-tail and belongs to no curated toolset.
    assert toolset_for_command("overview.status", family_map=family_map) is None
