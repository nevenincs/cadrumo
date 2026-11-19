"""Run a family's commands with every Python process they start observed, and name what those processes read.

A run prepares a journal directory in scratch and hands its commands the
environment that makes every Python process below them observe itself (see
:func:`~dev.dependency_observation.observation.prepare_inherited_journals`):
the producer itself, a Python child it starts, and a Python process a declared
non-Python driver starts with the environment it inherited. After the run, the
journals give the checkout files and listings those processes read.

The family's own outputs and stamp are not inputs: a producer that reads what
it is writing would otherwise never be fresh. A run that was not completely
observed gives no reads, only the reasons, and the family is then keyed on its
observed groups whole.
"""

from __future__ import annotations

import shutil
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from ..dependency_observation.observation import InheritedJournals, harvest_inherited, prepare_inherited_journals
from ..paths import REPO_ROOT
from .location import output_directory
from .registry import FixtureFamily
from .stamps import ObservedReads, stamp_path


@dataclass(frozen=True, slots=True)
class ObservedRun:
    """One family's observed commands: the environment they run in, and what they read."""

    root: Path
    journals: InheritedJournals

    def environment(self, environment: Mapping[str, str]) -> dict[str, str]:
        """``environment`` with the entries that make every Python process below it observe itself."""
        return self.journals.environment(environment)

    def reads(
        self, family: FixtureFamily, *, cache_directory: Path | None = None
    ) -> tuple[ObservedReads | None, tuple[str, ...]]:
        """What the run's processes read, without the family's own records; or ``None`` and why it is unknown."""
        observation = harvest_inherited(self.journals, self.root)
        if observation.incomplete:
            return None, tuple(dict.fromkeys(observation.incomplete))
        own = _OwnRecords(family, self.root, cache_directory)
        files = {self._member(path): digest for path, digest in observation.files.items() if not own.file(path)}
        listings = {
            self._member(path): digest for path, digest in observation.listings.items() if not own.listing(path)
        }
        return ObservedReads(files=dict(sorted(files.items())), listings=dict(sorted(listings.items()))), ()

    def _member(self, path: Path) -> str:
        root = self.root.resolve()
        return path.relative_to(root).as_posix() if path.is_relative_to(root) else str(path)


class _OwnRecords:
    """The family's outputs, its stamp and the directories that hold its outputs, which no run reads as inputs."""

    def __init__(self, family: FixtureFamily, root: Path, cache_directory: Path | None) -> None:
        self._stamp = stamp_path(family, root, cache_directory=cache_directory).resolve()
        self._root: Path | None = None
        self._patterns: tuple[str, ...] = family.outputs
        self._directories: frozenset[Path] = frozenset()
        if family.output_root is not None:
            output_root = output_directory(family.output_root, root).resolve()
            self._root = output_root
            self._directories = frozenset(
                output_root.joinpath(*PurePosixPath(pattern).parent.parts) for pattern in family.outputs
            )

    def file(self, path: Path) -> bool:
        if path == self._stamp:
            return True
        if self._root is None or not path.is_relative_to(self._root):
            return False
        member = PurePosixPath(path.relative_to(self._root).as_posix())
        return any(member.full_match(pattern) for pattern in self._patterns)

    def listing(self, path: Path) -> bool:
        return path in self._directories or path == self._stamp.parent


@contextmanager
def observed_run(root: Path, scratch: Path) -> Generator[ObservedRun]:
    """Prepare a journal directory at ``scratch`` and remove it after the run."""
    try:
        journals = prepare_inherited_journals(scratch, observed_root=root, tooling_root=REPO_ROOT)
        yield ObservedRun(root=root, journals=journals)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
