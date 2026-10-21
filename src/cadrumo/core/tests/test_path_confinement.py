"""Real-filesystem proof of the host-path confinement guard.

Every case builds the files, directories and links it needs in a temporary
directory and drives the guard against them. Nothing is patched: a refusal is
the guard meeting a real link, a real replaced file or a real oversized file.
Where a platform offers a different way to make the same obstruction, the test
picks that way and still asserts the refusal.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from ..path_confinement import (
    HostPathRefusal,
    confined_directory_refusal,
    host_path_form_refusal,
    opened_confined_file,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_CEILING = 1024
_CONTENT = b"%PDF-synthetic evidence"


def _link_directory(link: Path, target: Path) -> None:
    """Create the kind of directory link any account on this platform may create."""
    if sys.platform == "win32":
        import _winapi

        _winapi.CreateJunction(str(target), str(link))
    else:
        os.symlink(target, link, target_is_directory=True)


def _read(path: Path, *, root: Path | None = None, max_bytes: int = _CEILING) -> bytes | HostPathRefusal:
    with opened_confined_file(path, max_bytes=max_bytes, root=root) as opened:
        return opened if isinstance(opened, HostPathRefusal) else opened.read_bytes()


def _tree(tmp_path: Path) -> tuple[Path, Path]:
    """Return an allowed root holding one document and a sibling directory outside it."""
    root = tmp_path / "allowed"
    (root / "inbox").mkdir(parents=True)
    (root / "inbox" / "document.pdf").write_bytes(_CONTENT)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.pdf").write_bytes(b"outside the root")
    return root, outside


def test_a_file_inside_the_root_is_read_through_its_handle(tmp_path: Path) -> None:
    root, _outside = _tree(tmp_path)

    assert _read(root / "inbox" / "document.pdf", root=root) == _CONTENT
    assert _read(root / "inbox" / "document.pdf") == _CONTENT
    assert confined_directory_refusal(root / "inbox", root=root) is None
    assert confined_directory_refusal(root, root=root) is None


def test_a_path_outside_the_root_is_refused(tmp_path: Path) -> None:
    root, outside = _tree(tmp_path)

    assert _read(outside / "secret.pdf", root=root) is HostPathRefusal.OUTSIDE_ROOT
    assert confined_directory_refusal(outside, root=root) is HostPathRefusal.OUTSIDE_ROOT
    assert confined_directory_refusal(tmp_path, root=root) is HostPathRefusal.OUTSIDE_ROOT


def test_parent_traversal_is_refused_even_when_it_would_land_inside(tmp_path: Path) -> None:
    root, _outside = _tree(tmp_path)
    escaping = root / "inbox" / ".." / ".." / "outside" / "secret.pdf"
    returning = root / "inbox" / ".." / "inbox" / "document.pdf"

    assert escaping.is_file()
    assert _read(escaping, root=root) is HostPathRefusal.TRAVERSAL
    assert _read(returning, root=root) is HostPathRefusal.TRAVERSAL
    assert _read(returning) is HostPathRefusal.TRAVERSAL
    assert confined_directory_refusal(root / "inbox" / ".." / ".." / "outside", root=root) is HostPathRefusal.TRAVERSAL


def test_a_relative_path_is_refused_and_never_resolved_against_the_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _outside = _tree(tmp_path)
    monkeypatch.chdir(root)
    relative = Path("inbox") / "document.pdf"

    assert relative.is_file()
    assert host_path_form_refusal(relative) is HostPathRefusal.RELATIVE
    assert _read(relative, root=root) is HostPathRefusal.RELATIVE
    assert _read(relative) is HostPathRefusal.RELATIVE
    assert confined_directory_refusal(Path("inbox"), root=root) is HostPathRefusal.RELATIVE


def test_a_directory_link_beneath_the_root_that_points_outside_is_refused(tmp_path: Path) -> None:
    root, outside = _tree(tmp_path)
    _link_directory(root / "escape", outside)
    through_link = root / "escape" / "secret.pdf"

    assert through_link.read_bytes() == b"outside the root"
    assert _read(through_link, root=root) is HostPathRefusal.REDIRECTED
    assert confined_directory_refusal(root / "escape", root=root) is HostPathRefusal.REDIRECTED
    assert confined_directory_refusal(root / "escape" / "not-created-yet", root=root) is HostPathRefusal.REDIRECTED


def test_a_link_whose_target_is_missing_still_redirects(tmp_path: Path) -> None:
    root, outside = _tree(tmp_path)
    target = outside / "later"
    target.mkdir()
    _link_directory(root / "dangling", target)
    target.rmdir()

    assert confined_directory_refusal(root / "dangling" / "captures", root=root) is HostPathRefusal.REDIRECTED


def test_a_file_that_is_a_link_out_of_its_own_directory_is_refused(tmp_path: Path) -> None:
    root, outside = _tree(tmp_path)
    named = root / "inbox" / "linked.pdf"
    try:
        os.symlink(outside / "secret.pdf", named)
    except OSError:
        # This account may not create file links here. A directory link one
        # level up puts the same redirect in front of the same open.
        _link_directory(root / "redirected", outside)
        assert _read(root / "redirected" / "secret.pdf", root=root) is HostPathRefusal.REDIRECTED
        return

    assert named.read_bytes() == b"outside the root"
    assert _read(named) is HostPathRefusal.REDIRECTED
    assert _read(named, root=root) is HostPathRefusal.REDIRECTED


def test_only_a_regular_file_is_opened(tmp_path: Path) -> None:
    root, _outside = _tree(tmp_path)

    assert _read(root / "inbox", root=root) is HostPathRefusal.NOT_REGULAR_FILE
    assert _read(root / "inbox") is HostPathRefusal.NOT_REGULAR_FILE
    assert _read(root, root=root) is HostPathRefusal.NOT_REGULAR_FILE
    assert _read(root / "inbox" / "absent.pdf", root=root) is HostPathRefusal.NOT_FOUND
    assert _read(tmp_path / "absent-directory" / "document.pdf") is HostPathRefusal.NOT_FOUND
    if sys.platform != "win32":
        pipe = root / "inbox" / "pipe"
        os.mkfifo(pipe)
        assert _read(pipe, root=root) is HostPathRefusal.NOT_REGULAR_FILE


def test_the_size_ceiling_holds_at_open_and_for_the_bytes_actually_read(tmp_path: Path) -> None:
    root, _outside = _tree(tmp_path)
    exact = root / "inbox" / "exact.pdf"
    exact.write_bytes(b"x" * _CEILING)
    oversized = root / "inbox" / "oversized.pdf"
    oversized.write_bytes(b"x" * (_CEILING + 1))
    growing = root / "inbox" / "growing.pdf"
    growing.write_bytes(b"x" * _CEILING)

    assert _read(exact, root=root) == b"x" * _CEILING
    assert _read(oversized, root=root) is HostPathRefusal.TOO_LARGE
    with opened_confined_file(growing, max_bytes=_CEILING, root=root) as opened:
        assert not isinstance(opened, HostPathRefusal)
        with growing.open("ab") as appender:
            appender.write(b"y")
        assert opened.read_bytes() is HostPathRefusal.TOO_LARGE


def test_replacing_the_path_after_the_open_does_not_change_what_is_read(tmp_path: Path) -> None:
    root, outside = _tree(tmp_path)
    named = root / "inbox" / "document.pdf"
    replacement = tmp_path / "replacement.pdf"
    replacement.write_bytes(b"swapped in after the check")

    with opened_confined_file(named, max_bytes=_CEILING, root=root) as opened:
        assert not isinstance(opened, HostPathRefusal)
        if sys.platform == "win32":
            # The open handle denies deletion, so the path cannot be replaced at all.
            with pytest.raises(PermissionError):
                os.replace(replacement, named)
        else:
            os.replace(replacement, named)
            (root / "inbox").rename(root / "moved-away")
            os.symlink(outside, root / "inbox", target_is_directory=True)
            assert (root / "inbox" / "secret.pdf").read_bytes() == b"outside the root"
            assert not named.exists()
        assert opened.read_bytes() == _CONTENT
        assert opened.read_bytes() == _CONTENT


def test_directory_confinement_accepts_what_is_really_inside_and_refuses_a_file_in_the_way(tmp_path: Path) -> None:
    root, _outside = _tree(tmp_path)

    assert confined_directory_refusal(root / "captures" / "2025", root=root) is None
    assert not (root / "captures").exists()
    behind_a_file = confined_directory_refusal(root / "inbox" / "document.pdf" / "nested", root=root)
    assert behind_a_file is HostPathRefusal.NOT_DIRECTORY
    assert confined_directory_refusal(tmp_path / "absent-root" / "captures", root=tmp_path / "absent-root") is None


def _ambiguous_forms(root: Path) -> list[tuple[Path, HostPathRefusal]]:
    """Return path spellings this platform would resolve to something other than they say."""
    if sys.platform == "win32":
        inside = root / "inbox" / "document.pdf"
        share_alias = Path(f"\\\\localhost\\{root.drive[0]}$" + str(root)[len(root.drive) :]) / "inbox" / "document.pdf"
        return [
            (Path(f"{root.drive}inbox\\document.pdf"), HostPathRefusal.RELATIVE),
            (Path("\\inbox\\document.pdf"), HostPathRefusal.RELATIVE),
            (Path("\\\\.\\" + str(inside)), HostPathRefusal.UNSUPPORTED_FORM),
            (Path("\\\\?\\GLOBALROOT\\Device\\Null"), HostPathRefusal.UNSUPPORTED_FORM),
            (Path(str(inside) + ":stream"), HostPathRefusal.UNSUPPORTED_FORM),
            (Path(str(inside) + "::$DATA"), HostPathRefusal.UNSUPPORTED_FORM),
            (root / "inbox" / "document.pdf.", HostPathRefusal.UNSUPPORTED_FORM),
            (root / "inbox" / "NUL", HostPathRefusal.UNSUPPORTED_FORM),
            (root / "inbox" / "con.pdf", HostPathRefusal.UNSUPPORTED_FORM),
            (share_alias, HostPathRefusal.OUTSIDE_ROOT),
        ]
    return [
        (Path("inbox/document.pdf"), HostPathRefusal.RELATIVE),
        (Path(str(root / "inbox") + "/document.pdf\x00.txt"), HostPathRefusal.UNSUPPORTED_FORM),
        (Path("//" + str(root).lstrip("/")) / "inbox" / "document.pdf", HostPathRefusal.OUTSIDE_ROOT),
    ]


def test_path_forms_that_name_something_else_are_refused_before_any_open(tmp_path: Path) -> None:
    root, _outside = _tree(tmp_path)
    forms = _ambiguous_forms(root)

    assert forms
    for path, expected in forms:
        assert _read(path, root=root) is expected, str(path)
        assert confined_directory_refusal(path, root=root) is expected, str(path)


def test_a_plain_absolute_path_passes_the_form_check(tmp_path: Path) -> None:
    root, _outside = _tree(tmp_path)

    assert host_path_form_refusal(root / "inbox" / "document.pdf") is None
    assert host_path_form_refusal(root / "not created" / "résumé (final).pdf") is None
