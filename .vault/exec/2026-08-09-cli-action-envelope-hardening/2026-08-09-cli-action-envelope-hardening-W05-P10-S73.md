---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:39f792a7d5ed0a57ef9fbc4eb654c2bc6e070bf711ec4446a6891230f5353980'
step_id: 'S73'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Migrate corpus-search recovery producers to typed conditions and canonical actions

## Scope

- `src/cadrumo/application/corpus_search`

## Description

- Audit the corpus-search error surface for producers whose operator text is authored rather than catalogue-rendered.
- Attempt the standard migration, observe it refused by the surface's own constructor contract, and restore the module.

## Outcome

- The surface is already compliant, by an explicit and documented design rather than by accident. Every class binds a registered error code whose message key supplies the localized envelope message; the constructor's free-form message is declared developer-facing detail reached only through the exception's string form, and the operator-facing specifics ride on context.
- That is the contract this campaign asks for: the operator text comes from the catalogue and the machine facts come from context. No producer authors operator prose.
- The base constructor deliberately accepts no translation-key argument, which is what makes the property structural: a caller cannot supply operator text even by mistake.
- The package suite passes forty-eight tests serially and the package is lint clean.

## Notes

- The standard migration was attempted first and was wrong. Six producers were rewritten to pass a translation key, which the base constructor rejects; every one raised a type error at runtime. The module was restored by inverse patch rather than a destructive git verb, and the restoration was verified by the full package suite.
- The first restoration pass reinstated two sentences at the wrong call sites. Lint caught the resulting long line and one test caught the swapped text; both were corrected before the suite went green.
- The lesson generalises beyond this step: error classes in this tree are not uniform in their constructor contract. One surface discarded a required message it never used, another refuses a translation key outright. The signature must be read before a migration is applied, not assumed from the pattern that held elsewhere.
- No carry-forward.
