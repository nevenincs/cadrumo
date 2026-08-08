# TUI evaluation harness

Render any full-screen surface headlessly, drive it with real keystrokes, and
read the result as text. Built for **evaluation** — judging the operator
experience, the correctness of the projection, and the cost of a keystroke —
not for gating. It asserts nothing. The pass/fail authority stays with
`src/cadrumo/adapters/inbound/tui/tests/`.

Discardable: the whole harness is this directory plus a gitignored `.state/`.

## Use

```sh
uv run --no-sync python -m dev.tui surfaces
uv run --no-sync python -m dev.tui open setup
uv run --no-sync python -m dev.tui press down enter
uv run --no-sync python -m dev.tui type "12345678Z"
uv run --no-sync python -m dev.tui undo
```

Every command that changes the walk prints the resulting frame, so the loop is
always "gesture, look".

| command | effect |
| --- | --- |
| `open SURFACE [--size WxH] [--theme dark\|light]` | start a fresh walk |
| `press KEY...` | send key chords |
| `type TEXT` | send text one keystroke at a time |
| `fill SELECTOR VALUE` | set a value in one assignment, skipping the key pipeline |
| `click SELECTOR` | click a control |
| `show` | reprint, changing nothing |
| `undo` | drop the last gesture |
| `journal` | print the walk so far |
| `size WxH` / `theme ...` | re-render the same walk elsewhere |
| `shot [--out PATH]` | write the frame as SVG, for colour review |

## Surfaces

`setup`, `setup-modify`, `registration`, `login`, `manager`, `status`, `form`.

Each is built through the same doors the CLI uses — the real registration and
login doors, the real overview and status projections, the real setup
definition. Nothing is a stand-in, because a reading over a stand-in is a
reading about the stand-in.

## The frame

```
──────── frame 2 ──────── setup · 100x30 · dark · 443ms ────────
<the painted cells>
── focus: OptionList
── chain: OptionList → Button#btn-back → Button#btn-next → Button#btn-review
── keys:  enter=Select  escape=Anterior  f2=Resumen  ctrl+s=Guardar y salir
── eng:   mode=create pages=32 answered=1 cursor=entity-type
── eng:   page=entity-type widget=select status=unanswered required=False
── geom:  ok
```

Five bands, five different questions:

- **screen** — the cells, read off the real compositor.
- **focus / chain** — where the cursor is, and what the tab cycle contains.
- **keys** — the affordances offered *in this state*, not what the class declared.
- **eng** — what the flow engine holds. The TUI is a pure projection over
  `FlowState`, so painting and truth can disagree; printing both is what makes
  this evaluation rather than a screenshot.
- **geom** — appearance defects a structural check cannot see: content past the
  side edges, overflow that cannot scroll, a Screen scrolling because its host
  would not. Advisory readings, not assertions.

The header's `ms` is the cost of reaching the frame from a cold app.

## Why replay instead of a live session

State is the journal, not a process. Every command rebuilds the app and
replays the gestures, so a command is idempotent, a crash costs nothing, and
no daemon can go stale in a directory other campaigns write to. The journal is
also the artefact: the same walk replayed against a later tree shows what a
change did to the operator's experience.

## The profile

Four surfaces need a real profile. The harness keeps its own storage root under
`.state/` and creates one through the real registration door — real Argon2id,
real AEAD, real manifest — reusing it across sessions. It is never the
operator's root, and `.state/` is gitignored, so nothing it holds is
committable. Override the passphrase with `CADRUMO_TUI_HARNESS_PASSPHRASE`.
