---
tags:
  - '#exec'
  - '#legal-grounding-centralization'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S07'
related:
  - "[[2026-06-14-legal-grounding-centralization-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace legal-grounding-centralization with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S07 and 2026-06-14-legal-grounding-centralization-plan placeholders are machine-filled by
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
     The F2-final: decide prorrata subsystem fate — enroll as registry-declared aggregation source on 303/390 casillas OR delete the dormant subsystem per no-legacy-compatibility and ## Scope

- `src/aeat/domain/iva/_prorrata.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# F2-final: decide prorrata subsystem fate — enroll as registry-declared aggregation source on 303/390 casillas OR delete the dormant subsystem per no-legacy-compatibility

## Scope

- `src/aeat/domain/iva/_prorrata.py`

## Description

- Re-confirm at HEAD that the prorrata subsystem (`compute_prorrata_general`,
  `is_especial_mandatory`, `requires_sectoral_separation`, `aggregate_*_prorrata`) has
  zero production callers (only `__init__` re-exports + tests).
- Make the bind-or-delete decision: **RETAIN** the subsystem; defer enrollment as a
  separate IVA-deducibility feature.

## Outcome

DECISION: retain the prorrata subsystem, defer its enrollment into the live M303/M390
deducible-IVA calculation as a tracked follow-on feature. Rationale: the subsystem is
legally grounded (LIVA art. 9.1.c sectores diferenciados, art. 102 prorrata general,
art. 103 prorrata especial), tested, and CORRECT — it is forward-functional IVA capacity
the application will need to compute deducible IVA under prorrata, not legacy or
backwards-compatibility code. `no-legacy-compatibility` explicitly keeps forward-functional
capacity (the Modelo.M037 precedent) and deletes only code that reads/migrates an older
version's data; prorrata is neither. Deleting correct, legally-grounded, tested IVA logic
would destroy real work and a real future requirement. Its two regulatory thresholds were
already centralised to `external_constants` in F2-interim (P01.S03), so the inline-literal
concern is closed independent of enrollment.

## Notes

DEFERRED CARRY-FORWARD (per plan-closure-requires-exec-records): enrollment is a genuine
feature — it requires a prorrata aggregation source + resolver in the calculate mesh,
registry bindings on the deducible casillas (M303 28/44, M390 33), and the prorrata inputs
(operaciones con/sin derecho a deducir) sourced from the ledger. That is a deducible-IVA
calculation feature, not a centralisation cleanup, and is tracked for a dedicated pass. The
`no-dormant-source-resolvers` rule binds ModeloSourceResolvers enrolled in the mesh; the
prorrata functions are domain computation primitives, not yet mesh resolvers, so retaining
them pre-enrollment does not violate that rule. Until enrollment, the subsystem is
documented forward capacity with centralised thresholds.
