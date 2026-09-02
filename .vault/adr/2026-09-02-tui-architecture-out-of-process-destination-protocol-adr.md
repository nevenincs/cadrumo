---
tags:
  - '#adr'
  - '#tui-architecture'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:89985e9cc24effff727f10131a9e626b3fda61c15b8a221d5a8ea0cd31143c79'
related:
  - "[[2026-08-11-tui-architecture-adr]]"
  - "[[2026-09-02-unreachable-capability-tui-navigation-join-adr]]"
  - "[[2026-09-02-gate-integrity-adjudication-tui-entrypoint-contracts-adr]]"
  - "[[2026-09-02-cli-distribution-consolidation-adr]]"
  - '[[2026-09-02-gate-integrity-adjudication-research]]'
  - '[[2026-08-30-ci-lane-deconflation-cli-imports-tui-adr-d11-breach-audit]]'
---

# `tui-architecture` adr: `the out-of-process protocol that opens a full-screen destination` | (**status:** `accepted`)

## Problem Statement

Two CLI commands opened a full-screen surface by importing the dedicated TUI and
constructing its Textual applications in the CLI process. `modelo work review`
built a review record and handed the live object to a review host; `modelo work
select` handed a live work-unit tuple to a picker, read the chosen identifier
back as a return value, then admitted a workspace session and hosted a screen,
returning the refusal condition when admission declined.

`2026-09-02-gate-integrity-adjudication-tui-entrypoint-contracts-adr` adjudicated
those five import edges as a code defect rather than a stale contract, kept both
prohibitions unweakened, and handed the repair to the lane owning the TUI tree.
It also stated why the repair is not a call-site edit: neither crossing survives
a naive move to a child process, because one direction carries a built domain
record and the other carries a value read back out. A protocol has to be decided
before any call site can change.

## Considerations

- `2026-08-11-tui-architecture-adr` D11 forbids any backend package or sibling
  entrypoint from importing, loading, re-exporting, annotating against, or
  registering from the TUI, and names out-of-process execution as the sanctioned
  external reference.
- `2026-09-02-unreachable-capability-tui-navigation-join-adr` restates the same
  prohibition as a hard constraint on the very join the consolidation created.
- The consolidation's own session bridge at `src/cadrumo/entrypoints/cli/_tui_session.py`
  already keeps the boundary for the root request: it names the TUI by module
  string and executes it with `python -m`. It is the pattern to extend, not a
  competing one.
- The child inherits the requester's streams, because a full-screen session must
  own the terminal for its lifetime. That rules standard output out as a result
  channel: anything the child printed would land in front of the operator,
  interleaved with the session's terminal control sequences.
- A selection outcome is a string, so an exit status cannot carry it. Four
  outcomes have to stay distinguishable: a destination that returns nothing
  completing, a picker returning a choice, an operator leaving without choosing,
  and a workspace declining to admit the choice.
- `aeat-cli-contract` holds that transport is stable machine tokens and localized
  prose is output, never protocol. A workspace refusal's reconsideration
  condition is localized prose the operator must still see.
- The TUI's launcher is the sole TUI module permitted to wire concrete adapters,
  so any subject the child re-resolves has to be composed there.

## Considered options

**Serialise the domain record across the boundary.** Rejected. It would make the
rendered surface a projection of what a sibling entrypoint held earlier rather
than a read of current persistence, and it would give the record a second wire
shape to keep in step with the typed one.

**Carry the outcome on the child's exit status alone.** Rejected. A status cannot
carry a work-unit identifier, and squeezing four outcomes into small integers
makes a session that crashed indistinguishable from one an operator cancelled.

**Carry the outcome on the child's standard output.** Rejected on mechanism. The
child inherits the terminal so the parent cannot capture that stream without
taking the terminal away from the session it just started.

**Duplicate the wire vocabulary in each entrypoint package.** Rejected. Neither
package may import the other, so two copies would agree only until one was
edited, and the drift would surface as a session that silently opened the wrong
destination.

**A shared protocol module beside both entrypoint packages, arguments inward and
an outcome file outward.** Chosen.

## Constraints

- The protocol module may not live inside either entrypoint package: one
  direction is forbidden by the backend prohibition and the other by the sibling
  prohibition. It sits in the parent `entrypoints` package, alongside the adapter
  and operation composition modules both frontends already share.
