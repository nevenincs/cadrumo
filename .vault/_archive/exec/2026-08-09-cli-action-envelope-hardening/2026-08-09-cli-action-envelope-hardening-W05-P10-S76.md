---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:cbe4909361c9962f70e5ff3f8347376f1ff3aaec977d43336fa71f3a36842f06'
step_id: 'S76'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Migrate inventory recovery producers to typed conditions and canonical actions

## Scope

- `src/cadrumo/application/inventory`

## Description

- Delete the duplicated sentences from the five inventory refusals that already declared their own keys and context.

## Outcome

- All five refusals already carried a distinct locale key and full machine context: the rejected valuation method, and the actividad and year for both the conflict and the not-found cases. Only the leading positional sentence was redundant, and it was never the rendered text.
- The declared package now carries no operator-facing prose refusal.
- No locale leaf was added or changed, because each refusal already owned its key.
- The package suite passes twenty-four tests serially and is lint clean.

## Notes

- One failure in the package selection is unrelated peer breakage: a storage bucket-isolation test still matches on route and runtime sentences that no longer exist anywhere in production, having been migrated to keys by their owner. The stale matcher belongs to that surface, not to the inventory service, and no touched path appears in its traceback.
- No carry-forward.
