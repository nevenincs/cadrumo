"""Root-grammar invariants for the CLI surface.

The CLI exposes exactly two roots (`config` and `app`) with a fixed
noun-group ordering. These tests assert that the rejected verbs and
surfaces are not mounted, so the CLI grammar stays the intentional
one.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_sessionless_storage_root

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path: Path) -> Iterator[None]:
    with isolated_sessionless_storage_root(tmp_path=tmp_path):
        yield


def test_root_does_not_register_bare_reconcile_alias() -> None:
    """`aeat reconcile` is not a root verb; reconcile only lives
    under `aeat app modelo`."""

    result = invoke_cached_cli(["reconcile", "--help"])
    assert result.exit_code != 0, result.output


def test_app_does_not_register_deadlines_subgroup() -> None:
    """`aeat app deadlines` is not a verb tree. Deadline data is
    surfaced through the overview verb group."""

    result = invoke_cached_cli(["app", "deadlines", "--help"])
    assert result.exit_code != 0, result.output


def test_modelo_audit_export_remains_distinct_from_modelo_export() -> None:
    """`aeat app modelo export` (fichero-BOE exporter) and
    `aeat app modelo audit export` (evidence-bundle exporter) are
    distinct sibling verbs. Both must resolve, and each must carry
    its own purpose-specific help so operators are not confused."""

    audit_help = invoke_cached_cli(["app", "modelo", "audit", "export", "--help"])
    assert audit_help.exit_code == 0, audit_help.output

    modelo_export_help = invoke_cached_cli(["app", "modelo", "export", "--help"])
    assert modelo_export_help.exit_code == 0, modelo_export_help.output

    assert "fichero-BOE" in modelo_export_help.output
    assert "fichero-BOE" not in audit_help.output


def test_root_does_not_register_bare_audit_alias() -> None:
    """`aeat audit` is not a root verb. The evidence-bundle contract
    explicitly forbids root `aeat audit` or `aeat run` commands; the
    audit surface only lives under `aeat app modelo audit`."""

    result = invoke_cached_cli(["audit", "--help"])
    assert result.exit_code != 0, result.output


def test_root_does_not_register_bare_run_alias() -> None:
    """`aeat run` is not a root verb per the evidence-bundle contract.
    Replay belongs under `aeat app modelo audit replay`, never at
    the root."""

    result = invoke_cached_cli(["run", "--help"])
    assert result.exit_code != 0, result.output


def test_app_does_not_register_audit_subgroup_outside_modelo() -> None:
    """`aeat app audit` would split the audit verb tree away from the
    work-unit-bound modelo verb tree. The evidence-bundle contract scopes
    the surface to `aeat app modelo audit`; any sibling `aeat app
    audit` mount would be a redirection target that splits ownership."""

    result = invoke_cached_cli(["app", "audit", "--help"])
    assert result.exit_code != 0, result.output


def test_modelo_audit_verbs_only_register_canonical_four() -> None:
    """Only the four canonical audit verbs (show / check / export /
    replay) are mounted under `aeat app modelo audit`. Any other leaf
    (verify, status, list, browse, run, etc.) violates the ratified
    grammar from the evidence-bundle contract."""

    forbidden_leaves = (
        ("verify",),
        ("run",),
        ("status",),
        ("list",),
        ("browse",),
        ("inspect",),
    )
    for leaf in forbidden_leaves:
        result = invoke_cached_cli(["app", "modelo", "audit", *leaf, "--help"])
        assert result.exit_code != 0, (leaf, result.output)

    accepted_leaves = (("show",), ("check",), ("export",), ("replay",))
    for leaf in accepted_leaves:
        result = invoke_cached_cli(["app", "modelo", "audit", *leaf, "--help"])
        assert result.exit_code == 0, (leaf, result.output)
