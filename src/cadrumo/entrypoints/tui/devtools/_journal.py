"""The session journal: the only state this canonical devtool keeps.

A session is a header plus an ordered list of operator gestures. Nothing
else persists, and no process stays alive between commands: every command
rebuilds the app from birth and replays the gestures in order. That makes
each command idempotent, makes a crash cost nothing, and makes the journal
itself the artefact — the same walk can be replayed against a later tree to
see what the change did to the operator's experience.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from ....core.external_constants import UTF_8_ENCODING

_STRICT = ConfigDict(frozen=True, extra="forbid")


class Press(BaseModel):
    """Key chords delivered through the real key pipeline."""

    model_config = _STRICT
    kind: Literal["press"] = "press"
    keys: tuple[str, ...]


class Type(BaseModel):
    """Literal text, delivered one keystroke at a time.

    Character by character on purpose: live validation, answer echo and
    passphrase banding all fire per keystroke, and setting the value in
    one assignment would skip exactly the behaviour under evaluation.
    """

    model_config = _STRICT
    kind: Literal["type"] = "type"
    text: str


class Fill(BaseModel):
    """Set a widget value in one assignment, bypassing the key pipeline.

    The fast path for a long passphrase whose per-keystroke behaviour is
    not what is being looked at. It is recorded distinctly from
    :class:`Type` so a replay never misreports which path produced a value.
    """

    model_config = _STRICT
    kind: Literal["fill"] = "fill"
    selector: str
    value: str


class Click(BaseModel):
    """A mouse click on a selector."""

    model_config = _STRICT
    kind: Literal["click"] = "click"
    selector: str


Gesture = Annotated[Press | Type | Fill | Click, Field(discriminator="kind")]


class Session(BaseModel):
    """One evaluation walk over one surface."""

    model_config = ConfigDict(extra="forbid")

    surface: str
    width: int = 100
    height: int = 30
    theme: str = "dark"
    locale: str | None = None
    """An explicit output-language override, or ``None`` for ambient resolution.

    ``None`` leaves ``CADRUMO_OUTPUT_LANGUAGE`` untouched, so the render path
    resolves language the way an operator's real session would: from the
    active profile's stored preference, falling back to the settings
    default. Forcing this to a language on every walk would make an explicit
    Settings override permanently shadow a profile-level language change —
    exactly the axis the ``manager`` surface's language chooser needs to be
    read live, since an explicit override always outranks the profile's
    preference in :func:`~cadrumo.core.i18n.output_language`'s resolution
    order.
    """
    gestures: list[Gesture] = Field(default_factory=list)

    @property
    def size(self) -> tuple[int, int]:
        return (self.width, self.height)


def read_session(path: Path) -> Session:
    """Load a session, or refuse in a way that names the fix."""
    if not path.exists():
        message = f"no open session at {path}: run `open <surface>` first"
        raise FileNotFoundError(message)
    lines = [line for line in path.read_text(encoding=UTF_8_ENCODING).splitlines() if line.strip()]
    header = json.loads(lines[0])
    gestures = [json.loads(line) for line in lines[1:]]
    return Session.model_validate({**header, "gestures": gestures})


def write_session(path: Path, session: Session) -> None:
    """Persist a session as one header line plus one line per gesture."""
    path.parent.mkdir(parents=True, exist_ok=True)
    header = session.model_dump(mode="json", exclude={"gestures"})
    lines = [json.dumps(header, ensure_ascii=False)]
    lines.extend(json.dumps(g.model_dump(mode="json"), ensure_ascii=False) for g in session.gestures)
    path.write_text("\n".join(lines) + "\n", encoding=UTF_8_ENCODING, newline="\n")


def describe(gesture: Gesture) -> str:
    """One-line human rendering of a gesture, for the `journal` command."""
    match gesture:
        case Press():
            return f"press {' '.join(gesture.keys)}"
        case Type():
            return f"type {gesture.text!r}"
        case Fill():
            return f"fill {gesture.selector} = {gesture.value!r}"
        case Click():
            return f"click {gesture.selector}"
    return repr(gesture)


__all__ = [
    "Click",
    "Fill",
    "Gesture",
    "Press",
    "Session",
    "Type",
    "describe",
    "read_session",
    "write_session",
]
