---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:52bd07f346bf2f62bcb532d8809597194a0bb69cfde52acfded032dd7e380523'
step_id: 'S18'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-action-envelope-hardening with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S18 and 2026-08-09-cli-action-envelope-hardening-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Carry guarded command identity and verdict through the refusal boundary and ## Scope

- `src/cadrumo/entrypoints/cli/_errors.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Carry guarded command identity and verdict through the refusal boundary

## Scope

- `src/cadrumo/entrypoints/cli/_errors.py`

## Description

- Read the S17 `CliPolicyRefusalProjection` at the generic exception boundary
  and preserve its exact requested subject-leaf key over the root callback key.
- Pass the already-resolved `ResolvedPreconditionAction` into the canonical
  JSON error renderer without adding action data to free-form context.
- Derive text-mode condition, evidence, action, bindings, missing arguments,
  conditionality, and no-recovery lines from that same immutable wire DTO.
- Fail closed when the typed S17 marker carries an invalid projection while
  leaving untyped refusal producers assigned to later migration waves working.
- Add real text, JSON, no-recovery, malformed-marker, and untyped-control tests
  in `src/cadrumo/entrypoints/cli/tests/test_refusal_boundary_action_projection.py`.
- Repair file-local strict-typing defects in `src/cadrumo/entrypoints/cli/_errors.py`
  exposed by the configured type gate without changing their runtime contract.

## Outcome

The root guard's pre-dispatch refusal now reaches both CLI representations with
the identity of the terminal leaf the operator requested. JSON carries the
complete canonical record under `error.action`; text carries deterministic
schema-field serialization of the same record beneath the localized refusal.
Neither path reconstructs an executable command or promotes a suggestion
string into authority. Explicit no-recovery outcomes remain distinguishable
from actionable recovery, and a corrupt typed handoff cannot silently degrade
to an identity-less refusal.

The focused S18 plus S17 real-root lane passed 16 tests. The exact console path
also emitted the expected actionable JSON and text envelopes from a fresh
storage root. Ruff, formatting, strict BasedPyright, and the scoped diff gate
passed.

## Notes

The first focused invocation selected zero tests because the repository default
marker admits unit tests only; the authoritative rerun used the integration
marker and passed. An adjacent boundary lane passed 16 tests and retained one
stale S12-era failure whose assertion still dereferences the removed
`ErrorEnvelope.suggestion` field. An older JSON-boundary control could not set
up because its UUID-shaped profile label now violates the live bucket-manifest
contract; S18's direct real untyped-refusal control covers the relevant boundary.

During verification, peer checkpoint commit `04c3de99cf` captured the two S18
implementation files together with unrelated shared-worktree changes. This
executor performed no staging or commit and did not touch the Git lock. The
current HEAD was re-read and all proofs were rerun against the captured bytes.

