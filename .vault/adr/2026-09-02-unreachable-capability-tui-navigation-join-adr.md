---
tags:
  - '#adr'
  - '#unreachable-capability'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:a9b6773930b75dfa2f07d8688f206c8c6df724226487fc1e91b059072dc56bc3'
related:
  - "[[2026-09-02-unreachable-capability-research]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #adr) and one feature tag.
     Replace unreachable-capability with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     Status convention: the H1 status value is one of proposed, accepted,
     rejected, superseded, or deprecated. A new ADR starts as proposed; it
     moves to accepted or rejected when the decision is made; it becomes
     superseded when a later ADR replaces it (set by vault adr supersede,
     which also records superseded_by); and deprecated when it is retired
     without a direct successor.

     Amend vs supersede: refinements and concretization rewrite the accepted
     record's body in place (modified: carries the revision); a new ADR with
     supersession is only for a major pivot. One accepted record per
     decision.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `unreachable-capability` adr: `one tui entrypoint and a home-screen navigation join` | (**status:** `accepted`)

## Problem Statement

Five finished TUI areas ship inside the wheel and no operator can open any of
them. The reachability evidence and the per-module classification are in
`2026-09-02-unreachable-capability-research`; what that grounding cannot settle
is the decision the source itself defers. `src/cadrumo/entrypoints/tui/app.py:12`
records that every area exposes a mountable screen and every cohort gate is
green, and that the root mounts nothing because no navigation model exists.
Mounting one area makes it the whole product; mounting several without a way to
move between them offers destinations an operator cannot reach.

A second, smaller question sits in front of it. `aeat --tui [COMMAND_PATH]` is
already the accepted routing request under `2026-08-11-tui-architecture-adr`
and `2026-08-11-tui-interface-adr`, but a bare `aeat --tui` refused because the
root node carried no TUI posture, while a separate `aeat-tui` console script
started the session instead. Two spellings reached one surface and neither
reached an area.

## Considerations

- Every area is mountable and cohort-green; the blocker is design, not readiness
  (`src/cadrumo/entrypoints/tui/app.py:12`).
- The CLI may not import, load, re-export, annotate against, or register from
  the TUI; out-of-process execution is the sanctioned reference
  (`2026-08-11-tui-architecture-adr` D11).
- `src/cadrumo/entrypoints/tui/__main__.py` already ships, so a module-execution
  surface exists for a child process to target without new packaging.
- The CLI contract forbids parallel spellings for one surface, which
  `aeat-tui` beside `aeat --tui` was.
- Installed packaging already assumes `aeat` and `cadrumo-mcp` as the entry
  points (`dev/packaging/_installed_wheel_binding.py:152`).
- The frontend-capability gate refuses a full-screen request on a console that
  cannot host one, so the routing decision does not change non-terminal
  behaviour.

## Considered options

- **Mount one area as the root.** Rejected: it makes that area the product and
  strands the other four, which is the failure mode the root's own docstring
  names.
- **Command palette over an empty shell.** Rejected for now: most flexible and
  it could reuse the command-search index, but it is the largest build and it
  offers no visible inventory of what exists, which is what an operator meeting
  the product first needs.
- **Modelo as default with a key-bound switcher.** Rejected: fastest path to the
  primary task, but it implies Modelo is the whole product and buries the
  profile and credential journeys a new operator must complete first.
- **Home screen listing the areas.** Chosen. Each area pushes as a screen and
  returns home, which is exactly the shape the areas already expose.
- **Keep `aeat-tui` alongside `aeat --tui`.** Rejected: two spellings for one
  surface is the drift the CLI contract names, and no consumer required it.

## Constraints

- The join must not introduce a CLI-to-TUI import edge. The root request starts
  the session as a child interpreter against the module-execution surface.
- The home screen offers only areas whose cohort receipts are green. An area
  that regresses is removed from the home screen rather than shown broken.
- Locale keys for the home screen follow the catalogue contract: every supported
  locale carries a real translation, not a copied source string.
- The areas' files are owned by the in-flight TUI plans. This record decides the
  shape; the mounting work is executed by the plan step that awaits it,
  `W06.P13.S73` in `2026-08-11-tui-architecture-plan`, with the Modelo mount at
  `W06.P13.S92` in `2026-08-11-tui-interface-plan`.

## Implementation

Two layers, and only the first has landed.

The entrypoint layer is done. The root command node now declares an available
TUI posture, so a bare `aeat --tui` passes the routing gate instead of refusing
as unrouted. The root callback, on a bare invocation carrying the request,
starts one session and exits with its status rather than falling through to the
scripted landing surface. The session runs in a child interpreter addressed as
`python -m` against the TUI package, which keeps the sanctioned out-of-process
reference and names no TUI symbol from the CLI. The `aeat-tui` console script is
removed from packaging, and its former proof file now asserts the retirement so
a second spelling cannot return.

The navigation layer is the work this record authorises and does not perform.
The root app composes a home screen listing the five areas: profile, secret,
flows, operations and Modelo. Selecting one pushes that area's existing screen
with the session's composed operation services supplied at mount time; leaving
it returns to the home screen. The root keeps its present role as the holder of
composed services and gains no knowledge of any area's internals beyond the
screen it pushes. Nothing in the areas changes shape, because they already
expose the screens this join needs.

## Rationale

The home screen is the smallest join that makes every finished area reachable
without ranking them against each other. It matches the shape the areas already
have, so the mounting work is composition rather than redesign, and it gives an
operator meeting the product an inventory of what it can do. The palette
remains available later as a navigation accelerator over the same screens; it is
deferred rather than rejected on merit.

Retiring `aeat-tui` in the same record is deliberate. Leaving it would preserve
the parallel spelling the CLI contract forbids while the new request took over
its job, and the packaging already assumed it was gone.

## Consequences

Gains: one entrypoint reaches the full-screen product; roughly 5,700 lines of
finished operator capability across profile, secret, flows, operations and
Modelo become reachable once the navigation layer lands; the unreachable-module
audit loses its largest cluster for a real reason rather than a rooting change.

Costs: the home screen is new surface with new locale keys and its own tests.
Anyone invoking `aeat-tui` in a script must change to `aeat --tui`, which is a
breaking change to an installed console entry, taken before a public
compatibility floor exists and therefore without a shim.

Pitfall: mounting an area whose receipts are not green would put a broken
destination on the home screen, which is worse than an empty root because it
looks finished. The home screen's membership is a receipts question at mount
time, not a wish list.
