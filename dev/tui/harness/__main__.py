"""The repository TUI harness command line.

Every command that changes the walk prints the resulting frame, so the
loop is always "gesture, look" with no separate read step. Output goes to
stdout as UTF-8 regardless of the console code page: a Windows terminal
defaults to cp1252 and would otherwise mangle the box-drawing characters
the surfaces are built from.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from cadrumo.core.external_constants import SUPPORTED_OUTPUT_LANGUAGES
from cadrumo.entrypoints.tui.tests.fixture import workspace

from .journal import Click, Fill, Press, Session, Type, describe, read_session, write_session
from .replay import replay, replay_with_screenshot, screenshot
from .surfaces import SURFACES, resolve

SESSION_PATH = workspace() / "session.jsonl"


def _emit(text: str) -> None:
    sys.stdout.buffer.write(text.encode("utf-8", errors="replace") + b"\n")
    sys.stdout.buffer.flush()


def _show(session: Session) -> None:
    _emit(replay(session).render())


def _load() -> Session:
    return read_session(SESSION_PATH)


def _attempt(session: Session, *, refusal_note: str, shot: Path | None = None) -> int:
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
        if shot is None:
            frame = replay(session)
        else:
            shot.parent.mkdir(parents=True, exist_ok=True)
            frame = replay_with_screenshot(session, str(shot))
    except Exception as exc:  # a harness refusal, not a bug to hide — the harness has no gate to satisfy
        _emit(f"refused: {exc}\n{refusal_note}; the session on disk is unchanged.")
        return 1
    write_session(SESSION_PATH, session)
    _emit(frame.render())
    return 0


def _capture_sequence(
    name: str,
    sizes: list[str],
    themes: list[str],
    pages: list[str] | None,
    out: Path,
) -> int:
    """Run one scenario and print its captures as a single JSON document.

    A scenario the harness can name but not produce -- an unknown page, a
    sequence that leaves no such declaration, a walk that lands elsewhere --
    is a considered answer and is reported as ``refused:``. Anything else
    dies with its traceback, which the review tooling reads as a crash.
    """
    from .sequences import ScenarioError, Shot, capture_scenario, resolve_scenario, scenario_pages, scenario_surface

    try:
        scenario = resolve_scenario(name)
    except ScenarioError as refusal:
        _emit(f"refused: {refusal}")
        return 1
    shots: list[Shot] = []
    for page in pages or scenario_pages(scenario):
        for size in sizes:
            width, _, height = size.partition("x")
            for theme in themes:
                svg = out / f"{scenario_surface(name, page)}__{width}x{height}__{theme}.svg"
                shots.append(Shot(page=page, width=int(width), height=int(height), theme=theme, svg=svg))
    try:
        provenance, frames, refusals = capture_scenario(scenario, shots)
    except ScenarioError as refusal:
        _emit(f"refused: {refusal}")
        return 1
    document = {
        "provenance": provenance.model_dump(mode="json"),
        "captures": [
            {
                "surface": frame.surface,
                "page": frame.shot.page,
                "width": frame.shot.width,
                "height": frame.shot.height,
                "theme": frame.shot.theme,
                "svg": str(frame.shot.svg),
                "screen": frame.screen,
                "frame": frame.frame_text,
            }
            for frame in frames
        ],
        "refusals": [
            {
                "surface": refused.surface,
                "page": refused.shot.page,
                "width": refused.shot.width,
                "height": refused.shot.height,
                "theme": refused.shot.theme,
                "detail": refused.detail,
            }
            for refused in refusals
        ],
    }
    _emit(json.dumps(document, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    """Parse one command, apply it to the session, and print the frame."""
    parser = argparse.ArgumentParser(prog="python -m dev.tui.harness", description=__doc__)
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
    p_open.add_argument("--shot", default=None, help="also write the opening frame as SVG to this path")

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
    sub.add_parser("sequences", help="list the sequence-backed scenarios and their pages, as JSON")

    p_sequence = sub.add_parser(
        "sequence",
        help="run a scenario's documentation sequence and capture its pages; prints the captures as JSON",
    )
    p_sequence.add_argument("scenario")
    p_sequence.add_argument("--size", action="append", required=True, help="terminal size, WxH; repeatable")
    p_sequence.add_argument("--theme", action="append", choices=["dark", "light"], help="repeatable; default both")
    p_sequence.add_argument("--page", action="append", help="capture only this page; repeatable; default all")
    p_sequence.add_argument("--out", required=True, help="directory the SVGs are written into")

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
        # Imported only here and below: the scenarios load the documentation
        # engine and the installed launcher, which every per-frame `open`
        # would otherwise pay for.
        from .sequences import SEQUENCE_SCENARIOS, page_interfaces, scenario_pages, scenario_surface

        for name, scenario in sorted(SEQUENCE_SCENARIOS.items()):
            for page in scenario_pages(scenario):
                declared = page_interfaces(page)
                if declared:
                    _emit(f"{scenario_surface(name, page)} {','.join(declared)}")
        return 0

    if args.command == "sequences":
        from .sequences import SEQUENCE_SCENARIOS, scenario_pages, scenario_surface

        listing = [
            {
                "name": name,
                "summary": scenario.summary,
                "pages": {page: scenario_surface(name, page) for page in scenario_pages(scenario)},
            }
            for name, scenario in sorted(SEQUENCE_SCENARIOS.items())
        ]
        _emit(json.dumps(listing, ensure_ascii=False))
        return 0

    if args.command == "sequence":
        return _capture_sequence(args.scenario, args.size, args.theme or ["dark", "light"], args.page, Path(args.out))

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
        return _attempt(
            session,
            refusal_note="the surface did not open",
            shot=None if args.shot is None else Path(args.shot),
        )

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
