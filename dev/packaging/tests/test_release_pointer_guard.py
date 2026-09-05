"""The backward-bump guard refuses to un-publish a newer release pointer.

Every test drives the real module against real files on disk — the pointer texts
are the exact shapes the two generators emit, so a change to either generator's
version placement reds these tests rather than silently blinding the guard.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ..release_pointer_guard import (
    BackwardBumpError,
    PointerFormat,
    assert_forward_bump,
    check_pointer,
    extract_pointer_version,
    main,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _scoop_manifest(version: str) -> str:
    """Return a Scoop manifest in the shape packaging/scoop/generate.py emits."""
    return json.dumps(
        {
            "version": version,
            "description": "Deterministic Spanish tax calculation CLI",
            "homepage": "https://github.com/nevenincs/cadrumo",
            "license": "Apache-2.0",
            "url": f"https://github.com/nevenincs/cadrumo/releases/download/v{version}/cadrumo-{version}.tar.gz",
            "hash": "0" * 64,
        },
        indent=2,
    )


def _homebrew_formula(version: str) -> str:
    """Return a formula in the shape packaging/homebrew/generate.py emits.

    The version is carried only by the release-asset URL: the generated formula
    has no ``version`` stanza, which is exactly why the guard parses the URL.
    """
    return (
        "class Cadrumo < Formula\n"
        "  include Language::Python::Virtualenv\n"
        '  desc "Deterministic Spanish tax calculation CLI"\n'
        '  homepage "https://github.com/nevenincs/cadrumo"\n'
        f'  url "https://github.com/nevenincs/cadrumo/releases/download/v{version}/cadrumo-{version}.tar.gz"\n'
        f'  sha256 "{"0" * 64}"\n'
        '  license "Apache-2.0"\n'
        "end\n"
    )


# ---------------------------------------------------------------------------
# Version extraction
# ---------------------------------------------------------------------------


def test_scoop_version_is_read_from_the_manifest() -> None:
    """The Scoop pointer's version comes from its ``version`` key."""
    assert extract_pointer_version(_scoop_manifest("0.2.1"), PointerFormat.SCOOP) == "0.2.1"


def test_homebrew_version_is_read_from_the_release_asset_url() -> None:
    """The formula pins its version only in the URL a user's brew install resolves."""
    assert extract_pointer_version(_homebrew_formula("0.2.1"), PointerFormat.HOMEBREW) == "0.2.1"


def test_homebrew_extraction_ignores_urls_that_are_not_release_assets() -> None:
    """A homepage or resource URL must not be mistaken for the pinned version.

    Without the ``/releases/download/v`` anchor the first ``url`` in the file
    would win, and a resource URL would let any version past the guard.
    """
    formula = (
        "class Cadrumo < Formula\n"
        '  homepage "https://github.com/nevenincs/cadrumo"\n'
        '  resource "certifi" do\n'
        '    url "https://files.pythonhosted.org/packages/ab/cd/certifi-2099.1.1.tar.gz"\n'
        "  end\n"
        '  url "https://github.com/nevenincs/cadrumo/releases/download/v0.2.1/cadrumo-0.2.1.tar.gz"\n'
        "end\n"
    )
    assert extract_pointer_version(formula, PointerFormat.HOMEBREW) == "0.2.1"


@pytest.mark.parametrize(
    ("text", "pointer_format"),
    [
        ("{not json", PointerFormat.SCOOP),
        ("[]", PointerFormat.SCOOP),
        ('{"description": "no version key"}', PointerFormat.SCOOP),
        ('{"version": ""}', PointerFormat.SCOOP),
        ('{"version": 3}', PointerFormat.SCOOP),
        ("class Cadrumo < Formula\nend\n", PointerFormat.HOMEBREW),
        ('class Cadrumo < Formula\n  url "https://example.invalid/x.tar.gz"\nend\n', PointerFormat.HOMEBREW),
    ],
)
def test_an_unreadable_pointer_refuses_rather_than_reading_as_absent(text: str, pointer_format: PointerFormat) -> None:
    """A pointer the guard cannot parse must refuse, never pass as 'no prior version'.

    This is the load-bearing failure mode: silently treating an unparseable
    pointer as absent would turn the guard off exactly when the repository state
    is unexpected — the case it exists for.
    """
    with pytest.raises(ValueError) as refusal:
        extract_pointer_version(text, pointer_format)

    # `ValueError` alone is not evidence of a refusal: `json.JSONDecodeError`
    # IS a ValueError, so an unhandled parser crash escaping the guard would
    # satisfy this test while being the opposite of what it claims. Requiring
    # the handler's own prefix proves the guard refused deliberately, and it
    # is derived from the enum so a renamed format cannot leave a stale
    # literal asserting nothing.
    message = str(refusal.value)
    assert message.startswith(f"{pointer_format.value} "), (
        f"the refusal did not come from the {pointer_format.value} handler, so this "
        f"case proves a crash rather than a refusal: {message!r}"
    )


