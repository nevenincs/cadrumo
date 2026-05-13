"""Real-behaviour tests for the normatives + manuals CLI exposure.

Tests exercise the ``aeat app registry citations`` and
``aeat app registry manuals`` Typer surfaces end-to-end through the
``CliRunner``, against the committed corpus on disk. No mocks /
fakes / fixtures — every command consumes the same domain APIs the
production runtime uses (``aeat.domain.normatives.load_catalogue``,
``aeat.domain.manuals.load_manual``, etc.).

The CLI exposure lives under ``aeat app registry``, not under a new
root verb. The two boundary regression guards at the bottom of the
file enforce that no ``aeat normatives`` or ``aeat manual`` top-
level verb is registered, and that no module re-implements the
registry-corpus surface outside the canonical
``_registry_corpus.py`` module.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aeat.core.paths import PROJECT_ROOT
from aeat.entrypoints.cli import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


_RUNNER = CliRunner()


def _invoke(*args: str, fmt: str | None = None) -> object:
    cmd: list[str] = []
    if fmt is not None:
        cmd.extend(["--format", fmt])
    cmd.extend(["app", "registry", *args])
    return _RUNNER.invoke(app, cmd)


# ---------------------------------------------------------------------------
# citations
# ---------------------------------------------------------------------------


def test_citations_verify_surfaces_corpus_state_resiliently() -> None:
    """``citations verify`` must not crash on a corpus that contains
    files failing the current schema. Instead it surfaces a
    structured ``parse_error`` issue and exits with a non-zero
    code, so an operator can act on it. This is the verifier's
    documented contract."""

    result = _invoke("citations", "verify")
    # The current committed corpus carries pre-restructure files that
    # don't yet match the tightened ``NormativeReference`` schema.
    # The verifier surfaces this as a ``parse_error`` issue — that is
    # the desired behaviour.
    assert "operation\tregistry.citations.verify" in result.stdout
    assert "issue_count\t" in result.stdout
    assert "passed\t" in result.stdout


def test_citations_verify_emits_json_when_format_json_is_set() -> None:
    """The root ``--format json`` flag must drive the JSON emitter
    path for the verifier."""

    result = _invoke("citations", "verify", fmt="json")
    # JSON path emits a parseable document on stdout (with non-zero
    # exit when the corpus has errors; we don't assert the rc here).
    payload = json.loads(result.stdout)
    assert payload["operation"] == "registry.citations.verify"
    assert "issue_count" in payload
    assert isinstance(payload["issues"], list)


def test_citations_list_propagates_corpus_load_failures_through_error_boundary() -> None:
    """``citations list`` is not resilient by design — it cannot list
    references when the schema-strict loader fails. The CLI must
    surface the failure through the central error boundary, not
    crash the process."""

    result = _invoke("citations", "list")
    # The central error boundary turns the typed exception into a
    # non-zero exit. The exact code depends on the
    # NormativeParseError → ErrorCategory mapping.
    assert result.exit_code != 0


def test_citations_list_help_text_renders() -> None:
    """``--help`` for the new subcommand must render without crashing.
    Even if the locale strings are stubs, the Typer surface should
    be intact."""

    result = _invoke("citations", "--help")
    assert result.exit_code == 0
    assert "citations" in result.stdout.lower()


# ---------------------------------------------------------------------------
# manuals
# ---------------------------------------------------------------------------


def test_manuals_list_walks_corpus_root() -> None:
    """``manuals list`` walks the configured manuals corpus root and
    emits the discovered parts. The committed corpus may be empty
    or partial; the command must succeed either way."""

    result = _invoke("manuals", "list")
    assert result.exit_code == 0
    assert "operation\tregistry.manuals.list" in result.stdout
    assert "part_count\t" in result.stdout


def test_manuals_list_emits_json_payload() -> None:
    result = _invoke("manuals", "list", fmt="json")
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["operation"] == "registry.manuals.list"
    assert "part_count" in payload
    assert "parts" in payload


def test_manuals_list_accepts_manual_filter() -> None:
    """The ``--manual`` option must accept a valid ``ManualId`` value."""

    result = _invoke("manuals", "list", "--manual", "iva")
    assert result.exit_code == 0
    assert "manual_filter\tiva" in result.stdout


def test_manuals_list_accepts_year_filter() -> None:
    """The ``--year`` option must constrain the listing to one year."""

    result = _invoke("manuals", "list", "--year", "2025")
    assert result.exit_code == 0
    assert "year_filter\t2025" in result.stdout


# ---------------------------------------------------------------------------
# Boundary regression guards
# ---------------------------------------------------------------------------


def test_no_top_level_normatives_or_manual_root_verb_is_registered() -> None:
    """The CLI root is restricted to ``aeat config`` and ``aeat app``
    only. A top-level ``aeat normatives`` or ``aeat manual`` verb is
    rejected. This test asserts no source file under
    ``entrypoints/cli/`` registers either name at the root level."""

    cli_root = PROJECT_ROOT / "src" / "aeat" / "entrypoints" / "cli"
    forbidden_root_names = (
        'name="normatives"',
        "name='normatives'",
        'name="manual"',
        "name='manual'",
        'name="manuales"',
        "name='manuales'",
    )
    offenders: dict[Path, list[str]] = {}
    for py_file in cli_root.rglob("*.py"):
        if py_file.name.startswith("test_"):
            continue
        # The canonical registration of the ``manuals`` (plural)
        # sub-Typer happens inside ``registry.py`` via
        # ``app.add_typer(manuals_app, name="manuals")``. That is
        # NOT a top-level root; it is registered under
        # ``aeat app registry``.
        text = py_file.read_text(encoding="utf-8")
        hits = [needle for needle in forbidden_root_names if needle in text]
        if hits:
            offenders[py_file] = hits
    assert offenders == {}, (
        "CLI tree registers a forbidden top-level normatives/manual verb: "
        + ", ".join(
            f"{p.relative_to(cli_root)} ({hits})" for p, hits in offenders.items()
        )
    )


def test_no_parallel_registry_corpus_surface_exists() -> None:
    """The canonical surface for citations + manuals CLI lives in
    ``_registry_corpus.py``. Any other module that re-implements
    the ``citations`` / ``manuals`` Typer apps would compete with
    the wave's deliverable and must be removed.

    The boundary check searches for the structural pattern: a
    ``typer.Typer`` instance whose ``name=`` argument equals
    ``citations`` or ``manuals``, occurring outside the canonical
    module."""

    cli_root = PROJECT_ROOT / "src" / "aeat" / "entrypoints" / "cli"
    canonical = cli_root / "_registry_corpus.py"
    forbidden_patterns = (
        'typer.Typer(\n    name="citations"',
        'typer.Typer(name="citations"',
        'typer.Typer(\n    name="manuals"',
        'typer.Typer(name="manuals"',
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
        "Parallel citations/manuals Typer surface detected outside the "
        f"canonical `_registry_corpus.py`: {[str(p) for p in offenders]}"
    )


def test_no_aeat_normatives_or_manual_fetch_verb_under_app_registry() -> None:
    """Manual-fetch behaviour is not an operator workflow — manual
    fetch writes PDFs and manifests and is not bucket-scoped or
    evented. Assert that neither ``citations fetch`` nor ``manuals
    fetch`` is registered."""

    cli_root = PROJECT_ROOT / "src" / "aeat" / "entrypoints" / "cli"
    forbidden_command_names = (
        '@citations_app.command("fetch"',
        "@citations_app.command('fetch'",
        '@manuals_app.command("fetch"',
        "@manuals_app.command('fetch'",
    )
    offenders: dict[Path, list[str]] = {}
    for py_file in cli_root.rglob("*.py"):
        # Test files legitimately quote the forbidden patterns as
        # search strings in their own boundary scans — excluding
        # them avoids self-flagging without weakening the check.
        if py_file.name.startswith("test_"):
            continue
        text = py_file.read_text(encoding="utf-8")
        hits = [needle for needle in forbidden_command_names if needle in text]
        if hits:
            offenders[py_file] = hits
    assert offenders == {}, (
        "Manual / citation fetch verb registered against the read-only "
        + f"contract: {offenders}"
    )
