# TUI visual inventory

Render every drivable TUI surface to disk as an image, at several terminal
geometries and under both appearances, so a human can look at them.

This is development tooling. It ships in no wheel, and the production TUI does
not know it exists.

## Why it drives the harness instead of importing it

The accepted TUI architecture decision makes `cadrumo.entrypoints.tui` an
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
uv run --no-sync python -m dev.tui rasterise --run latest --cell-height 32
uv run --no-sync python -m dev.tui diff baseline --against latest
```

`rasterise` repaints an existing run's PNGs from the SVGs it already holds,
without driving the harness at all. Those SVGs are the harness's own output
and stay valid however this tool's rasteriser changes, so fixing a rendering
defect -- or just wanting the frames at a different resolution -- costs
seconds instead of another full matrix at minutes per frame.

A run whose `manifest.json` was written by an older schema is refused rather
than upgraded, with a message naming both versions. Runs are gitignored and
cheap to regenerate; migration code here would be defending data that nobody
should be keeping.

`render` writes into `.tmp-tui-visual-inventory/<run>/` (gitignored):
`png/`, `svg/`, `text/`, a `manifest.json`, and an `index.md` to start reading
from. `--cell-height` raises the output resolution without changing the grid.

`diff` compares two runs on two independent axes -- the PNG digest and the
harness's own text reading -- and writes side-by-side highlight images plus
unified text diffs for the frames that moved. It exits non-zero when anything
changed, so it works as a review gate as well as a report.

## How the render loop handles failure

A frame can fail in three ways, and conflating them wastes either time or
evidence:

- **refused** -- the harness caught an application guard (an unmet profile
  readiness rule, a fixture it cannot provision) and said so. These are raised
  while building the app, before layout, so the terminal geometry cannot change
  the answer. The frame is recorded, and the surface's remaining frames are
  recorded as *not attempted* rather than re-asked. Re-asking cost twenty
  minutes per run on a surface that can never open. `--no-skip-refused` forces
  every frame anyway.
- **crashed** -- the harness process died with a raw traceback. Nothing caught
  it, so it is not a considered answer: an import error from a peer's
  half-finished edit in a shared worktree is the common case here, and it is
  usually gone on the next attempt. Retried (`--retries`, default 1).
- **raster** -- the harness produced a frame this tool could not repaint. Never
  retried; the SVG on disk will be identical next time.

Nothing that failed is dropped. The manifest keeps `failures` and `skipped`
separately, `blocked_surfaces` names any surface that produced no frame at all,
and the index prints all three. A run that quietly stops mentioning what it
gave up on is indistinguishable from a run that was never asked for it.

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
