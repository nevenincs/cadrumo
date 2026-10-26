---
tags:
  - '#adr'
  - '#registry-dated-validity'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:0369f6b09f9e8e102424c380d23a5ad6c66aebe9243d5e4898857e53ecf84d02'
related:
  - "[[2026-09-04-registry-dated-validity-event-date-keyed-parameters-adr]]"
  - '[[2026-08-27-registry-dated-validity-research]]'
---
# `registry-dated-validity` adr: `registry reads resolve at the application boundary` | (**status:** `accepted`)

## Problem Statement

A registry parameter is hosted on a revision, and only the filing context —
modelo, filing year and period token — names one. Domain calculators do not hold
that triple. When the sibling event-date record tried to give the bienes de
inversion figures a registry home, threading the acquisition year into the domain
functions turned out to be necessary but not sufficient: the consumer still could
not name the revision that hosts the parameter, and the modelo 303 mid-year split
for 2024 makes the period token load-bearing rather than derivable from a year.

That is not a fact about one feature. It is a question about where a registry read
belongs, and it will be asked again by every domain calculator that needs a
regulated value.

## Considerations

Measured at HEAD: revision selection has roughly thirty production call sites and
every one is in the application layer. Not one is in a domain package. Revision
selection is already, uniformly, an application responsibility, and no domain
module has ever performed one.

Three domain modules DO read registry parameters directly — the rental tier
resolver, the rental amortisation ledger, and the maternidad computation. Those
reads are legitimate: the registry package is itself domain, so the import is
intra-layer, and every read goes through the validated authority as the
authority-flow rule requires.

What is NOT sanctioned in those sites is how they name a revision. Each passes the
filing year as the revision id, which works only because modelo 100's revision
directories are exactly the years and its parameters are year-suffixed. That is a
coincidence of one modelo's naming, not a mechanism. Modelo 303 already broke it
in 2024.

## Considered options

- **Thread modelo and revision id down into the domain calculators.** Rejected. It
  would make a domain package the first in the tree to perform revision selection,
  against a thirty-site convention, and it drags a compiled snapshot type into
  arithmetic kernels that need only the numbers.

- **Let each domain module derive a revision id from a year.** Rejected. That is
  the modelo 100 coincidence generalised into a rule, and it is already false for
  modelo 303.

- **Resolve at the application boundary and pass a required, provenance-carrying
  typed bundle into the domain calculator. CHOSEN.**

## Constraints

The bundle carries no defaults and has one legitimate constructor that reads the
validated authority, so a domain function cannot be called without resolved
values and a missing parameter stays unconstructable rather than silently zero.

The refusal moves to the resolver, which is the only layer able to emit a
classified, operator-facing diagnostic. A bare raise from the domain would be
worse under no-silent-under-declaration, which wants a structured advisory rather
than an exception.

Resolved values carry their provenance — the parameter ids and the hosting
revision — into the result, so a replay or oracle can refuse a result whose
provenance disagrees with the bundle it was handed. Without that, supplying the
same bundle to both a producer and its oracle would make a wrong bundle
self-consistent and cost the oracle its independence.

The three existing domain reads are accepted and are NOT churned; they work and
are gated. What is forbidden is a fourth derivation of a revision id from a filing
year. The modelo 100 coincidence is converted into a gated precondition so that
the day that modelo splits mid-year, the failure is a loud test rather than a
resolution error in front of an operator.

## Implementation

Add a public, semantically named defining module per calculator family holding a
frozen parameter bundle with no defaults, plus a resolver that builds it from a
revision and a date context through the canonical parameter read. The bundle lives
in domain because it is registry-reading domain logic; it is CALLED from
application, which supplies the revision it selected.

Domain calculators take the bundle. Enums that currently carry values revert to
being pure classifiers.

Add the modelo 100 precondition gate asserting that every filing year that modelo
supports is a declared revision id, so the existing three sites fail loudly if
that stops being true.

## Rationale

This inverts a dependency that was never actually inverted anywhere else. The
application already holds a compiled revision at every site that needs one, so the
bundle costs no new plumbing; what it buys is that the domain stops needing a fact
it has no way to obtain.

It also preserves the property the whole campaign exists to protect. Fail-closed
survives because the bundle cannot be constructed without the registry, and the
refusal lands where it can be explained rather than merely raised.

## Consequences

Domain calculators become testable with an explicit bundle rather than a registry
fixture, and the values they use carry provenance into the result.

A fourth revision-id-from-year derivation becomes a gate failure rather than a
convention someone has to remember.

This record does not decide whether the existing three domain reads should
eventually move. They are correct today; moving them is a separate question with
its own cost.
