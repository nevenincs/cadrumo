---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:4137b45f307f7c5b55f1f41d38fdde111e89c18b29b83914ae17d48b8f5e4eed'
step_id: 'S64'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Update Spanish product locale messages through the locales CLI

## Scope

- `Spanish locale catalogue`

## Description

- Snapshot all four locale catalogue hashes before mutation.
- Run the reviewed Spanish-only production command `python -m cadrumo.locales canonicalize-product-identity --locale es` under isolated local storage.
- Compare every parsed changed leaf with the production identity normaliser and classify each change by referent.
- Verify catalogue audits, focused tests, sibling hash equality, raw residue classification, and live Spanish help output.

## Outcome

- The command changed exactly 29 semantic leaves: 22 command-leading references became `aeat`, and 7 product-display references became `CADRUMO`.
- Parsed key sets are identical before and after the mutation, and every changed value equals the production normaliser result.
- The Spanish catalogue hash changed from `9C06BEA436A970C041C1B5B6E0697552328E30CEA51E7468AB32AF0E0E26DD52` to `58CC27A9731B392490F0E8523A15DA26B88B17B08EA222AD4656B5962E7679D1`.
- English, Catalan, and Hungarian hashes remained unchanged.
- Catalogue scaffold and audit checks passed for all four locales; 38 focused tests passed; live Spanish help presents `CADRUMO`, `AEAT`, and the `aeat` command without stale title-case or command-leading forms.

## Notes

- The production YAML serializer produced a 154-insertion and 161-deletion textual diff; semantic comparison isolated the 29 intended leaf changes.
- No questionable replacements were found. `AEAT` remained at 238 occurrences and `CADRUMO_` remained at 20 occurrences.
- Raw Spanish residue is classified as 7 `CADRUMO` product displays, 20 `CADRUMO_*` environment references, 224 `aeat` command prefixes, one `registry/aeat` authority path, 234 standalone `AEAT` authority references, and one retained `cadrumo-vault/` machine or historical folder name.
- English and Spanish targeted residue is zero. Remaining display/command residues are Catalan 13/26 and Hungarian 6/24 for S65 and S66.
- No locale YAML was hand-edited.

## Regression ancestry and corrective restoration

The original S64 transaction at `955efcadf3` changed 29 Spanish leaves: 22
stale command prefixes to `aeat` and seven product-display references to
`CADRUMO`. Commit `38894cae07` later changed those seven display leaves back
to title-case `Cadrumo` under the repudiated casing ruling. The command
guidance remained canonical and required no further command change.

S95 restored the binding all-caps runtime tuple, S96 established reciprocal
supersession for the conflicting July 13 ADR, and S97 clarified that ADR as
historical evidence only. S62 then restored and independently passed the
shared renderer and locale-maintenance expectations. S63 restored and
independently passed the English catalogue. This corrective S64 pass therefore
changes only the seven Spanish display leaves left by `38894cae07` and retains
the original 29-change evidence above as historical proof of the first
catalogue migration.

## Corrective semantic evidence

- Before mutation, the Spanish catalogue was 442,107 bytes with SHA-256
  `D4DC3DFF9CA825049BB3A75D5818743B4AB31A05BEAE7843A344F43D374B19AA`.
- After the production Spanish-only canonicalizer, it is 449,246 bytes with
  SHA-256
  `2D97F3174AA18D65ECFBE5856A6D4FCF015606AFB54447610DE85BAFCD8E3A72`.
- Parsed comparison proves exactly seven changed leaves, each equal to the
  production normalizer's `Cadrumo` to `CADRUMO` result. There are zero command
  changes, key additions, key removals, type changes, or other semantic
  changes.
- All four catalogues contained exactly 3,702 keys before mutation. Spanish
  retains exactly 3,702 keys, every leaf remains a string, and its production
  placeholder-map digest is unchanged at
  `ECF9F59F5BF1E0228F5FD6836595940F7B9150C7824453C8B1DC771DC8CEC918`.
