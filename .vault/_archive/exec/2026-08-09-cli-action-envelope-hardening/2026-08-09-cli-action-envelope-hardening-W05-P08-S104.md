---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:ee54c6cca7aa21b7d610b53e93aa02887e1e7810a9d66a8d14ec156da6785d34'
step_id: 'S104'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Migrate calc-sheets exception producers to typed catalogue/live-input verdicts or explicit terminal/no-recovery dispositions

## Scope

- `src/cadrumo/application/storage/calc_sheets/_engine.py`
- `src/cadrumo/application/storage/calc_sheets/_evidence.py`
- `src/cadrumo/application/storage/calc_sheets/_layout.py`
- `src/cadrumo/application/storage/calc_sheets/_translator.py`

## Description

- Delete the translator error's unused message parameter and every dead argument at its twenty call sites.
- Drop the duplicated sentences from the two engine refusals that already declared a key.
- Migrate the evidence contributor refusal to the registered engine key with the transaction identity as a fact.
- Rewrite the two assertions that compared the rendered text against a sentence.

## Outcome

- The declared modules carry no operator-facing prose refusal; the layout module already had none.
- The substantive finding is that the translator's twenty sentences were never reachable. Its constructor always called the base initialiser with a fixed sentence plus the registered translation key, discarding whatever the caller passed. Removing the parameter makes that structural rather than a convention a future caller could violate.
- Both engine refusals already declared their own keys and restated them in English; only the catalogue half was rendered.
- Two hardening assertions compared the rendered text against the deleted sentence. They now assert the registered key, which is what the boundary actually surfaces.
- The engine, evidence and translator selections pass twenty-four tests serially, and the package is lint clean.

## Notes

- Executed file by file with a test run between each.
- The wider package suite carries unrelated failures from missing Spanish casilla labels in the modelo schema catalogue. That gap belongs to the casilla-schema campaign, which owns continuidad label authoring against official sources; the failing paths do not reach the modules changed here.
- No carry-forward.
