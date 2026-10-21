"""Copy a directory tree the way ``shutil.copytree`` does, with the per-file work run in parallel.

Assembly stages tens of thousands of dependency files, and for most of them the
copy function only confirms the previous stage's bytes and links them. That is
waiting on the filesystem, not computing, so the files are copied by a pool of
threads once every directory exists. The result is the tree ``copytree`` makes:
the same directories and the same files, links followed, ``ignore`` applied to
each directory's names, and directory metadata copied after the files.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

WORKERS = 12
"""Enough threads to keep a local disk busy with links and small copies."""


def copy_tree(
    source: Path,
    destination: Path,
    *,
    copy_function: Callable[[Path, Path], object],
    ignore: Callable[[str, list[str]], Iterable[str]] | None = None,
    workers: int = WORKERS,
) -> None:
    """Make the new ``destination`` hold ``source``'s files, each placed by ``copy_function``."""
    directories: list[tuple[Path, Path]] = []
    files: list[tuple[Path, Path]] = []
    for current, names, members in os.walk(source, followlinks=True):
        skipped = set(ignore(current, [*names, *members])) if ignore is not None else set()
        names[:] = sorted(name for name in names if name not in skipped)
        here = Path(current)
        target = destination / here.relative_to(source)
        directories.append((here, target))
        files.extend((here / name, target / name) for name in sorted(members) if name not in skipped)
    destination.mkdir(parents=True, exist_ok=False)
    for _here, target in directories:
        target.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="tree-copy") as pool:
        # Every copy is waited for, so the first failure is raised and none is left running.
        for future in [pool.submit(copy_function, source_file, target) for source_file, target in files]:
            future.result()
    for here, target in reversed(directories):
        shutil.copystat(here, target)
