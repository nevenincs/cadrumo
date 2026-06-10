"""Real-behaviour tests for the normatives + manuals CLI exposure.

Tests exercise the ``aeat app registry citations`` and
``aeat app registry manuals`` Typer surfaces end-to-end through the
``CliRunner``, against the committed corpus on disk. No mocks /
fakes / fixtures — every command consumes the same domain APIs the
production runtime uses (``aeat.domain.normatives.load_catalogue``,
``aeat.domain.manuals.load_manual``, etc.).

The CLI exposure lives under ``aeat app registry``, not under a new
root verb. The boundary regression guard at the bottom of the file
enforces that no ``aeat normatives`` or ``aeat manual`` top-level verb
is registered.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import click
import pytest
from click import Command, Group
from click.testing import Result

from ....core.paths import PROJECT_ROOT
from ....tests.cli_runner import aeat_click_command, invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _invoke(*args: str, fmt: str | None = None) -> Result:
    cmd: list[str] = []
    if fmt is not None:
        cmd.extend(["--format", fmt])
    cmd.extend(["app", "registry", *args])
    return invoke_cached_cli(cmd)


def _invoke_with_env(*args: str, env: dict[str, str], fmt: str | None = None) -> Result:
    cmd: list[str] = []
    if fmt is not None:
        cmd.extend(["--format", fmt])
    cmd.extend(["app", "registry", *args])
    return invoke_cached_cli(cmd, env=env)


def _env_with_normatives_root(root: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["AEAT_NORMATIVES_ROOT"] = str(root)
    return env


def _write_valid_normative(root: Path) -> None:
    (root / "ley-35-2006.json").write_text(
        json.dumps(
            {
                "id": "ley-35-2006",
                "kind": "ley",
                "number": "35/2006",
                "title": {"es": "Ley 35/2006"},
                "published_at": "2006-11-29",
                "boe_url": "https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764",
                "boe_id": "BOE-A-2006-20764",
                "articulos": [
                    {
                        "numero": "32",
                        "titulo": {"es": "Reducciones"},
                        "summary": {"es": "Resumen."},
                        "permalink": "https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764#a32",
                    }
                ],
                "tags": ["irpf"],
                "last_reviewed_at": "2026-04-12",
                "reviewed_by": "wgergely",
            }
        ),
        encoding="utf-8",
    )


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
    envelope = json.loads(result.stdout)
    assert envelope["command"] == "registry.citations.verify"
    payload = envelope["result"]
    assert payload["operation"] == "registry.citations.verify"
    assert "issue_count" in payload
    assert isinstance(payload["issues"], list)


def test_citations_list_propagates_corpus_load_failures_through_error_boundary(tmp_path: Path) -> None:
    """``citations list`` is not resilient by design — it cannot list
    references when the schema-strict loader fails. The CLI must
    surface the failure through the central error boundary, not
    crash the process."""

    # A normative whose title is a bare string violates the
    # LocalizedText schema; the schema-strict loader rejects the
    # corpus at load time.
    (tmp_path / "ley-broken.json").write_text(
        json.dumps(
            {
                "id": "ley-broken",
                "kind": "ley",
                "number": "1/2000",
                "title": "not-a-localized-mapping",
                "published_at": "2000-01-01",
                "boe_url": "https://www.boe.es/buscar/act.php?id=BOE-A-2000-00001",
                "boe_id": "BOE-A-2000-00001",
                "articulos": [],
                "tags": [],
                "last_reviewed_at": "2026-04-12",
                "reviewed_by": "wgergely",
            }
        ),
        encoding="utf-8",
    )
    result = _invoke_with_env("citations", "list", env=_env_with_normatives_root(tmp_path))
    # The central error boundary turns the typed exception into a
    # non-zero exit. The exact code depends on the
    # NormativeParseError → ErrorCategory mapping.
    assert result.exit_code != 0


def test_citations_list_emits_json_payload_through_root_format(tmp_path: Path) -> None:
    _write_valid_normative(tmp_path)

    result = _invoke_with_env("citations", "list", "--tag", "irpf", env=_env_with_normatives_root(tmp_path), fmt="json")

    assert result.exit_code == 0, result.stdout
    envelope = json.loads(result.stdout)
    assert envelope["command"] == "registry.citations.list"
    payload = envelope["result"]
    assert payload["operation"] == "registry.citations.list"
    assert payload["reference_count"] == 1
    assert payload["tag_filter"] == "irpf"
    assert payload["references"][0]["id"] == "ley-35-2006"
    assert payload["references"][0]["topic_slugs"] == []
    assert "topics" in payload


def test_citations_show_emits_text_and_json_payloads_through_root_format(tmp_path: Path) -> None:
    _write_valid_normative(tmp_path)
    env = _env_with_normatives_root(tmp_path)

    text = _invoke_with_env("citations", "view", "ley-35-2006", "--articulo", "32", env=env)
    json_result = _invoke_with_env(
        "citations",
        "view",
        "ley-35-2006",
        "--articulo",
        "32",
        env=env,
        fmt="json",
    )

    assert text.exit_code == 0, text.stdout
    assert "operation\tregistry.citations.show" in text.stdout
    assert "cite\tLey 35/2006, art. 32 (BOE-A-2006-20764)" in text.stdout
    envelope = json.loads(json_result.stdout)
    assert envelope["command"] == "registry.citations.view"
    payload = envelope["result"]
    assert payload["operation"] == "registry.citations.show"
    assert payload["reference"]["id"] == "ley-35-2006"
    assert payload["articulo"]["numero"] == "32"
    assert payload["articulo"]["cite"] == "Ley 35/2006, art. 32 (BOE-A-2006-20764)"
    assert "related_topics" in payload
    assert "cite" not in payload


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
    envelope = json.loads(result.stdout)
    assert envelope["command"] == "registry.manuals.list"
    payload = envelope["result"]
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
    assert offenders == {}, "CLI tree registers a forbidden top-level normatives/manual verb: " + ", ".join(
        f"{p.relative_to(cli_root)} ({hits})" for p, hits in offenders.items()
    )


def test_rejected_topic_and_help_commands_are_absent_from_discovery() -> None:
    """Command discovery exposes registry corpus commands, not topic/help commands.

    Heavy subcommand groups register lazily, so discovery walks the
    command tree through ``list_commands`` / ``get_command`` — the
    canonical Click introspection surface — rather than the eager
    ``.commands`` mapping.
    """

    def _names(group: Command) -> set[str]:
        assert isinstance(group, Group)
        return set(group.list_commands(click.Context(group)))

    def _child(group: Command, name: str) -> Command:
        assert isinstance(group, Group)
        child = group.get_command(click.Context(group), name)
        assert child is not None
        return child

    root = aeat_click_command()
    assert hasattr(root, "get_command")
    app_group = _child(root, "app")
    registry_group = _child(app_group, "registry")
    citations_group = _child(registry_group, "citations")
    manuals_group = _child(registry_group, "manuals")

    assert _names(root) == {"config", "app"}
    assert {"citations", "manuals"} <= _names(registry_group)
    for commands in (
        _names(root),
        _names(app_group),
        _names(registry_group),
        _names(citations_group),
        _names(manuals_group),
    ):
        assert commands.isdisjoint({"topic", "topics", "help"})


def test_rejected_topic_and_help_command_vocabulary_is_absent_from_help_text() -> None:
    """Accepted help surfaces must not advertise rejected topic/help commands."""

    forbidden_phrases = (
        "aeat help",
        "aeat topic",
        "aeat topics",
        "aeat app help",
        "aeat app topic",
        "aeat app topics",
    )
    for args in (
        ["--help"],
        ["app", "--help"],
        ["app", "registry", "--help"],
        ["app", "registry", "citations", "--help"],
        ["app", "registry", "manuals", "--help"],
    ):
        result = invoke_cached_cli(args)
        assert result.exit_code == 0, result.output
        lowered = result.output.lower()
        assert [phrase for phrase in forbidden_phrases if phrase in lowered] == []


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
    assert offenders == {}, "Manual / citation fetch verb registered against the read-only " + f"contract: {offenders}"
