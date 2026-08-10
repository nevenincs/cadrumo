---
tags:
  - '#exec'
  - '#current-schema-only-purge'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:7983617ab7d228e7bacca081fded301a33ad30e489ac1aaaa515c34e910a237a'
step_id: 'S21'
related:
  - "[[2026-08-10-current-schema-only-purge-plan]]"
---

# Require result_disposition for applicable official Modelo 303 observation payloads

## Scope

- `src/cadrumo/application/calculations/_observations_repository.py`

## Description

- Screen every prepared observation envelope for a resolved result disposition,
  rather than only those routed through the opt-in carry ingress.
- Scope the refusal to official, carry-capable Modelo 303 payloads, reading
  carry-capability from the payload's own declared casillas.
- Site the predicate in the module that already owns Modelo 303 carry policy.
- Correct the docstring sentence that described the tolerance as intent.

## Outcome

Landed in `25a22cb` with its proof step, after a design ruling.

The guard was not missing. It existed, was correct, and was OPT-IN: reachable only
by passing a flag that defaults to false, so the generic storage path persisted
official Modelo 303 carry evidence with no resolved disposition. A safety
mechanism switched off by default is off in exactly the cases nobody thought
about, which is the population it exists for.

A documented sentence appeared to sanction this, saying generic storage
intentionally remains readable for legacy evidence and unrelated consumers. The
implementer declined to delete a documented contract in a regulated path, which
was the right call, and the ruling collapsed it on a fact neither of us had
invoked: this tree is pre-release with no released data, so "legacy evidence"
has no referent -- no older version of this application wrote anything. What
remained of the sentence was "unrelated consumers", meaning other modelos and
sources with no disposition concept, and that is a scope limit on the refusal
rather than a tolerance.

The refusal is scoped by the shape of the DEFECT rather than the shape of the
modelo. Carry-capability is read from the payload's own declared casillas -- the
four compensación boxes the ingress already normalises -- so an observation that
cannot feed a later period's compensación is untouched. That satisfies the
scoping requirement structurally instead of by discipline, which cannot drift.

## Notes

The corrected docstring does not merely stop being false. It states the true
thing in the place the false thing stood: the requirement is not part of the
opt-in, every prepared envelope is screened, and storage staying open for
unrelated consumers is a bound on the refusal.

The requirement remains presence-only and never re-derives. The disposition is a
determined fact resolved at the declaration header or the filing boundary;
recomputing it at the write site would make a regulated determination answerable
in two places.
