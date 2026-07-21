---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-13'
step_id: 'S67'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Regenerate locale scaffold output and pass locale parity checks

## Scope

- `generated locale scaffold`

## Description

- Re-run the authoritative production locale scaffold in write mode under
  isolated valid CADRUMO local state after the complete corrective catalogue,
  authority, and validator ancestry landed and passed independent review.
- Prove the write is an exact byte no-op before running the production scaffold
  check and audit commands.
- Verify identical key sets, exact string leaf types, production placeholder
  parity, product and command residue, valid machine identifiers, and preserved
  AEAT authority vocabulary across Catalan, English, Spanish, and Hungarian.
- Run the complete owned i18n, locale, parity, translation-honesty, and root-help
  test slice plus live `aeat --language` help in all four languages.
- Close only S67 while preserving every other plan checkbox.

## Outcome

The production `python -m cadrumo.locales scaffold` write completed under a
fresh isolated valid unsecured state and changed zero bytes. Catalan remains
442,017 bytes with SHA-256
`9A4BBE39A1DCA9B4B42175D5DAF1DAECC0E0BCEBD354F52E759BFEFDE30BC5CC`;
English remains 403,956 bytes with
`06C2550F40D46982ADBBBA713D3031B1BB54CEBBE1141C80340F749C6F70325B`;
Spanish remains 449,246 bytes with
`2D97F3174AA18D65ECFBE5856A6D4FCF015606AFB54447610DE85BAFCD8E3A72`;
and Hungarian remains 458,599 bytes with
`9F659FD5A312A7B1B1B5219A43B00285E3F3BD8CEEF81F90F6C03D2CEFE30F9B`.

All four catalogues have the same 3,702-key set, every leaf has runtime type
exactly `str`, and every production placeholder-map digest is
`ECF9F59F5BF1E0228F5FD6836595940F7B9150C7824453C8B1DC771DC8CEC918`.
Production audit and `scaffold --check` both report all four catalogues `ok`.
There are zero exact `Cadrumo` values and zero production-classified
command-leading lowercase `cadrumo` references.

The complete owned acceptance slice passed 76 tests. Live help for `es`, `en`,
`ca`, and `hu` exited zero in every language; each output contains one exact
`CADRUMO` product display, two `AEAT` authority references, and 27 lowercase
`aeat` command references, with zero exact `Cadrumo` and zero stale lowercase
`cadrumo` commands.

## Notes

### Historical execution evidence

The first S67 execution at `3a5ac58ba0` generated and translated thirty then-new
keys in all four languages. A stale S65 background writer overlapped its first
scaffold attempt and malformed `ca.yml`; the writer was terminated, the
catalogue was reconstructed byte-for-byte from the committed S65 blob through
an explicit patch, and work resumed only after atomic locale-manager fix
`4a3511c9d6` landed. An interrupted translation pass left forty-five explicit
placeholders. Those exact leaves were inspected and filled through targeted
production locale CLI calls rather than another bulk transformation. That pass
reported clean scaffold and audit output, 22 focused tests, three broader
command-authority failures outside S67, no remaining child locale process, and
an unchanged intentional-identical allowlist. These incidents remain historical
evidence; they are not replayed or hidden by the corrective no-op proof.

### Corrective ancestry

S89 implementation `2d976745ee` and PASS audit `b634581f60` established the
shared 3,702-string-key catalogue baseline. S90 implementation `934a20eaaf` and
PASS audit `5f70903315` restored the binding `CADRUMO` display while retaining
the `aeat` executable and `AEAT` authority. S91 implementation `ee4bb7f9ad` was
failed by audit `9b372bba70`; S92 implementation `e513202907` fixed both HIGH
formatter findings and PASS audit `ee4f25296a` accepted them. S91 closure
`a2a83ec6be` and PASS re-review `28dac1a2f5` then accepted the production
validator in its scoped lane.

S93 implementation `9ea3b77f24` restored the identity tuple but FAIL audit
`ef9bbc64fe` found false descendant closures. S94 implementation
`132f9b5352` reopened them and PASS audit `1ab78e5176` cleared that plan blocker.
S95's logical authority repair across `f70329749d` and `3db2049e84` was failed
by audit `bb97babbd5` because a second accepted ADR remained. S96 implementation
`db4976fdc0` repaired the reciprocal graph but FAIL audit `9cb59a4444` found a
contradictory historical status note. S97 implementation `b17f29e140` removed
that last semantic conflict, and PASS audit `cc57185b09` established the active
binding matrix used here.