# ---------------------------------------------------------------------------
# Monotonicity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("existing", "incoming"),
    [
        (None, "0.1.0"),
        ("0.2.1", "0.2.2"),
        ("0.2.1", "0.2.1"),
        ("0.2.9", "0.2.10"),
        ("0.2.1", "1.0.0"),
        ("1.0.0rc1", "1.0.0"),
    ],
)
def test_a_forward_or_equal_bump_is_allowed(existing: str | None, incoming: str) -> None:
    """First publication, republish, and every forward move pass."""
    assert_forward_bump(existing=existing, incoming=incoming)


@pytest.mark.parametrize(
    ("existing", "incoming"),
    [
        ("0.2.2", "0.2.1"),
        ("0.2.10", "0.2.9"),
        ("1.0.0", "0.9.9"),
        ("1.0.0", "1.0.0rc1"),
    ],
)
def test_a_backward_bump_is_refused_with_both_versions_named(existing: str, incoming: str) -> None:
    """Refusal names what is committed and what would overwrite it."""
    with pytest.raises(BackwardBumpError) as excinfo:
        assert_forward_bump(existing=existing, incoming=incoming)
    message = str(excinfo.value)
    assert existing in message
    assert incoming in message
    assert "un-publish" in message


def test_numeric_ordering_is_used_not_string_ordering() -> None:
    """0.2.10 is newer than 0.2.9; a string compare would invert exactly this pair."""
    assert_forward_bump(existing="0.2.9", incoming="0.2.10")
    with pytest.raises(BackwardBumpError):
        assert_forward_bump(existing="0.2.10", incoming="0.2.9")


@pytest.mark.parametrize(
    ("existing", "incoming"),
    [("0.2.1", "not-a-version"), ("not-a-version", "0.2.1")],
)
def test_an_unparseable_version_refuses_rather_than_comparing(existing: str, incoming: str) -> None:
    """Monotonicity that cannot be established is refused, not assumed."""
    with pytest.raises(ValueError):
        assert_forward_bump(existing=existing, incoming=incoming)


# ---------------------------------------------------------------------------
# End to end against real files, through the real CLI
# ---------------------------------------------------------------------------


def test_an_absent_pointer_is_the_first_publication(tmp_path: Path) -> None:
    """A shared repository with no manifest for this product yet passes."""
    absent = tmp_path / "bucket" / "cadrumo.json"
    assert check_pointer(absent, version="0.2.1", pointer_format=PointerFormat.SCOOP) is None


def test_scoop_backward_bump_refuses_against_a_real_committed_manifest(tmp_path: Path) -> None:
    """The real generator-shaped manifest on disk drives a real refusal."""
    pointer = tmp_path / "cadrumo.json"
    pointer.write_text(_scoop_manifest("0.3.0"), encoding="utf-8")
    with pytest.raises(BackwardBumpError):
        check_pointer(pointer, version="0.2.1", pointer_format=PointerFormat.SCOOP)


def test_homebrew_backward_bump_refuses_against_a_real_committed_formula(tmp_path: Path) -> None:
    """Same guarantee for the formula, whose version lives only in its URL."""
    pointer = tmp_path / "cadrumo.rb"
    pointer.write_text(_homebrew_formula("0.3.0"), encoding="utf-8")
    with pytest.raises(BackwardBumpError):
        check_pointer(pointer, version="0.2.1", pointer_format=PointerFormat.HOMEBREW)


def test_cli_exits_non_zero_on_a_backward_bump_and_zero_on_a_forward_one(tmp_path: Path) -> None:
    """The workflow consumes the exit status, so the exit status is the contract."""
    pointer = tmp_path / "cadrumo.json"
    pointer.write_text(_scoop_manifest("0.3.0"), encoding="utf-8")
    backward = ["--existing", str(pointer), "--version", "0.2.1", "--format", "scoop"]
    forward = ["--existing", str(pointer), "--version", "0.3.1", "--format", "scoop"]
    assert main(backward) == 1
    assert main(forward) == 0


def test_cli_exits_zero_when_no_pointer_is_committed_yet(tmp_path: Path) -> None:
    """The first publication into a freshly created shared repository is not a regression."""
    argv = ["--existing", str(tmp_path / "absent.json"), "--version", "0.2.1", "--format", "scoop"]
    assert main(argv) == 0


def test_cli_exits_non_zero_on_an_unreadable_committed_pointer(tmp_path: Path) -> None:
    """A corrupt committed pointer blocks the publication instead of being ignored."""
    pointer = tmp_path / "cadrumo.json"
    pointer.write_text("{ not json", encoding="utf-8")
    argv = ["--existing", str(pointer), "--version", "0.2.1", "--format", "scoop"]
    assert main(argv) == 1
