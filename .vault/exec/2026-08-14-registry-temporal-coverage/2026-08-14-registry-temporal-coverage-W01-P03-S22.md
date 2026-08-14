---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:016cc04e9f53c0a811f119b16aa74d22e0faf7c200885ae54f825dc7eaa309ef'
step_id: 'S22'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
---

# Build and run the embed classifier: mechanically enumerate every modelo-specific module by name pattern and Modelo enum reference, force exactly one classification per module as regulatory data embed, machinery with recorded justification, or dead, including the two per-modelo formula runtimes, with a gate that reds on any module in the derived set left unclassified so the inventory is exhaustive by construction

## Scope

- `dev/`
- `src/cadrumo/domain/calculations/registry/tests/`

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

The derivation yields 36 modelo-specific modules, every one adjudicated exactly
once, with zero reconciliation failures. Eight are regulatory data embeds and
twenty-eight are machinery; none is dead, because every derived module has at
least one importer under the package root.

The derived set strictly contains the 18-module figure the campaign brief
supplied as a cross-check, and adds 18 the brief did not name. Not one of the
added eighteen carries a modelo code in its file name: each is a generic module
caught only because it reads a concrete modelo member or defines a modelo-scoped
symbol. Three of the eight embeds come from that added set, so the difference was
not cosmetic.

The regulatory-literal detector reaches the confirmed embed independently: it
flags the shared-constants module's ejercicio tuple, its three seasonal index
coefficients, its difficult-justification percentage and the Lorca 2022
reduction percentage, without being told to look for them.

The gate bites, proven twice against the real package tree rather than a
fixture. A module named for a modelo, planted and then removed, took the derived
set to 37 and reddened both the tool's check mode and the gate with a message
naming the module, its modelo and the signal that caught it. A second plant
naming no modelo in its file name, carrying only a modelo-scoped defined symbol,
reddened the same way -- the case a file-name glob cannot see. The tool returned
to a clean 36-module reconciliation after each removal.

## Notes

This Step deletes nothing and migrates nothing; it produces the inventory and
the protection list the migration Step consumes.

The eight embeds are the applicability rule table and its Spanish verdict prose,
the Modelo 202 modalidad rule module, the censo foundation year, the Modelo 100
letter-casilla first year, the annual-orden shared constants module, the
annual-orden legal-reference prose, and the two annual-orden model modules that
each restate the Lorca 2022 reduction percentage as a literal.

Only two of the eight migrate whole: the Modelo 202 modalidad module and the
annual-orden shared constants module. The other six are mixed, and each
justification states exactly which content migrates and which must survive,
because a whole-module deletion there would take working machinery with it. The
two annual-orden model modules in particular keep every projection, snapshot and
raw parse model, and every pydantic percentage and ejercicio field bound: those
are the definitional ranges of their units, not values the orden fixes. With the
reduction declared in the authoring tree, both re-derive as machinery on the next
run.

The machinery justifications are the protection list. Every annual-orden parsing
module -- keys, source, manifest, projection compiler and resolution -- is
machinery and survives, as do the three other Modelo 303 projections, matching
the campaign's stated intent to keep that family pending the operator's ruling on
full authoring-tree migration. The Modelo 347 threshold module is recorded as the
worked example of the shape an embed should be migrated into: the regulatory
figure arrives through the curated core external-constants channel and the module
owns only the strictness of the comparison.

Three observations for the campaign, none actioned here. First, the annual-orden
Lorca 2022 reduction percentage is spelled as a `Decimal` literal in three
separate modules, so the migration must retire all three spellings or the
duplication survives the extraction. Second, one production identifier in the
annual-orden projection models names a plan step id, which the source-hygiene
rule forbids; it is outside this Step's scope. Third, the classification of the
Modelo 100 letter-casilla first year and the censo foundation year as embeds is a
judgement the adjudication records rather than a mechanical result: both are
Python-resident regulatory years, and if the campaign reads either as a parser
format detail instead, the ledger row is where that ruling belongs.