- English remained byte-identical at 403,956 bytes and
  `06C2550F40D46982ADBBBA713D3031B1BB54CEBBE1141C80340F749C6F70325B`;
  Catalan remained byte-identical at 434,939 bytes and
  `8C5814BC6AD33DB287C3A9A133A2C6671E42CE3BFDB58C8F7BC1B94E492CACCE`;
  Hungarian remained byte-identical at 451,606 bytes and
  `F7D1A4DA52D5578A5FC0CDAF7125201169E73922E06C4B87BA614E8330AE0942`.
- Spanish now contains zero exact title-case `Cadrumo` references and zero
  command-leading lowercase `cadrumo` references. Its seven exact `CADRUMO`
  displays, 20 `CADRUMO_` environment references, 224 `aeat` command
  references, 234 standalone `AEAT` authority references, and one
  `registry/aeat` authority path remain correctly classified. The lowercase
  `cadrumo_secret_store_backend` setting and `cadrumo-vault/` storage name are
  valid machine identifiers and remain intact.

## Corrective verification

- The production `audit` and `scaffold --check` commands report all four
  catalogues healthy.
- The locale audit, S92 formatter grammar, placeholder parity, catalogue
  parity, and translation-honesty slice passed 54 tests.
- Isolated live `aeat --language es --help` contains exact `CADRUMO`, `AEAT`,
  and `aeat` command guidance. It contains neither exact title-case `Cadrumo`
  nor a command-leading lowercase `cadrumo` token.
- The first read-only semantic probe inherited the retired `aeat.db` state and
  correctly refused it. Every subsequent probe and gate used a fresh isolated
  `CADRUMO_LOCAL_STORAGE_ROOT` with valid unsecured local state.
- No Python path changed, so Ruff, formatting, and Ty are not applicable to
  this catalogue-only transaction. `git diff --check` passes, and the Spanish
  YAML diff is exactly seven insertions and seven deletions.
- Plan validation passes with the known `PLAN022` ordering warning. The
  feature-tagged broad Vault check remains nonzero on 348 unrelated legacy
  structure errors and 85 pre-existing warnings; references, schema, ADR
  status, rename integrity, and encoding are clean. No global Vault repair or
  index regeneration was attempted.
- No locale YAML was hand-edited; the production module CLI performed the sole
  catalogue mutation. English, Catalan, Hungarian, S65 through S67, S25, and
  every other open descendant remain outside this Step.

## S87 contextual-casing correction

Authority Step S87 at `03cd792be3` binds `prose_name='Cadrumo'` separately
from identity-context `display_name='CADRUMO'`, while retaining `aeat` as the
sole human executable and `AEAT` as the authority. Earlier all-caps prose
claims in this record are retained only as historical evidence.

This pass used five explicit production `locales set` operations against
Spanish. Three sentence-prose leaves now use `Cadrumo`; `mcp.call.timeout` and
`mcp.elicitation.refusal.no_channel` now direct operators to the human `aeat`
command. The identity headings `cli.operator_surface.help.root.heading` and
`cli.root.landing.headline` remain exact `CADRUMO`. No broad canonicalizer or
text replacement was used.

Spanish changed by exactly five insertions and five deletions, from SHA-256
`2D97F3174AA18D65ECFBE5856A6D4FCF015606AFB54447610DE85BAFCD8E3A72`
to
`02C6765D56B101DDF3F9E81833DC55A47A62CE033319FC7A0EEE9BC9EA996104`.
English remained byte-identical at
`6241114C3A643E9F60283E526386080A7AD31D7A965012221F956A557D594426`,
Catalan at
`9A4BBE39A1DCA9B4B42175D5DAF1DAECC0E0BCEBD354F52E759BFEFDE30BC5CC`,
and Hungarian at
`9F659FD5A312A7B1B1B5219A43B00285E3F3BD8CEEF81F90F6C03D2CEFE30F9B`.
The real Spanish catalogue assertion covers all seven classified keys and
preserves the `AEAT` authority referent in the root identity heading.

Production `audit` and `scaffold --check` reported all four catalogues healthy.
The renderer, formatter-contract, locale-audit, and parity slice passed 62 real
tests. Ruff lint, Ruff format, and Ty passed for the changed semantic test, and
the scoped diff passes whitespace validation. No test was skipped, patched, or
converted to an expected failure.
