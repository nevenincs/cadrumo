---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:958bf2e22166b0c34e4666f4d01958a706fa18bc1ef57e33700024fe0b669714'
step_id: 'S65'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Update Catalan product locale messages through the locales CLI

## Scope

- `Catalan locale catalogue`

## Description

- Snapshot all four locale catalogue hashes before mutation.
- Run the reviewed Catalan-only production command `python -m cadrumo.locales canonicalize-product-identity --locale ca` under isolated local storage.
- Compare every parsed changed leaf with the production identity normaliser and classify each change by referent.
- Verify catalogue audits, focused tests, sibling hash equality, raw residue classification, and live Catalan help output.

## Outcome

- The command changed exactly 39 semantic leaves: 26 command-leading references became `aeat`, and 13 product-display references became `CADRUMO`.
- Parsed key sets are identical before and after the mutation, and every changed value equals the production normaliser result.
- The Catalan catalogue hash changed from `9A6F5FE244A671515A6EB66E40817EAA918077791123342759708A1FD19FD12E` to `91573AD9E6529EF9BDFFE9BAB9B12593C7DA6DA8A221E5BF0654FD5FAFCD6888`.
- English, Spanish, and Hungarian hashes remained unchanged.
- Catalogue scaffold and audit checks passed for all four locales; 38 focused tests passed; live Catalan help presents `CADRUMO`, `AEAT`, and the `aeat` command without stale title-case or command-leading forms.

## Notes

- The production YAML serializer produced a 169-insertion and 176-deletion textual diff; semantic comparison isolated the 39 intended leaf changes.
- No questionable replacements were found. `AEAT` remained at 231 occurrences and `CADRUMO_` remained at 21 occurrences.
- Raw Catalan residue is classified as 13 `CADRUMO` product displays, 21 `CADRUMO_*` settings, 225 `aeat` command prefixes, one `registry/aeat/treaties/` authority taxonomy path, 227 standalone `AEAT` authority references, and four `AEAT_*` authority settings.
- The only valid remaining lowercase `cadrumo` machine or historical residue is `cadrumo-vault/` in `cli.config.google.sync.calc.export_help`. No lowercase `cadrumo` setting, MCP executable, URI scheme, or companion namespace is present.
- English, Spanish, and Catalan targeted residue is zero. Remaining Hungarian display/command residue is 6/24 for S66.
- No locale YAML was hand-edited.

## Regression ancestry and corrective restoration

The original S65 transaction at `1f45f80020` changed 39 Catalan leaves: 26
stale command prefixes to `aeat` and 13 product-display references to
`CADRUMO`. Commit `38894cae07` later changed those 13 display leaves back to
title-case `Cadrumo` under the repudiated casing ruling. The command guidance
remained canonical and required no further command change.

S95 restored the binding all-caps runtime tuple, S96 established reciprocal
supersession for the conflicting July 13 ADR, and S97 clarified that ADR as
historical evidence only. S62 then restored and independently passed the
shared renderer and locale-maintenance expectations; S63 and S64 restored and
independently passed the English and Spanish catalogues. This corrective S65
pass therefore changes only the 13 Catalan display leaves left by
`38894cae07` and retains the original 39-change evidence above as historical
proof of the first catalogue migration.

## Corrective semantic evidence

- Before mutation, the Catalan catalogue was 434,939 bytes with SHA-256
  `8C5814BC6AD33DB287C3A9A133A2C6671E42CE3BFDB58C8F7BC1B94E492CACCE`.
- After the production Catalan-only canonicalizer, it is 442,017 bytes with
  SHA-256
  `9A4BBE39A1DCA9B4B42175D5DAF1DAECC0E0BCEBD354F52E759BFEFDE30BC5CC`.
- Parsed comparison proves exactly 13 changed leaves, each equal to the
  production normalizer's `Cadrumo` to `CADRUMO` result. There are zero command
  changes, key additions, key removals, type changes, or other semantic
  changes.
- All four catalogues contained exactly 3,702 keys before mutation. Catalan
  retains exactly 3,702 keys, every leaf remains a string, and its production
  placeholder-map digest is unchanged at
  `ECF9F59F5BF1E0228F5FD6836595940F7B9150C7824453C8B1DC771DC8CEC918`.
