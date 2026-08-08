"""The harness command line.

Every command that changes the walk prints the resulting frame, so the
loop is always "gesture, look" with no separate read step. Output goes to
stdout as UTF-8 regardless of the console code page: a Windows terminal
defaults to cp1252 and would otherwise mangle the box-drawing characters
the surfaces are built from.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ._fixture import workspace
from ._journal import Click, Fill, Press, Session, Type, describe, read_session, write_session
from ._replay import replay, screenshot
from ._surfaces import SURFACES, resolve

SESSION_PATH = workspace() / "session.jsonl"


def _emit(text: str) -> None:
    sys.stdout.buffer.write(text.encode("utf-8", errors="replace") + b"\n")
    sys.stdout.buffer.flush()


def _show(session: Session) -> None:
    _emit(replay(session).render())


def _load() -> Session:
    return read_session(SESSION_PATH)


def _advance(session: Session) -> None:
    write_session(SESSION_PATH, session)
    _show(session)


def main(argv: list[str] | None = None) -> int:
    """Parse one command, apply it to the session, and print the frame."""
    parser = argparse.ArgumentParser(prog="python -m dev.tui", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_open = sub.add_parser("open", help="start a fresh session on a surface")
    p_open.add_argument("surface", choices=sorted(SURFACES))
    p_open.add_argument("--size", default="100x30", help="terminal size, WxH")
    p_open.add_argument("--theme", default="dark", choices=["dark", "light"])

    p_press = sub.add_parser("press", help="send key chords")
    p_press.add_argument("keys", nargs="+")

    p_type = sub.add_parser("type", help="send literal text, one keystroke at a time")
    p_type.add_argument("text")

    p_fill = sub.add_parser("fill", help="set a widget value in one assignment")
    p_fill.add_argument("selector")
    p_fill.add_argument("value")

    p_click = sub.add_parser("click", help="click a selector")
    p_click.add_argument("selector")

    sub.add_parser("show", help="reprint the current frame, changing nothing")
    sub.add_parser("undo", help="drop the last gesture and reprint")
    sub.add_parser("journal", help="print the walk so far")
    sub.add_parser("surfaces", help="list the drivable surfaces")

    p_shot = sub.add_parser("shot", help="write the current frame as SVG")
    p_shot.add_argument("--out", default=str(workspace() / "frame.svg"))

    p_size = sub.add_parser("size", help="re-render the same walk at another terminal size")
    p_size.add_argument("size", help="WxH")

    p_theme = sub.add_parser("theme", help="re-render the same walk under the other appearance")
    p_theme.add_argument("theme", choices=["dark", "light"])

    args = parser.parse_args(argv)

    if args.command == "surfaces":
        for name in sorted(SURFACES):
            surface = SURFACES[name]
            mark = " (needs profile)" if surface.needs_profile else ""
            _emit(f"{name:<14} {surface.summary}{mark}")
        return 0

    if args.command == "open":
        width, _, height = args.size.partition("x")
        resolve(args.surface)
        session = Session(
            surface=args.surface,
            width=int(width),
            height=int(height),
            theme=args.theme,
        )
        _advance(session)
        return 0

    session = _load()

    match args.command:
        case "press":
            session.gestures.append(Press(keys=tuple(args.keys)))
            _advance(session)
        case "type":
            session.gestures.append(Type(text=args.text))
            _advance(session)
        case "fill":
            session.gestures.append(Fill(selector=args.selector, value=args.value))
            _advance(session)
        case "click":
            session.gestures.append(Click(selector=args.selector))
            _advance(session)
        case "undo":
            if not session.gestures:
                _emit("nothing to undo: the session is at its first frame")
                return 1
            session.gestures.pop()
            _advance(session)
        case "size":
            width, _, height = args.size.partition("x")
            session.width, session.height = int(width), int(height)
            _advance(session)
        case "theme":
            session.theme = args.theme
            _advance(session)
        case "show":
            _show(session)
        case "journal":
            _emit(f"{session.surface} · {session.width}x{session.height} · {session.theme}")
            for index, gesture in enumerate(session.gestures, start=1):
                _emit(f"{index:>3}. {describe(gesture)}")
        case "shot":
            out = Path(args.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            _emit(f"wrote {screenshot(session, str(out))}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
