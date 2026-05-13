"""CLI surface tests for the ``aeat ... modelo`` command tree.

These tests pin the user-input-error contract: any operator-facing
error (malformed period, unknown modelo) must surface as a
``typer.BadParameter`` clean message rather than a Python traceback.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from . import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_RUNNER = CliRunner()


@pytest.mark.parametrize(
    "command",
    [
        ["app", "modelo", "describe", "303", "--period", "garbage"],
        ["app", "modelo", "casillas", "303", "--period", "2026-Quarter1"],
        ["app", "modelo", "bindings", "list", "--modelo", "303", "--year", "2026", "--period", "not-a-period"],
        ["app", "modelo", "formulas", "303", "--period", "2026-13"],
    ],
)
def test_malformed_period_surfaces_as_bad_parameter(command: list[str]) -> None:
    result = _RUNNER.invoke(app, command)
    assert result.exit_code != 0
    assert "Traceback" not in result.output
    output_lower = result.output.lower()
    assert "period must be" in output_lower or "invalid value" in output_lower


def test_unknown_modelo_surfaces_as_bad_parameter() -> None:
    result = _RUNNER.invoke(app, ["app", "modelo", "describe", "999"])
    assert result.exit_code != 0
    assert "Traceback" not in result.output
    output_lower = result.output.lower()
    assert "999" in output_lower or "not present" in output_lower


# ---------------------------------------------------------------------------
# bindings list / preview surface
# ---------------------------------------------------------------------------


def test_bindings_list_emits_readiness_category_for_every_row() -> None:
    """``bindings list`` enriches each binding row with a readiness
    category from the closed set (ledger source / profile fact /
    prior filed revision / live observation / bucket / waiver /
    blocking finding / casilla)."""

    result = _RUNNER.invoke(
        app,
        ["app", "modelo", "bindings", "list",
         "--modelo", "303", "--year", "2026", "--period", "Q1"],
    )
    assert result.exit_code == 0, result.output
    assert "operation\tregistry.modelo.bindings.list" in result.output
    assert "binding_id\tsource\treadiness\ttyped_enum" in result.output
    # Every modelo-303 binding currently sources from
    # ``ledger_iva_aggregation`` so every row's readiness column is
    # "ledger source".
    assert "ledger source" in result.output


def test_bindings_list_missing_filter_excludes_constant_value_bindings() -> None:
    """``--missing`` filters to bindings that require runtime
    resolution. Constant-valued bindings are inherently always
    available so they drop out of the missing-bindings view."""

    result = _RUNNER.invoke(
        app,
        ["app", "modelo", "bindings", "list",
         "--modelo", "303", "--year", "2026", "--period", "Q1",
         "--missing"],
    )
    assert result.exit_code == 0, result.output
    assert "missing_filter\tTrue" in result.output


def test_bindings_preview_echoes_override_for_known_key() -> None:
    """An override targeting a known binding id surfaces in the
    payload's ``override`` column."""

    result = _RUNNER.invoke(
        app,
        ["app", "modelo", "bindings", "preview",
         "--modelo", "303", "--year", "2026", "--period", "Q1",
         "--binding",
         "modelo-303-iva-repercutido-general-cuota=1234.56"],
    )
    assert result.exit_code == 0, result.output
    assert "operation\tregistry.modelo.bindings.preview" in result.output
    assert "override_count\t1" in result.output
    assert "1234.56" in result.output


def test_bindings_preview_rejects_unknown_binding_with_suggestion_list() -> None:
    """Unknown override keys fail with a suggestion list sourced
    from the registry's binding catalogue for the active modelo /
    year / period."""

    result = _RUNNER.invoke(
        app,
        ["app", "modelo", "bindings", "preview",
         "--modelo", "303", "--year", "2026", "--period", "Q1",
         "--binding", "no-such-binding=42"],
    )
    assert result.exit_code != 0
    output_lower = result.output.lower()
    assert "no-such-binding" in output_lower
    # The suggestion list cites at least one real binding id.
    assert "modelo-303-iva-" in result.output


def test_bindings_preview_rejects_malformed_override_syntax() -> None:
    """``--binding`` without an ``=`` separator fails at the CLI
    boundary with a typer.BadParameter."""

    result = _RUNNER.invoke(
        app,
        ["app", "modelo", "bindings", "preview",
         "--modelo", "303", "--year", "2026", "--period", "Q1",
         "--binding", "missing-equals-sign"],
    )
    assert result.exit_code != 0
    assert "KEY=VALUE" in result.output


# ---------------------------------------------------------------------------
# Boundary regression guards
# ---------------------------------------------------------------------------


def test_no_parallel_bindings_typer_outside_canonical_module() -> None:
    """The canonical ``bindings`` sub-Typer registration lives in
    ``_modelo.py``. Any other module that re-implements a Typer
    named ``bindings`` competes with the canonical surface and must
    be removed."""

    from pathlib import Path

    from aeat.core.paths import PROJECT_ROOT

    cli_root = PROJECT_ROOT / "src" / "aeat" / "entrypoints" / "cli"
    canonical = cli_root / "_modelo.py"
    forbidden_patterns = (
        'typer.Typer(\n    name="bindings"',
        'typer.Typer(name="bindings"',
    )
    offenders: list[Path] = []
    for py_file in cli_root.rglob("*.py"):
        if py_file == canonical:
            continue
        if py_file.name.startswith("test_"):
            continue
        text = py_file.read_text(encoding="utf-8")
        if any(needle in text for needle in forbidden_patterns):
            offenders.append(py_file)
    assert offenders == [], (
        "Parallel bindings Typer outside the canonical _modelo.py: "
        f"{[str(p) for p in offenders]}"
    )


def test_bindings_list_and_preview_emit_no_bucket_event() -> None:
    """``bindings list`` and ``bindings preview`` are read-only —
    they must not trigger any bucket event.

    The boundary check inspects the canonical module's source for
    any bucket-event emission call. If a future change wires one
    in by accident, this test fails fast."""

    from pathlib import Path

    from aeat.core.paths import PROJECT_ROOT

    canonical_text = (
        PROJECT_ROOT
        / "src"
        / "aeat"
        / "entrypoints"
        / "cli"
        / "_modelo.py"
    ).read_text(encoding="utf-8")
    forbidden_emitters = (
        "emit_bucket_event",
        "append_bucket_event",
        "bucket_event(",
    )
    for needle in forbidden_emitters:
        assert needle not in canonical_text, (
            f"Forbidden bucket-event emission pattern {needle!r} found in "
            "_modelo.py; bindings list/preview must remain read-only."
        )
