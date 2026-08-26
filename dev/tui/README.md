# TUI visual inventory

Render every drivable TUI surface to disk as an image, at several terminal
geometries and under both appearances, so a human can look at them.

This is development tooling. It ships in no wheel, and the production TUI does
not know it exists.

## Why it drives the harness instead of importing it

`2026-08-11-tui-architecture-adr` D11 makes `cadrumo.entrypoints.tui` an
outermost entrypoint that no development tool may import, load, re-export,
annotate against, or register from, and places pilot, replay, screenshot and
surface tooling inside `cadrumo.entrypoints.tui.devtools`. Out-of-process
execution is the only external reference it sanctions.

So this package owns none of that. It runs the in-boundary harness as a
subprocess, rasterises the SVG that harness writes, and reads the source tree
as text to enumerate what exists. A test in `tests/` fails if any module here
grows an import of the TUI package.

## Commands

```
uv run --no-sync python -m dev.tui viewports          # the geometries a render covers
uv run --no-sync python -m dev.tui inventory          # every interface, and its coverage
uv run --no-sync python -m dev.tui render             # every surface, default matrix
uv run --no-sync python -m dev.tui render -s status -v tall -t dark
uv run --no-sync python -m dev.tui diff baseline --against latest
```

`render` writes into `.tmp-tui-visual-inventory/<run>/` (gitignored):
`png/`, `svg/`, `text/`, a `manifest.json`, and an `index.md` to start reading
from. `--cell-height` raises the output resolution without changing the grid.

`diff` compares two runs on two independent axes -- the PNG digest and the
harness's own text reading -- and writes side-by-side highlight images plus
unified text diffs for the frames that moved. It exits non-zero when anything
changed, so it works as a review gate as well as a report.

## Reading the artefacts

- A blank box in a PNG may be a glyph the pinned Cascadia Mono lacks rather
  than a defect in the surface. Each frame's `missing_glyphs` in the manifest
  says which characters those were.
- `geometry_findings` carries the harness's own advisory readings (content
  painted past the edges, overflow that cannot scroll, competing scroll
  owners). They are readings, not assertions; the reviewer judges.
- A surface whose content includes a clock -- session deadlines on the status
  page -- differs between runs by construction, so `diff` will report it as
  changed every time. That is the surface being non-deterministic, not the
  tool being wrong. The harness's own build-cost stamp is a different case
  and is redacted from the diffed text into the manifest's `elapsed_ms`:
  that number is this tool's noise rather than the surface's behaviour, and
  left in it would mark every frame changed on every run.
- The `form` surface is declared SYNTHETIC by the harness. Do not read
  findings off its field content.

## Coverage

`inventory` lists every `App` and `Screen` subclass the source tree defines and
whether a render reached it. Interfaces reached only by a keystroke -- dialogs,
review screens, field-edit modals -- report as NOT RENDERED, because the
harness opens a surface and captures its first frame. That is a real gap in
coverage rather than a state to declare acceptable; closing it means teaching
the in-boundary harness to walk to those screens.
