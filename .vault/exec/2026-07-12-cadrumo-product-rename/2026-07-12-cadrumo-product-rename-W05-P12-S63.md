---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-17'
body_hash: 'sha256:ccda19c65cb7d01a4c55d63416b41e13164a88b0785c7b8e595c6f4dd3eed502'
step_id: 'S63'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Update English product locale messages through the locales CLI

## Scope

- `English locale catalogue`

## Description

- Snapshot all four locale catalogue hashes before mutation.
- Run the reviewed English-only production command `python -m cadrumo.locales canonicalize-product-identity --locale en` under isolated local storage.
- Compare every parsed changed leaf with the production identity normaliser and classify each change by referent.
- Verify catalogue audits, focused tests, sibling hash equality, and live English help output.

## Outcome

- The command changed exactly 38 semantic leaves: 28 command-leading references became `aeat`, and 10 product-display references became `CADRUMO`.
- Parsed key sets are identical before and after the mutation, and every changed value equals the production normaliser result.
- The English catalogue hash changed from `2108A1AC2E2C60B8713FE8C7A850CD55525451C7D17B5263F51DE9FF6D7ED630` to `FD1949009563A0D3211164BC7C715848B6717D26DB951AC75559C7A9698A0037`.
- Spanish, Catalan, and Hungarian hashes remained unchanged.
- Catalogue scaffold and audit checks passed for all four locales; 38 focused tests passed; live English help presents `CADRUMO`, `AEAT`, and the `aeat` command without stale title-case or command-leading forms.

## Notes

- The production YAML serializer produced a 147-insertion and 152-deletion textual diff; semantic comparison isolated the 38 intended leaf changes.
- No questionable replacements were found. `AEAT` remained at 224 occurrences and `CADRUMO_` remained at 21 occurrences.
- English targeted residue is zero. Remaining display/command residues are Spanish 7/22, Catalan 13/26, and Hungarian 6/24 for S64 through S66.
- No locale YAML was hand-edited.

## Regression ancestry and corrective restoration

The original S63 transaction at `1512ec2994` changed 38 English leaves: 28
stale command prefixes to `aeat` and 10 product-display references to
`CADRUMO`. Commit `38894cae07` later changed those 10 display leaves back to
title-case `Cadrumo` under the repudiated second casing ruling. Commit
`9cb54a26f6` repeated that title-case authority in the ADR/runtime ancestry but
did not modify the English catalogue directly.

S95 restored the binding all-caps runtime tuple, S96 established reciprocal
supersession for the conflicting July 13 ADR, and S97 clarified that ADR as
historical evidence only. S62 then restored and independently passed the shared
renderer and locale-maintenance expectations at commits `6226f2fe57` and
`fc7c25b0af`. This corrective S63 pass therefore changes only the 10 English
raw-catalogue display leaves left by `38894cae07`; English command guidance was
already canonical and required zero further command changes.

## Corrective semantic evidence

- Before mutation, the English catalogue was 397,282 bytes with SHA-256
  `E93111E585118B7B416757B37E4AFD810A58305B7985718CEC79853FF8D406E1`.
- After the production English-only canonicalizer, it is 403,956 bytes with
  SHA-256
  `06C2550F40D46982ADBBBA713D3031B1BB54CEBBE1141C80340F749C6F70325B`.
- Parsed comparison proves exactly 10 changed leaves, each equal to the
  production normalizer's `Cadrumo` to `CADRUMO` result. There are zero command
  changes, key additions, key removals, or other semantic changes. The
  serializer produced a 10-insertion and 10-deletion textual diff.
- All four catalogues contained exactly 3,702 keys before mutation. English
  retains exactly 3,702 keys, every leaf remains a string, and its production
  placeholder-map digest is unchanged at
  `ECF9F59F5BF1E0228F5FD6836595940F7B9150C7824453C8B1DC771DC8CEC918`.
- Catalan remained byte-identical at 434,939 bytes and
  `8C5814BC6AD33DB287C3A9A133A2C6671E42CE3BFDB58C8F7BC1B94E492CACCE`;
  Spanish remained byte-identical at 442,107 bytes and
  `D4DC3DFF9CA825049BB3A75D5818743B4AB31A05BEAE7843A344F43D374B19AA`;
  Hungarian remained byte-identical at 451,606 bytes and
  `F7D1A4DA52D5578A5FC0CDAF7125201169E73922E06C4B87BA614E8330AE0942`.
