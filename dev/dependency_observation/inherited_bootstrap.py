"""Observe a Python process started anywhere below an observed run, then let its program run unchanged.

:func:`~dev.dependency_observation.observation.prepare_inherited_journals`
copies this file as ``sitecustomize.py`` into a directory it puts first on
``PYTHONPATH``, beside a file naming the observer's checkout and the observed
checkout. Python imports it while starting up, before the program's own main
module runs, so every Python process that inherits the run's environment,
whoever starts it, installs the dependency observer and journals what it reads.

It acts only while the environment still names the journal directory it sits
in. A process that cannot install the observer journals that fault, so the run
counts as incomplete rather than looking like one that read nothing.

This file uses the standard library only until the observer is installed.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

#: Named in ``observation``, which is unimportable before the path is set.
_JOURNALS_VARIABLE = "CADRUMO_OBSERVED_JOURNALS"
_ROOTS_FILE = "observer-roots.txt"


def _fault(journals: Path, error: BaseException) -> None:
    reason = f"bootstrap failed in process {os.getpid()}: {type(error).__name__}"
    try:
        with (journals / f"{uuid.uuid4().hex}.journal").open("w", encoding="utf-8") as journal:
            journal.write(f"B\t-\t{os.getpid()}\nX\t-\t{reason}\n")
    except OSError:
        # Neither observed nor able to say so: stop before the program runs unobserved.
        os._exit(70)


def _main() -> None:
    journals = Path(__file__).resolve().parent.parent
    named = os.environ.get(_JOURNALS_VARIABLE)
    if named is None or not named or os.path.normcase(os.path.realpath(named)) != os.path.normcase(str(journals)):
        return
    try:
        tooling, observed = (journals / _ROOTS_FILE).read_text(encoding="utf-8").splitlines()
        sys.path.insert(0, tooling)
        try:
            from dev.dependency_observation.observation import observe_inherited
        finally:
            sys.path.remove(tooling)
        observe_inherited(Path(observed), journals)
    except Exception as error:  # a fault must reach the journals, never pass for an unobserved process
        _fault(journals, error)


_main()
