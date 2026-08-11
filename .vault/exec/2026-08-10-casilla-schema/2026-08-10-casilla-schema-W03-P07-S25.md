---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:a612944d89df0cdaee47e143ecaa21b2b2b12765449a3c85394cd875b99fa810'
step_id: 'S25'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---
# implement the owner-ruled progress counts: typed state plus counts against the named manifest denominator, UNDEFINED when no manifest exists, never a bare percentage

## Scope

- `src/cadrumo/application/modelo/`

## Description

- Add the core `ModeloWorkProgressState` vocabulary with complete, in-progress, blocked, and undefined states.
- Add frozen progress and denominator records to `ModeloWorkReview`, naming the calculation-completeness manifest by kind, registry revision, and source reference.
- Count only persisted, non-empty observations whose casilla ids occur in that revision manifest.
- Derive complete and blocked states from the latest persisted verification verdict while refusing a complete state whose manifest members have not all materialised.
- Prove manifest-bearing, manifest-less, partial, blocked, and verified-complete behavior through bundled registry data and real encrypted repositories.
- Gate the complete review payload against forbidden ratio tokens in field names and refuse unnamed or impossible counts at model validation.

## Outcome

S25 now exposes one facade-exported progress record on the canonical modelo work review producer. Manifest-bearing work reports materialised and target counts against an explicit revision-bound denominator. Manifest-less M189 work reports UNDEFINED with no counts or denominator. Real persisted M130 revisions exercise zero, partial, blocked, and complete outcomes without a percentage field or ratio-named field.

Focused verification passed: 7 modelo work review tests, Ruff formatting and lint over the five owned Python surfaces, BasedPyright with 0 errors, 0 warnings and 0 notes, focused collection of all 7 tests, facade import execution through `uv run --no-sync python`, and focused `git diff --check`. The payload field-name gate recursively inspects the emitted `ModeloWorkReview` JSON schema. `vaultspec-core vault check all` exited zero with this execution record clean; its standing unrelated warning inventory remained visible and untouched.

The gate-bite proof temporarily changed the no-manifest producer branch from UNDEFINED to IN_PROGRESS. The real M189 storage test failed in `ModeloWorkProgress` validation because a defined state lacked counts and a named denominator. The original UNDEFINED branch was restored, after which the focused suite passed.

A formal read-only review reported no CRITICAL or HIGH findings. Its initial MEDIUM finding about payload-gate scope was closed by recursively inspecting the complete review JSON schema, and its LOW finding about partial-count evidence was closed by persisting exactly one manifest observation. Follow-up review found no remaining findings.

## Notes

The initial inventory contained six unrelated modified paths and no S25 collision. Peer churn continued during execution; all unrelated source, tests, Vault documents, and generated surfaces were preserved. The owned facade additions were inspected against their live diffs before validation.

A combined focused-plus-import-hygiene pytest invocation exceeded the 120-second command boundary and its exact process tree then exited; no result is claimed for that broader gate. The separately executed S25 focused suite and static gates are green. `vaultspec-core status casilla-schema` confirms S25 remains open as instructed. No plan checkbox, staging area, commit, audit document, or summary artifact was changed for this step.