- English now contains zero exact title-case `Cadrumo` references and zero
  command-leading lowercase `cadrumo` references. All 224 `AEAT` occurrences
  remain intact. The sole lowercase `cadrumo` leaf remains the valid
  `cadrumo-vault/` machine identifier.

## Corrective verification

- The production `audit` and `scaffold --check` commands report all four
  catalogues healthy.
- The locale audit, S92 formatter grammar, placeholder parity, catalogue parity,
  and translation-honesty slice passed 54 tests.
- Isolated live `aeat --language en --help` contains five `CADRUMO` references,
  two `AEAT` references, and 27 lowercase `aeat` guidance references. It contains
  neither exact title-case `Cadrumo` nor a command-leading lowercase `cadrumo`
  token.
- The first read-only semantic probe inherited the retired `aeat.db` state and
  correctly refused it. Every subsequent probe and gate used a fresh isolated
  `CADRUMO_LOCAL_STORAGE_ROOT` with valid unsecured local state.
- The first live-help assertion wrapper had an unbalanced diagnostic regular
  expression and failed after the help command itself succeeded. The corrected
  assertion reran the unchanged live command and passed; no product failure was
  hidden.
- No Python path changed, so Ruff and Ty are not applicable to this catalogue
  transaction. `git diff --check` passes for the English catalogue.
- Focused feature, frontmatter, Markdown, placeholder, and annotation checks
  pass; S63 has no remaining scaffold annotation. The feature index retains its
  pre-existing stale-index warning. The broader feature-tagged `check all`
  remains nonzero on 319 legacy filename-structure errors, 26 modified-stamp
  warnings, 59 scaffold-annotation warnings in other documents, and that stale
  index; references, schema, ADR status, rename integrity, and encoding are
  clean.
- No locale YAML was hand-edited; the production module CLI performed the sole
  catalogue mutation. Spanish, Catalan, Hungarian, S64 through S67, S25, and all
  other reopened descendants remain outside this Step.

## S87 contextual-casing correction

Authority Step S87 landed at `03cd792be3` with the immutable split
`prose_name='Cadrumo'` and `display_name='CADRUMO'`. The accepted executable
ADR's status note remains binding: sentence prose uses `Cadrumo`, identity
contexts may use `CADRUMO`, the human executable is `aeat`, and the authority
is `AEAT`. Earlier all-caps sentence-prose outcomes in this record are retained
only as historical evidence.

This corrective pass used eight explicit production `locales set` operations
against English. Seven sentence-prose leaves now use `Cadrumo`, and
`mcp.elicitation.refusal.no_channel` now tells operators to run the equivalent
`aeat` CLI command. The identity headings
`cli.operator_surface.help.root.heading` and `cli.root.landing.headline`
remain exact `CADRUMO`. No broad canonicalizer or text replacement was used.

The English catalogue changed by exactly eight insertions and eight deletions,
from SHA-256
`06C2550F40D46982ADBBBA713D3031B1BB54CEBBE1141C80340F749C6F70325B`
to
`6241114C3A643E9F60283E526386080A7AD31D7A965012221F956A557D594426`.
Spanish remained byte-identical at
`2D97F3174AA18D65ECFBE5856A6D4FCF015606AFB54447610DE85BAFCD8E3A72`,
Catalan at
`9A4BBE39A1DCA9B4B42175D5DAF1DAECC0E0BCEBD354F52E759BFEFDE30BC5CC`,
and Hungarian at
`9F659FD5A312A7B1B1B5219A43B00285E3F3BD8CEEF81F90F6C03D2CEFE30F9B`.
The real catalogue semantic assertion distinguishes all three naming contexts
and preserves `AEAT` in the identity heading's authority clause.

Production `audit` and `scaffold --check` reported all four catalogues healthy.
The focused renderer, formatter-contract, locale-audit, and parity slice passed
61 real tests. Ruff lint, Ruff format, and Ty passed for the changed semantic
test. The first combined gate wrapper reached its orchestration timeout while
running the otherwise independent checks; each gate was then rerun separately
to completion. No test was skipped, patched, or converted to an expected
failure.
