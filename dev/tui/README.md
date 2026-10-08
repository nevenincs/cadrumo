# TUI visual inventory

Render every drivable TUI surface to disk as an image, at several terminal
geometries and under both appearances, so a human can look at them.

This is development tooling. It ships in no wheel, and the production TUI does
not know it exists.

## Boundary

`dev.tui.harness` owns pilot, replay, screenshot, surface, and fixture tooling.
It imports the shipped TUI it exercises. Production code has no reverse import
or discovery path into this package. The inventory runner starts the harness as
a subprocess so each capture gets isolated process and storage state.

## Commands

```
uv run --no-sync python -m dev.tui viewports          # the geometries a render covers
uv run --no-sync python -m dev.tui inventory          # every interface, and its coverage
uv run --no-sync python -m dev.tui render             # every surface, default matrix
uv run --no-sync python -m dev.tui render -s status -v tall -t dark
uv run --no-sync python -m dev.tui render --sequence modelo-303-first-quarter
uv run --no-sync python -m dev.tui runs               # the review runs on disk, newest first
uv run --no-sync python -m dev.tui snapshot baseline  # keep the current review under a name
uv run --no-sync python -m dev.tui rasterise --run latest --cell-height 32
uv run --no-sync python -m dev.tui diff baseline --against latest
uv run --no-sync python -m dev.tui serve              # browse the runs live from the tailnet
uv run --no-sync python -m dev.tui notes --json       # the notes left while browsing
```

`rasterise` repaints an existing run's PNGs from the SVGs it already holds,
without driving the harness at all. Those SVGs are the harness's own output
and stay valid however this tool's rasteriser changes, so fixing a rendering
defect -- or just wanting the frames at a different resolution -- costs
seconds instead of another full matrix at seconds per frame.

`render` always targets the canonical review at `runs/current`. `snapshot`
copies that review aside under a name of your choosing, and is the only way a
second run directory comes to exist -- so it is what makes the `diff` above
possible. A name already taken is refused rather than overwritten: a full
matrix costs tens of minutes and runs are gitignored, so the
snapshot is the only copy of the review it holds. `--replace` is how an
operator says the older review is finished with.

`runs` lists what is on disk, newest first, marking any run that is partial
and any whose manifest cannot be read.

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

## Modelo workbench from documentation sequences

The Modelo workbench shows its figures only for a declaration that has been
created and calculated through the registry, which no fixture surface can
supply. A
sequence scenario borrows that state from the documentation: it names a
`cli-sequence` whose committed golden already records the real CLI chain
(profile, ledger, evidence, create, calculate, verify, file), runs it once in
the documentation engine's hermetic sandbox, and checks the result against
that golden. The installed workbench is then composed over the sandbox the
way `aeat app tui` composes it, and each capture walks the operator's path on
a freshly built app: Declarations, the declaration's row, which opens its
workbench, then the keys that reach each further page (`s` for the sources
view).

Each scenario captures the Declarations list, the workbench and its sources
view, at each requested viewport and appearance, as surfaces named
`seq-<sequence>--<page>`. The manifest records, per frame, the sequence,
its documentation page, the golden's digest, and whether the run still
reproduced that golden; a frame from a run that did not says so in the index
and in the review page. Scenarios render in the sandbox's pinned English.

`render` with no filter renders the surfaces and then every scenario.
`--sequence` narrows it to the named scenarios (`all` for every scenario and
no surfaces), just as `--surface` narrows it to surfaces. The scenario table
lives in `dev/tui/harness/sequences.py`; a scenario is a sequence id plus the
modelo whose declaration it opens, and the page table there names each page's
screen and the keys that reach it.

## How the render loop handles failure

A frame can fail in more than one way, and conflating them wastes either
time or evidence:

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

## Reviewing from another device

`serve` starts a small web server for looking at the runs from a phone or
another machine on the tailnet. It asks the local `tailscale` client for this
machine's tailnet address and binds that and nothing else, because the tailnet
is its only access control; it refuses to start when Tailscale is not running
rather than fall back to the local network.
`--host 127.0.0.1` keeps it on this machine, `--port` moves it off 8740, and a
wildcard address is refused.

It does not wait for a render to finish. A render writes each PNG as it goes
and the manifest only at the end, so the server watches the `png/` directory
of every run and pushes a change to the open page as each frame lands. A frame
appears once its file has stopped changing, never half written. Start `serve`
first, then `render` in another terminal, and the page fills in over the run.

The page reviews elements, not images. A render holds each element once per
state, viewport and appearance, so its thousand-odd frames reduce to a few
dozen elements, each reviewed once:

- a workbench fixture surface, such as `home` or `ledger-overview`, across
  its fixture states (`ready`, `empty`, `stale`, `unavailable`, and the
  failing ones);
- a Modelo page from the sequence scenarios, such as `workbench` or
  `sources`, across the documentation sequences whose declarations it shows;
- a single-state screen, such as `login`.

The grid shows one card per element. Filter by review status (to review,
changed since sign-off, reviewed, open notes), by kind, by state, or by name;
the size and theme selectors choose which frame each card previews. Open an
element to flip its frame by state, size and theme -- arrow keys or a swipe
for the state, `v` for the size, `t` for the theme -- or pick any frame from
the sheet of every frame below it. `j` and `k` move between elements, and
`Reviewed, next` signs one off and opens the next in one tap on a phone.

A note belongs to the element. By default it also points at the frame on
screen when it was written, so a remark about one state at one size leads
straight back to that frame.

Notes and sign-offs are stored by the server in
`.tui-review/notes.sqlite3` (gitignored), outside the run tree, so they
survive the server stopping, a re-render and `snapshot --replace`. A note
records the element's digest over every frame it held, and the pointed
frame's image digest; a sign-off records the digest of every frame it
covered. When any frame of an element is re-rendered, added or removed, its
sign-off lapses, the element is listed as changed, and the frames that moved
are outlined so only they need a second look; nothing reads as approval of
pixels nobody has seen. The server also refuses a sign-off sent from a page
that had not yet shown the element's latest frames.

A store written before notes were kept per element is refused with a message
naming both schema versions; move it aside to start a new one.

`notes` prints the open notes grouped by element, flagging any whose element
or pointed frame has been re-rendered since; `--all` includes resolved ones
and `--json` gives a form another tool can read. `--run` names the run the
notes are compared with, `current` by default.

## Coverage

`inventory` lists every `App` and `Screen` subclass the source tree defines and
whether a render reached it. Interfaces reached only by a keystroke -- dialogs,
review screens, field-edit modals -- report as NOT RENDERED, because the
harness opens a surface and captures its first frame. That is a real gap in
coverage rather than a state to declare acceptable; closing it means teaching
the development harness to walk to those screens.
