---
tags:
  - '#audit'
  - '#cli-testimonial'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - '[[2026-05-21-fresh-cli-persona-testimonial-wave-plan]]'
  - '[[2026-05-20-testimonial-driven-cli-verification-playbook-reference]]'
---

# Fresh CLI persona testimonial briefs

Brief sheet for the fresh `2026-05-21` testimonial wave.

## Shared Rules

- Operate only through `uv run aeat ...`, `uv run --no-sync aeat ...`,
  and `--help`.
- Do not read source files, tests, registry data, or vault documents
  while acting as the persona.
- Use an isolated scratch root under `.vault-scratch/fresh-personas`.
- Set `AEAT_LIVE_TESTS_ENABLED=0`.
- Do not attempt live AEAT network calls, submission, or credential use.
- Quote real commands and real output snippets.
- Report first-person operator feedback: what worked, what failed, what
  felt misleading, which capabilities appeared missing, and which outputs
  looked legally or arithmetically risky.
- Grade bugs and gaps as blocker, major, minor, or cosmetic.

## Personas

### Ana - Sole Professional

Goal: create a sole-professional profile, discover whether Modelo 130 is
required, create or inspect a Modelo 130 workflow, and judge whether the
CLI explains the missing inputs clearly.

Scratch id: `ana-profesional`.

### Bruno - Company Administrator

Goal: determine whether the CLI can model a sociedad limitada profile,
prepare or inspect Modelo 303, and understand what company-tax work is
available versus out of scope.

Scratch id: `bruno-company`.

### Clara - Landlord

Goal: model rental-income facts, discover the annual Renta path for
rental income, and judge whether deductible rental expenses are visible
and traceable.

Scratch id: `clara-landlord`.

### Diego - Payroll Retentions

Goal: act as a small employer trying to understand Modelo 111
retentions, required inputs, and whether the CLI exposes enough workflow
surface to prepare the filing safely.

Scratch id: `diego-retentions`.

### Elena - Correction Handoff

Goal: create a modelo work unit, inspect verify/file/export/help flows,
then discover how a corrected or complementary filing would be handled.

Scratch id: `elena-correction`.

### Fatima - Legal Explainability

Goal: use registry, manual, overview, and modelo help surfaces to answer
why an obligation applies and where a casilla value or manual source is
grounded.

Scratch id: `fatima-explain`.
