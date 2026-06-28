---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-07-config-cli-profile-surface-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-event-history-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-modelo-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-apoderamientos-surface-research]]"
  - '[[2026-06-03-profile-lifecycle-cli-cascade-supersession-adr]]'
---


# `cli-workflow-redesign` adr: `Config profile use shortcut and cross-surface profile list with status` | (**status:** `superseded by [[2026-05-16-profile-lifecycle-cli-adr]]`)

> Supersession reader note: the named 2026-05-16 ADR is archived.
> Current active orientation is the `2026-05-16-profile-lifecycle-cli-plan`
> plus `2026-06-03-profile-lifecycle-cli-cascade-supersession-adr`.
> Treat the profile shortcut/list shape below as historical unless a later
> accepted profile-lifecycle authority re-enrols it.

## Problem Statement

Gestoras operating under apoderamiento switch between client profiles
many times per day. The 2026-05-07 config-cli-profile-surface ADR
defines `aeat config profile set active NAME` as the switching command,
but this is three navigation levels deep and gives no cross-surface
visibility into in-flight modelo state across profiles. The apex §2
locks active-profile safety (mandatory header on every `aeat app *`
output, 30-second switch-warning) but does not name a discoverable
short verb for switching, and `aeat config profile list` shows only
profile metadata without any indication of which profile has draft
calculations, recently filed records, or unverified work units.

## Considerations

- `set active NAME` is correct as the canonical longer form, but
  operators need a verb that is one word, easy to type, and obvious
  in help output.
- `use` is the standard verb across developer tooling for "switch
  context" (Kubernetes `kubectl use`, Git `git switch`, `nvm use`).
- Bucket event history records `profile.activated` events; combined
  with modelo lifecycle events it provides the substrate for an
  enriched profile list.
- The HARD RULE forbids a root-level `aeat switch` or `aeat use`
  shortcut. The convenience must live under `config profile`.
- Cross-surface aggregation reads (joining profile list with bucket
  events and modelo state) are not a separate root; they belong on
  the surface that owns profile listing.

## Constraints

- `aeat config profile use NAME` is an accepted command and is exactly
  equivalent to `aeat config profile set active NAME`. The two
  commands share the same code path; they are aliases.
- The `use` verb is documented as the operator-preferred form in help
  text; `set active` is documented as the explicit form.
- `aeat config profile list --with-status` extends the existing
  `aeat config profile list` verb with an opt-in column set sourced
  from bucket-event-history and modelo work-unit state.
- Without `--with-status` the existing profile-list output is
  unchanged (backward-compatible at the JSON envelope level).
- With `--with-status` the output gains, per profile row:
  `last_activated_at` (latest `profile.activated` event timestamp);
  `draft_work_units_count` (work units with at least one draft
  revision); `verified_unfiled_count` (work units with a
  `verified_complete` revision but no `filed` revision);
  `last_filed_at` (most recent `modelo.filed` event timestamp);
  `last_event_at` (most recent bucket event of any kind).
- All `--with-status` fields are derived from bucket-event-history
  and modelo repository queries; no new storage is introduced.
- No root-level `aeat switch` or `aeat use` shortcut survives.

## Implementation

Verb registration:

- Register `aeat config profile use` as an alias of `aeat config
  profile set active`. The command's help text reads "Switch the
  active profile. Alias of `set active`."
- The Typer command shares the implementation function; the alias is
  a second `@app.command("use")` decoration over the same callable.

`list --with-status` shape:

```text
aeat config profile list [--with-status] [--format json|text]
```

Implementation in `application/profile/_list.py`:

- When `--with-status` is set, query bucket-event-history for the most
  recent `profile.activated`, `modelo.filed`, and bucket event per
  profile id; query the modelo work-unit repository for draft and
  verified-unfiled counts per profile id.
- Compose the enriched row dataclass and emit through `_emit`.
- Text output renders a fixed-width status table; JSON output adds
  the named fields to each profile entry in the envelope's `profiles`
  list.

Discoverability hooks:

- `aeat config profile --help` lists `use` immediately after `set
  active` with the alias note.
- `aeat config profile set active NAME` success output footer
  includes a one-line hint: "(short form: `aeat config profile use
  NAME`)" when emitted in text format.
- `aeat app overview status` text output includes a footer hint when
  more than one profile is present: "(switch profile: `aeat config
  profile use NAME` — see `aeat config profile list --with-status`)"

## Rationale

`use` is universally understood as the switch verb in developer
tooling and reduces the cognitive load of cross-client switching for
gestoras. Keeping it as an alias of `set active` preserves the
canonical 2026-05-07 ADR grammar while delivering the short form
operators expect. `list --with-status` answers the "where is my work
across all clients?" question with one command, derived entirely from
existing bucket event history and work-unit repository data — no new
storage is required. Both additions sit under `aeat config profile`,
respecting the HARD RULE that root has only `config` and `app`.

## Consequences

- The 2026-05-07 config-cli-profile-surface ADR remains the canonical
  source for the full profile verb tree; this ADR extends it with the
  `use` alias and `--with-status` flag.
- The bucket-event-history per-service emission scope already covers
  `profile.activated` and `modelo.filed` events; no event-history
  changes are required.
- The profile application service gains a cross-surface aggregation
  query (`application/profile/_status_aggregator.py`) that joins
  bucket event history with modelo work-unit state.
- Tests must cover: `use` alias produces the same outcome as `set
  active`; `list --with-status` returns correct counts for buckets
  with draft, verified-unfiled, and filed work units; `list --with-
  status` JSON envelope is a superset of the baseline `list`
  envelope; the active-profile hint footer appears only when more
  than one profile is present.
