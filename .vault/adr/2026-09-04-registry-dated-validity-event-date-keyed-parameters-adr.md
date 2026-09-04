---
tags:
  - '#adr'
  - '#registry-dated-validity'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:27dcbca602492c2ba70e283d3e9100a5452273a04257019ac775686844ec4ae4'
related:
  - "[[2026-09-04-registry-dated-validity-regulatory-constant-placement-sweep-audit]]"
---

# `registry-dated-validity` adr: `event-date keyed regulatory parameters` | (**status:** `proposed`)

## Problem Statement

A registry parameter is addressed by modelo, revision and filing period. Some
regulated values are not governed by the filing period at all: they are fixed by
the law in force when an EVENT occurred, and that event can predate every
revision the owning modelo declares.

The placement sweep measured three clusters that cannot be authored as registry
data for this reason alone. The bienes de inversion regularisation window and
divisors are fixed by the law in force at ACQUISITION, and a good acquired in
2016 stays inside its nine-year window until 2025, while modelo 303 declares
revisions only from 2022. The prorrata especial margins are sharper still: one
provision carries two values with two validity windows and two different
comparison operators, and the earlier value governs years no revision covers.
Each remains a Python literal not because nobody moved it, but because the
registry has no address for it.

## Considerations

The value-level date axis ALREADY EXISTS and is almost entirely unused. The
registry declares five axes — filing period, devengo date, transaction date,
invoice date and submission date — yet all 359 parameter values in the registry
use the filing period. Four declared axes have never been exercised.

So the missing capability is NOT the axis on the value. It is the ADDRESS of the
parameter: resolution requires naming a modelo revision, and revisions are
law-selected per filing period. Even a value correctly keyed to a transaction
date cannot be reached if no revision of that modelo exists for the year the
transaction falls in.

A working precedent already ships. The IVA rate table is a modelo-independent,
event-date-keyed value store: records carry an effective window with legal
references, and the lookup takes a member state, a rate kind and a date, with no
modelo or revision in the address at all. Its own header comment records a defect
this design already caught and corrected, where a refresh boundary had been read
as a legal effect and silently made two open years unvaluable.

Backfilling revisions was considered and rejected during remediation:
manufacturing twenty-two modelo 303 revisions to host four numbers would invent
grounding for revisions the product does not otherwise support.

## Considered options

- **Extend revision coverage backwards to span every reachable event year.
  Rejected.** It fabricates revisions to host values, and the fabricated
  grounding would be indistinguishable from real grounding to every consumer.

- **Key the value to the filing period anyway and accept the approximation.
  Rejected as legally wrong.** It applies current law retroactively to an event
  governed by earlier law, which inverts the purpose of the provisions in
  question.

- **Author for covered years and fall back to a code constant for the rest.
  Rejected.** It is the silent consumer-side fallback the authority-flow rule
  forbids, and it makes "no parameter" and "old event" indistinguishable.

- **A modelo-independent, event-date-keyed parameter space, on the shipped IVA
  rate-table pattern. CHOSEN.** Values are addressed by provision and event date
  rather than by modelo revision, carry an explicit effective window and legal
  references, and are resolved through the validated authority.

- **Leave them as leaf constants with corpus drift gates. Chosen as the interim,
  not the destination.** It is honest and cheap, and it is what stands today.

## Constraints

Resolution must fail closed. A value whose event date falls in no declared window
is a grounding defect and must raise, never fall back to a literal.

An effective window states a LEGAL effect and never a data-refresh boundary. The
IVA table's own recorded defect is the precedent: treating a refresh date as a
legal start silently made two open years unvaluable.

Every record carries its legal references and is validated against the catalogue,
so an uncatalogued or out-of-window citation is refused as it is today.

The existing filing-period parameters are unaffected. This adds an address for
values the current model cannot express; it does not migrate values the current
model holds correctly.

Consolidation stays by PROVISION, never by VALUE. Three sites in the codebase
deliberately refuse to merge values that agree today, and merging them would
introduce defects.

## Implementation

Establish a modelo-independent value space addressed by provision identity plus an
event date, modelled on the IVA rate table: an effective window per record, legal
references per record, resolution through the validated registry authority, and a
typed resolver that names its date axis explicitly at the call site.

Migrate the measured blocked clusters first, because each already has a known
provision and a known consumer: the bienes de inversion windows, threshold and
divisors, then the prorrata especial margin pair with its two operators.

The SAL figures and the maritime exemption fraction are NOT in scope here. They
are blocked by a missing period in their consumer signatures, not by the address
model, and threading a date through those functions is separate work.

Where a value stays a leaf constant pending migration, bind it with a drift gate
that reads the corpus text rather than restating the literal.

## Rationale

The sweep showed the codebase already contains its own answer twice over: values
resolved from the registry at runtime and failing closed, and a modelo-independent
dated table for exactly the case where a modelo revision is the wrong address.
This decision generalises the second pattern rather than inventing a mechanism.

It also keeps the campaign's central honesty property intact. The reason these
figures stayed in Python was never neglect — the sweep found their documentation
excellent, each citing its binding provision. They stayed because the registry
could not express them. Giving them an address removes the excuse without
weakening any refusal.

## Consequences

Filing-grade values governed by an event date become resolvable registry data with
dated windows and legal references, so they can be corrected without a code change
and cannot silently drift.

Four declared date axes stop being dead capability.

Until the space exists, the blocked clusters remain leaf constants and must not be
forced into modelo-revision parameters; the placement audit records why each is
blocked so the attempt is not repeated.

This decision does not settle where age bands and comparison margins that already
key on the filing period should live. Those are authorable today and several were
authored during remediation.