- English remained byte-identical at 403,956 bytes and
  `06C2550F40D46982ADBBBA713D3031B1BB54CEBBE1141C80340F749C6F70325B`;
  Spanish remained byte-identical at 449,246 bytes and
  `2D97F3174AA18D65ECFBE5856A6D4FCF015606AFB54447610DE85BAFCD8E3A72`;
  Hungarian remained byte-identical at 451,606 bytes and
  `F7D1A4DA52D5578A5FC0CDAF7125201169E73922E06C4B87BA614E8330AE0942`.
- Catalan now contains zero exact title-case `Cadrumo` references and zero
  command-leading lowercase `cadrumo` references. Its 13 exact `CADRUMO`
  displays, 21 `CADRUMO_` environment references, 225 `aeat` command
  references, 227 standalone `AEAT` authority references, four `AEAT_*`
  authority settings, and one `registry/aeat/treaties/` authority path remain
  correctly classified. The sole lowercase `cadrumo` occurrence is the valid
  `cadrumo-vault/` storage name.

## Corrective verification

- The production `audit` and `scaffold --check` commands report all four
  catalogues healthy.
- The locale audit, S92 formatter grammar, placeholder parity, catalogue
  parity, and translation-honesty slice passed 54 tests.
- Isolated live `aeat --language ca --help` contains five `CADRUMO`, two
  `AEAT`, and 27 lowercase `aeat` references. It contains neither exact
  title-case `Cadrumo` nor a command-leading lowercase `cadrumo` token.
- Every production command and live-help probe used a fresh isolated
  `CADRUMO_LOCAL_STORAGE_ROOT` with valid unsecured local state.
- No Python path changed, so Ruff, formatting, and Ty are not applicable to
  this catalogue-only transaction. `git diff --check` passes, and the Catalan
  YAML diff is exactly 13 insertions and 13 deletions.
- Plan validation passes with the known `PLAN022` ordering warning. The
  feature-tagged broad Vault check remains nonzero on 348 unrelated legacy
  structure and feature-folder errors plus 84 pre-existing warnings;
  references, schema, ADR status, rename integrity, and encoding are clean.
  No global Vault repair or index regeneration was attempted.
- No locale YAML was hand-edited; the production module CLI performed the sole
  catalogue mutation. English, Spanish, Hungarian, S66, S67, S25, and every
  other open descendant remain outside this Step.

## S87 contextual-casing correction

Authority Step S87 at `03cd792be3` binds sentence-prose `Cadrumo` separately
from identity-context `CADRUMO`, while retaining `aeat` as the human executable
and `AEAT` as the authority. Earlier all-caps prose claims in this record remain
historical evidence only.

This pass used eleven explicit production `locales set` operations against
Catalan. Nine sentence-prose leaves now use `Cadrumo`; `mcp.call.timeout` and
`mcp.elicitation.refusal.no_channel` now direct operators to `aeat`. The two
identity headings remain exact `CADRUMO`. No broad canonicalizer or replacement
was used.

The eleven semantic leaf changes produce thirteen inserted and thirteen deleted
YAML lines. Catalan changed from SHA-256
`9A4BBE39A1DCA9B4B42175D5DAF1DAECC0E0BCEBD354F52E759BFEFDE30BC5CC`
to
`D202C2F634134F4E172FFFF01B8DDE81551D11BD43766FE43CFD7CAE7F93A428`.
English remained byte-identical at
`6241114C3A643E9F60283E526386080A7AD31D7A965012221F956A557D594426`,
Spanish at
`02C6765D56B101DDF3F9E81833DC55A47A62CE033319FC7A0EEE9BC9EA996104`,
and Hungarian at
`9F659FD5A312A7B1B1B5219A43B00285E3F3BD8CEEF81F90F6C03D2CEFE30F9B`.
The real Catalan assertion covers all thirteen classified leaves and retains
the `AEAT` authority referent in the root identity heading.

Production `audit` and `scaffold --check` reported all four catalogues healthy.
The renderer, formatter-contract, locale-audit, and parity slice passed 63 real
tests. Ruff lint, Ruff format, and Ty passed for the changed semantic test, and
the scoped diff passes whitespace validation. No test was skipped, patched, or
converted to an expected failure.
