"""Scrub secrets out of a live run as it is recorded, and refuse to write anything that still carries one.

Every string the drivers record (tool arguments, tool results, narration,
stream lines) passes through :class:`Scrubber` before it is kept. Exact values
are replaced: the run's profile password, the model credential, and every
host variable value outside the process allow-list. Only the replaced form is
ever written.

:func:`write_capture` is the one writer. It serializes a document, scrubs it
again, and sweeps it for any exact secret in any of its encodings and for
secret-shaped text. A hit refuses the write and raises: nothing is written,
not a partial file and not a redacted one. Raw streams are never kept.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Final

from dev.test_runs.paths import allocate_run_directory, test_log_root

CAPTURE_FAMILY: Final = "agent-eval"
MINIMUM_SCRUBBED_LENGTH: Final = 8
"""Shorter host values ("1", "C:") cannot be told apart from ordinary text and carry no credential."""

_SCRUBBED_PREFIX: Final = "[scrubbed:"
_SECRET_SHAPES: Final = (
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}"),
    re.compile(
        r'"(?:password|passphrase|profile_passphrase|passphrase_confirmation|secret|api_key|apikey|credential|token)"'
        r'\s*:\s*"(?!\[scrubbed:)[^"]{4,}"',
        re.IGNORECASE,
    ),
)


class CaptureLeakError(Exception):
    """A capture still carried a secret after scrubbing; nothing was written."""


def _encodings(value: str) -> tuple[str, ...]:
    """The forms a value takes in captured text: raw, JSON-escaped, and doubly escaped."""
    escaped = json.dumps(value)[1:-1]
    twice = json.dumps(escaped)[1:-1]
    return tuple(dict.fromkeys((value, escaped, twice)))


class Scrubber:
    """Replaces every known secret value with a labelled placeholder."""

    def __init__(self, secrets: Iterable[tuple[str, str]]) -> None:
        """Take ``(label, value)`` pairs; values shorter than the minimum length are ignored."""
        replacements: dict[str, str] = {}
        for label, value in secrets:
            if len(value) < MINIMUM_SCRUBBED_LENGTH:
                continue
            for form in _encodings(value):
                replacements.setdefault(form, f"{_SCRUBBED_PREFIX}{label}]")
        self._replacements = sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True)

    def add(self, label: str, value: str) -> None:
        """Learn one more secret during a run, such as a key reference issued mid-run."""
        merged = dict(self._replacements)
        if len(value) >= MINIMUM_SCRUBBED_LENGTH:
            for form in _encodings(value):
                merged.setdefault(form, f"{_SCRUBBED_PREFIX}{label}]")
        self._replacements = sorted(merged.items(), key=lambda item: len(item[0]), reverse=True)

    def scrub(self, text: str) -> str:
        """Return ``text`` with every known secret form replaced."""
        for value, placeholder in self._replacements:
            if value in text:
                text = text.replace(value, placeholder)
        return text

    def scrub_value(self, value: Any) -> Any:
        """Scrub every string inside a JSON-shaped value, keys included."""
        if isinstance(value, str):
            return self.scrub(value)
        if isinstance(value, dict):
            return {self.scrub(str(key)): self.scrub_value(item) for key, item in value.items()}
        if isinstance(value, list | tuple):
            return [self.scrub_value(item) for item in value]
        return value

    def residual(self, text: str) -> list[str]:
        """Describe every secret still present: a known value in any form, or a secret-shaped string."""
        leaks = [
            f"known secret {placeholder} still present" for value, placeholder in self._replacements if value in text
        ]
        leaks.extend(
            f"secret-shaped text matching {pattern.pattern!r}" for pattern in _SECRET_SHAPES if pattern.search(text)
        )
        return leaks


def capture_directory(label: str) -> Path:
    """Allocate this lane run's capture directory under the development ``.logs/agent-eval``."""
    path = allocate_run_directory(test_log_root(), family=CAPTURE_FAMILY, label=label)
    path.mkdir(parents=True, exist_ok=False)
    return path


def write_capture(directory: Path, name: str, document: Any, scrubber: Scrubber) -> Path:
    """Write one scrubbed JSON document, or nothing at all if any secret survives scrubbing."""
    text = scrubber.scrub(json.dumps(scrubber.scrub_value(document), indent=2, sort_keys=True, default=str))
    leaks = scrubber.residual(text)
    if leaks:
        raise CaptureLeakError(f"refused to write {name}: {'; '.join(sorted(set(leaks)))}")
    path = directory / name
    path.write_text(text + "\n", encoding="utf-8")
    return path
