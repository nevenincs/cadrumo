"""Native documentation build selectors remain owned by the documentation compile."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.storage_environment import STORAGE_ROOT
from dev.docs import compile_once
from dev.docs.build import DOCS_FLAVOR_ENV
from dev.docs.compile_once import main as compile_main
from dev.docs.sequence_build_gate import SEQUENCE_CHECK_SKIP_ENV

from .. import docs_build
from ..docs_build import compile_command, compile_environment
from ..docs_stage import DocsPackagingError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_LANGUAGES = ("en", "es", "ca", "hu")


def test_the_compile_carries_product_storage_and_no_documentation_selector(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The packaging driver owns where product state goes and nothing else.

    Every documentation selector is the compile's own, so an ambient one must
    not survive into its environment: a second authority for the flavour, the
    search index or a root's place in the site is what one compile retires.
    """
    monkeypatch.setenv(DOCS_FLAVOR_ENV, "web")
    monkeypatch.setenv("CADRUMO_DOCS_PAGEFIND_MODE", "full")
    monkeypatch.setenv(SEQUENCE_CHECK_SKIP_ENV, "1")
    environment = compile_environment(tmp_path / "storage")

    assert environment[STORAGE_ROOT.variable] == str(tmp_path / "storage")
    carried = sorted(key for key in environment if key.startswith("CADRUMO_DOCS_"))
    assert not carried, f"the packaging driver carried documentation selectors the compile owns: {carried}"


@pytest.mark.parametrize("check_sequences", [None, False, True])
def test_the_compile_command_names_the_desktop_flavor_strictly_and_both_roots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, check_sequences: bool | None
) -> None:
    """The command is read back through the compile's own argument parser.

    Asserting the flags through the parser that consumes them is what keeps a
    renamed flag from passing: a raw string comparison would not notice.
    """
    html_root, build_root = tmp_path / "html", tmp_path / "build"
    command = compile_command(html_root, build_root)
    monkeypatch.delenv(SEQUENCE_CHECK_SKIP_ENV, raising=False)
    if check_sequences is None:
        command.remove("--no-check-sequences")
    elif check_sequences:
        command.append("--check-sequences")

    assert command[1:3] == ["-m", "dev.docs.compile_once"], f"the command does not run the compile: {command}"
    recorded: dict[str, object] = {}

    def record(root: Path, **settings: object) -> object:
        recorded.update(settings, html_root=root)
        # The packaging command asks for the roots and not for the stored form,
        # so the result it is handed reports none: the compile composes the
        # roots from it and removes it again.
        return SimpleNamespace(
            languages=_LANGUAGES,
            roots=dict.fromkeys(_LANGUAGES, root),
            stored=None,
            seconds=0.0,
            html_root=root,
        )

    monkeypatch.setattr(compile_once, "compile_language_roots", record)
    assert compile_main(command[3:]) == 0

    assert recorded["html_root"] == html_root
    assert recorded["build_root"] == build_root
    assert recorded["flavor"] == "desktop"
    assert recorded["stored"] is None, "the package ships the roots, so the stored form is an intermediate"
    # The docs lane compiles the web flavour, so nothing else holds the pages
    # the packaged copy builds to a warnings-as-errors standard.
    assert recorded["strict"] is True, "the only compile of the desktop flavour tolerates warnings"
    assert recorded["check_sequences"] is (check_sequences is not False)


def test_a_failed_compile_stops_the_packaging_build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """One failing compile refuses, names its log, and leaves no root behind."""
    monkeypatch.setattr(
        docs_build,
        "run_command",
        lambda *_args, **_settings: SimpleNamespace(returncode=2, stdout="boom\n", stderr="", duration_seconds=0),
    )
    with pytest.raises(SystemExit, match="User documentation compile failed: exit 2"):
        docs_build._compile_roots(tmp_path / "build", tmp_path / "work", _LANGUAGES)
    assert (tmp_path / "work" / "compile.log").read_text(encoding="utf-8") == "boom\n"


def test_a_compile_that_wrote_no_root_for_a_declared_language_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A successful compile is not proof it wrote the roots the package declares."""
    monkeypatch.setattr(
        docs_build,
        "run_command",
        lambda *_args, **_settings: SimpleNamespace(returncode=0, stdout="", stderr="", duration_seconds=0),
    )
    with pytest.raises(DocsPackagingError, match="wrote no root for"):
        docs_build._compile_roots(tmp_path / "build", tmp_path / "work", _LANGUAGES)


def test_the_apex_language_is_a_declared_root(tmp_path: Path) -> None:
    """The HTML root is read off the apex language's root, so it must be one of them."""
    roots = docs_build.language_roots(tmp_path / "build", _LANGUAGES)
    assert OutputLanguage.EN.value in roots
    assert {root.parent for root in roots.values()} == {roots[OutputLanguage.EN.value].parent}
