"""One devtool frame: what is painted, what is reachable, and what the engine believes.

The five bands answer five different questions, and no one of them
substitutes for another:

- **screen** — the cells the operator sees, read off the real compositor.
- **focus** — where the cursor is and what the tab cycle contains.
- **keys** — the affordances actually offered at this moment.
- **engine** — what the flow engine holds. The TUI is a pure projection
  over ``FlowState``, so painting and truth can disagree; printing both
  side by side is what makes this evaluation rather than a screenshot.
- **geometry** — the appearance defects a structural check cannot see:
  content off the side edges, overflow that cannot scroll, a Screen that
  scrolls because its host would not.

Timing rides on the header. It is the cost of reaching this frame from a
cold app, which is the number a per-keystroke feel question turns on.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Any

from rich.console import Console
from textual.app import App
from textual.containers import ScrollableContainer
from textual.widget import Widget


def _widget_label(widget: object) -> str:
    name = type(widget).__name__
    ident = getattr(widget, "id", None)
    return f"{name}#{ident}" if ident else name


def screen_text(app: App[Any], width: int, height: int) -> str:
    """The painted cells as plain text.

    Rendered through a recording Rich console over the app's own
    compositor — the same object ``export_screenshot`` renders to SVG, so
    this is the real frame and not a re-layout of it.
    """
    console = Console(
        width=width,
        height=height,
        record=True,
        file=io.StringIO(),
        legacy_windows=False,
    )
    # The compositor IS the frame: the same object export_screenshot renders.
    console.print(app.screen._compositor, end="")
    return console.export_text(styles=False).rstrip("\n")


def focus_band(app: App[Any]) -> tuple[str, list[str]]:
    """The focused control and the full tab cycle."""
    chain = [_widget_label(w) for w in app.screen.focus_chain]
    focused = _widget_label(app.focused) if app.focused is not None else "(nothing focused)"
    return focused, chain


def key_band(app: App[Any]) -> list[str]:
    """Every binding active right now, as ``key=action`` pairs.

    Read from ``active_bindings`` rather than the declared ``BINDINGS``:
    what matters for evaluation is what is offered on THIS screen in THIS
    state, which is not always what the class declared.
    """
    offered: list[str] = []
    for key, active in app.screen.active_bindings.items():
        binding = active.binding
        if not getattr(active, "enabled", True):
            continue
        label = binding.description or binding.action
        offered.append(f"{key}={label}")
    return offered


def engine_band(app: App[Any]) -> list[str]:
    """What the flow engine holds, for a surface that has one.

    Returns an empty list for the surfaces that are not flow-driven; they
    carry no engine truth to disagree with their pixels.
    """
    definition = getattr(app, "definition", None)
    state = getattr(app, "state", None)
    if definition is None or state is None:
        return []

    from cadrumo.application.flows import page_status, visible_sequence

    sequence = list(visible_sequence(definition, state))
    answered = sum(1 for entry in sequence if state.answers.get(entry.key))
    cursor = next((e for e in sequence if e.key == state.cursor), None)

    lines = [
        f"mode={state.mode} pages={len(sequence)} answered={answered} cursor={state.cursor}",
    ]
    if cursor is not None:
        status = page_status(state, cursor.key)
        required = getattr(cursor.page, "required", None)
        lines.append(
            f"page={cursor.key} widget={getattr(cursor.page, 'widget', '?')} status={status} required={required}",
        )
    if state.verdicts:
        for key, verdict in state.verdicts.items():
            lines.append(f"verdict[{key}]={verdict}")
    return lines


def geometry_band(app: App[Any], width: int) -> list[str]:
    """Appearance defects, reported as readings rather than assertions.

    These are the same three properties the shipped visual gates prove.
    Here they are advisory: the harness reports, the reviewer judges.
    """
    findings: list[str] = []

    offenders = [
        f"{_widget_label(w)}{w.region}"
        for w in app.screen.walk_children()
        if isinstance(w, Widget) and w.display and (w.region.x < 0 or w.region.right > width)
    ]
    if offenders:
        findings.append(f"painted past the side edges: {', '.join(offenders)}")

    for host in app.screen.walk_children():
        if not isinstance(host, ScrollableContainer) or not host.display:
            continue
        if host.virtual_size.height > host.container_size.height and host.max_scroll_y <= 0:
            findings.append(
                f"{_widget_label(host)} overflows "
                f"({host.virtual_size.height} rows in {host.container_size.height}) but cannot scroll",
            )

    vertical_owners = [
        host
        for host in app.screen.walk_children()
        if isinstance(host, ScrollableContainer) and host.display and host.show_vertical_scrollbar
    ]
    if len(vertical_owners) > 1:
        findings.append(
            "multiple visible vertical scroll owners: " + ", ".join(_widget_label(host) for host in vertical_owners),
        )

    if app.screen.show_vertical_scrollbar:
        findings.append(f"{type(app.screen).__name__} itself is scrolling")

    return findings


@dataclass
class Frame:
    """One captured moment, ready to print."""

    index: int
    surface: str
    width: int
    height: int
    theme: str
    locale: str
    elapsed_ms: float
    text: str
    focused: str
    chain: list[str]
    keys: list[str]
    engine: list[str] = field(default_factory=list)
    geometry: list[str] = field(default_factory=list)

    def render(self) -> str:
        rule = "─" * 8
        out = [
            f"{rule} frame {self.index} {rule} {self.surface} · "
            f"{self.width}x{self.height} · {self.theme} · {self.locale} · {self.elapsed_ms:.0f}ms {rule}",
            self.text,
            f"── focus: {self.focused}",
            f"── chain: {' → '.join(self.chain) if self.chain else '(no focusable controls)'}",
            f"── keys:  {'  '.join(self.keys) if self.keys else '(none offered)'}",
        ]
        for line in self.engine:
            out.append(f"── eng:   {line}")
        if self.geometry:
            out.extend(f"── GEOM:  {line}" for line in self.geometry)
        else:
            out.append("── geom:  ok")
        return "\n".join(out)


def capture(
    app: App[Any],
    *,
    index: int,
    surface: str,
    width: int,
    height: int,
    theme: str,
    locale: str,
    elapsed_ms: float,
) -> Frame:
    """Read every band off a live app."""
    focused, chain = focus_band(app)
    return Frame(
        index=index,
        surface=surface,
        width=width,
        height=height,
        theme=theme,
        locale=locale,
        elapsed_ms=elapsed_ms,
        text=screen_text(app, width, height),
        focused=focused,
        chain=chain,
        keys=key_band(app),
        engine=engine_band(app),
        geometry=geometry_band(app, width),
    )


__all__ = [
    "Frame",
    "capture",
    "engine_band",
    "focus_band",
    "geometry_band",
    "key_band",
    "screen_text",
]
