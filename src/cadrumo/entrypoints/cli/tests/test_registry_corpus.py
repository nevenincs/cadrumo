"""Real-behaviour tests for the legal citation + manuals CLI exposure.

Tests exercise the ``aeat app registry citations`` and
``aeat app registry manuals`` Typer surfaces end-to-end through the
shared cached CLI runner, against the committed corpus on disk. No mocks /
fakes / fixtures — every command consumes the same domain APIs the
production runtime uses (the reviewed registry legal catalogue,
``cadrumo.domain.manuals.load_manual``, etc.).

The CLI exposure lives under ``aeat app registry``, not under a new
root verb. The boundary regression guard at the bottom of the file
enforces that no ``cadrumo normatives`` or ``cadrumo manual`` top-level verb
is registered.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from click.testing import Result
from typer._click.core import Context as TyperContext
from typer.core import TyperGroup

from ....core.directory_scan import scan_directory
from ....tests import REPO_ROOT
from ....tests.cli_runner import cadrumo_click_command, invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_CURRENT_LEGAL_AUTHORITY_TERMS = (
    "legal authority id",
    "autoridad legal",
    "autoritat legal",
    "jogi hivatkozásazonosító",
)


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


# ---------------------------------------------------------------------------
# citations
# ---------------------------------------------------------------------------


def test_citations_verify_surfaces_current_legal_catalogue_state() -> None:
    result = _invoke("citations", "verify")

    assert result.exit_code == 0, result.stdout
    assert "operation\tregistry.citations.verify" in result.stdout
    assert "issue_count\t0" in result.stdout
    assert "passed\tTrue" in result.stdout


def test_citations_verify_emits_json_when_format_json_is_set() -> None:
    result = _invoke("citations", "verify", fmt="json")

    assert result.exit_code == 0, result.stdout
    envelope = json.loads(result.stdout)
    assert envelope["command"] == "registry.citations.verify"
    payload = envelope["result"]
    assert payload["operation"] == "registry.citations.verify"
    assert payload["issue_count"] == 0
    assert payload["passed"] is True
    assert payload["issues"] == []


def test_citations_list_ignores_legacy_normatives_root_override(tmp_path: Path) -> None:
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
                "reviewed_by": "operator",
            },
        ),
        encoding="utf-8",
    )
    result = _invoke_with_env("citations", "list", env=_env_with_normatives_root(tmp_path))

    assert result.exit_code == 0, result.stdout
    assert "operation\tregistry.citations.list" in result.stdout


def test_citations_list_emits_json_payload_through_root_format() -> None:
    result = _invoke("citations", "list", "--tag", "irpf", fmt="json")

    assert result.exit_code == 0, result.stdout
    envelope = json.loads(result.stdout)
    assert envelope["command"] == "registry.citations.list"
    payload = envelope["result"]
    assert payload["operation"] == "registry.citations.list"
    assert payload["reference_count"] >= 1
    assert payload["tag_filter"] == "irpf"
    assert any(reference["id"] == "rd-439-2007" for reference in payload["references"])
    assert "topics" in payload


def test_citations_show_emits_text_and_json_payloads_through_root_format() -> None:
    text = _invoke("citations", "view", "ley-35-2006", "--articulo", "32")
    json_result = _invoke(
        "citations",
        "view",
        "ley-35-2006",
        "--articulo",
        "32",
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


def test_citations_view_help_uses_current_legal_authority_terms() -> None:
    result = _invoke("citations", "view", "--help")

    assert result.exit_code == 0, result.stdout
    rendered = result.stdout.lower()
    assert any(term in rendered for term in _CURRENT_LEGAL_AUTHORITY_TERMS), result.stdout
    assert "normative" not in rendered


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


def _cli_source_modules(cli_root: Path) -> list[Path]:
    """Return the non-test CLI source modules, floored at the corpus source.

    Both root-verb boundary scans below walk this tree and assert an empty
    offender map; that green is meaningless if the walk found nothing. A rename
    of ``_CLI_ROOT`` or a package relocation would empty the corpus and pass
    identically to a clean tree, so the floor here guarantees every consumer's
    walk actually reached the CLI surface.
    """
    modules = [
        py_file
        for py_file in scan_directory(cli_root, pattern="*.py", recursive=True)
        if not py_file.name.startswith("test_")
    ]
    assert len(modules) > 100, (
        f"scanned only {len(modules)} CLI modules under {cli_root}; the scan corpus collapsed (a "
        "package relocation or rename), so an empty offender map would mean 'nothing was checked' "
        "rather than 'nothing is wrong'"
    )
    return modules


def test_no_top_level_normatives_or_manual_root_verb_is_registered() -> None:
    """The CLI root is restricted to ``aeat config`` and ``aeat app``
    only. A top-level ``cadrumo normatives`` or ``cadrumo manual`` verb is
    rejected. This test asserts no source file under
    ``entrypoints/cli/`` registers either name at the root level."""

    cli_root = REPO_ROOT / "src" / "cadrumo" / "entrypoints" / "cli"
    forbidden_root_names = (
        'name="normatives"',
        "name='normatives'",
        'name="manual"',
        "name='manual'",
        'name="manuales"',
        "name='manuales'",
    )
    offenders: dict[Path, list[str]] = {}
    for py_file in _cli_source_modules(cli_root):
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

    def _names(group: TyperGroup) -> set[str]:
        return set(group.list_commands(TyperContext(group)))

    def _child(group: TyperGroup, name: str) -> TyperGroup:
        child = group.get_command(TyperContext(group), name)
        assert child is not None
        assert isinstance(child, TyperGroup)
        return child

    root = cadrumo_click_command()
    assert isinstance(root, TyperGroup)
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
        "cadrumo help",
        "cadrumo topic",
        "cadrumo topics",
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

    cli_root = REPO_ROOT / "src" / "cadrumo" / "entrypoints" / "cli"
    forbidden_command_names = (
        '@citations_app.command("fetch"',
        "@citations_app.command('fetch'",
        '@manuals_app.command("fetch"',
        "@manuals_app.command('fetch'",
    )
    offenders: dict[Path, list[str]] = {}
    # Test files legitimately quote the forbidden patterns as search strings in
    # their own boundary scans; the helper excludes them, and floors the corpus so
    # a collapsed walk cannot green this scan.
    for py_file in _cli_source_modules(cli_root):
        text = py_file.read_text(encoding="utf-8")
        hits = [needle for needle in forbidden_command_names if needle in text]
        if hits:
            offenders[py_file] = hits
    assert offenders == {}, "Manual / citation fetch verb registered against the read-only " + f"contract: {offenders}"
