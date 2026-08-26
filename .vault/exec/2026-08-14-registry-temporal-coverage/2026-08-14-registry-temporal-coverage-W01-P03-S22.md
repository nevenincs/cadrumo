---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-08-14'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:294bb9822989e5aeea5929bcc143f8e780708ec14b69b41436ed0a9d6de1bb57'
step_id: 'S22'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
---

# Build and run the embed classifier: mechanically enumerate every modelo-specific module by name pattern and Modelo enum reference, force exactly one classification per module as regulatory data embed, machinery with recorded justification, or dead, including the two per-modelo formula runtimes, with a gate that reds on any module in the derived set left unclassified so the inventory is exhaustive by construction

## Scope

- `dev/registry/analysis/modelo_embed_classification.py`
- `dev/registry/analysis/modelo_embed_classification.toml`
- `dev/registry/tests/test_modelo_specific_embed_classification.py`

## Description

- Add `dev/registry/modelo_embed_classification.py`: derive the modelo-specific
  registry module set from three independent signals, gather regulatory-literal
  evidence per module, and reconcile both against a checked-in adjudication
  ledger.
- Derive the set from `cadrumo.core.Modelo` rather than from any authored list,
  so adding a modelo to the enum widens the detector with no edit to the tool.
- Signal one, module name: a modelo code appears as a token in the file name.
  Signal two, modelo reference: the body reads a concrete `Modelo.M###` member.
  Signal three, defined symbol: a module-level function, class or constant the
  module DEFINES carries a modelo code token.
- Detect regulatory-literal evidence in three mechanical families: a `Decimal`
  literal, an integer literal in the filing-year span, and a string literal
  that reads as authored prose by constant-name suffix or Spanish orthography.
- Add `dev/registry/modelo_embed_classification.toml`: one adjudication per
  derived module, each carrying a written justification, and, for a machinery
  claim, one disposition per detected evidence occurrence keyed by enclosing
  symbol, evidence kind and assigned name rather than by line number.
- Refuse, in reconciliation: a derived module with no adjudication; a ledger row
  the derivation no longer yields; an empty justification; an embed with no
  destination or no tree-ownership declaration; an embed whose declared queue
  contradicts its derived modelo set; a machinery claim leaving detected
  evidence unanswered; a disposition matching no live evidence; and a dead claim
  for a module the import graph still reaches.
- Add the gate at
  `src/cadrumo/domain/calculations/registry/tests/test_modelo_specific_embed_classification.py`,
  covering the reconciliation, each derivation signal against a newly written
  module, each refusal family, and an anchor assertion that the detector still
  finds the known embed.

## Outcome

The original classifier was delivered earlier, but its durable gate was reopened on 2026-08-26 after public-module relocation made it red. Before reconciliation it derived 43 modules against 41 ledger entries and emitted 62 failures: 30 stale private paths paired with their public replacements, plus two genuinely new modules.

Commit `bce006e444` maps all 30 relocations through the exact `c94133f295` history, classifies `deadline_coordinate.py` as reasoned machinery and `inventory_bindings.py` as an unowned regulatory embed, and replaces the deleted `SUPPORTED_EJERCICIOS` anchor with the live censo foundation-year embed. Both the anchor and dropped-entry mutation remain non-vacuous.

Current results are 43 derived modules, 43 ledger entries, and zero reconciliation failures. `python -m dev.registry.analysis.modelo_embed_classification --check` passes, the focused test module passes 10/10, and Ruff passes.

## Notes

This row maintains the exhaustive inventory and does not itself migrate or delete production facts. The current unowned S23 queue derived from the green ledger includes the complete Modelo 202 applicability/reason cluster, the censo foundation year, the Modelo 100 letter-casilla first year, and the Modelo 100 inventory 2025 binding. Mixed applicability content for 303/390 and annual-Orden/Lorca content remain explicitly campaign-owned and are not opportunistically migrated here.

The historical 36-module inventory is no longer treated as a timeless completion claim; closure now rests on the current derived denominator and the mutation-backed zero-failure gate.
