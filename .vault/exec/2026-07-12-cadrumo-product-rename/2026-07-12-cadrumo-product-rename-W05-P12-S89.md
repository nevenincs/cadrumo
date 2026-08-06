---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:a381ad5a30dec1cf17e1cbae9d43fce7a0c0a4501e11a16bc0302c1b46ef4d68'
step_id: 'S89'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Correct locale scalar and placeholder parity through the locale CLI

## Scope

- `English`
- `Spanish`
- `Catalan`
- `and Hungarian locale catalogues`

## Description

- Establish the four clean `12d80d1d42` catalogue hashes before mutation and
  preserve the partially completed CLI transaction while S90 restores the
  binding product identity authority.
- Resolve every analyst shorthand to its existing canonical dotted catalogue
  path before mutation.
- Apply thirty-two scalar corrections and remove eight retired null leaves
  exclusively through `python -m cadrumo.locales set` and
  `python -m cadrumo.locales remove` under isolated local state.
- Run `python -m cadrumo.locales canonicalize-product-identity --locale` once
  for each of `es`, `en`, `ca`, and `hu` after reviewed S90 restored
  `PRODUCT_IDENTITY.display_name` to `CADRUMO`.
- Verify exact values, semantic diff classification, string leaf types, key and
  placeholder parity, scaffold and catalogue audit status, focused tests, raw
  residue, and live root help in all four languages.

## Outcome

- Every catalogue contains the same 3,702 keys, every leaf is a string, and
  placeholder sets are identical across English, Spanish, Catalan, and
  Hungarian for every key.
- The production CLI made exactly thirty-two reviewed `set` corrections:
  English eight, Spanish one, Catalan six, and Hungarian seventeen. It also
  removed `cli.config.bucket` and `cli.config.unlock` from every locale, for
  eight `remove` operations. Both retired keys are absent everywhere.
- Exact semantic classification against HEAD found thirty-two corrected value
  changes, eight removals, thirty-six S90-authorized reversals of the
  `12d80d1d42` `Cadrumo` catalogue regression, and zero unexpected deltas.
- Final SHA-256 hashes are English
  `06C2550F40D46982ADBBBA713D3031B1BB54CEBBE1141C80340F749C6F70325B`,
  Spanish `2D97F3174AA18D65ECFBE5856A6D4FCF015606AFB54447610DE85BAFCD8E3A72`,
  Catalan `9A4BBE39A1DCA9B4B42175D5DAF1DAECC0E0BCEBD354F52E759BFEFDE30BC5CC`,
  and Hungarian
  `9F659FD5A312A7B1B1B5219A43B00285E3F3BD8CEEF81F90F6C03D2CEFE30F9B`.
- `scaffold --check` and `audit` reported all four catalogues `ok`; the three
  call-site placeholder parity tests passed; the combined locale and i18n
  suite passed twenty-five tests; and `git diff --check` passed.
- Real `aeat --help` passed in all four languages under isolated state. Each
  rendered `CADRUMO`, retained AEAT as the authority, used the `aeat` command,
  and contained no `Cadrumo` regression.
- Raw `Cadrumo` residue is zero. No command-leading lowercase `cadrumo` remains;
  the remaining lowercase occurrences are valid settings and `cadrumo-vault`
  storage identifiers.

## Notes

- Pre-transaction hashes at `12d80d1d42` were English
  `964B83085C4DFBB5CC6DAF458BF86D95A41285C6D8A000DFCF311888C06570D8`,
  Spanish `1F858CAD1A19F68A60DCC9923022A49D9D6C202D4143910737D7ED215ADA8177`,
  Catalan `F7FAF491F776CD4ADECD11357979CCE3E99195DAED636ED92583BA920489A9B2`,
  and Hungarian
  `20A586C91F2DF74113CF4919FC17254B2E712139A008B788885DD35AE9441751`.
- The command transcript for English was eight successful `set` calls for
  `cli.app.modelo.iva_wallet.seed_conflict`,
  `cli.app.modelo.iva_wallet.seed_invalid_amount`,
  `cli.operator_surface.errors.contract_not_accepted`,
  `cli.operator_surface.errors.source_kind_options`,
  `cli.operator_surface.errors.unknown_source_kind`, `mcp.call.timeout`,
  `review.operator.errors.unsupported_item_type`, and
  `wizard.test.example.choices.yes.label`, followed by successful removal of
  `cli.config.bucket` and `cli.config.unlock`.
- The Spanish transcript was one successful `set` call for
  `wizard.test.example.choices.yes.label`, followed by successful removal of
  `cli.config.bucket` and `cli.config.unlock`.
- The Catalan transcript began with successful `set` calls for
  `cli.app.modelo.iva_wallet.seed_conflict` and
  `cli.app.modelo.iva_wallet.seed_invalid_amount`. A shorthand attempt at
  `cli.auth.google.status.errors.unreadable_active_profile` was refused by the
  production CLI without mutation. The corrected transcript then used
  `application.auth.operator.errors.unreadable_active_profile`,
  `application.modelo.errors.external_import_justificante_mismatch`,
  `application.modelo.errors.external_import_justificante_missing`, and
  `wizard.test.example.choices.yes.label`, followed by successful removal of
  `cli.config.bucket` and `cli.config.unlock`.
- The Hungarian transcript was seventeen successful `set` calls for
  `cli.app.modelo.iva_wallet.seed_conflict`,
  `cli.app.modelo.iva_wallet.seed_invalid_amount`,
  `cli.operator_surface.errors.contract_not_accepted`,
  `cli.operator_surface.errors.source_kind_options`,
  `cli.operator_surface.errors.unknown_source_kind`,
  `application.modelo.errors.external_import_justificante_mismatch`,
  `application.modelo.errors.external_import_justificante_missing`,
  `application.auth.operator.login.refused_live_tests_disabled`,
  `application.modelo.errors.computed_casilla_binding_conflict`,
  `application.registry.errors.manual_section_not_found`,
  `application.registry.errors.manual_section_requires_structure`,
  `errors.calc.dispatch_key_unknown`,
  `errors.calc.text_input_non_text_casillas`,
  `errors.calc.unknown_text_input_casillas`,
  `errors.calc.unsupported_comparison_op`, `errors.calc.unsupported_op`, and
  `wizard.test.example.choices.yes.label`, followed by successful removal of
  `cli.config.bucket` and `cli.config.unlock`.
- `mcp.call.timeout` and `review.operator.errors.unsupported_item_type` in
  Hungarian already held their reviewed values and were deliberately not
  mutated.
- Commit `12d80d1d42` landed during the transaction and changed all four clean
  catalogue baselines plus the identity authority to `Cadrumo`. Work stopped
  before canonicalization. Reviewed S90 commits `934a20eaaf` and `5f70903315`
  restored and audited the binding `CADRUMO` authority; only then did the four
  production canonicalizer calls reverse the thirty-six raw catalogue deltas.
- All locale writes were made by the production locale CLI. No YAML catalogue
  was hand-edited.
- The shared-branch feature-surface gate had no Python files in S89 scope, so
  path-scoped Ruff and owned-test discovery were not applicable. The scoped
  `vault check all` completed successfully with no errors; its warnings concern
  pre-existing modified stamps, annotations, and the feature index outside this
  six-path transaction.
