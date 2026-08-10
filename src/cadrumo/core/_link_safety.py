"""Link-safety predicate shared by every path guard in the codebase.

A guard that refuses to follow a link into or out of a controlled tree must
ask about both reparse-point kinds Windows exposes, not just the POSIX one:
``Path.is_symlink()`` is False for a Windows directory junction, so a check
written with it alone fails open against a junction. Thirty-one sites spelled
the two-part test inline before this module existed, and the one place the
predicate was already named lived in a journal repository, unreachable from
any other package.

The neighbouring primitives -- :func:`~cadrumo.core.fsync_parent_dir`,
:func:`~cadrumo.core.exclusive_file_lock` -- are freestanding path helpers
re-exported from the package root, and this follows that shape deliberately.
"""

from __future__ import annotations

from pathlib import Path

__all__ = ["is_link_like"]


def is_link_like(path: Path) -> bool:
    """Return whether ``path`` is a symlink or a Windows junction.

    Note the asymmetry that makes this worth naming: a junction is a
    *directory-only* reparse point. A guard that already requires
    :meth:`~pathlib.Path.is_file` therefore loses nothing by testing
    ``is_symlink()`` alone, because a junction cannot satisfy ``is_file()``
    in the first place. Those sites are correct as written and are not
    defects awaiting this helper; the ones that need it are the guards over
    directories, and the guards that run before any kind is established.
    """
    return path.is_symlink() or path.is_junction()
