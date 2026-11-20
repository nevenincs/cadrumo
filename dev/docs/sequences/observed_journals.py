"""Observation of the docs check and its profile workers: the journal directory, worker script and entry points.

The generic observer lives in :mod:`dev.dependency_observation.observation`.
This module adds what only the docs engine owns: the sandbox's journal
directory beside the profile storage root, the observed profile worker script
(``observed_worker.py``) and the entry points of the check and worker
processes.
"""

from __future__ import annotations

import atexit
import os
import shutil
import tempfile
from pathlib import Path
from typing import Final

from dev.dependency_observation.observation import (
    CHILD_SCRIPT_NAME,
    JOURNAL_SUFFIX,
    Observation,
    active_observation,
    observe_process,
    populate_journal_directory,
)

#: The directory, beside a sandbox's profile storage root, that collects worker journals.
JOURNAL_DIRECTORY_NAME: Final[str] = "docs-dependency-observations"
#: The observed worker script's name, in the checkout and as copied beside the journals.
WORKER_SCRIPT_NAME: Final[str] = "observed_worker.py"

_OBSERVING_SCRIPTS: Final[dict[str, Path]] = {
    WORKER_SCRIPT_NAME: Path(__file__).with_name(WORKER_SCRIPT_NAME),
    CHILD_SCRIPT_NAME: Path(__file__).resolve().parents[2] / "dependency_observation" / CHILD_SCRIPT_NAME,
}


def prepare_worker_journals(storage_root: Path) -> Path | None:
    """Prepare the journal directory and worker script for a sandbox, when this process is observed.

    Returns:
        The directory holding the worker script copy (``observed_worker.py``)
        and the journals its workers write, or ``None`` when unobserved.
    """
    observation = active_observation()
    if observation is None:
        return None
    directory = storage_root.parent / JOURNAL_DIRECTORY_NAME
    populate_journal_directory(observation, directory, _OBSERVING_SCRIPTS)
    return directory


def observe_check(root: Path) -> Observation:
    """Observe the ``check`` process, with a journal directory of its own for children it starts itself.

    The directory sits under the checkout's ``.tmp`` and is removed when the process exits.
    """
    observation = observe_process(root)
    if observation.own_journals is None:
        scratch = observation.root / ".tmp"
        with observation.suspended():
            scratch.mkdir(exist_ok=True)
            directory = Path(tempfile.mkdtemp(prefix="docs-observed-", dir=scratch))
        atexit.register(shutil.rmtree, directory, ignore_errors=True)
        observation.own_journals = directory
        populate_journal_directory(observation, directory, _OBSERVING_SCRIPTS)
    return observation


def observe_worker(root: Path, journals: Path) -> None:
    """Observe this docs profile worker, streaming what it reads into a journal under ``journals``."""
    observation = observe_process(root)
    observation.adopt_journal_directory(journals, _OBSERVING_SCRIPTS)
    journal = (journals / f"{os.getpid()}{JOURNAL_SUFFIX}").open("a", encoding="utf-8", errors="surrogateescape")
    observation.attach_journal(journal)
