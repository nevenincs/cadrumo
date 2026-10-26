"""Answer each start of the components role with a conversation the real role recorded, chosen by its command.

A surface reaches the component engine only through the shared client, which
starts the Cadrumo binary as the ``components`` role. A :class:`RoleReplay`
stands in for the process alone: each start replays, on a real pipe, the
transcript recorded for its command (:mod:`.components_role_replay`), so the
client decodes and answers real lines. A setup that carries an approved digest
is answered with the recorded setup less its review line, which is what the
engine sends under an approval: it plans, checks the network and goes on, or
reports a changed plan, without asking. Nothing here decides anything about a
component.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from .components_role_replay import TRANSCRIPTS, ReplayLaunch, transcript_lines

__all__ = ["RoleReplay"]


@dataclass
class RoleReplay:
    """Starts a replay of the transcript named for each command, and keeps every launch for the test."""

    transcripts: Mapping[str, Sequence[str]]
    """Each command's transcripts, used in turn by its successive starts; the last one repeats."""
    stall_after: Mapping[str, int] = field(default_factory=dict)
    unstartable: bool = False
    launches: list[ReplayLaunch] = field(default_factory=list)
    _used: dict[str, int] = field(default_factory=dict)

    def __call__(
        self, image: Path, arguments: Sequence[str], environment: Mapping[str, str], directory: Path
    ) -> ReplayLaunch:
        del image, directory
        if self.unstartable:
            raise OSError("the components role could not be started")
        command = arguments[2]
        names = self.transcripts[command]
        turn = self._used.get(command, 0)
        self._used[command] = turn + 1
        name = names[min(turn, len(names) - 1)]
        lines = transcript_lines(name)
        if "--approve" in arguments:
            lines = [line for line in lines if json.loads(line)["type"] != "review"]
        launch = ReplayLaunch(
            lines=lines,
            status=TRANSCRIPTS[name]["exit"],
            stall_after=self.stall_after.get(name),
            arguments=tuple(arguments),
            environment=dict(environment),
        )
        self.launches.append(launch)
        return launch

    def commands(self) -> list[tuple[str, ...]]:
        """Every start's command line after the role arguments, in order."""
        return [launch.arguments[2:] for launch in self.launches]
