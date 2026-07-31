---
tags:
  - '#exec'
  - '#profile-setup-flow'
date: '2026-07-24'
modified: '2026-07-24'
body_hash: 'sha256:c2592122d155e8a6a7650b59481f94891e1eb7d7079acc7ca51f0bdd068844e2'
step_id: 'S34'
related:
  - "[[2026-07-23-profile-setup-flow-plan]]"
---

# Migrate the non-interactive quiet and accept-defaults walks onto run_scripted_flow with one shared definition builder and one coercer, preserving force-visible law and localized refusal surfaces

## Scope

- `src/cadrumo/application/wizard/_commands.py`

## Description

- Make `_setup_flow_definition` the single definition builder for both frontends and route the `--quiet` and `--accept-defaults` paths through `run_scripted_flow` over it, retiring the line-mode runner from every non-interactive wizard path.
- Extract one coercer, `_answers_model_from_canonical`, serving three callers (post-interactive coercion and both scripted paths), re-validating each committed answer through the same widget validation and canonical parsing the retired runner used.
- Reproduce the force-visible law by stripping `visible_when` on exactly the explicitly-flagged pages for one walk; keep every other gate governing.
- Preserve the wizard's localized refusal surface on a substrate rejection by re-raising the model's precise validation error, with the substrate remaining the sole answer authority on success.
- Add the scripted-versus-interactive parity gate: identical answer maps and submit eligibility over the same definition for an individual and a legal-entity walk, plus starved-required-page and trailing-token refusals with counts-only diagnostics.
- Remove the `run_flow`, prompter, and runner imports from the command module; relocate the scripted prompter helper to test support for the peer stream's runner retirement.
- Correct the modify-honesty rendering test to pin profile-language provenance: expected strings computed at use time under explicit overrides, profile-language rendering asserted present and the other locale's rendering asserted absent, parametrized over an English and a Spanish profile.

## Outcome

Landed as `e9f931c7d9` with the test correction `a7b9c52f89`. Independent code review verdict: clean pass, no critical or high findings, every axis closed — parity, force-visible law, coercer invariants across both real frontends, error-surface preservation, deletions, and the test correction confirmed as a strengthening rather than a weakening. Wizard and flows suites at that committed state: 411 passed, zero failed — the campaign's first fully-green state. The diagnosis this step was briefed with was falsified honestly: no settings ContextVar leak exists; the edit command renders in the active profile's chosen language by design, and the prior red was the test asserting an import-time ambient constant against the correct profile-language output.

## Notes

- The descendant-group splice was deliberately deferred out of this step: splicing mid-migration would have desynced the shared scripted token fixtures. It proceeds as its own step with the count page defaulting to zero descendants so group-less walks stay token-compatible.
- Review low findings carried to the honesty review: a latent coercer narrowing if a review-mode reset leaves a visible optional page uncommitted (unreachable on current fields); the scripted projection stores raw canonical tokens for visibility evaluation while the driver stores widget-canonicalized ones (inert while gates key on select and checkbox tokens); a theoretical wrong-field attribution if a substrate refusal field diverges from the model's first-failing field; force-visible stripping cannot reach repeating-group instance pages (inert — group pages carry no CLI flags).
- The superseded leak diagnosis is recorded loudly, not buried: one real cause (notice rendering after the language override unwound) was fixed in the legal-checks step; the second alleged cause did not exist, and no in-process multi-command language exposure remains.
