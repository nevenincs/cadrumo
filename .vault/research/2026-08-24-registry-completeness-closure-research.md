---
tags:
  - '#research'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:726c9777b9954da4905a6cdb88dbe52c135b67a6790dd9e68044d465e88ac21c'
related:
  - '[[2026-08-14-registry-temporal-coverage-authority-grade-coverage-adr]]'
  - '[[2026-08-14-registry-temporal-coverage-plan]]'
  - '[[2026-08-10-aeat-export-fragment-generator-authority-plan]]'
  - '[[2026-08-22-source-casilla-integration-plan]]'
---

# `registry-completeness-closure` research: `shipped corpus closure boundary`

The shipped registry cannot yet be called complete for every revision it presently
advertises as fileable: the live capability gate reports 14 revisions across 13 modelos
without an export layout. The evidence does not support filling those rows uniformly.
Some are authoring gaps, some have an over-broad revision window, some lack a canonical
producer vocabulary, and some lack a trustworthy official design. Closure therefore
needs one derived denominator and evidence-specific dispositions, executed through the
three existing campaigns rather than a fourth competing implementation plan.

## Findings

### Completeness has three separate denominators

Schema-family resolution, declared authority grade, and filing emission answer different
questions. The revision coverage manifest reports whether each enrolled family is
populated, cited as not applicable, or blocked pending evidence; the authority-grade
ladder refuses a revision whose declared calculation or filing reach outruns those
families; the filing capability gate independently refuses every revision without an
export layout. Treating any one of the three as the whole definition would hide a gap
visible to another. `src/cadrumo/domain/calculations/registry/_schema_family_coverage.py:36`,
`src/cadrumo/domain/calculations/registry/_validate_authority_grade.py:25`,
`src/cadrumo/domain/calculations/registry/tests/test_filing_capability_worklist.py:353`.

### The measurable filing backlog is 14 revisions, not every known AEAT modelo

On 2026-08-24 the live filing-capability test derived 14 non-emitting revisions across
13 modelos: 036, 038, 136, 182, 185, 187, 188, 194, 220 (two revisions), 390, 721, 763,
and 840. This is the relevant shipped-registry denominator because the test walks the
registered revisions rather than inventing modelos absent from the supported corpus.
`src/cadrumo/domain/calculations/registry/tests/test_filing_capability_worklist.py:353`.

The blockers already demonstrate four different remedy classes. M390/2021 has only 10
casillas where filing-grade siblings have at least 325, so casilla authoring precedes its
layout. M036 and M220 lack namespaced producer identities for non-casilla fields. M182,
M187, M188, M194, M220 and M763 cite designs whose authority does not cover their whole
open revision window. M136 and M721 have no bundled record design; M038's bundled form is
not a trustworthy field table; and M840 exposes a transport-versus-record terminator
semantic the renderer cannot currently express. The gate derives these reasons in
`src/cadrumo/domain/calculations/registry/tests/test_filing_capability_worklist.py:131`.

### Existing approved campaigns already own the implementation layers

The temporal-coverage plan owns schema-family enrollment, authority-grade enforcement,
revision horizons, corpus migration, localization of migrated prose, and the final
blocking coverage matrix. The export-fragment plan owns official-source semantic maps,
render profiles, generated revision trees, and emitted-byte proof; its remaining M390
sequence explicitly covers the 2022-2025 exact designs, while 2021 stays unsupported
until exact authority is enrolled. The source-casilla plan owns source-to-casilla
bindings and already assigns the M182 donor-row work. Creating a parallel closure plan
would fork ownership; a roll-up decision may sequence and reconcile these plans but
should not duplicate their steps. `.vault/plan/2026-08-14-registry-temporal-coverage-plan.md:14`,
`.vault/plan/2026-08-10-aeat-export-fragment-generator-authority-plan.md:143`,
`.vault/plan/2026-08-22-source-casilla-integration-plan.md:325`.

### The coverage contract exists but campaign state has drifted

The schema-family projection and authority-grade ladder are present in current HEAD and
their focused tests pass (23 coverage tests and 18 grade tests on 2026-08-24). The S02
execution record exists, but S02 remains unchecked; S03 has implementation and tests but
no matching execution record. The implementation rode inside broad commit `a16b0b8ffd7`,
so independent review and explicit reconciliation are required before either row can be
reported complete. `.vault/exec/2026-08-14-registry-temporal-coverage/2026-08-14-registry-temporal-coverage-W01-P01-S02.md:14`,
`src/cadrumo/domain/calculations/registry/tests/test_authority_grade_ladder.py:1`, commit
`a16b0b8ffd7`.

### Evidence absence must remain a refusal, not a fabricated layout

The alternatives are: author every missing row from whatever artifact exists; delete or
demote every blocked revision; or preserve the derived worklist and resolve each row by
its actual prerequisite. The first invents wire semantics for M038, M840, and modelos
without designs. The second silently narrows published support and contradicts the
standing completion criterion. The evidence favors the third: split over-broad windows,
acquire exact authority where published, author semantics only after canonical owners
exist, and keep genuinely unsupported years loud. The ADR must settle how the three
existing campaign denominators roll up into one release claim without creating a second
coverage authority.

### Boundaries not yet adjudicated

This research has not yet established from live AEAT/BOE authority whether each missing
historical design can still be acquired, nor whether every registered open-ended window
reflects a genuinely published unchanged design. Those are tax/evidence reviews, not
inferences from filenames or similarity, and remain inputs to per-revision adjudication.

## Sources

- `src/cadrumo/domain/calculations/registry/_schema_family_coverage.py:36`
- `src/cadrumo/domain/calculations/registry/_validate_authority_grade.py:25`
- `src/cadrumo/domain/calculations/registry/tests/test_filing_capability_worklist.py:131`
- `src/cadrumo/domain/calculations/registry/tests/test_filing_capability_worklist.py:353`
- `.vault/plan/2026-08-14-registry-temporal-coverage-plan.md:14`
- `.vault/plan/2026-08-10-aeat-export-fragment-generator-authority-plan.md:143`
- `.vault/plan/2026-08-22-source-casilla-integration-plan.md:325`
- `.vault/exec/2026-08-14-registry-temporal-coverage/2026-08-14-registry-temporal-coverage-W01-P01-S02.md:14`
- `src/cadrumo/domain/calculations/registry/tests/test_authority_grade_ladder.py:1`
- commit `a16b0b8ffd7`
