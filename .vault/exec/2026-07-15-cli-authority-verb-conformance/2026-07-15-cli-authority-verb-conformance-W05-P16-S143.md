---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S143'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Reconcile intentional identical-locale declarations after the grammar migration

## Scope

- `src/cadrumo/locales/_intentional_identical.json`

## Description

- Read the intentional-identical allowlist and confirm every entry carries a stated reason.
- Establish how the wholesale pending bucket and its ceiling are consumed by the honesty ratchet.
- Check whether the locale CLI exposes a verb that can retire a wholesale bucket.

## Outcome

The allowlist is reconciled. Every per-key entry states a real reason, and the reasons are the legitimate kind the contract allows: official AEAT and Spanish-government brand names such as the Cl@ve family and VERI*FACTU, AEAT domain stems such as casilla and modelo, universal technical tokens such as ID and SHA-256, genuine cross-language spelling coincidences, and pure placeholder or punctuation templates with no prose to translate. None is a silent mute for an untranslated string.

The Spanish locale is fully reconciled onto per-key entries with no wholesale bucket. Catalan and Hungarian still carry an `untranslated_pending` bucket, but each is pinned at an `_untranslated_ceiling` of zero. Reading the ratchet confirms zero is genuinely zero tolerance: the verdict fails when the identical-key count exceeds the ceiling, so at zero any new untranslated string fails the gate. The two buckets are therefore vestigial rather than permissive, and the honesty gate passes.

## Notes

One finding is recorded rather than acted on. The two vestigial buckets are residue from a completed translation pass and could be retired to leave Catalan and Hungarian in the same fully-reconciled shape as Spanish, which would also remove the latent lever of raising a ceiling to mute future untranslated strings.

They were left in place deliberately. The locale CLI exposes `allow-identical` to ADD an entry but no verb that removes one, and its `remove` verb targets a locale string leaf rather than an allowlist entry. Retiring the buckets would therefore require hand-editing the allowlist, which is absolutely barred. Adding a removal verb is real work but belongs to the locale CLI surface rather than this Step, so it is reported for scheduling instead of being forced here.

No hand edit was made to the allowlist or to any catalogue.
