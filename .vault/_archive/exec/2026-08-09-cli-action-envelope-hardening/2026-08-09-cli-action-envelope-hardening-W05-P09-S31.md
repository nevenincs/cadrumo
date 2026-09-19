---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:776c8a8364d2f3eceb28e301cfeed34bb1ecc5fbe47551c76c53690896831b97'
step_id: 'S31'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Migrate overview next-step producers and blank-state advisories to typed actions

## Scope

- `src/cadrumo/application/overview`
- Precondition outside the declared scope: `src/cadrumo/application/operator_actions`

## Description

- Add `DeclaredNextAction` to the application action records as the success-path counterpart of the precondition verdict, carrying a stable action identity plus fully resolved argument bindings and refusing an unresolved or duplicated binding.
- Add a locale-neutral overview declaration module holding the shared declaration helper, the closed status next-step identifier enum, and the status next-step producer moved out of the CLI renderer.
- Replace the data-prep walkthrough free-form next-command string with a declared action per step; steps whose continuation needs operator-supplied input declare none.
- Replace the pipeline-health readiness row next-command string with a declared action for all seven readiness states.
- Replace the calendar warning fix-command string with a declared action across the profile-completeness, censo-enrolment, unverified-justificante, evidence-conflict, and simplificado-forfait warnings.
- Declare the twelve overview catalogue actions the producers name, each resolving against the live command tree and its required inputs.
- Rewrite the four owned application test modules onto the typed contract.

## Outcome

Three families of raw `aeat` command prose left the application layer: six data-prep steps, seven pipeline readiness rows, and five calendar warning producers. Each now names a catalogue action; none carries a command string, a CLI path, or presentation text.

The status next-step decision, which previously lived only in the CLI renderer as locale prose, is now an application producer returning ordered rows of a closed step identifier plus an optional declared action. Two rows were added that the previous surface only stated as prose with an embedded command: the profile-creation row when no active profile exists, and the storage-diagnostics row when local rows are unreadable.

Twelve catalogue entries were declared. Three initially declared for informational "list what you already have" steps were removed again before commit: a completed step has nothing to advance, and an unconsumed declaration is dead capacity.

Seven of the thirteen data-prep branches resolve to an executable action. The other six declare none, because their real continuation needs a statement file, a document path, an invoice's six fields, or a transaction id and percentage that the read model cannot know. That is recorded as an honest absence rather than a placeholder command.

Application overview and action tests: 399 passed. The live catalogue-resolution gate proves every new entry resolves against the real Click tree and result-schema registry.

## Notes

- `src/cadrumo/application/operator_actions` sits outside the Step's declared scope. `DeclaredNextAction` was placed there rather than inside the overview package on purpose: a producer-side forward-action carrier local to one package is exactly how the divergent next-command fields this campaign is removing entered the tree, and the sibling ledger, modelo and wizard slices need the same record. Catalogue entries were likewise added there because a declared action that is not in the catalogue cannot resolve, so the declaration is a precondition of the consuming change rather than a follow-up.
- The catalogue's own roster test asserted a frozen tuple of every action id. That is a moment encoded as a pass condition: every slice that legitimately declares an action must edit the constant, and after the second such edit it detects nothing. It was replaced with the ordering property the test is named for - sorted, unique, canonically namespaced.
- Two application overview tests fail on peer surfaces, not this one: the agenda cohort-partition test against uncommitted `domain/deadlines/_engine.py`, and the explain profile-facts test against uncommitted `domain/calculations/registry/_schema.py`. Both were confirmed to sit on peer-modified files and neither touches an action, a next-step producer or a warning.
- Work was interrupted once by a peer's uncommitted syntax error in the core identity package, which broke every import in the tree. It was not touched; the run resumed once the peer's edit settled.
