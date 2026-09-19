---
tags:
  - '#audit'
  - '#profile-auth-crossref'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:2fa764faeca8775105c3e4e154c6ad17385fc9dc6440d8d26a6e7b0d1641289e'
related: []
---

# `profile-auth-crossref` audit: `Compound-write bypass and derived-aggregate desync sweep`

## Scope

A semantic sweep for every site sharing the two defect classes found while
fixing the profile manager's certificate page, rather than only the two
sites an operator happened to notice.

Class A is a cross-field agreement nothing seeds: two or more stored
values that must carry the same answer, where no surface populates one
from another, so the operator retypes and the disagreement surfaces far
from where it was created. Class B is a second write path: a generic
single-fact door reaching a field whose correctness depends on work the
owning writer does alongside the write.

Discovery ran `vaultspec-rag` semantic queries per class, each paired
with a targeted `rg` confirmation and, where a candidate survived, a
real-behaviour probe against an encrypted profile. Structural
enumeration ran beside it: every production caller of the plural and
singular profile-fact write doors, every schema-declared aggregate whose
value is derived from an indexed row namespace, and every consumer of the
generic field door.

## Findings

### auth-provider-workflow-drift | high | The profile table wrote the auth provider without activating it

The profile overview walks the schema, so the `auth` section renders as
ordinary editable rows. Selecting one opened the generic single-field
box, which writes one fact and does nothing else. Measured against a real
encrypted profile: editing the provider row wrote `clave_permanente` to
the profile fact while the workflow state's provider stayed unset, so the
profile claimed a provider no session had been activated for. That is
precisely the drift the certificate action's commit half was written to
prevent; the table bypassed `configure_operator_auth` entirely.

### auth-identity-not-seeded | high | Three surfaces name one taxpayer and none populated the others

The fiscal identity, the Cl@ve credential and the certificate's own
subject all name the same person, and the fail-closed session guard
refuses a login whenever the first two disagree. Nothing seeded any of
them from any other: the certificate page read only the `auth` section,
so it could not see the fiscal identity, and the certificate's subject
was read only at session bind. Measured: editing the credential row to
one identifier left the fiscal identity at another, silently, with the
disagreement surfacing only as a refused login.

### descendientes-count-desync | medium | A derived aggregate is editable while the rows it derives from are invisible

`renta_family.descendientes_count` is a derived aggregate over the
`renta_family.descendiente.{n}.*` rows; the entry surface, the wizard
descendant door and the checkpoint projection each rewrite it in the same
atomic batch as the rows so they cannot drift. The manager can. The count
is a declared schema field and renders as an editable row, while the rows
it counts are an indexed fact namespace the manager does not render at
all, so the operator edits a number with nothing beside it to contradict.
Measured: writing seven through the manager's field door against a
profile carrying two descendant rows left the count at seven and the rows
at two. The divergence splits the filing, because the
`renta-2024-profile-descendientes-count` binding reads the stored count
out of the profile fact index while casillas 0513 and 0514 are injected
from the rows.

### settings-credential-fallback | none | Not a defect; the dual source is deliberate and tested

Cl@ve credentials resolve from the active profile and fall back to
settings. This looked like a divergence candidate but is a documented,
tested decision with the profile taking precedence, and the setup page
routes its refusal through the same resolver the session entry uses so it
cannot refuse a credential the session would accept.

### divergence-guard-reachability | none | The seeding must suggest, never derive

A pre-existing test records that the identity agreement is enforced once,
at session entry, and that deriving one field from the other would make
the divergence refusal unreachable, which would read as the guard passing
rather than the guard being gone. The seeding added here suggests into an
empty row only and never overwrites an answered one, so the divergence
stays reachable through both the application door and the page.

## Recommendations

Route a field whose correctness depends on compound work to the writer
that owns it, rather than teaching the generic door about particular
fields. The manager action now declares the paths it is the sole writer
of, and a row naming one opens that action; the ownership is declared by
the action because the action is what knows why its fields are
inseparable.

Seed an agreement rather than deriving it. Where several stored values
must carry one answer, populate an empty field from whichever surface
already holds it and leave an answered field alone, so the operator stops
retyping without the disagreement becoming unsayable.

Where a derived aggregate must stay operator-settable, reconcile it on
the calculate path instead of locking the row. The descendientes count is
deliberately dual-purpose, since a bare count with no rows is a supported
declaration of the filer's family situation, so the action taken is a
non-blocking advisory that fires only when a stored count contradicts
rows that exist.

A follow-on ADR must decide whether the profile schema should mark
derived aggregates as such, so that the manager can render them as
computed rather than editable wherever no standalone declaration is
intended. This audit does not settle that; the descendientes count is the
only instance found, and it is the case where a standalone declaration IS
intended.