- The child must compose its own adapter scope. It is a fresh interpreter, so
  nothing the requesting process bound is available to it.
- Output language is process state, not inherited. An explicit language selection
  on the requesting command has to travel as a token or the child renders in a
  different locale from the envelope beside it.
- The requesting command still reads the work-unit list itself for its
  machine-readable envelope, so a picker invocation reads the catalogue twice,
  once per process. That is the boundary's cost and it is accepted.
- A headless proof of a destination cannot depend on provisioned work without
  making the proof a profile fixture, so the self-test invocation of the picker
  offers an empty catalogue - a state the picker already renders honestly.

## Implementation

One module in the shared `entrypoints` package owns the crossing: the closed set
of requestable destination tokens, the closed set of outcome tokens, the argument
surface, and the render and parse functions for both a request and an outcome
record. The destination tokens are the canonical command identities the
requesting commands already emit in their envelopes, so a destination has one
spelling product-wide rather than a transport-only alias.

Inward, a request carries the destination token, the file the outcome is written
to, and identifiers only: work-unit id, bucket id, an include-discarded flag, an
output-language token, and the self-test flag. The child re-resolves the subject
those identifiers name, so every rendered surface is read from persistence in the
process that renders it.

Outward, the child writes one outcome record - an outcome token plus an optional
work-unit id and an optional localized detail - into the file the request names.
The record is JSON rather than the product's tab-separated line grammar, because
the detail field carries operator prose whose own tabs and newlines would
otherwise be indistinguishable from record structure. Behaviour branches only on
the token; the detail is something the requester renders. The record is written
only on a completed session: a non-zero child status leaves no record, so a
failure cannot arrive at the requester as a cancellation.

The TUI's module-execution surface gains the argument surface and dispatches on
it. Without a destination it starts the root session exactly as before. With one
it runs a destination session module that resolves the subject through new
launcher composition seams, opens the destination, and records the outcome. The
picker-to-workspace chain moves wholly inside that session, because which
destination a selection reaches is the frontend's own routing decision and
splitting it across the boundary would relocate that decision into the CLI.

On the requesting side the session bridge gains a destination call that allocates
a scratch directory for the outcome record, spawns the child, and parses the
record back. Both commands keep their existing substitution seam: the private
function each one calls now opens the out-of-process session instead of
constructing an application, and the resolution and envelope logic around it is
untouched.

## Rationale

The knockout criterion is that the protocol has exactly one definition while
being owned by neither entrypoint. Every alternative either duplicates the
vocabulary across a boundary that forbids the two sides from checking each other,
or forces one package to import the other, which is the dependency the whole
boundary exists to prevent. Placing it in the parent package resolves both, and
it is not a new pattern: the adapter and operation composition modules already
live there for the same reason.

The outcome file wins over the two channels that look simpler because the
mechanism decides it, not taste. Standard output is not available at all while
the child owns the terminal, and an exit status cannot carry an identifier. Once
a file is the channel, keeping the record structured and the tokens closed costs
nothing and buys fail-closed parsing at both ends.

Sending identifiers rather than records is what makes the repair an improvement
over the in-process version rather than a like-for-like port. The old code
rendered whatever the CLI had already built; the new code reads the subject in the
process that shows it, so the surface cannot display a record that has since
changed underneath it.

## Consequences

The production prohibition the adjudication preserved is now kept by the code
rather than merely reported against it. The CLI names no TUI symbol anywhere, and
the full-screen frontend stays an outermost process entrypoint.

The crossing is proven by execution, not by import. A real child process runs the
picker destination headless, mounts it, leaves, writes its outcome, and exits
clean; refused requests - an unknown destination token, a missing outcome file, a
missing or malformed subject - fail closed and leave no record at all.

The costs are honest and small. A picker invocation reads the work-unit catalogue
once per process. Starting a destination now pays interpreter startup, which an
in-process call did not. And a destination that wants to return something new has
to extend the protocol rather than change a return type, which is more ceremony
per change and is exactly the friction that keeps the boundary visible.

The pattern generalises: a third command needing a full-screen destination adds a
token to the closed set and a session to the dispatch table, and gets the same
argument surface, the same outcome vocabulary, and the same fail-closed parsing
without touching either entrypoint's knowledge of the other.
