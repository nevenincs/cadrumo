# TUI evaluation harness

Render any full-screen surface headlessly, drive it with real keystrokes, and
read the result as text. Built for **evaluation** — judging the operator
experience, the correctness of the projection, and the cost of a keystroke —
not for gating. It asserts nothing. The pass/fail authority stays with
`src/cadrumo/entrypoints/tui/tests/`.

Discardable: the whole harness is this directory plus a gitignored `.state/`.

## Use

```sh
uv run --no-sync python -m cadrumo.entrypoints.tui.devtools surfaces
uv run --no-sync python -m cadrumo.entrypoints.tui.devtools open manager
uv run --no-sync python -m cadrumo.entrypoints.tui.devtools press down enter
uv run --no-sync python -m cadrumo.entrypoints.tui.devtools type "12345678Z"
uv run --no-sync python -m cadrumo.entrypoints.tui.devtools undo
```

Every command that changes the walk prints the resulting frame, so the loop is
always "gesture, look". A mutating command replays before it writes: a
gesture that raises (a bad selector, an unreachable surface) is refused and
reported, and the journal on disk is left exactly as it was — it never
records a gesture that did not actually work.

| command | effect |
| --- | --- |
| `open SURFACE [--size WxH] [--theme dark\|light] [--locale es\|en\|ca\|hu]` | start a fresh walk |
| `press KEY...` | send key chords |
| `type TEXT` | send text one keystroke at a time |
| `fill SELECTOR VALUE` | set a value in one assignment, skipping the key pipeline |
| `click SELECTOR` | click a control |
| `show` | reprint, changing nothing |
| `undo` | drop the last gesture |
| `journal` | print the walk so far |
| `size WxH` / `theme ...` / `locale ...` | re-render the same walk elsewhere |
| `shot [--out PATH]` | write the frame as SVG, for colour review |

`--locale`/`locale` drives the same `OUTPUT_LANGUAGE_ENV_VAR` axis the CLI's
`--output-language` uses, so a surface can be read under `es`, `en`, `ca` or
`hu` — the walk's gestures are untouched, only the active output language
changes before the app is rebuilt. The frame header prints the active
locale (or `auto`) next to the theme.

Omit `--locale`, or set it back with `locale auto`, to leave
`CADRUMO_OUTPUT_LANGUAGE` untouched and let the render path resolve
language ambiently — from the active profile's stored preference, falling
back to the settings default. This matters for `manager`: an explicit
override always outranks the profile's preference, so forcing a locale on
that surface would permanently shadow its own language-chooser field and
make a genuine live-switch defect look identical to a working one.

## Concurrent reviewers

Set `CADRUMO_TUI_WORKSPACE` to a name of your own before any command:

```sh
export CADRUMO_TUI_WORKSPACE=rendering
```

Each workspace gets its own session journal **and** its own storage root, so
two reviewers working at once cannot clobber each other's walk or contend on
the same bucket and active-profile pointer. Without it everyone shares
`default`.

## Surfaces

`registration`, `login`, `manager`, `status`, `modelo-work-wizard`, `form`.

Each uses the canonical public profile and presentation contracts. The manager
surface exercises authenticated profile editing and logout. The Modelo wizard
surface provisions a real Modelo 130 work unit and renders the exact
application-owned flow definition over it.

## The frame

```
──────── frame 2 ──────── modelo-work-wizard · 100x30 · dark · 443ms ────────
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