S62 implementation `6226f2fe57` and PASS audit `fc7c25b0af` restored shared
help and locale-maintenance expectations. The catalogue restorations then
landed and passed independent review in order: S63 `8644548342` /
`5087f0cf67`, S64 `2dbbdbb89a` / `47295b569d`, S65 `56fea16316` /
`b5a2a07e71`, and S66 `6c11c6c08c` with evidence clarification
`084ee2e18c` / PASS audit `efb1f48a22`. This ancestry leaves the checked-out
catalogues at the exact hashes proven by the no-op write above.

### Identity and verification classification

The remaining lowercase product-stem values are intentional machine settings
or storage history: `cadrumo-vault/` appears once in every catalogue, and
`cadrumo_secret_store_backend` appears once in Spanish and once in Hungarian.
Human command guidance remains lowercase `aeat`. `AEAT`, `AEAT_*`, and each
`registry/aeat` path remain authority-owned. Exact catalogue counts are:
Catalan 13 `CADRUMO`, 21 `CADRUMO_`, 225 lowercase `aeat`, 227 standalone
`AEAT`, four `AEAT_`, and one `registry/aeat`; English 10, 21, 227, 220, four,
and one respectively; Spanish seven, 20, 225, 234, four, and one; and Hungarian
six, 20, 217, 222, four, and one.

The 76-test run covered the complete core i18n and locale test directories,
catalogue parity, translation honesty, and root-help shape. No locale YAML,
intentional-identical allowlist, production code, CLI, documentation,
packaging, or generated scaffold derivative changed in this closure.

Plan validation, feature frontmatter, modified-stamp, Markdown, placeholder,
and annotation checks all exit zero; plan validation retains the known
non-monotonic `PLAN022` warning, and the S67 record has no remaining scaffold
annotation. The feature-surface gate has no owned Python path for Ruff or
test-module discovery, so the explicit 76-test acceptance slice supplies the
runtime evidence. The broad feature-tagged Vault check remains nonzero on 348
pre-existing shared-corpus errors and 81 warnings: 319 legacy filename-shape
errors, 29 unrelated feature-folder integrity errors, old modified stamps and
annotations, and the stale feature index. References, schema, ADR status,
rename integrity, encoding, and every S67-owned document check are clean.

## S87 contextual acceptance correction

Authority Step S87 at `03cd792be3` replaces the absolute all-caps premise with
the binding contextual contract: sentence prose uses `Cadrumo`, identity
headings may use `CADRUMO`, the human executable is `aeat`, machine identifiers
use `cadrumo` or `CADRUMO_` as defined by the identity tuple, and the Spanish
authority remains `AEAT`. Earlier zero-`Cadrumo` claims above are historical
evidence only.

The authoritative scaffold write is byte-for-byte a no-op after S63 through
S66. Final hashes are English
`6241114C3A643E9F60283E526386080A7AD31D7A965012221F956A557D594426`,
Spanish
`02C6765D56B101DDF3F9E81833DC55A47A62CE033319FC7A0EEE9BC9EA996104`,
Catalan
`D202C2F634134F4E172FFFF01B8DDE81551D11BD43766FE43CFD7CAE7F93A428`,
and Hungarian
`D61AF25DF70D31B8BAC73B15C457F1C82EAD95E05C5ABDF332B2E71F8BE26716`.
No catalogue value changed in this Step.

The final acceptance gate asserts the exact sentence-prose key sets—seven
English, three Spanish, nine Catalan, and three Hungarian—and the exact two
identity-heading keys in every catalogue. It verifies every classified MCP
recovery key names `aeat`, rejects stale command-leading `cadrumo` through the
production matcher, and pins package, distribution, MCP, resource-scheme,
environment-prefix, storage-history, and `AEAT` authority forms. Production
audit supplies the key, scalar-type, and placeholder-parity proof.

Production `audit` and `scaffold --check` report all four catalogues healthy.
The complete core-i18n, locale, and catalogue-parity slice passed 80 real tests.
Ruff lint, Ruff format, and Ty passed for the contextual acceptance test, and
the scoped diff passes whitespace validation. No fake, mock, patch, skip, or
expected-failure shortcut was introduced.
