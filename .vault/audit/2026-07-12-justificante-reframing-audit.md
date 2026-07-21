---
tags:
  - '#audit'
  - '#justificante-reframing'
date: '2026-07-12'
modified: '2026-07-12'
related:
  - "[[2026-04-21-justificante-reframing-plan]]"
  - "[[2026-04-21-justificante-reframing-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-filing-record-adr]]"
---

# `justificante-reframing` audit: `legacy plan supersession reconciliation`

## Scope

Reconcile the unchecked April 21 narrative plan against the accepted filing-record
architecture and the current reconciliation CLI, so an obsolete command vocabulary
does not reappear as active development work.

## Findings

### obsolete-import-vocabulary | low | every unchecked criterion belongs to a retired workflow

The April plan proposed a `docs/concepts/aeat-pdfs.md` page and four legacy
`aeat filing import --from-*` routes. The document does not exist and none of
those option names is present in the current Python source. That absence is not
an implementation gap: the accepted filing-record architecture intentionally
models a filed revision and AEAT-attested evidence under `aeat app modelo`, not
as a generic past-filing import surface.

The current reconciliation boundary is implemented by `modelo reconcile pull`,
`modelo reconcile file --file`, and `modelo reconcile history`. It treats a
justificante as receipt metadata and a declaration as a distinct, optional
casilla-level evidence kind. The public filing-record import command carries
evidence kind explicitly. This is a more precise successor to the plan's
narrative premise; reintroducing the four old flags would create a parallel,
unsupported CLI vocabulary.

The original plan's GitHub issue hygiene and generic quality-gate items are
historical project administration, not current source work. Its proposed
vocabulary-lock test also guards a superseded package shape. No unchecked
criterion remains an active implementation task.

## Recommendations

- Mark the seven legacy checklist rows resolved as superseded and add a clear
  plan-status notice. Do not create the old document or revive any `--from-*`
  command.
- Any future taxpayer-facing PDF guide must start through the required current
  documentation workflow and describe the accepted filing-record/reconcile
  surface rather than this retired plan.
