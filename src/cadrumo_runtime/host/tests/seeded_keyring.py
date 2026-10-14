"""A process-local keyring that starts with the entries a test handed it, selectable in a child process.

A runtime test keeps the person's stored sign-in proof in its own in-process
keyring. A command-line child process needs the same proof to resume that
sign-in, so the test writes the entries to a file and the child selects this
backend through ``PYTHON_KEYRING_BACKEND``; it reads the file once and then
behaves like the in-memory keyring.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Final

from cadrumo.tests.explicit_keyring_selection import explicit_selection_priority
from cadrumo.tests.in_memory_keyring import InMemoryKeyring

SEEDED_KEYRING: Final = f"{__name__}.SeededKeyring"
SEED_VARIABLE: Final = "TEST_KEYRING_SEED_FILE"


class SeededKeyring(InMemoryKeyring):
    """The in-memory keyring, filled at start from the file the test named."""

    priority = explicit_selection_priority(SEEDED_KEYRING)

    def __init__(self) -> None:
        super().__init__()
        seed = os.environ.get(SEED_VARIABLE)
        if seed is not None:
            for service, username, password in json.loads(Path(seed).read_text(encoding="utf-8")):
                self.set_password(service, username, password)


def write_seed(path: Path, entries: dict[tuple[str, str], str]) -> Path:
    """Write keyring entries for a child process to start with."""
    path.write_text(json.dumps([[service, username, value] for (service, username), value in entries.items()]))
    return path
