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

from ....core.external_constants import SUPPORTED_OUTPUT_LANGUAGES
from .fixture import workspace
from .journal import Click, Fill, Press, Session, Type, describe, read_session, write_session
from .replay import replay, screenshot
from .surfaces import SURFACES, resolve

SESSION_PATH = workspace() / "session.jsonl"


def _emit(text: str) -> None:
    sys.stdout.buffer.write(text.encode("utf-8", errors="replace") + b"\n")
    sys.stdout.buffer.flush()


def _show(session: Session) -> None:
    _emit(replay(session).render())


def _load() -> Session:
    return read_session(SESSION_PATH)


def _attempt(session: Session, *, refusal_note: str) -> int:
    """Replay ``session`` and persist it only once the replay has succeeded.

    Every command rebuilds the app from birth and replays the WHOLE
    gesture list, so a mutation under test here is always the LAST entry:
    every gesture before it already passed this same check on an earlier
    command. A raise during replay can therefore only originate from this
    session's own new state (the mutation itself, or pre-existing
    environmental flakiness no ordering fix changes) — never from a
    gesture that already ran clean and got silently dropped mid-walk.
    That is what makes "persist only on success" safe here: nothing this
    replay would have done differently gets lost by not writing it, because
    the app that ran it is discarded either way and no later command can
    observe a partial walk.
    """
    try:
        frame = replay(session)
    except Exception as exc:  # a harness refusal, not a bug to hide — the harness has no gate to satisfy
        _emit(f"refused: {exc}\n{refusal_note}; the session on disk is unchanged.")
        return 1
    write_session(SESSION_PATH, session)
    _emit(frame.render())
    return 0


def main(argv: list[str] | None = None) -> int:
    """Parse one command, apply it to the session, and print the frame."""
    parser = argparse.ArgumentParser(prog="python -m cadrumo.entrypoints.tui.devtools", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_open = sub.add_parser("open", help="start a fresh session on a surface")
    p_open.add_argument("surface", choices=sorted(SURFACES))
    p_open.add_argument("--size", default="100x30", help="terminal size, WxH")
    p_open.add_argument("--theme", default="dark", choices=["dark", "light"])
    p_open.add_argument(
        "--locale",
        default=None,
        choices=sorted(SUPPORTED_OUTPUT_LANGUAGES),
        help="force the output language; omit to resolve ambiently (profile preference, then default)",
    )

    p_press = sub.add_parser("press", help="send key chords")
    p_press.add_argument("keys", nargs="+")

    p_type = sub.add_parser("type", help="send literal text, one keystroke at a time")
    p_type.add_argument("text")

    p_fill = sub.add_parser("fill", help="set a widget value in one assignment")
    p_fill.add_argument("selector")
    p_fill.add_argument("value")

    p_click = sub.add_parser("click", help="click a selector")
    p_click.add_argument("selector")

    sub.add_parser("view", help="reprint the current frame, changing nothing")
    sub.add_parser("undo", help="drop the last gesture and reprint")
    sub.add_parser("journal", help="print the walk so far")
    sub.add_parser("surfaces", help="list the drivable surfaces")
    sub.add_parser("coverage", help="list each surface and the interfaces it paints at its opening frame")

    p_shot = sub.add_parser("shot", help="write the current frame as SVG")
    p_shot.add_argument("--out", default=str(workspace() / "frame.svg"))

    p_size = sub.add_parser("size", help="re-render the same walk at another terminal size")
    p_size.add_argument("size", help="WxH")

    p_theme = sub.add_parser("theme", help="re-render the same walk under the other appearance")
    p_theme.add_argument("theme", choices=["dark", "light"])

    p_locale = sub.add_parser("locale", help="re-render the same walk under another output language")
    p_locale.add_argument(
        "locale",
        choices=(*sorted(SUPPORTED_OUTPUT_LANGUAGES), "auto"),
        help="a forced language, or 'auto' to drop back to ambient resolution",
    )

    args = parser.parse_args(argv)

    if args.command == "surfaces":
        for name in sorted(SURFACES):
            surface = SURFACES[name]
            mark = " (needs profile)" if surface.needs_profile else ""
            _emit(f"{name:<14} {surface.summary}{mark}")
        return 0

    if args.command == "coverage":
        for name in sorted(SURFACES):
            declared = SURFACES[name].interfaces
            if declared:
                _emit(f"{name} {','.join(declared)}")
        return 0

    if args.command == "open":
        width, _, height = args.size.partition("x")
        resolve(args.surface)
        session = Session(
            surface=args.surface,
            width=int(width),
            height=int(height),
            theme=args.theme,
            locale=args.locale,
        )
        return _attempt(session, refusal_note="the surface did not open")

    session = _load()

    match args.command:
        case "press":
            session.gestures.append(Press(keys=tuple(args.keys)))
            return _attempt(session, refusal_note="the press was not recorded")
        case "type":
            session.gestures.append(Type(text=args.text))
            return _attempt(session, refusal_note="the type was not recorded")
        case "fill":
            session.gestures.append(Fill(selector=args.selector, value=args.value))
            return _attempt(session, refusal_note="the fill was not recorded")
        case "click":
            session.gestures.append(Click(selector=args.selector))
            return _attempt(session, refusal_note="the click was not recorded")
        case "undo":
            if not session.gestures:
                _emit("nothing to undo: the session is at its first frame")
                return 1
            session.gestures.pop()
            return _attempt(session, refusal_note="the undo was not recorded")
        case "size":
            width, _, height = args.size.partition("x")
            session.width, session.height = int(width), int(height)
            return _attempt(session, refusal_note="the resize was not recorded")
        case "theme":
            session.theme = args.theme
            return _attempt(session, refusal_note="the theme change was not recorded")
        case "locale":
            session.locale = None if args.locale == "auto" else args.locale
            return _attempt(session, refusal_note="the locale change was not recorded")
        case "view":
            _show(session)
        case "journal":
            _emit(
                f"{session.surface} · {session.width}x{session.height} · {session.theme} · {session.locale or 'auto'}",
            )
            for index, gesture in enumerate(session.gestures, start=1):
                _emit(f"{index:>3}. {describe(gesture)}")
        case "shot":
            out = Path(args.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            _emit(f"wrote {screenshot(session, str(out))}")
        case unknown:
            # The parser owns the accepted verb set; an unrecognised one here
            # means the two drifted apart, and refusing beats silent success.
            _emit(f"unknown command: {unknown}")
            return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
