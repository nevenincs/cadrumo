---
tags:
  - '#adr'
  - '#assets-core'
date: '2026-09-24'
modified: '2026-09-24'
body_schema: 'body-v2'
body_hash: 'sha256:9a966672e91205f6c19908f595ddd360a9b26a534faedffef651b618d43b8839'
related:
  - "[[2026-09-24-assets-core-profile-indexed-object-write-path-reference]]"
  - "[[2026-09-23-assets-core-amortization-method-set-adr]]"
---

# `assets-core` adr: `The average workforce is written per year through one typed profile subject` | (**status:** `accepted`)

## Problem Statement

Authorization: the operator's standing pre-approval for this lane's work, applied by CADRUMO-ADMIN on 2026-09-24 when it assigned the average-workforce write path as plan step S13 and granted its file slots.

Job-creating and renewable self-consumption free depreciation read the
enterprise's average workforce per calendar year, which schema version 7 stores
as `irpf.plantilla_media` instances. No command or screen can write those
instances, and reads through the profile port arrive as strings the canonical
reader refuses (`2026-09-24-assets-core-profile-indexed-object-write-path-reference`).
Both frontends need one typed way to declare, list and withdraw a year, and
consumers need one typed read.

## Considerations

- A calendar year is the instance's identity; positions are storage.
- Renumbering on removal, as the descendant subject does, rewrites unrelated
  instances and races concurrent writers.
- The existing write door already validates every instance and commits by
  compare-and-swap.

## Considered options

- Extend `add-row` to non-repeatable object fields. Rejected: it addresses rows
  by position and free-form values, not by the year the law measures.
- Copy the descendant subject. Rejected: compaction renumbers instances and
  loads the record twice.
- A year-keyed subject over a shared application service. Chosen.

## Constraints

- The field, its five validators and the write-time hook are CALENDAR-owned
  and fixed by schema version 7; this decision adds no schema change.
- CLI transport tokens stay stable; the workforce value crosses the boundary as
  text and becomes a `Decimal`, never a float.

## Implementation

One application service, shared by CLI and TUI, lists the declared years,
sets a year and removes a year. Setting a declared year overwrites its three
leaves; setting a new year takes the next free index, counting cleared
indices as occupied. Removing clears the year's three leaves. Each operation
loads the record once and writes once through the existing door with the
loaded record as the compare-and-swap expectation, under a new write-door
member. The same service offers the typed read: stored strings pass through
the profile value validator before the canonical reader judges them, and the
activity-asset operations take that read beside the taxpayer-modality reader.

The CLI subject is `aeat config profile plantilla-media` with `set` (year,
average workforce, state), `list` and `remove` (year), keyed on its own
command identity `config.profile.plantilla_media.*`. The TUI adds an edit
modal to the profile manager's `irpf` panel for set and remove, wired through
the installed session like the repeatable-section rows.

## Rationale

Keying on the year makes every write address exactly the fact the law
measures, keeps other instances untouched, and lets validation refuse a
repeated year instead of a caller guessing positions. One service keeps CLI and
TUI identical and gives consumers the typed read the port lacks.

## Consequences

- The workforce incentives can be wired once a year can be declared.
- The shared command specs, four CLI catalogues, the write-door contract test
  and the cold-leaf lists change in coordinated slots.
- A future indexed object can reuse the service's index allocation and typed
  read rather than the descendant compaction.
- Authorized by the operator's coordinator on 2026-09-24 as plan step S13,
  ahead of the S11 resolver wiring.
