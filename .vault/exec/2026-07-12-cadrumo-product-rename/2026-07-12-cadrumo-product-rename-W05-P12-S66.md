---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S66'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Update Hungarian product locale messages through the locales CLI

## Scope

- `Hungarian locale catalogue`

## Description

- Snapshot all four locale catalogue hashes before mutation.
- Run the reviewed Hungarian-only production command `python -m cadrumo.locales canonicalize-product-identity --locale hu` under isolated local storage.
- Compare every parsed changed leaf with the production identity normaliser and classify each change by referent.
- Verify catalogue audits, focused tests, sibling hash equality, raw residue classification, and live Hungarian help output.

## Outcome

- The command changed exactly 28 semantic leaves: 22 command-bearing leaves contained 24 command-leading references that became `aeat`, and 6 product-display references became `CADRUMO`.
- Parsed key sets are identical before and after the mutation, and every changed value equals the production normaliser result.
- The Hungarian catalogue hash changed from `9BC8CEED6AB0E139003697D072CF2D93D3DA81CC698354C167036EDC10776655` to `4540D54CA3F0C6A65060ECC3629E0C82437E2FD40FCCF1987B1F9EE57335E1BF`.
- English, Spanish, and Catalan hashes remained unchanged.
- Catalogue scaffold and audit checks passed for all four locales; 38 focused tests passed; live Hungarian help presents `CADRUMO`, `AEAT`, and the `aeat` command without stale title-case or command-leading forms.

## Notes

- The production YAML serializer produced a 133-insertion and 147-deletion textual diff; semantic comparison isolated the 28 intended leaf changes.
- No questionable replacements were found. `AEAT` remained at 226 occurrences and `CADRUMO_` remained at 20 occurrences.
- Raw Hungarian residue is classified as 6 `CADRUMO` product displays, 20 `CADRUMO_*` settings, 215 `aeat` command prefixes, one Hungarian prose reference to the `aeat` product CLI, one `registry/aeat/treaties/` authority path, 222 standalone `AEAT` authority references, and four `AEAT_*` authority settings.
- The valid remaining lowercase `cadrumo` residues are exactly `cadrumo_secret_store_backend` in `adapters.google.oauth_flow.suggestions.use_keyring_or_synthetic` and `cadrumo-vault/` in `cli.config.google.sync.calc.export_help`. No lowercase MCP executable, URI scheme, or companion namespace is present.
- Targeted title-case and command-leading residue is zero in all four catalogues.
- No locale YAML was hand-edited.

## Regression ancestry and corrective restoration

The original S66 transaction changed 28 Hungarian leaves: 22 command-bearing
leaves contained 24 stale command prefixes that became `aeat`, and six
product-display references became `CADRUMO`. Commit `38894cae07` later changed
those six display leaves back to title-case `Cadrumo` under the repudiated
second casing ruling. Hungarian command guidance remained canonical and
required no further command change.

S95 restored the binding all-caps runtime tuple, S96 established reciprocal
supersession for the conflicting July 13 ADR, and S97 clarified that ADR as
historical evidence only. S62 then restored and independently passed the
shared renderer and locale-maintenance expectations; S63, S64, and S65
restored and independently passed the English, Spanish, and Catalan
catalogues. This corrective S66 pass therefore changes only the six Hungarian
display leaves left by `38894cae07` and retains the original 28-change evidence
above as historical proof of the first catalogue migration.

## Corrective semantic evidence

- Before mutation, the Hungarian catalogue was 451,606 bytes with SHA-256
  `F7D1A4DA52D5578A5FC0CDAF7125201169E73922E06C4B87BA614E8330AE0942`.
- After the production Hungarian-only canonicalizer, it is 458,599 bytes with
  SHA-256
  `9F659FD5A312A7B1B1B5219A43B00285E3F3BD8CEEF81F90F6C03D2CEFE30F9B`.
- Parsed comparison proves exactly six changed leaves, each equal to the
  production normalizer's `Cadrumo` to `CADRUMO` result. There are zero command
  changes, key additions, key removals, type changes, or other semantic
  changes. The YAML diff is exactly six insertions and six deletions.
- All four catalogues contained exactly 3,702 keys before mutation. Hungarian
  retains exactly 3,702 keys, every leaf remains a string, and its production
  placeholder-map digest is unchanged at
  `ECF9F59F5BF1E0228F5FD6836595940F7B9150C7824453C8B1DC771DC8CEC918`.
