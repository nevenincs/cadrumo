---
tags: ["#exec", "#cli-testimonial"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'P02.S03-P04.S12'
related:
  - '[[2026-05-21-fresh-cli-persona-testimonial-wave-plan]]'
  - '[[2026-05-21-fresh-cli-persona-testimonials-audit]]'
  - '[[2026-05-21-fresh-cli-persona-findings-inventory-audit]]'
  - '[[2026-05-21-fresh-cli-persona-repair-plan]]'
---

# `fresh-cli-persona-testimonial-wave` `P02-P04`

Ran the fresh CLI persona wave, consolidated the findings, reproduced
serious claims directly, and wrote the follow-up repair plan.

- Ran six persona agents: Ana, Bruno, Clara, Diego, Elena, Fatima.
- Wrote the persona audit.
- Wrote the severity-graded findings inventory.
- Wrote the follow-up repair plan.
- Closed `S03` through `S12`.

## Coordinator Reproduction

Confirmed:

- direct legal-entity profile creation misparses `--legal-entity-form sl`
  as an IRPF income category;
- `casillas 303 --period 1T --form-number 69` returns only the header
  while the unfiltered computed list includes casilla number `69`;
- export recovery text points at `aeat app modelo verify` instead of the
  actual `aeat app modelo work verify`;
- `aeat app manual --help` is absent;
- `casillas 111 --required` returns only the header.

Not confirmed as a stable clean-environment defect:

- the cross-persona `SecureObjectUnreadable` import error. The symbol is
  currently exported, and coordinator runs of filing-record list,
  verification-report list, Modelo 303 work create/calculate, and Modelo
  130 calculate/verify did not crash.

## Tests

`uv run vaultspec-core vault plan check .vault/plan/2026-05-21-fresh-cli-persona-testimonial-wave-plan.md` passed.

`uv run vaultspec-core vault plan check .vault/plan/2026-05-21-fresh-cli-persona-repair-plan.md` passed.

`uv run python -m aeat.locales audit` initially found missing key `aggregation.source_mesh.errors.duplicate_relation_owner` in all locale files.

`uv run python -m aeat.locales scaffold` repaired the locale scaffold. The first scaffold attempt failed while writing `hu.yml`; rerunning the same required CLI completed successfully.

`uv run python -m aeat.locales audit` then passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`uv run python -m aeat.locales scaffold --check` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.
