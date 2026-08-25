"""Real-git proofs that the co-landing check bites, and bites only where it should.

Every fixture below builds an actual git repository with actual commits and runs
the production ``check_colanding`` over it. Nothing is mocked: a check that reads
a stubbed diff proves the stub, not the check, and this gate's whole claim is
that it sees a real change a real commit made.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from .. import LocaleManager, check_colanding, resolve_change
from ..errors import LocaleError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LOCALES = ("ca", "en", "es", "hu")


def _run(repo: Path, *arguments: str) -> None:
    subprocess.run(  # noqa: S603 - fixed executable, arguments are test-local
        ["git", *arguments],  # noqa: S607
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def _write_catalogues(repo: Path, entries: dict[str, str]) -> None:
    """Write the same key set to every locale with locale-distinct values."""
    locales_dir = repo / "src" / "cadrumo" / "locales"
    locales_dir.mkdir(parents=True, exist_ok=True)
    for locale in _LOCALES:
        lines = ["surface:"]
        for leaf, value in entries.items():
            lines.append(f"  {leaf}: '{value} ({locale})'")
        (locales_dir / f"{locale}.yml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_module(repo: Path, keys: tuple[str, ...]) -> None:
    module = repo / "src" / "cadrumo" / "feature.py"
    module.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(f"    render(tr({key!r}))" for key in keys) or "    return None"
    module.write_text(
        "from cadrumo.core.i18n import tr\n\n\ndef surface():\n" + body + "\n",
        encoding="utf-8",
    )


@pytest.fixture
def repo(tmp_path: Path) -> Iterator[Path]:
    """A real git repository carrying one module and four catalogues in lock-step."""
    root = tmp_path / "checkout"
    root.mkdir()
    _run(root, "init", "-q")
    _run(root, "config", "user.email", "colanding@example.invalid")
    _run(root, "config", "user.name", "colanding")
    _write_module(root, ("surface.greeting",))
    _write_catalogues(root, {"greeting": "Hola"})
    _run(root, "add", "-A")
    _run(root, "commit", "-qm", "baseline: key and call site land together")
    yield root


def _manager(repo: Path) -> LocaleManager:
    src_dir = repo / "src" / "cadrumo"
    return LocaleManager(src_dir, src_dir / "locales")


def test_a_change_that_lands_key_and_call_site_together_passes(repo: Path) -> None:
    """The green case, proved first: a co-landing commit must not red."""
    _write_module(repo, ("surface.greeting", "surface.farewell"))
    _write_catalogues(repo, {"greeting": "Hola", "farewell": "Adios"})
    _run(repo, "add", "-A")
    _run(repo, "commit", "-qm", "add a surface with its catalogue entry")

    result = check_colanding(_manager(repo), "last", repo)

    assert result.added_keys == ("surface.farewell",)
    assert result.findings == (), [finding.render() for finding in result.findings]
    assert result.ok


def test_a_call_site_landing_without_its_catalogue_entry_is_refused(repo: Path) -> None:
    """Bite proof one: the uncatalogued-call-site invariant."""
    _write_module(repo, ("surface.greeting", "surface.farewell"))
    _run(repo, "add", "-A")
    _run(repo, "commit", "-qm", "add a surface and forget the catalogue")

    result = check_colanding(_manager(repo), "last", repo)

    assert not result.ok
    (finding,) = result.findings
    assert finding.kind == "uncatalogued-call-site"
    assert finding.key == "surface.farewell"
    for locale in _LOCALES:
        assert f"{locale}.yml" in finding.detail


def test_a_partially_catalogued_call_site_names_only_the_absent_locales(repo: Path) -> None:
    """The finding must name which catalogues to repair, not merely that one is short."""
    _write_module(repo, ("surface.greeting", "surface.farewell"))
    _write_catalogues(repo, {"greeting": "Hola", "farewell": "Adios"})
    locales_dir = repo / "src" / "cadrumo" / "locales"
    (locales_dir / "hu.yml").write_text("surface:\n  greeting: 'Hola (hu)'\n", encoding="utf-8")
    _run(repo, "add", "-A")
    _run(repo, "commit", "-qm", "add a surface, catalogue three of four locales")

    result = check_colanding(_manager(repo), "last", repo)

    (finding,) = result.findings
    assert "hu.yml" in finding.detail
    assert "en.yml" not in finding.detail


def test_removing_the_last_call_site_and_leaving_the_key_is_refused(repo: Path) -> None:
    """Bite proof two: the orphaned-catalogue-key invariant."""
    _write_module(repo, ())
    _run(repo, "add", "-A")
    _run(repo, "commit", "-qm", "retire the surface and leave the catalogue standing")

    result = check_colanding(_manager(repo), "last", repo)

    assert not result.ok
    (finding,) = result.findings
    assert finding.kind == "orphaned-catalogue-key"
    assert finding.key == "surface.greeting"


def test_removing_the_call_site_and_the_key_together_passes(repo: Path) -> None:
    """The retirement done correctly must stay green, or the gate punishes the fix."""
    _write_module(repo, ())
    _write_catalogues(repo, {})
    _run(repo, "add", "-A")
    _run(repo, "commit", "-qm", "retire the surface and its catalogue entries together")

    result = check_colanding(_manager(repo), "last", repo)

    assert result.removed_keys == ("surface.greeting",)
    assert result.findings == (), [finding.render() for finding in result.findings]


def test_moving_a_call_site_between_modules_is_not_an_orphan(repo: Path) -> None:
    """A key that merely relocated still has a consumer and must not be flagged.

    The change-scoped delta alone would call this an orphan, because the key left
    every module the change touched. Only the whole-tree confirmation can tell a
    relocation from a retirement.
    """
    _write_module(repo, ())
    moved = repo / "src" / "cadrumo" / "relocated.py"
    moved.write_text(
        "from cadrumo.core.i18n import tr\n\n\ndef surface():\n    render(tr('surface.greeting'))\n",
        encoding="utf-8",
    )
    _run(repo, "add", "-A")
    _run(repo, "commit", "-qm", "relocate the surface without changing its key")

    result = check_colanding(_manager(repo), "last", repo)

    assert result.removed_keys == ()
    assert result.findings == ()


def test_a_change_touching_no_python_is_a_cheap_clean_pass(repo: Path) -> None:
    """The ordinary commit must cost nothing and report an honest empty delta."""
    (repo / "README.md").write_text("notes\n", encoding="utf-8")
    _run(repo, "add", "-A")
    _run(repo, "commit", "-qm", "docs only")

    result = check_colanding(_manager(repo), "last", repo)

    assert result.inspected_modules == 0
    assert result.added_keys == ()
    assert result.ok


def test_a_test_module_is_not_a_call_site(repo: Path) -> None:
    """Test fixtures declare no operator-facing surface and must not red the gate."""
    tests_dir = repo / "src" / "cadrumo" / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_feature.py").write_text(
        "from cadrumo.core.i18n import tr\n\n\ndef test_surface():\n    assert tr('surface.not_a_real_key')\n",
        encoding="utf-8",
    )
    _run(repo, "add", "-A")
    _run(repo, "commit", "-qm", "add a test that names a key")

    result = check_colanding(_manager(repo), "last", repo)

    assert result.inspected_modules == 0
    assert result.ok


def test_staged_work_is_compared_before_it_lands(repo: Path) -> None:
    """The default selector must see the index, which is the whole point of the gate."""
    _write_module(repo, ("surface.greeting", "surface.farewell"))
    _run(repo, "add", "-A")

    result = check_colanding(_manager(repo), "staged", repo)

    assert result.change == "staged changes against HEAD"
    assert not result.ok
    assert result.findings[0].key == "surface.farewell"


def test_an_empty_index_falls_back_to_the_last_commit_rather_than_passing_vacuously(repo: Path) -> None:
    """With nothing staged the gate must still compare a change, not report a clean state.

    Anti-vacuity for the whole module: the invocation with an empty index is the
    common one (a manual hook run, a CI job), and answering it with a green
    no-op would make the gate indistinguishable from not being installed.
    """
    _write_module(repo, ("surface.greeting", "surface.farewell"))
    _run(repo, "add", "-A")
    _run(repo, "commit", "-qm", "add a surface and forget the catalogue")

    result = check_colanding(_manager(repo), "staged", repo)

    assert result.change == "HEAD~1..HEAD"
    assert not result.ok
    assert result.findings[0].key == "surface.farewell"


def test_an_unrecognised_change_selector_is_refused(repo: Path) -> None:
    """A typo'd selector must fail loudly rather than silently comparing nothing."""
    with pytest.raises(LocaleError, match="unrecognised change selector"):
        resolve_change("yesterday", repo)
