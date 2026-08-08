---
tags:
  - '#exec'
  - '#m303-carry-reconciliation'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:40f265d89d957dead98d16b47f8e1c3479ceca7f103b18e5e5f809cb03e5e7fc'
step_id: 'S09'
related:
  - "[[2026-08-07-m303-carry-reconciliation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace m303-carry-reconciliation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S09 and 2026-08-07-m303-carry-reconciliation-plan placeholders are machine-filled by
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
     The Rebind the four further twin literals discovery found in the registry binding validator, which a hand-listed inventory of nine had also missed and ## Scope

- `src/cadrumo/domain/iva_compensation/_filed_derivation.py src/cadrumo/domain/iva_compensation/__init__.py src/cadrumo/domain/calculations/registry/_bindings.py src/cadrumo/application/calculations/_iva_compensation_casillas.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Rebind the four further twin literals discovery found in the registry binding validator, which a hand-listed inventory of nine had also missed

## Scope

- `src/cadrumo/domain/iva_compensation/_filed_derivation.py src/cadrumo/domain/iva_compensation/__init__.py src/cadrumo/domain/calculations/registry/_bindings.py src/cadrumo/application/calculations/_iva_compensation_casillas.py`

## Description

Discovery immediately found four further twin literals that the hand list and the
review's own inventory of nine had both missed. They sat inside a module-level
tuple in the registry binding validator, which is why a scan reading only
string-valued attributes reported that module as naming nothing: the shape hid
the twins from the check that existed to find them.

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

## Outcome

The identity check now also reads tokens held inside module-level tuples, lists,
sets and frozensets, and reports the holding attribute with its index.

Rebinding the four required a declaration move. Three of them already existed in
the domain carry-forward policy, but the applied-in-period token was declared
only one layer up, and the registry cannot reach an application-layer
declaration. It was moved down beside the others in the domain policy and is now
re-exported by the calculations vocabulary module, which is the pattern that
module's own docstring already describes for the tokens a policy owns.

The new sibling edge from the registry to the domain compensation package
introduces no cycle: the compensation package imports only core. The layered
contract treats the domain as one layer, and the only registry-scoped forbidden
contract names a different domain package.

## Verification

Proven by mutation, delivered as a pytest plugin loaded from outside the
repository so nothing tracked changed. The plugin rebuilds the validator's
source-id tuple from equal-but-distinct strings, forcing new objects through
runtime slice concatenation rather than a copy an interning optimisation would
hand back unchanged.

The gate reds under the mutation, naming the exact holding attribute and index.
Recorded under both scheduling modes as required: red with parallelism disabled,
and also red under the project's default parallel options, because a plugin
passed on the command line is inherited by each worker and its configure hook
runs there too. Green with the mutation removed.

Import-linter contract status verified as described in the sibling record: the
four contracts this edge could affect are KEPT.

<!-- Where the evidence is that something RAN, quote the instrument rather than
     summarising it: the invocation, then the runner's verbatim summary line.

         uv run --no-sync pytest <paths> -m integration -n 0
         15 passed in 10.35s

     The invocation shows the selection (marker expression and path scope); the
     summary line shows what that selection produced. A run that selected nothing
     exits zero and reads as green, so a paraphrase such as "the tests pass"
     discards exactly the part a reader needs. Quote, do not summarise. -->

## Notes

The four twins were a genuine finding beyond the brief's inventory, which is the
argument for discovery over enumeration stated as evidence rather than as
reasoning.

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