- English remained byte-identical at 403,956 bytes and
  `06C2550F40D46982ADBBBA713D3031B1BB54CEBBE1141C80340F749C6F70325B`;
  Spanish remained byte-identical at 449,246 bytes and
  `2D97F3174AA18D65ECFBE5856A6D4FCF015606AFB54447610DE85BAFCD8E3A72`;
  Catalan remained byte-identical at 442,017 bytes and
  `9A4BBE39A1DCA9B4B42175D5DAF1DAECC0E0BCEBD354F52E759BFEFDE30BC5CC`.
- Hungarian now contains zero exact title-case `Cadrumo` references and zero
  production-classified command-leading lowercase `cadrumo` references. Its
  six exact `CADRUMO` displays, 20 `CADRUMO_` environment references, 215
  `aeat` command prefixes, one Hungarian prose reference to the `aeat` product
  CLI, 222 standalone `AEAT` authority references, four `AEAT_*` authority
  settings, and one `registry/aeat/treaties/` authority path remain correctly
  classified. The exact lowercase
  `cadrumo_secret_store_backend` setting and `cadrumo-vault/` storage name each
  remain once as valid machine identifiers.

## Corrective verification

- The production `audit` and `scaffold --check` commands report all four
  catalogues healthy.
- The locale audit, S92 formatter grammar, placeholder parity, catalogue
  parity, and translation-honesty slice passed 54 tests.
- Isolated live `aeat --language hu --help` contains exact `CADRUMO`, `AEAT`,
  and 27 lowercase `aeat` command references. It contains neither exact
  title-case `Cadrumo` nor a command-leading lowercase `cadrumo` token.
- The catalogue mutation and every successful semantic, audit, scaffold, test,
  and live-help run used a fresh isolated `CADRUMO_LOCAL_STORAGE_ROOT` with
  valid unsecured local state. An initial read-only semantic comparison omitted
  that isolation, inherited a retired `aeat.db`, and correctly refused before
  catalogue loading; the comparison was rerun successfully in isolated state.
  The first parallel help assertion wrapper also used two PowerShell map keys
  that differed only by case and failed before running its commands; distinct
  diagnostic keys fixed the wrapper, after which the unchanged gates passed.
- No Python path changed, so Ruff, formatting, and Ty are not applicable to
  this catalogue-only transaction. `git diff --check` passes, and the
  Hungarian YAML diff is exactly six insertions and six deletions.
- Plan validation passes with the known `PLAN022` ordering warning. Focused
  frontmatter, Markdown, and placeholder checks pass, and S66 has no remaining
  scaffold annotation. The feature-tagged broad Vault check remains nonzero on
  348 unrelated legacy structure and feature-folder errors plus pre-existing
  modified-stamp, annotation, and stale-index warnings; references, schema,
  ADR status, rename integrity, and encoding are clean. No global Vault repair
  or index regeneration was attempted.
- No locale YAML was hand-edited; the production module CLI performed the sole
  catalogue mutation. English, Spanish, Catalan, S67, S25, and every other
  open descendant remain outside this Step.

## S87 contextual-casing correction

Authority Step S87 at `03cd792be3` binds sentence-prose `Cadrumo` separately
from identity-context `CADRUMO`, while retaining `aeat` as the human executable
and `AEAT` as the authority. Earlier all-caps prose claims in this record remain
historical evidence only.

This pass used four explicit production `locales set` operations against
Hungarian. Three sentence-prose leaves now use `Cadrumo`, and
`mcp.elicitation.refusal.no_channel` now directs operators to the `aeat` CLI.
The two identity headings remain exact `CADRUMO`. No broad canonicalizer or
text replacement was used.

The four semantic leaf changes produce four inserted and five deleted YAML
lines. Hungarian changed from SHA-256
`9F659FD5A312A7B1B1B5219A43B00285E3F3BD8CEEF81F90F6C03D2CEFE30F9B`
to
`D61AF25DF70D31B8BAC73B15C457F1C82EAD95E05C5ABDF332B2E71F8BE26716`.
English remained byte-identical at
`6241114C3A643E9F60283E526386080A7AD31D7A965012221F956A557D594426`,
Spanish at
`02C6765D56B101DDF3F9E81833DC55A47A62CE033319FC7A0EEE9BC9EA996104`,
and Catalan at
`D202C2F634134F4E172FFFF01B8DDE81551D11BD43766FE43CFD7CAE7F93A428`.
The real Hungarian assertion covers all six classified leaves and preserves
the `AEAT` authority referent in the root identity heading.

Production `audit` and `scaffold --check` reported all four catalogues healthy.
The renderer, formatter-contract, locale-audit, and parity slice passed 64 real
tests. Ruff lint, Ruff format, and Ty passed for the changed semantic test, and
the scoped diff passes whitespace validation. No test was skipped, patched, or
converted to an expected failure.
