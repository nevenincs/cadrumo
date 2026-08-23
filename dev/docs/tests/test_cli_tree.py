"""Tests for the ``cli-tree.json`` help-projection generator (``dev/docs/cli_tree.py``).

The projection is the build-time help catalogue the ``cli-sequence`` browser
widget consumes. These tests prove it generates, is byte-deterministic across
two builds, covers every node the immutable command graph yields, round-trips through
its serialised form, and that a documented command path absent from the
projection fails loudly with nearest-candidate hints — a free conformance gate
against CLI drift.

The independent tree walk (:func:`_collect_all_path_keys_in_subprocess`) is a
separate materialisation from the generator's own walk, so the coverage test
proves the projection loop enrolls every collected node rather than restating
its own output.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from ..cli_reference import _reference_subprocess_environment
from ..cli_tree import (
    CLI_TREE_STATIC_RELPATH,
    CliCommandNode,
    CliTree,
    CliTreePathNotFoundError,
    CliTreePathsNotFoundError,
    ParamKind,
    assert_documented_paths_present,
    build_cli_tree_in_subprocess,
    default_cli_tree_path,
    load_cli_tree,
    resolve_command_path,
    serialise_cli_tree,
    write_cli_tree,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.docs]


def _collect_all_path_keys_in_subprocess() -> set[str]:
    """Return every command path authored by the immutable graph."""
    code = textwrap.dedent(
        """
        from cadrumo.entrypoints.cli.command_api import command_spec_nodes
        for node in command_spec_nodes():
            print(' '.join(node.path))
        """,
    )
    with TemporaryDirectory(prefix="cadrumo-cli-tree-cov-") as storage_root:
        result = subprocess.run(
            [sys.executable, "-c", code],
            env=_reference_subprocess_environment(Path(storage_root)),
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    if result.returncode != 0:
        raise RuntimeError(f"independent path collection failed (exit {result.returncode}):\n{result.stderr}")
    return {line for line in result.stdout.splitlines() if line.strip()}


@pytest.fixture(scope="module")
def cli_tree() -> CliTree:
    """The generated projection, built once per module through the clean subprocess."""
    return build_cli_tree_in_subprocess()


def test_projection_generates_nonempty(cli_tree: CliTree) -> None:
    """The projection is a populated mapping keyed by space-joined command paths."""
    assert len(cli_tree.root) > 100
    assert "aeat" in cli_tree.root
    root_node = cli_tree.root["aeat"]
    assert root_node.kind == "group"
    assert root_node.path == ("aeat",)


def test_projection_is_deterministic() -> None:
    """Two independent builds serialise byte-for-byte identically."""
    first = serialise_cli_tree(build_cli_tree_in_subprocess())
    second = serialise_cli_tree(build_cli_tree_in_subprocess())
    assert first == second


def test_serialised_form_has_sorted_keys(cli_tree: CliTree) -> None:
    """The canonical serialisation sorts keys and ends with a newline."""
    text = serialise_cli_tree(cli_tree)
    assert text.endswith("\n")
    # Top-level keys appear in sorted order.
    import json

    payload = json.loads(text)
    assert list(payload) == sorted(payload)


def test_projection_covers_every_collected_path(cli_tree: CliTree) -> None:
    """Every node an independent tree walk yields is present in the projection."""
    independent = _collect_all_path_keys_in_subprocess()
    assert independent, "independent walk yielded no paths"
    assert set(cli_tree.root) == independent


def test_leaf_and_group_kinds_are_distinguished(cli_tree: CliTree) -> None:
    """A dispatching group and an invokable leaf carry the right ``kind``."""
    group = resolve_command_path(cli_tree, "aeat app modelo")
    leaf = resolve_command_path(cli_tree, "aeat app modelo work calculate")
    assert group.kind == "group"
    assert leaf.kind == "leaf"
    assert "COMMAND [ARGS]..." in group.usage


def test_positional_argument_is_classified_as_argument(cli_tree: CliTree) -> None:
    """A single-subject positional id projects as an argument, not an option.

    Regression guard: Typer wraps positionals in ``TyperArgument`` which is not
    a ``click.Argument`` subclass, so an ``isinstance`` classifier silently
    mislabels every positional as an option.
    """
    node = resolve_command_path(cli_tree, "aeat app ledger view")
    arguments = [p for p in node.params if p.kind is ParamKind.ARGUMENT]
    assert arguments, "ledger view must carry a positional transaction-id argument"
    assert any("transaction_id" in name for p in arguments for name in p.names)
    assert node.usage.startswith("aeat app ledger view")


def test_option_names_carry_flag_spellings(cli_tree: CliTree) -> None:
    """An option projects its ``--flag`` spellings, not its Python name."""
    node = resolve_command_path(cli_tree, "aeat app modelo work calculate")
    options = [p for p in node.params if p.kind is ParamKind.OPTION]
    assert options
    assert any(name.startswith("--") for p in options for name in p.names)


def test_machine_secret_and_profile_authentication_metadata_matches_live_projection(
    cli_tree: CliTree,
) -> None:
    """The generated discovery tree carries the same value-free graph contracts."""
    from cadrumo.entrypoints.cli.command_api import command_registration_projection

    registration = command_registration_projection()
    rows = {("aeat", *(row.cli_path or ())): row for row in registration.commands}
    secret_paths = set()
    for path, row in rows.items():
        node = resolve_command_path(cli_tree, path)
        assert node.machine_secret_payloads == row.machine_secret_payloads
        assert node.profile_authentication == row.profile_authentication
        if node.machine_secret_payloads:
            secret_paths.add(path)
    assert secret_paths == {
        ("aeat", "config", "login"),
        ("aeat", "config", "passphrase", "change"),
        ("aeat", "config", "profile", "create"),
        ("aeat", "config", "profile", "restore"),
        ("aeat", "config", "auth", "certificate", "secret", "set"),
    }

    root = resolve_command_path(cli_tree, "aeat")
    assert root.profile_authentication_contract == registration.profile_authentication_contract
    assert all(
        node.profile_authentication_contract is None
        for key, node in cli_tree.root.items()
        if key != "aeat"
    )
    rendered = serialise_cli_tree(cli_tree).lower()
    assert all(token not in rendered for token in ('"value"', '"example"', "secretstr"))


def test_round_trip_through_serialised_form(cli_tree: CliTree, tmp_path: Path) -> None:
    """Serialise → load reconstructs an equal projection."""
    path = tmp_path / "cli-tree.json"
    path.write_text(serialise_cli_tree(cli_tree), encoding="utf-8")
    reloaded = load_cli_tree(path)
    assert reloaded.root == cli_tree.root


def test_resolve_accepts_tuple_and_string(cli_tree: CliTree) -> None:
    """A command path resolves identically as a tuple or a space-joined string."""
    by_tuple = resolve_command_path(cli_tree, ("aeat", "app", "modelo", "work", "calculate"))
    by_string = resolve_command_path(cli_tree, "aeat app modelo work calculate")
    assert by_tuple.path == by_string.path


def test_resolve_accepts_path_without_executable_prefix(cli_tree: CliTree) -> None:
    """A path missing the leading ``aeat`` token still resolves."""
    with_prefix = resolve_command_path(cli_tree, "aeat app modelo work calculate")
    without_prefix = resolve_command_path(cli_tree, "app modelo work calculate")
    assert with_prefix.path == without_prefix.path


def test_missing_path_raises_with_candidates(cli_tree: CliTree) -> None:
    """A documented path absent from the projection fails loudly with hints."""
    with pytest.raises(CliTreePathNotFoundError) as excinfo:
        resolve_command_path(cli_tree, "aeat app modelo work calculat")
    error = excinfo.value
    assert error.path_key == "aeat app modelo work calculat"
    assert error.candidates  # nearest matches offered
    assert "aeat app modelo work calculate" in error.candidates


def test_assert_documented_paths_present_passes_for_real_paths(cli_tree: CliTree) -> None:
    """The batch gate accepts a set of genuinely documented paths."""
    assert_documented_paths_present(
        cli_tree,
        ["aeat app modelo work calculate", ("aeat", "app", "ledger", "view")],
    )


def test_assert_documented_paths_present_accumulates_every_absent_path(cli_tree: CliTree) -> None:
    """The batch gate accumulates every absent path into one raised error.

    Mirrors the engine's accumulating-diagnostics convention: an author sees the
    whole worklist in one pass, not one build failure at a time.
    """
    with pytest.raises(CliTreePathsNotFoundError) as excinfo:
        assert_documented_paths_present(
            cli_tree,
            [
                "aeat app modelo work calculate",  # present — must not appear
                "aeat app nonexistent verb",
                "aeat app modelo work calculat",  # a typo with a near candidate
            ],
        )
    error = excinfo.value
    assert set(error.path_keys) == {"aeat app nonexistent verb", "aeat app modelo work calculat"}
    assert len(error.errors) == 2
    # The typo carries a nearest-candidate hint; the aggregate message lists both.
    typo_error = next(e for e in error.errors if e.path_key == "aeat app modelo work calculat")
    assert "aeat app modelo work calculate" in typo_error.candidates
    assert "aeat app nonexistent verb" in str(error)


def test_write_cli_tree_emits_default_static_path(tmp_path: Path) -> None:
    """``write_cli_tree`` writes canonical JSON at the default static location."""
    output = default_cli_tree_path(tmp_path)
    assert output.relative_to(tmp_path) == CLI_TREE_STATIC_RELPATH
    tree = write_cli_tree(output)
    assert output.is_file()
    on_disk = output.read_text(encoding="utf-8")
    assert on_disk == serialise_cli_tree(tree)
    # A second write with unchanged content is idempotent (byte-identical).
    write_cli_tree(output)
    assert output.read_text(encoding="utf-8") == on_disk


def test_command_node_is_strict(cli_tree: CliTree) -> None:
    """The node model rejects an unknown field (strict boundary)."""
    sample = next(iter(cli_tree.root.values()))
    payload = sample.model_dump(mode="json")
    payload["unexpected"] = "x"
    with pytest.raises(ValueError, match="unexpected"):
        CliCommandNode.model_validate(payload)
